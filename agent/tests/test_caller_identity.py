import json
from uuid import uuid4

import httpx
import pytest

from calypso_agent.caller_identity import caller_phone, resolve_caller_phone


def record(call_id="call", project_id="project", identity=None):
    return {"id": call_id, "project_id": project_id, "direction": "inbound",
            "from": identity or {"type": "phone_number", "value": "+15555550123"}}


def test_only_verified_inbound_phone_is_accepted():
    assert caller_phone(record(), call_id="call", project_id="project") == "+15555550123"
    for changed in [record(call_id="other"), record(project_id="other"),
                    {**record(), "direction": "outbound"},
                    record(identity={"type": "email", "value": "relative@example.com"}),
                    record(identity={"type": "phone_number", "value": "+1555***0123"})]:
        assert caller_phone(changed, call_id="call", project_id="project") is None


@pytest.mark.asyncio
async def test_resolver_uses_chert_call_not_participant_label(tmp_path):
    call_id = str(uuid4())
    (tmp_path / "credentials.json").write_text(json.dumps({"access_token": "secret", "project_id": "project", "origin": "https://chert.test"}))
    seen = []
    def handler(request):
        seen.append(request)
        assert request.url.path == f"/api/v1/calls/{call_id}"
        assert request.headers["Authorization"] == "Bearer secret"
        assert request.headers["x-chert-project-id"] == "project"
        return httpx.Response(200, json={"data": record(call_id=call_id)})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        assert await resolve_caller_phone("chert-bridge-" + call_id, home=tmp_path, client=http) == "+15555550123"
        assert await resolve_caller_phone("+15555550123", home=tmp_path, client=http) is None
        assert not http.is_closed
    assert len(seen) == 1


@pytest.mark.asyncio
async def test_resolver_handles_missing_credentials_and_auth_failure(tmp_path, caplog):
    call_id = str(uuid4())
    assert await resolve_caller_phone("chert-bridge-" + call_id, home=tmp_path) is None
    (tmp_path / "credentials.json").write_text(json.dumps({"access_token": "do-not-log", "project_id": "project"}))
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(401))) as http:
        assert await resolve_caller_phone("chert-bridge-" + call_id, home=tmp_path, client=http) is None
    assert "do-not-log" not in caplog.text
