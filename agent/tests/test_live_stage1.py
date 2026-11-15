import asyncio
from io import BytesIO
import json
from types import SimpleNamespace as NS
import wave

import httpx
from PIL import Image
import pytest

from calypso_agent.backend_client import FakeBackendClient
from calypso_agent.contract import IntroRequest, Person, PersonDetail
from calypso_agent.conversation import SetupScript
from calypso_agent.grok import GrokSpeech
from calypso_agent.live_media import CameraSamples, FaceCropper, RoomSpeech, wait_bridge_ready, wav_bytes
from calypso_agent.main import Config
from calypso_agent.speech import FakeSTT, FakeTTS
from calypso_agent.stage1_backend import ControlledBackend


def test_live_mode_requires_explicit_selection_and_no_secret_in_errors():
    env = {"CALYPSO_STAGE1": "true", "CALYPSO_CALL_MODE": "patient", "XAI_API_KEY": "do-not-print"}
    with pytest.raises(ValueError, match="automatic patient routing") as error:
        Config.from_env(env)
    assert "do-not-print" not in str(error.value)
    env["CALYPSO_CALL_MODE"] = "setup"
    with pytest.raises(ValueError, match="CALYPSO_BACKEND_URL"):
        Config.from_env(env)
    env.update(CALYPSO_BACKEND_URL="http://localhost:8000", CALYPSO_API_TOKEN="secret")
    assert Config.from_env(env).mode == "setup"
    env["STAGE1_RECOGNITION"] = "guess"
    with pytest.raises(ValueError, match="STAGE1_RECOGNITION"):
        Config.from_env(env)


@pytest.mark.asyncio
async def test_grok_speech_http_contract():
    audio = wav_bytes(b"\0\0" * 1600)
    seen = []
    def handler(request):
        assert request.headers["authorization"] == "Bearer secret"
        seen.append(request.url.path)
        if request.url.path == "/v1/stt":
            assert b"speech.wav" in request.content and b"audio/wav" in request.content
            return httpx.Response(200, json={"text": "Yes."})
        body = json.loads(request.content)
        assert body["voice_id"] == "eve"
        assert body["output_format"] == {"codec": "wav", "sample_rate": 16000}
        return httpx.Response(200, content=audio)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        speech = GrokSpeech("secret", client=client)
        assert await speech.transcribe(audio) == "Yes."
        assert await speech.synthesize("Hello") == audio
        await speech.close()
        assert not client.is_closed
    assert seen == ["/v1/stt", "/v1/tts"]


@pytest.mark.asyncio
async def test_grok_rejects_failed_auth_and_wrong_audio_format():
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(401))) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await GrokSpeech("bad", client=client).transcribe(b"fixture")
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, content=b"not a wav"))) as client:
        with pytest.raises((wave.Error, EOFError)):
            await GrokSpeech("secret", client=client).synthesize("Hello")


@pytest.mark.asyncio
async def test_real_setup_can_collect_camera_samples_after_greeting():
    api = FakeBackendClient(patient=Person(id="p", name="Mary", is_patient=True),
                            enrollment=PersonDetail(id="r", name="Sarah"))
    tts = FakeTTS()
    async def crops():
        assert tts.spoken and "Is that right?" in tts.spoken[-1]
        return [b"crop1", b"crop2", b"crop3"]
    result = await SetupScript(api, FakeSTT(["Sarah", "Baking", "yes"]), tts).run(crops)
    assert result.id == "r"
    assert len(api.intros[0].face_jpegs_b64) == 3


@pytest.mark.asyncio
async def test_setup_never_enrolls_when_camera_capture_fails():
    api = FakeBackendClient(patient=Person(id="p", is_patient=True), enrollment=PersonDetail(id="r"))
    async def crops():
        raise ValueError("No clear face")
    with pytest.raises(ValueError, match="No clear face"):
        await SetupScript(api, FakeSTT(["Sarah", "Baking", "yes"]), FakeTTS()).run(crops)
    assert not api.intros and api.calls[0].ended is not None


@pytest.mark.asyncio
async def test_camera_drops_ambiguous_samples_and_rejects_stale_crops():
    class Cropper:
        result = b"crop"
        def crop(self, image):
            return self.result
    cropper = Cropper()
    samples = CameraSamples(cropper)
    for _ in range(3):
        await samples.add(None)
    assert await samples.collect() == [b"crop"] * 3
    samples.samples[0] = (0, b"stale")
    with pytest.raises(ValueError):
        await samples.collect()
    cropper.result = None
    await samples.add(None)
    assert not samples.samples


def test_real_face_detector_rejects_blank_camera():
    assert FaceCropper().crop(Image.new("RGB", (640, 480), "black")) is None


class Events:
    metadata = "{}"
    def __init__(self):
        self.handlers = {}
    def on(self, event, callback):
        self.handlers.setdefault(event, []).append(callback)
    def off(self, event, callback):
        self.handlers[event].remove(callback)
    def emit(self, event, *args):
        for callback in self.handlers.get(event, []):
            callback(*args)


