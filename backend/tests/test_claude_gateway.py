"""Real gateway/API writes with deterministic model tool requests, never live keys."""

from collections import deque
from pathlib import Path
from types import SimpleNamespace as NS

import httpx
import pytest


class Block:
    def __init__(self, body): self.body = body
    def model_dump(self, **kwargs): return self.body


class FakeClaude:
    def __init__(self, actions):
        self.actions = deque(actions)
        self.messages = self
        self.requests = []
    async def create(self, **request):
        self.requests.append(request)
        action = self.actions.popleft()
        if action is None:
            return NS(content=[Block({"type": "text", "text": "Waiting for the caller."})])
        name, args = action
        return NS(content=[Block({"type": "tool_use", "id": f"tool-{len(self.requests)}", "name": name, "input": args})])


@pytest.fixture
def gateway_app(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "backend"))
    monkeypatch.setenv("CALYPSO_API_TOKEN", "gateway-token")
    monkeypatch.setenv("CALYPSO_DB", str(tmp_path / "backend.db"))
    monkeypatch.setenv("CALYPSO_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("CALYPSO_JOBS", "inline")
    monkeypatch.setenv("CALYPSO_STORAGE", "local")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from calypso.app import create_app
    return create_app()


@pytest.mark.asyncio
async def test_claude_drives_setup_and_real_backend_enrollment(gateway_app):
    from calypso.claude_controller import ClaudeController
    model = FakeClaude([
        ("speak", {"text": "Hi, I'm Calypso⁻¹. Who are you to Mary?"}), None,
        ("speak", {"text": "What do you share?"}), None,
        ("confirm_intro", {"name": "Sarah", "relationship": "daughter", "memory": "Baking on Sundays"}), None,
        ("save_intro", {}), ("speak", {"text": "Your introduction is saved."}), ("finish", {}), None,
    ])
    gateway_app.state.claude_controller = ClaudeController(model)
    async with gateway_app.router.lifespan_context(gateway_app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=gateway_app),
            base_url="http://test", headers={"Authorization": "Bearer gateway-token"}) as client:
            await client.post("/people", json={"name": "Mary", "is_patient": True})
            session = (await client.post("/agent/sessions", json={"mode": "setup", "participant": "phone", "caller_phone": "+15555550123"})).json()["session_id"]
            async def event(kind, **fields):
                response = await client.post(f"/agent/sessions/{session}/events", json={"kind": kind, **fields})
                assert response.status_code == 200, response.text
                return response.json()
            greeting = (await event("start"))["speech"][0]
            assert "What's your name" in greeting and "Hi Mary" not in greeting
            await event("utterance", text="Sarah, her daughter")
            assert "You are Sarah, Mary's daughter." in (await event("utterance", text="Baking on Sundays"))["speech"][0]
            finished = await event("utterance", text="Yes", face_jpegs_b64=["eA=="] * 3)
            assert finished["done"] and finished["enrolled_person_id"]
            assert "Please hang up now" in finished["speech"][0]
            assert finished["cards"][0]["title"] == "Saved"
            person = (await client.get("/people/" + finished["enrolled_person_id"])).json()
            assert person["name"] == "Sarah" and person["relationship"] == "daughter"
            assert person["facts"] == ["Baking on Sundays"]
            assert person["phone"] == "+15555550123"
            assert (await client.post(f"/agent/sessions/{session}/end")).status_code == 200
            assert not gateway_app.state.agent_sessions
    assert model.requests[0]["tool_choice"]["disable_parallel_tool_use"] is True


@pytest.mark.asyncio
async def test_model_tools_cannot_bypass_confirmation_patient_or_group_rules(gateway_app):
    from calypso.claude_controller import ClaudeController, Effects, Session, StartSession
    controller = ClaudeController()
    session = Session("sid", "cid", StartSession(mode="setup", participant="phone"), {"name": "Mary"})
    writes = []
    async def api(method, path, body=None):
        writes.append((method, path, body))
        return {"id": "p", "name": "Mary", "is_patient": True}
    effects = Effects(session_id="sid")
    with pytest.raises(ValueError, match="Read back"):
        await controller.execute("save_intro", {}, session, effects, api)
    await controller.execute("confirm_intro", {"name": "Sarah", "relationship": "daughter", "memory": "Baking"}, session, effects, api)
    with pytest.raises(ValueError, match="explicit yes"):
        await controller.execute("save_intro", {}, session, effects, api)
    session.last_text = "Yes"
    session.intro_confirmed = True
    assert (await controller.execute("save_intro", {}, session, effects, api))["waiting_for_camera"]
    assert writes == []
    session.config.mode = "group"
    session.recognized_id = "p"
    with pytest.raises(ValueError, match="Patient"):
        await controller.execute("show_identity", {}, session, Effects(session_id="sid"), api)
    with pytest.raises(ValueError, match="one newcomer"):
        await controller.execute("speak", {"text": "Hello"}, session, Effects(session_id="sid"), api)
    session.learning_count = 3
    await controller.execute("speak", {"text": "How do you know Mary?"}, session, Effects(session_id="sid"), api)
    with pytest.raises(ValueError, match="one newcomer"):
        await controller.execute("speak", {"text": "Another question"}, session, Effects(session_id="sid"), api)
    assert not effects.cards


