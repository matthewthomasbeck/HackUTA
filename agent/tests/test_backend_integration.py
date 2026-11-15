"""Real backend routes/storage with controlled model results; no network needed."""

from io import BytesIO
from pathlib import Path
import sqlite3

import httpx
from PIL import Image
import pytest

from calypso_agent.backend_client import BackendClient
from calypso_agent.conversation import SetupScript
from calypso_agent.core import GroupCall
from calypso_agent.speech import FakeSTT, FakeTTS
from calypso_agent.stage1_backend import ControlledBackend


@pytest.mark.asyncio
async def test_setup_then_group_against_actual_backend(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "backend"))
    monkeypatch.setenv("CALYPSO_API_TOKEN", "integration-token")
    monkeypatch.setenv("CALYPSO_DB", str(tmp_path / "backend.db"))
    monkeypatch.setenv("CALYPSO_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("CALYPSO_JOBS", "inline")
    monkeypatch.setenv("CALYPSO_STORAGE", "local")
    from calypso.app import create_app
    app = create_app()
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
            auth = {"Authorization": "Bearer integration-token"}
            response = await http.post("/people", headers=auth,
                json={"name": "Mary", "is_patient": True})
            assert response.status_code == 201
            api = BackendClient("http://test", "integration-token", client=http)
            state = tmp_path / "enrollment.json"
            setup_backend = ControlledBackend(api, state)
            out = BytesIO()
            Image.new("RGB", (80, 80), "blue").save(out, "JPEG")
            person = await SetupScript(setup_backend,
                FakeSTT(["Sarah, Mary's daughter", "Baking", "yes"]), FakeTTS()).run([out.getvalue()] * 3)
            # Real M1 backend stores enrollment but leaves extraction to M2.
            assert person.name is None and person.face_photo_url
            group_backend = ControlledBackend(api, state, outcome="identified", name="Sarah", relationship="daughter")
            group = await GroupCall.start(group_backend, [person.id])
            await group.on_frame("bridge", out.getvalue())
            card = group.scheduler.current()
            assert card.title == "Test profile: Sarah"
            await group.end()
            detail = await api.person(person.id)
            assert detail.name is None  # Controlled labels never overwrite real profiles.
            photo = await http.get(person.face_photo_url)
            assert photo.status_code == 200 and photo.content == out.getvalue()
    with sqlite3.connect(tmp_path / "backend.db") as conn:
        calls = conn.execute("SELECT kind, ended FROM calls").fetchall()
        assert len(calls) == 2 and all(ended for _, ended in calls)
        assert conn.execute("SELECT COUNT(*) FROM utterances WHERE source='call'").fetchone()[0] == 3