@pytest.mark.asyncio
async def test_bridge_readiness_waits_for_signal_and_removes_callback():
    room = Events()
    task = asyncio.create_task(wait_bridge_ready(room, timeout=1))
    await asyncio.sleep(0)
    assert not task.done()
    room.metadata = '{"chert_bridge_ready":true}'
    room.emit("room_metadata_changed", "old")
    await task
    assert room.handlers["room_metadata_changed"] == []
    await wait_bridge_ready(room, timeout=0.1)  # Already-ready rooms also work.


@pytest.mark.asyncio
async def test_bridge_readiness_timeout_never_greets():
    room = Events()
    with pytest.raises(TimeoutError):
        await wait_bridge_ready(room, timeout=0.001)
    assert room.handlers["room_metadata_changed"] == []


@pytest.mark.asyncio
async def test_audio_segments_one_utterance_and_suppresses_output_echo():
    recorded = []
    class Provider:
        async def transcribe(self, audio):
            recorded.append(audio)
            return "Sarah"
    speech = RoomSpeech(Provider(), None)
    speech.speaking = True
    speech.feed(b"echo")
    assert speech.frames.empty()
    speech.speaking = False
    task = asyncio.create_task(speech.listen(timeout_s=1))
    await asyncio.sleep(0)
    for _ in range(20):  # 400 ms of audible speech
        speech.feed(b"\0\x20" * 320)
    for _ in range(41):  # 820 ms of silence ends the utterance
        speech.feed(b"\0\0" * 320)
    assert await task == "Sarah"
    assert speech.last_wav == recorded[0]
    with wave.open(BytesIO(recorded[0]), "rb") as wav:
        assert wav.getframerate() == 16000 and wav.getnchannels() == 1
    assert await speech.listen(timeout_s=0) is None
    assert speech.last_wav is None


@pytest.mark.asyncio
async def test_controlled_recognition_persists_enrollment_across_sessions(tmp_path):
    api = FakeBackendClient(patient=Person(id="p", is_patient=True), enrollment=PersonDetail(id="r", name="Sarah"))
    path = tmp_path / "enrollment.json"
    # The underlying fake still receives the recognition call, just as the real
    # HTTP backend does. The wrapper owns only the controlled result.
    first = ControlledBackend(api, path, outcome="identified", name="Sarah")
    assert (await first.recognize(b"unknown", "phone", "c1")).faces[0].result.status == "learning"
    await first.enroll(IntroRequest(transcript="Sarah", face_jpegs_b64=["eA=="] * 3))
    second = ControlledBackend(api, path, outcome="identified", name="Sarah")
    result = (await second.recognize(b"different live frame", "phone", "c2")).faces[0].result
    assert result.person_id == "r" and result.status == "identified"
    assert (await second.person("r")).name == "Test profile: Sarah"
    assert json.loads(path.read_text()) == {"person_id": "r"}
    assert (path.stat().st_mode & 0o777) == 0o600
    second.outcome = "uncertain"
    assert (await second.recognize(b"frame", "phone", "c2")).faces[0].result.status == "uncertain"
    assert (await second.person("p")).is_patient is True


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["setup", "group"])
async def test_live_call_wiring_cleans_up_after_hangup_or_speech_failure(monkeypatch, tmp_path, mode):
    import calypso_agent.main as live
    api = FakeBackendClient(patient=Person(id="p", name="Mary", is_patient=True),
                            enrollment=PersonDetail(id="r", name="Sarah"))
    closed = []
    async def close_api():
        closed.append("backend")
    api.close = close_api
    events = []
    class Gateway:
        session_id = None
        def __init__(self, *a): pass
        async def start(self, mode, participant, outcome, **kwargs): self.session_id = "session"
        async def event(self, kind, **fields):
            events.append(kind)
            if events.count("utterance") == 3:
                return {"speech": ["Introduction saved"], "done": True}
            return {"speech": ["Welcome"] if kind == "start" else []}
        async def close(self): closed.append("gateway")
    monkeypatch.setattr(live, "GatewayClient", Gateway)
    class Provider:
        def __init__(self, *a): pass
        async def close(self): closed.append("speech")
    monkeypatch.setattr(live, "GrokSpeech", Provider)
    room = Events()
    room.metadata = '{"chert_bridge_ready":true}'
    class Samples:
        async def collect(self): return [b"one", b"two", b"three"]
    monkeypatch.setattr(live, "CameraSamples", Samples)
    class Output:
        def __init__(self, room, scheduler=None):
            self.audio, self.scheduler = None, scheduler
        async def start(self): pass
        async def run(self): await asyncio.Event().wait()
        def caption(self, text):
            if "Introduction saved" in text:
                room.emit("disconnected")
        async def close(self): closed.append("media")
    monkeypatch.setattr(live, "Publisher", Output)
    class Speech(FakeSTT):
        def __init__(self, *a, **kw):
            super().__init__(["Sarah", "Baking", "yes"])
            self.caption = kw["caption"]
        async def speak(self, text): self.caption(text)
        async def listen(self, timeout_s=20):
            if mode == "group": raise RuntimeError("STT disconnected")
            return await super().listen(timeout_s)
    monkeypatch.setattr(live, "RoomSpeech", Speech)
    participant = NS(identity="chert-bridge-test", track_publications={})
    async def wait_for_participant(**kwargs): return participant
    ctx = NS(room=room, wait_for_participant=wait_for_participant)
    config = Config(mode, "https://backend.test", "secret", "xai", state_file=str(tmp_path / "enrolled.json"))
    if mode == "group":
        with pytest.raises(RuntimeError, match="STT disconnected"):
            await asyncio.wait_for(live.run_call(ctx, config), 6)
    else:
        await asyncio.wait_for(live.run_call(ctx, config), 2)
        assert events.count("utterance") == 3
    assert all(call.ended is not None for call in api.calls)
    assert set(closed) == {"gateway", "speech", "media"}
    assert all(not callbacks for callbacks in room.handlers.values())