@pytest.mark.asyncio
async def test_gateway_auth_missing_key_and_modes(gateway_app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=gateway_app), base_url="http://test") as client:
        body = {"mode": "setup", "participant": "phone"}
        assert (await client.post("/agent/sessions", json=body)).status_code == 401
        client.headers["Authorization"] = "Bearer gateway-token"
        assert (await client.post("/agent/sessions", json=body)).status_code == 503
        assert (await client.post("/agent/sessions", json={**body, "mode": "patient"})).status_code == 422


@pytest.mark.asyncio
async def test_group_recognition_triggers_claude_once_and_never_guesses():
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
    from calypso.claude_controller import ClaudeController, MediaEvent, Session, StartSession
    model = FakeClaude([("show_identity", {}), None])
    session = Session("sid", "cid", StartSession(mode="group", participant="phone"), {})
    status = ["identified"]
    async def api(method, path, body=None):
        if path == "/recognize":
            return {"faces": [{"result": {"status": status[0], "person_id": "r"}}]}
        return {"id": "r", "name": "Sarah", "relationship": "daughter", "is_patient": False}
    controller = ClaudeController(model)
    effect = await controller.respond(session, MediaEvent(kind="frame", jpeg_b64="eA=="), api)
    assert effect.cards[0].title == "Sarah" and not effect.speech
    assert not (await controller.respond(session, MediaEvent(kind="frame", jpeg_b64="eA=="), api)).cards
    status[0] = "uncertain"
    assert not (await controller.respond(session, MediaEvent(kind="frame", jpeg_b64="eA=="), api)).cards
    assert session.recognized_id is None
    assert len(model.requests) == 2


@pytest.mark.asyncio
async def test_confirmed_intro_waits_for_camera_without_reconfirming():
    from calypso.claude_controller import ClaudeController, MediaEvent, Session, StartSession
    model = FakeClaude([
        ("save_intro", {}), ("speak", {"text": "Please hold your face steady."}), None,
        ("speak", {"text": "Waiting for three clear samples."}), None,
        ("save_intro", {}), ("speak", {"text": "Saved."}), ("finish", {}), None,
    ])
    session = Session("sid", "cid", StartSession(mode="setup", participant="phone"), {})
    session.pending_intro = {"name": "Sarah", "relationship": "daughter", "memory": "Baking"}
    writes = []
    async def api(method, path, body=None):
        if path == "/people/from_intro":
            writes.append(body)
            return {"id": "r"}
        return {"ok": True}
    controller = ClaudeController(model)
    waiting = await controller.respond(session, MediaEvent(kind="utterance", text="Yes"), api)
    assert waiting.needs_face_crops and session.intro_confirmed
    assert not writes
    await controller.respond(session, MediaEvent(kind="utterance", text="You can capture my face."), api)
    assert session.pending_intro and session.intro_confirmed
    finished = await controller.respond(session, MediaEvent(kind="camera_ready", face_jpegs_b64=["eA=="] * 3), api)
    assert finished.done and finished.enrolled_person_id == "r" and not finished.needs_face_crops
    assert len(writes) == 1


@pytest.mark.asyncio
async def test_camera_permission_alone_never_confirms_an_intro():
    from calypso.claude_controller import ClaudeController, MediaEvent, Session, StartSession
    model = FakeClaude([None])
    session = Session("sid", "cid", StartSession(mode="setup", participant="phone"), {})
    session.pending_intro = {"name": "Sarah", "relationship": "daughter", "memory": "Baking"}
    async def api(*args): return {"ok": True}
    await ClaudeController(model).respond(session, MediaEvent(kind="utterance", text="You can capture my face."), api)
    assert not session.intro_confirmed and session.pending_intro is None


