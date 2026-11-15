"""Chert/LiveKit media transport. Claude decisions execute on the backend."""

import asyncio
from dataclasses import dataclass
import logging
import os
import sys
import time

from livekit import rtc
from livekit.agents import AgentServer, AutoSubscribe, JobContext, cli

from .backend_client import b64
from .gateway import GatewayClient
from .caller_identity import resolve_caller_phone, wait_chert_bridge
from .contract import Card
from .latency import fresh_cards, latency_ms
from .grok import GrokSpeech
from .live_media import CameraSamples, Publisher, RoomSpeech, audio_frames, video_frames, wait_bridge_ready
from .scheduler import CardScheduler

log = logging.getLogger("calypso.live")


@dataclass
class Config:
    mode: str
    backend_url: str
    backend_token: str
    xai_key: str
    outcome: str = "learning"
    state_file: str = "data/stage1-enrollment.json"
    participant_id: str | None = None
    controlled: bool = False

    @classmethod
    def from_env(cls, env=None):
        env = os.environ if env is None else env
        mode = env.get("CALYPSO_CALL_MODE")
        if mode not in {"setup", "group", "recognize", "auto"}:
            raise ValueError("Set CALYPSO_CALL_MODE=setup, recognize, auto or group; automatic patient routing is not enabled")
        missing = [name for name in ("CALYPSO_BACKEND_URL", "CALYPSO_API_TOKEN", "XAI_API_KEY") if not env.get(name)]
        if missing:
            raise ValueError("Missing environment variables: " + ", ".join(missing))
        outcome = env.get("STAGE1_RECOGNITION", "learning")
        if outcome not in {"identified", "learning", "uncertain"}:
            raise ValueError("STAGE1_RECOGNITION must be identified, learning, or uncertain")
        return cls(mode, env["CALYPSO_BACKEND_URL"], env["CALYPSO_API_TOKEN"], env["XAI_API_KEY"],
            outcome, env.get("STAGE1_STATE_FILE", "data/stage1-enrollment.json"),
            env.get("STAGE1_PARTICIPANT_ID") or None,
            env.get("CALYPSO_CONTROLLED_RECOGNITION", "false").lower() == "true")


