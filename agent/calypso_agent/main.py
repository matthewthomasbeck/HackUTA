"""Chert/LiveKit media transport. Claude decisions execute on the backend."""

import asyncio
from dataclasses import dataclass
import logging
import os
import sys

from livekit import rtc
from livekit.agents import AgentServer, AutoSubscribe, JobContext, cli

from .backend_client import b64
from .gateway import GatewayClient
from .contract import Card
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

    @classmethod
    def from_env(cls, env=None):
        env = os.environ if env is None else env
        if env.get("CALYPSO_STAGE1") != "true":
            raise ValueError("Set CALYPSO_STAGE1=true to explicitly enable controlled test recognition")
        mode = env.get("CALYPSO_CALL_MODE")
        if mode not in {"setup", "group"}:
            raise ValueError("Set CALYPSO_CALL_MODE=setup or group; automatic patient routing is not enabled")
        missing = [name for name in ("CALYPSO_BACKEND_URL", "CALYPSO_API_TOKEN", "XAI_API_KEY") if not env.get(name)]
        if missing:
            raise ValueError("Missing environment variables: " + ", ".join(missing))
        outcome = env.get("STAGE1_RECOGNITION", "learning")
        if outcome not in {"identified", "learning", "uncertain"}:
            raise ValueError("STAGE1_RECOGNITION must be identified, learning, or uncertain")
        return cls(mode, env["CALYPSO_BACKEND_URL"], env["CALYPSO_API_TOKEN"], env["XAI_API_KEY"],
            outcome, env.get("STAGE1_STATE_FILE", "data/stage1-enrollment.json"),
            env.get("STAGE1_PARTICIPANT_ID") or None)


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
    dialogue_done = False
    last_progress = None

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
            spawn(gateway.shown(card.model_dump(mode="json")))
    publisher.on_shown = shown

    def disconnected(*_):
        stopped.set()

    def left(participant):
        if participant.identity == selected_identity:
            stopped.set()

    async def apply(effects):
        nonlocal needs_crops, dialogue_done
        needs_crops = effects.get("needs_face_crops", False)
        dialogue_done = effects.get("done", False)
        async with effect_lock:
            for card in effects.get("cards", []):
                publisher.scheduler.push(Card.model_validate(card))
            for text in effects.get("speech", []):
                await speech.speak(text)
        return effects.get("done", False)

    async def frame(image):
        nonlocal needs_crops, last_progress
        crop = await samples.add(image)
        if config.mode == "setup":
            progress = samples.progress
            publisher.camera_status = (f"Camera: {progress}/3 clear face samples" if progress else
                                       "Camera: waiting for one clear face")
            if progress != last_progress:
                log.info("camera_samples=%d/3", progress)
                last_progress = progress
            if ready.is_set() and needs_crops and progress == 3 and not dialogue_done:
                crops = await samples.collect()
                needs_crops = False
                await apply(await gateway.event("camera_ready", face_jpegs_b64=[b64(c) for c in crops]))
        if ready.is_set() and config.mode == "group":
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
        await wait_bridge_ready(ctx.room)
        await gateway.start(config.mode, selected_identity, config.outcome)
        if await apply(await gateway.event("start")):
            return
        ready.set()
        while not stopped.is_set() and not dialogue_done:
            text = await speech.listen()
            if dialogue_done:
                return
            try:
                crops = await samples.collect()
            except ValueError:
                crops = []
            effects = await gateway.event("utterance" if text else "silence",
                text=text, face_jpegs_b64=[b64(crop) for crop in crops])
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


server = AgentServer()


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