@pytest.mark.asyncio
async def test_setup_greeting_does_not_address_unknown_caller_as_patient():
    from calypso.claude_controller import ClaudeController, Effects, Session, StartSession
    session = Session("sid", "cid", StartSession(mode="setup", participant="phone"), {"name": "Mary"})
    effects = Effects(session_id="sid")
    async def api(*args): return {}
    await ClaudeController().execute("speak", {"text": "Hi Mary!"}, session, effects, api)
    assert effects.speech == ["Hi, I'm Calypso⁻¹. I help Mary remember loved ones. What's your name, and how do you know Mary?"]


def test_unsaved_closing_never_claims_success():
    from calypso.claude_controller import ClaudeController, Effects, Session, StartSession
    session = Session("sid", "cid", StartSession(mode="setup", participant="phone"), {})
    effects = Effects(session_id="sid")
    ClaudeController.finish_setup(session, effects)
    assert effects.done and effects.cards[0].title != "Saved"
    assert "No introduction was saved" in effects.speech[0]
    assert "Please hang up now" in effects.speech[0]


CARD = {"kind": "today", "title": "Today", "lines": ["Lunch with Sarah"]}


def _group_session():
    from calypso.claude_controller import Session, StartSession
    return Session("sid", "cid", StartSession(mode="group", participant="phone"), {})


def _recording_api(card=CARD, delay=0):
    calls = []
    async def api(method, path, body=None):
        calls.append((method, path, body))
        if path == "/recall":
            if delay:
                import asyncio
                await asyncio.sleep(delay)
            return {"intent": "today" if card else "none", "card": card}
        return {"ok": True}
    api.calls = calls
    return api


@pytest.mark.asyncio
async def test_group_utterance_calls_recall_not_sonnet():
    from calypso.claude_controller import ClaudeController, MediaEvent
    model = FakeClaude([])
    api = _recording_api()
    effects = await ClaudeController(model).respond(_group_session(), MediaEvent(kind="utterance", text="what day is it"), api)
    assert len(effects.cards) == 1 and effects.cards[0].kind == "today"
    assert model.requests == []
    recall = [c for c in api.calls if c[1] == "/recall"]
    assert recall[0][2]["lines"] == [{"speaker": "phone", "text": "what day is it"}]


@pytest.mark.asyncio
async def test_group_recall_none_no_sonnet():
    from calypso.claude_controller import ClaudeController, MediaEvent
    model = FakeClaude([])
    effects = await ClaudeController(model).respond(_group_session(), MediaEvent(kind="utterance", text="nice weather"), _recording_api(card=None))
    assert not effects.cards and model.requests == []


@pytest.mark.asyncio
async def test_group_recall_timeout_returns_empty():
    import time
    from calypso.claude_controller import ClaudeController, MediaEvent
    model = FakeClaude([])
    start = time.monotonic()
    effects = await ClaudeController(model).respond(_group_session(), MediaEvent(kind="utterance", text="hello"), _recording_api(delay=5))
    assert time.monotonic() - start <= 4.5
    assert not effects.cards and not effects.speech and model.requests == []


@pytest.mark.asyncio
async def test_group_recall_http_error_returns_empty():
    from calypso.claude_controller import ClaudeController, MediaEvent
    async def api(method, path, body=None):
        if path == "/recall":
            raise httpx.HTTPStatusError("boom", request=None, response=None)
        return {"ok": True}
    effects = await ClaudeController(FakeClaude([])).respond(_group_session(), MediaEvent(kind="utterance", text="hello"), api)
    assert not effects.cards


@pytest.mark.asyncio
async def test_group_recall_debounced_10s(monkeypatch):
    import time
    from calypso.claude_controller import ClaudeController, MediaEvent
    now = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: now[0])
    session = _group_session()
    controller = ClaudeController(FakeClaude([]))
    api = _recording_api()
    first = await controller.respond(session, MediaEvent(kind="utterance", text="one"), api)
    now[0] += 1
    second = await controller.respond(session, MediaEvent(kind="utterance", text="two"), api)
    now[0] += 10
    third = await controller.respond(session, MediaEvent(kind="utterance", text="three"), api)
    assert len(first.cards) == 1 and not second.cards and len(third.cards) == 1


