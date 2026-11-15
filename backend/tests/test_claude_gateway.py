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
            session = (await client.post("/agent/sessions", json={"mode": "setup", "participant": "phone"})).json()["session_id"]
            async def event(kind, **fields):
                response = await client.post(f"/agent/sessions/{session}/events", json={"kind": kind, **fields})
                assert response.status_code == 200, response.text
                return response.json()
            assert "Who are you" in (await event("start"))["speech"][0]
            await event("utterance", text="Sarah, her daughter")
            assert "Sarah" in (await event("utterance", text="Baking on Sundays"))["speech"][0]
            finished = await event("utterance", text="Yes", face_jpegs_b64=["eA=="] * 3)
            assert finished["done"] and finished["enrolled_person_id"]
            person = (await client.get("/people/" + finished["enrolled_person_id"])).json()
            assert person["name"] == "Sarah" and person["relationship"] == "daughter"
            assert person["facts"] == ["Baking on Sundays"]
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