@pytest.mark.asyncio
async def test_video_publisher_uses_same_participant_for_one_audio_and_video_track(monkeypatch):
    import calypso_agent.live_media as media
    frames, shown, unpublished = [], [], []
    class Source:
        def __init__(self, *args): pass
        def capture_frame(self, frame): frames.append(frame)
        async def aclose(self): pass
    monkeypatch.setattr(media.rtc, "VideoSource", Source)
    monkeypatch.setattr(media.rtc, "AudioSource", Source)
    monkeypatch.setattr(media.rtc.LocalVideoTrack, "create_video_track", lambda *a: "video")
    monkeypatch.setattr(media.rtc.LocalAudioTrack, "create_audio_track", lambda *a: "audio")
    published = []
    encoding = []
    async def publish(track, options):
        published.append((track, options.source))
        if track == "video":
            encoding.append(options)
        return NS(sid=track)
    async def unpublish(sid): unpublished.append(sid)
    room = NS(local_participant=NS(publish_track=publish, unpublish_track=unpublish))
    publisher = media.Publisher(room, on_shown=shown.append)
    await publisher.start()
    task = asyncio.create_task(publisher.run())
    await asyncio.sleep(0.25)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    await publisher.close()
    assert [track for track, _ in published] == ["video", "audio"]
    assert len(frames) >= 1 and (frames[0].width, frames[0].height) == (720, 1280)
    assert encoding[0].video_encoding.max_bitrate == 2_500_000
    assert encoding[0].simulcast is False
    assert len(shown) == 1
    assert unpublished == ["video", "audio"]


@pytest.mark.asyncio
async def test_gateway_transport_preserves_enrollment_and_closes_remote_session(tmp_path):
    from calypso_agent.gateway import GatewayClient
    seen = []
    def handler(request):
        seen.append(request.url.path)
        assert request.headers["Authorization"] == "Bearer transport-token"
        body = json.loads(request.content) if request.content else None
        if request.url.path == "/agent/sessions":
            assert body["controlled"] is True and body["mode"] == "setup"
            return httpx.Response(201, json={"session_id": "sid", "call_id": "cid"})
        if request.url.path.endswith("/events") and request.url.path != "/agent/events":
            assert body["kind"] == "utterance" and body["text"] == "Yes"
            return httpx.Response(200, json={"speech": [], "cards": [], "done": True, "enrolled_person_id": "relative"})
        return httpx.Response(200, json={"ok": True})
    async with httpx.AsyncClient(base_url="https://gateway.test",
        headers={"Authorization": "Bearer transport-token"}, transport=httpx.MockTransport(handler)) as client:
        path = tmp_path / "enrollment.json"
        gateway = GatewayClient("https://gateway.test", "transport-token", path, client=client)
        await gateway.start("setup", "phone", "learning")
        assert (await gateway.event("utterance", text="Yes"))["done"]
        assert json.loads(path.read_text()) == {"person_id": "relative"}
        await gateway.close()
        assert not client.is_closed
    assert seen[-1] == "/agent/sessions/sid/end"


def test_portrait_captions_page_without_dropping_words():
    from calypso_agent.cards import CALL_SIZE, BACKGROUND, caption_cards, render
    from PIL import ImageChops
    text = " ".join(f"word{i}" for i in range(100))
    pages = caption_cards(text)
    assert len(pages) > 1
    assert " ".join(line for page in pages for line in page.lines).split() == text.split()
    for page in pages:
        image = render(page, {}, size=CALL_SIZE)
        assert image.size == (720, 1280)
        diff = ImageChops.difference(image, Image.new("RGB", CALL_SIZE, BACKGROUND))
        left, top, right, bottom = diff.getbbox()
        assert left >= 40 and right <= 680 and bottom <= 1100