@pytest.mark.asyncio
async def test_pending_newcomer_reply_goes_to_sonnet():
    from calypso.claude_controller import ClaudeController, MediaEvent
    model = FakeClaude([None])
    session = _group_session()
    session.awaiting_newcomer_reply = True
    api = _recording_api()
    controller = ClaudeController(model)
    await controller.respond(session, MediaEvent(kind="utterance", text="She is my niece"), api)
    assert len(model.requests) == 1 and session.awaiting_newcomer_reply is False
    assert not [c for c in api.calls if c[1] == "/recall"]
    effects = await controller.respond(session, MediaEvent(kind="utterance", text="what day is it"), api)
    assert len(model.requests) == 1 and len(effects.cards) == 1


@pytest.mark.asyncio
async def test_group_speak_sets_awaiting_newcomer_reply():
    from calypso.claude_controller import ClaudeController, Effects
    session = _group_session()
    session.learning_count = 3
    async def api(*args): return {}
    await ClaudeController().execute("speak", {"text": "Who is this?"}, session, Effects(session_id="sid"), api)
    assert session.awaiting_newcomer_reply is True


@pytest.mark.asyncio
async def test_returning_relative_uses_real_result_and_stored_memory():
    from calypso.claude_controller import ClaudeController, MediaEvent, Session, StartSession
    model = FakeClaude([("show_identity", {}), None])
    session = Session("sid", "cid", StartSession(mode="recognize", participant="phone",
        enrolled_person_id="wrong-fixture", outcome="learning"), {"name": "Mary"})
    requests = []
    async def api(method, path, body=None):
        requests.append((path, body))
        if path == "/recognize":
            return {"faces": [{"result": {"status": "identified", "person_id": "real-relative"}}]}
        assert path == "/people/real-relative"
        return {"id": "real-relative", "name": "Keanu", "relationship": "brother",
                "is_patient": False, "facts": ["We visited the lake."]}
    effects = await ClaudeController(model).respond(session, MediaEvent(kind="frame", jpeg_b64="eA=="), api)
    assert effects.cards[0].title == "Keanu"
    assert effects.cards[0].lines == ["Mary's brother", "We visited the lake."]
    assert not effects.speech
    assert requests[0][1]["exclude_patient"] is True


@pytest.mark.asyncio
async def test_opening_recognition_ignores_voice_and_spoken_identity():
    from calypso.claude_controller import ClaudeController, MediaEvent, Session, StartSession
    controller = ClaudeController(FakeClaude([]))
    session = Session("sid", "cid", StartSession(mode="recognize", participant="phone"), {"name": "Mary"})
    requests = []
    async def api(method, path, body=None):
        requests.append((path, body))
        return {}
    effects = await controller.respond(session, MediaEvent(kind="utterance",
        text="I am Sarah", voice_wav_b64="d2F2", jpeg_b64="eA=="), api)
    assert not effects.cards and not effects.speech
    assert [path for path, _ in requests] == ["/calls/cid/lines"]
    assert session.recognized_id is None
    with pytest.raises(ValueError, match="remain silent"):
        await controller.execute("speak", {"text": "Who are you?"}, session, effects, api)


@pytest.mark.asyncio
async def test_frame_uses_face_only_and_never_accepts_voice_only_result():
    from calypso.claude_controller import ClaudeController, MediaEvent, Session, StartSession
    session = Session("sid", "cid", StartSession(mode="recognize", participant="phone"), {})
    async def api(method, path, body=None):
        assert path == "/recognize"
        assert body["face_jpeg_b64"] == "eA==" and not body.get("voice_wav_b64")
        return {"faces": [], "voice_only": {"status": "identified", "person_id": "voice-person"}}
    effects = await ClaudeController(FakeClaude([])).respond(session,
        MediaEvent(kind="frame", jpeg_b64="eA==", voice_wav_b64="d2F2"), api)
    assert not effects.cards and session.recognized_id is None


@pytest.mark.asyncio
async def test_recognize_mode_start_greets_once_and_patient_cannot_be_shown():
    from calypso.claude_controller import ClaudeController, Effects, MediaEvent, Session, StartSession
    controller = ClaudeController(FakeClaude([]))
    session = Session("sid", "cid", StartSession(mode="recognize", participant="phone"), {"name": "Mary"})
    async def api(*args): return {"name": "Mary", "is_patient": True}
    effects = await controller.respond(session, MediaEvent(kind="start"), api)
    assert effects.cards and effects.speech == ["Hi, it's Calypso. One moment while I see who's here."]
    assert not (await controller.respond(session, MediaEvent(kind="start"), api)).speech
    session.recognized_id = "patient"
    with pytest.raises(ValueError, match="Patient"):
        await controller.execute("show_identity", {}, session, Effects(session_id="sid"), api)


