import base64
from io import BytesIO
import json
from pathlib import Path
import wave

import httpx
from PIL import Image, ImageChops
import pytest

from calypso_agent.backend_client import BackendClient, FakeBackendClient
from calypso_agent.cards import BACKGROUND, render
from calypso_agent.contract import (BusEvent, CallCreate, CallLineIn, Card,
                                    FaceResult, IntroRequest, Person, PersonDetail,
                                    RecognitionResult, RecognizeRequest, RecognizeResponse)
from calypso_agent.conversation import SetupScript
from calypso_agent.core import GroupCall
from calypso_agent.scheduler import CardScheduler
from calypso_agent.speech import FakeSTT, FakeTTS
from calypso_agent.state import CallState


def jpeg(color="blue"):
    out = BytesIO()
    Image.new("RGB", (64, 64), color).save(out, "JPEG")
    return out.getvalue()


def backend():
    return FakeBackendClient(
        patient=Person(id="patient", name="Mary", is_patient=True),
        enrollment=PersonDetail(id="relative", name="Sarah", relationship="daughter",
                                facts=["Bakes with Mary on Sundays"]),
    )


@pytest.mark.asyncio
async def test_enroll_then_recognize_in_separate_call():
    api, voice = backend(), FakeTTS()
    setup = SetupScript(api, FakeSTT(["I'm Sarah, Mary's daughter.",
                                    "We bake together on Sundays.", "yes"]), voice)
    crops = [jpeg("blue"), jpeg("green"), jpeg("red")]
    person = await setup.run(crops)
    assert person.name == "Sarah"
    assert setup.state == "done"
    assert api.intros[0].face_jpegs_b64 == [base64.b64encode(c).decode() for c in crops]
    assert "Sarah" in api.intros[0].transcript
    assert api.calls[0].ended is not None

    group = await GroupCall.start(api, ["patient", "relative"])
    await group.on_frame("relative-phone", crops[0])
    await group.on_frame("relative-phone", crops[0])
    card = group.scheduler.current()
    assert card.kind == "identity" and card.title == "Sarah"
    assert "daughter" in card.lines
    assert render(card, {}).size == (1280, 720)
    assert len([e for e in api.events if e.stage == "card.queued"]) == 1
    await group.end()
    assert all(c.ended is not None for c in api.calls)


@pytest.mark.asyncio
async def test_setup_script_silence_reprompts_once_then_ends():
    api, tts = backend(), FakeTTS()
    setup = SetupScript(api, FakeSTT([None, None]), tts)
    assert await setup.run([jpeg()] * 3) is None
    assert not api.intros
    assert sum("didn't catch" in line for line in tts.spoken) == 1
    assert api.calls[0].ended is not None


@pytest.mark.asyncio
async def test_setup_requires_confirmation_and_three_crops():
    api = backend()
    setup = SetupScript(api, FakeSTT(["Sarah", "Baking", "no", None, None]), FakeTTS())
    assert await setup.run([jpeg()] * 3) is None
    assert not api.intros
    with pytest.raises(ValueError, match="three"):
        await SetupScript(api, FakeSTT([]), FakeTTS()).run([jpeg()])


def test_identified_emits_identity_card_once():
    state = CallState({"r": PersonDetail(id="r", name="Sarah")})
    result = RecognitionResult(status="identified", person_id="r")
    assert len(state.on_result("phone", result)) == 1
    assert state.on_result("phone", result) == []


def test_learning_debounced_three_frames_and_uncertainty_resets():
    state = CallState({})
    learning = RecognitionResult(status="learning")
    assert state.on_result("phone", learning) == []
    assert state.on_result("phone", learning) == []
    assert state.on_result("phone", RecognitionResult(status="uncertain")) == []
    assert state.on_result("phone", learning) == []
    assert state.on_result("phone", learning) == []
    assert state.on_result("phone", learning)[0].kind == "learning"
    assert state.on_result("phone", learning) == []


def test_patient_and_unknown_profile_ignored():
    state = CallState({"p": PersonDetail(id="p", name="Mary", is_patient=True)})
    assert state.on_result("patient", RecognitionResult(status="identified", person_id="p")) == []
    assert state.on_result("missing", RecognitionResult(status="identified", person_id="missing")) == []
    assert state.on_result("patient", None) == []


def test_card_scheduler_no_preempt_under_min():
    scheduler = CardScheduler(clock=lambda: 0)
    a = Card(kind="identity", title="A", lines=[])
    b = Card(kind="identity", title="B", lines=[])
    scheduler.push(a)
    assert scheduler.current(0) == a
    scheduler.push(b)
    assert scheduler.current(4) == a
    assert scheduler.current(7) == b
    assert scheduler.current(17) is None


def test_no_duplicate_within_60s_and_no_queued_duplicates():
    now = [0]
    scheduler = CardScheduler(clock=lambda: now[0])
    card = Card(kind="learning", title="Getting to know someone new…", lines=[])
    assert scheduler.push(card)
    assert not scheduler.push(card)
    scheduler.current(0)
    now[0] = 59
    assert not scheduler.push(card)
    now[0] = 60
    assert scheduler.push(card)


@pytest.mark.parametrize("kind", ["identity", "learning", "today", "memory"])
def test_render_size_and_safe_margins(kind):
    image = render(Card(kind=kind, title="A title " * 40, lines=["x" * 200] * 10), {})
    assert image.size == (1280, 720) and image.mode == "RGB"
    diff = ImageChops.difference(image, Image.new("RGB", image.size, BACKGROUND))
    left, top, right, bottom = diff.getbbox()
    assert left >= 40 and top >= 40 and right <= 1240 and bottom <= 680