async def run_call(ctx, config):
    # No prompts, identity decisions, enrollment or backend tool dispatch here.
    gateway = GatewayClient(config.backend_url, config.backend_token, config.state_file)
    provider = GrokSpeech(config.xai_key)
    publisher = Publisher(ctx.room, CardScheduler())
    samples = CameraSamples()
    speech = RoomSpeech(provider, publisher.audio, caption=publisher.caption)
    tasks = set()
    stopped, failed, ready = asyncio.Event(), asyncio.Event(), asyncio.Event()
    errors, tracks = [], set()
    video_sid = None
    effect_lock = asyncio.Lock()
    selected_identity = config.participant_id
    needs_crops = False
    active_mode = "recognize" if config.mode == "auto" else config.mode
    dialogue_done = False
    last_progress = None
    caller_phone = None
    latencies = {}

    def spawn(coro):
        task = asyncio.create_task(coro)
        tasks.add(task)
        def done(task):
            tasks.discard(task)
            if not task.cancelled() and task.exception():
                errors.append(task.exception())
                failed.set()
        task.add_done_callback(done)
        return task

    def shown(card):
        if gateway.session_id and card.kind in {"identity", "learning", "today", "memory"}:
            payload = card.model_dump(mode="json")
            spawn(gateway.shown(payload, latencies.pop(card.model_dump_json(), None)))
    publisher.on_shown = shown

    def disconnected(*_):
        stopped.set()

    def left(participant):
        if participant.identity == selected_identity:
            stopped.set()

    async def apply(effects):
        nonlocal needs_crops, dialogue_done, active_mode
        async with effect_lock:
            if dialogue_done:
                return True
            active_mode = effects.get("mode") or active_mode
            needs_crops = effects.get("needs_face_crops", False)
            dialogue_done = effects.get("done", False)
            for card in effects.get("cards", []):
                publisher.scheduler.push(Card.model_validate(card))
            if dialogue_done and effects.get("cards"):
                publisher.pinned_card = Card.model_validate(effects["cards"][-1])
                publisher.camera_status = ""
            for text in effects.get("speech", []):
                await speech.speak(text)
        return effects.get("done", False)

    async def frame(image):
        nonlocal needs_crops, last_progress
        crop = await samples.add(image)
        if active_mode == "setup":
            progress = samples.progress
            if not dialogue_done:
                publisher.camera_status = (f"Camera: {progress}/3 clear face samples" if progress else
                                           "Camera: waiting for one clear face")
            if progress != last_progress:
                log.info("camera_samples=%d/3", progress)
                last_progress = progress
            if ready.is_set() and needs_crops and progress == 3 and not dialogue_done:
                crops = await samples.collect()
                needs_crops = False
                await apply(await gateway.event("camera_ready", face_jpegs_b64=[b64(c) for c in crops]))
        if ready.is_set() and not dialogue_done and active_mode in {"group", "recognize"}:
            # Empty input also clears the server's consecutive-frame debounce.
            effects = await gateway.event("frame", jpeg_b64=b64(crop) if crop else None)
            # Frame events may request a newcomer question. The server enforces
            # the one-question rule; the media process only plays its effects.
            await apply(effects)

    def subscribed(track, publication, participant):
        nonlocal video_sid
        if participant.identity != selected_identity or track.sid in tracks:
            return
        if publication.source in {rtc.TrackSource.SOURCE_SCREENSHARE, rtc.TrackSource.SOURCE_SCREENSHARE_AUDIO}:
            return
        tracks.add(track.sid)
        log.info("subscribed_media kind=%s source=%s", track.kind, publication.source)
        if track.kind == rtc.TrackKind.KIND_VIDEO:
            if video_sid is not None and video_sid != track.sid:
                return
            video_sid = track.sid
            spawn(video_frames(track, frame))
        elif track.kind == rtc.TrackKind.KIND_AUDIO:
            spawn(audio_frames(track, speech))

    async def workflow():
        await wait_bridge_ready(ctx.room,
            confirmed_bridge=lambda: wait_chert_bridge(selected_identity))
        await gateway.start(config.mode, selected_identity, config.outcome, caller_phone=caller_phone, controlled=config.controlled)
        started = time.monotonic()
        initial = await gateway.event("start")
        if config.mode == "auto":
            async def finish_recognition_window():
                await asyncio.sleep(max(0, 5 - (time.monotonic() - started)) + 0.1)
                while not dialogue_done and active_mode == "recognize":
                    if await apply(await gateway.event("recognition_timeout")):
                        return
                    if active_mode == "recognize":
                        await asyncio.sleep(0.25)
            spawn(finish_recognition_window())
        ready.set()
        if await apply(initial):
            return
        while not stopped.is_set() and not dialogue_done:
            text = await speech.listen()
            sentence_end = time.monotonic()
            if dialogue_done:
                return
            try:
                crops = await samples.collect()
            except ValueError:
                crops = []
            voice = getattr(speech, "last_wav", None) if text and active_mode != "recognize" else None
            effects = await gateway.event("utterance" if text else "silence",
                text=text, face_jpegs_b64=[b64(crop) for crop in crops],
                voice_wav_b64=b64(voice) if voice else None)
            if text:
                now = time.monotonic()
                cards = effects.get("cards", [])
                kept = fresh_cards(cards, sentence_end, now)
                for card in cards:
                    if card.get("kind") in {"today", "memory"}:
                        ms = latency_ms(sentence_end, now)
                        log.info("recall_latency_ms=%d kind=%s dropped=%s", ms, card["kind"], card not in kept)
                        if card in kept:
                            latencies[Card.model_validate(card).model_dump_json()] = ms
                effects = {**effects, "cards": kept}
            if await apply(effects):
                return

    ctx.room.on("disconnected", disconnected)
    ctx.room.on("participant_disconnected", left)
    ctx.room.on("track_subscribed", subscribed)
    def reconnecting(*_):
        log.warning("LiveKit reconnecting: media connection interrupted")
        publisher.camera_status = "Connection interrupted; reconnecting…"
    def reconnected(*_):
        log.info("LiveKit reconnected")
        publisher.camera_status = "Connection restored"
    ctx.room.on("reconnecting", reconnecting)
    ctx.room.on("reconnected", reconnected)
    try:
        await publisher.start()
        spawn(publisher.run())
        participant = await ctx.wait_for_participant(identity=selected_identity)
        selected_identity = participant.identity
        if config.mode in {"setup", "auto"}:
            caller_phone = await resolve_caller_phone(selected_identity)
            log.info("verified_caller_phone_available=%s", bool(caller_phone))
        log.info("Claude media transport: mode=%s, participant=%s", config.mode, selected_identity)
        for publication in participant.track_publications.values():
            if publication.track:
                subscribed(publication.track, publication, participant)
        spawn(workflow())
        waiters = [asyncio.create_task(stopped.wait()), asyncio.create_task(failed.wait())]
        try:
            await asyncio.wait(waiters, return_when=asyncio.FIRST_COMPLETED)
            if errors:
                publisher.caption("The connection was interrupted. Please hang up and call again.")
                await asyncio.sleep(3)
                raise errors[0]
        finally:
            for task in waiters:
                task.cancel()
            await asyncio.gather(*waiters, return_exceptions=True)
    finally:
        ctx.room.off("disconnected", disconnected)
        ctx.room.off("participant_disconnected", left)
        ctx.room.off("track_subscribed", subscribed)
        ctx.room.off("reconnecting", reconnecting)
        ctx.room.off("reconnected", reconnected)
        pending = list(tasks)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        try:
            await gateway.close()
        finally:
            try:
                await publisher.close()
            finally:
                await provider.close()


# Bound warm workers on the 4 GB instance; SDK production defaults can start
# many idle processes. Expose health only on the instance's loopback interface.
server = AgentServer(num_idle_processes=int(os.getenv("CALYPSO_IDLE_PROCESSES", "1")),
                     host="127.0.0.1", port=int(os.getenv("CALYPSO_MEDIA_PORT", "8081")))


@server.rtc_session(agent_name=os.getenv("AGENT_NAME", "calypso-stage1"))
async def entrypoint(ctx: JobContext):
    config = Config.from_env()
    await ctx.connect(auto_subscribe=AutoSubscribe.SUBSCRIBE_ALL)
    try:
        await run_call(ctx, config)
    except Exception as error:
        # Avoid printing response bodies, credentials, or transcripts.
        log.error("Stage 1 call failed (%s). Check service connectivity and test configuration.", type(error).__name__)
        raise
    finally:
        ctx.shutdown(reason="stage1 call ended")


if __name__ == "__main__":
    if "--check" in sys.argv:
        config = Config.from_env()
        print(f"Stage 1 configuration valid: mode={config.mode}, controlled_recognition={config.outcome}.")
        print("Service connectivity, room dispatch and real media still require a call test.")
    else:
        cli.run_app(server)