@pytest.mark.asyncio
async def test_recognize_session_api_accepts_mode_with_immediate_greeting(gateway_app):
    from calypso.claude_controller import ClaudeController
    gateway_app.state.claude_controller = ClaudeController(FakeClaude([]))
    async with gateway_app.router.lifespan_context(gateway_app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=gateway_app),
            base_url="http://test", headers={"Authorization": "Bearer gateway-token"}) as client:
            await client.post("/people", json={"name": "Mary", "is_patient": True})
            response = await client.post("/agent/sessions", json={"mode": "recognize", "participant": "phone"})
            assert response.status_code == 201, response.text
            sid = response.json()["session_id"]
            effects = (await client.post(f"/agent/sessions/{sid}/events", json={"kind": "start"})).json()
            assert len(effects["speech"]) == 1 and effects["cards"][0]["kind"] == "learning"
            assert (await client.post(f"/agent/sessions/{sid}/end")).status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("faces", [[], [{"result": {"status": "identified", "person_id": "a"}},
                                      {"result": {"status": "identified", "person_id": "b"}}]])
async def test_missing_or_multiple_faces_never_selects_one(faces):
    from calypso.claude_controller import ClaudeController, MediaEvent, Session, StartSession
    session = Session("sid", "cid", StartSession(mode="recognize", participant="phone"), {})
    session.recognized_id = "previous"
    async def api(*args): return {"faces": faces}
    effect = await ClaudeController(FakeClaude([])).respond(session, MediaEvent(kind="frame", jpeg_b64="eA=="), api)
    assert session.recognized_id == (None if faces else "previous")
    assert bool(effect.cards) == bool(faces)
    assert not effect.speech


@pytest.mark.asyncio
async def test_recognition_dropped_frames_do_not_hide_identity_and_uncertainty_is_deduped():
    from calypso.claude_controller import ClaudeController, MediaEvent, Session, StartSession
    session = Session("sid", "cid", StartSession(mode="recognize", participant="phone"), {"name": "Mary"})
    controller = ClaudeController(FakeClaude([("show_identity", {}), None]))
    status = "identified"
    async def api(method, path, body=None):
        if path == "/recognize":
            return {"faces": [{"result": {"status": status, "person_id": "r"}}]}
        return {"name": "Keanu", "relationship": "brother", "is_patient": False}
    await controller.respond(session, MediaEvent(kind="start"), api)
    for _ in range(2):
        assert not (await controller.respond(session, MediaEvent(kind="frame"), api)).cards
    assert (await controller.respond(session, MediaEvent(kind="frame", jpeg_b64="eA=="), api)).cards[0].title == "Keanu"
    assert not (await controller.respond(session, MediaEvent(kind="frame"), api)).cards
    assert session.recognized_id == "r"
    status = "uncertain"
    assert (await controller.respond(session, MediaEvent(kind="frame", jpeg_b64="eA=="), api)).cards
    assert session.recognized_id is None
    assert not (await controller.respond(session, MediaEvent(kind="frame", jpeg_b64="eA=="), api)).cards


@pytest.mark.asyncio
async def test_auto_recognized_relative_finishes_without_enrollment():
    from calypso.claude_controller import ClaudeController, MediaEvent, Session, StartSession
    controller = ClaudeController(FakeClaude([]))
    session = Session("sid", "cid", StartSession(mode="auto", participant="phone"), {"name": "Mary"})
    requests = []
    async def api(method, path, body=None):
        requests.append(path)
        if path == "/recognize":
            assert not body.get("voice_wav_b64")
            return {"faces": [{"result": {"status": "identified", "person_id": "r"}}]}
        assert path == "/people/r"
        return {"name": "Keanu", "relationship": "brother", "is_patient": False, "facts": ["School together"]}
    start = await controller.respond(session, MediaEvent(kind="start"), api)
    assert start.mode == "recognize" and start.speech
    effects = await controller.respond(session, MediaEvent(kind="frame", jpeg_b64="eA=="), api)
    assert effects.done
    assert effects.cards[0].title == "You are Keanu"
    assert effects.cards[0].lines == ["Mary's brother", "School together", "Please hang up now."]
    assert "Please hang up" in effects.speech[0]
    assert not (await controller.respond(session, MediaEvent(kind="recognition_timeout"), api)).speech
    assert "/people/from_intro" not in requests