def test_identity_with_missing_photo_uses_placeholder():
    card = Card(kind="identity", title="Sarah", lines=["daughter"], image_urls=["missing"])
    image = render(card, {})
    assert image.getpixel((1072, 280)) != BACKGROUND
    supplied = render(card, {"missing": Image.new("RGB", (100, 100), "red")})
    assert supplied.getpixel((1072, 280)) == (255, 0, 0)
    assert supplied.tobytes() != image.tobytes()


@pytest.mark.asyncio
async def test_http_backend_sends_auth_and_real_contract():
    calls = []
    def handler(request):
        calls.append(request)
        assert request.headers["authorization"] == "Bearer test-token"
        if request.url.path == "/people":
            assert request.url.params["is_patient"] == "true"
            return httpx.Response(200, json=[Person(id="p", name="Mary", is_patient=True).model_dump()])
        return httpx.Response(200, json={"faces": [], "voice_only": None})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://backend.test") as http:
        api = BackendClient("https://backend.test", "test-token", client=http)
        assert (await api.patient()).name == "Mary"
        assert (await api.recognize(jpeg(), "phone", "call")).faces == []
    assert len(calls) == 2


def test_shared_contract_has_not_drifted():
    root = Path(__file__).resolve().parents[2]
    assert (root / "agent/calypso_agent/contract.py").read_bytes() == (root / "backend/calypso/models.py").read_bytes()


def test_fake_speech_provider_contract():
    assert FakeSTT(["hi"]).transcribe(b"fixture")[0].text == "hi"
    with wave.open(BytesIO(FakeTTS().synthesize("hi")), "rb") as wav:
        assert (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) == (16000, 1, 2)


@pytest.mark.asyncio
async def test_enrollment_failure_still_ends_call():
    api = backend()
    async def fail(intro):
        raise RuntimeError("backend unavailable")
    api.enroll = fail
    script = SetupScript(api, FakeSTT(["Sarah", "Baking", "yes"]), FakeTTS())
    with pytest.raises(RuntimeError, match="backend unavailable"):
        await script.run([jpeg()] * 3)
    assert api.calls[0].ended is not None
    assert script.state != "done"


@pytest.mark.asyncio
async def test_group_unknown_then_uncertain_or_multiple_faces_never_gets_identity():
    api = backend()
    group = await GroupCall.start(api, [])
    for _ in range(3):
        await group.on_frame("unknown", jpeg())
    assert group.scheduler.current().kind == "learning"
    async def ambiguous(*args):
        return RecognizeResponse(faces=[FaceResult(result=RecognitionResult(status="uncertain"))])
    api.recognize = ambiguous
    await group.on_frame("ambiguous", jpeg())
    async def composite(*args):
        return RecognizeResponse(faces=[FaceResult(result=RecognitionResult(status="identified", person_id="relative"))] * 2)
    api.recognize = composite
    await group.on_frame("grid", jpeg())
    assert not any(e.payload["card"]["kind"] == "identity" for e in api.events)
    await group.end()


@pytest.mark.asyncio
async def test_http_enrollment_call_logging_and_events_match_contract():
    seen = []
    def handler(request):
        assert request.headers["authorization"] == "Bearer secret"
        body = json.loads(request.content) if request.content else None
        seen.append(request.url.path)
        if request.url.path == "/calls":
            assert CallCreate.model_validate(body).kind == "setup"
            return httpx.Response(201, json={"id": "c1", "kind": "setup", "started": "2026-11-14T20:00:00Z"})
        if request.url.path.endswith("/lines"):
            assert CallLineIn.model_validate(body).text == "Sarah"
        elif request.url.path == "/people/from_intro":
            intro = IntroRequest.model_validate(body)
            assert len(intro.face_jpegs_b64) == 3 and intro.call_id == "c1"
            return httpx.Response(201, json=Person(id="r", name="Sarah").model_dump())
        elif request.url.path == "/agent/events":
            assert BusEvent.model_validate(body).stage == "card.queued"
        return httpx.Response(200, json={"ok": True})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        api = BackendClient("https://backend.test", "secret", client=http)
        call = await api.start_call("setup", [])
        await api.log_line(call.id, CallLineIn(speaker="caller", text="Sarah"))
        assert (await api.enroll(IntroRequest(transcript="Sarah", face_jpegs_b64=["eA=="] * 3, call_id=call.id))).id == "r"
        await api.event("card.queued", {})
        await api.end_call(call.id)
    assert seen == ["/calls", "/calls/c1/lines", "/people/from_intro", "/agent/events", "/calls/c1/end"]


def test_identity_replaces_placeholders_in_observed_call_sequence():
    now = [0.0]
    scheduler = CardScheduler(clock=lambda: now[0])
    waiting = Card(kind="learning", title="Looking for a familiar face…", lines=[])
    uncertain = Card(kind="learning", title="Not sure who this is yet…", lines=[])
    identity = Card(kind="identity", title="Keanu", lines=["Mary's brother", "School together"])
    scheduler.push(waiting)
    assert scheduler.current() == waiting
    scheduler.push(uncertain)
    assert not scheduler.push(uncertain)
    now[0] = 4
    scheduler.push(identity)
    assert scheduler.current() == identity
    now[0] = 15
    assert scheduler.current() is None  # no stale uncertainty left in the queue


def test_identity_does_not_preempt_another_real_card():
    now = [0.0]
    scheduler = CardScheduler(clock=lambda: now[0])
    memory = Card(kind="memory", title="A shared memory", lines=["A day at the lake"])
    identity = Card(kind="identity", title="Keanu", lines=["Mary's brother"])
    scheduler.push(memory)
    assert scheduler.current() == memory
    now[0] = 2
    scheduler.push(Card(kind="learning", title="Not sure", lines=[]))
    scheduler.push(identity)
    assert scheduler.current() == memory
    now[0] = 6
    assert scheduler.current() == identity