@pytest.mark.asyncio
async def test_auto_timeout_starts_enrollment_once_without_guessing(monkeypatch):
    from calypso.claude_controller import ClaudeController, MediaEvent, Session, StartSession
    import calypso.claude_controller as module
    now = [100.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: now[0])
    controller = ClaudeController(FakeClaude([("speak", {"text": "Introduce yourself"}), None]))
    session = Session("sid", "cid", StartSession(mode="auto", participant="phone"), {"name": "Mary"})
    async def api(*args): raise AssertionError("No identity lookup or enrollment write expected")
    await controller.respond(session, MediaEvent(kind="start"), api)
    now[0] = 104.9
    assert not (await controller.respond(session, MediaEvent(kind="recognition_timeout"), api)).speech
    now[0] = 105.1
    effects = await controller.respond(session, MediaEvent(kind="recognition_timeout"), api)
    assert effects.mode == "setup" and not effects.done
    assert "What's your name" in effects.speech[0]
    assert session.recognized_id is None
    assert not (await controller.respond(session, MediaEvent(kind="recognition_timeout"), api)).speech


@pytest.mark.asyncio
async def test_auto_late_face_cannot_bypass_enrollment_deadline(monkeypatch):
    from calypso.claude_controller import ClaudeController, MediaEvent, Session, StartSession
    import calypso.claude_controller as module
    now = [100.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: now[0])
    controller = ClaudeController(FakeClaude([("speak", {"text": "Introduce yourself"}), None]))
    session = Session("sid", "cid", StartSession(mode="auto", participant="phone"), {"name": "Mary"})
    async def api(*args): raise AssertionError("No late identity lookup")
    await controller.respond(session, MediaEvent(kind="start"), api)
    now[0] = 106
    effects = await controller.respond(session, MediaEvent(kind="frame", jpeg_b64="eA=="), api)
    assert effects.mode == "setup" and "What's your name" in effects.speech[0]


@pytest.mark.asyncio
async def test_auto_session_api_starts_recognition_and_cleans_up(gateway_app):
    from calypso.claude_controller import ClaudeController
    gateway_app.state.claude_controller = ClaudeController(FakeClaude([]))
    async with gateway_app.router.lifespan_context(gateway_app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=gateway_app),
            base_url="http://test", headers={"Authorization": "Bearer gateway-token"}) as client:
            await client.post("/people", json={"name": "Mary", "is_patient": True})
            response = await client.post("/agent/sessions", json={"mode": "auto", "participant": "phone"})
            assert response.status_code == 201, response.text
            sid = response.json()["session_id"]
            effects = (await client.post(f"/agent/sessions/{sid}/events", json={"kind": "start"})).json()
            assert effects["mode"] == "recognize" and len(effects["speech"]) == 1
            events = [e for e in (await client.get("/events/recent?limit=1000")).json()
                      if e["payload"].get("session_id") == sid]
            started = [e["payload"] for e in events if e["stage"] == "agent.session"]
            assert started and started[0]["mode"] == "auto" and started[0]["participant"] == "phone"
            modes = [e["payload"] for e in events if e["stage"] == "agent.mode"]
            assert [(m["previous"], m["mode"], m["participant"]) for m in modes] == [("auto", "recognize", "phone")]
            assert (await client.post(f"/agent/sessions/{sid}/end")).status_code == 200


@pytest.mark.asyncio
async def test_auto_timeout_emits_agent_mode_setup(gateway_app, monkeypatch):
    from calypso.claude_controller import ClaudeController
    import calypso.claude_controller as module
    now = [100.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: now[0])
    gateway_app.state.claude_controller = ClaudeController(FakeClaude([("speak", {"text": "Introduce yourself"}), None]))
    async with gateway_app.router.lifespan_context(gateway_app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=gateway_app),
            base_url="http://test", headers={"Authorization": "Bearer gateway-token"}) as client:
            await client.post("/people", json={"name": "Mary", "is_patient": True})
            sid = (await client.post("/agent/sessions", json={"mode": "auto", "participant": "phone"})).json()["session_id"]
            await client.post(f"/agent/sessions/{sid}/events", json={"kind": "start"})
            now[0] = 105.1
            effects = (await client.post(f"/agent/sessions/{sid}/events", json={"kind": "recognition_timeout"})).json()
            assert effects["mode"] == "setup"
            modes = [e["payload"] for e in (await client.get("/events/recent?limit=1000")).json()
                     if e["stage"] == "agent.mode" and e["payload"].get("session_id") == sid]
            assert [(m["previous"], m["mode"]) for m in modes] == [("auto", "recognize"), ("recognize", "setup")]
