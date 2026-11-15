"""Resolve caller metadata from Chert, never from speech or model output."""

import json
import logging
import os
from pathlib import Path
import re
from urllib.parse import urlsplit
from uuid import UUID

import httpx

log = logging.getLogger("calypso.caller")
PHONE = re.compile(r"\+[1-9]\d{7,14}\Z")


def caller_phone(record, *, call_id, project_id):
    if record.get("id") != call_id or record.get("project_id") != project_id or record.get("direction") != "inbound":
        return None
    identity = record.get("from")
    if not isinstance(identity, dict) or identity.get("type") != "phone_number":
        return None
    value = identity.get("value")
    return value if isinstance(value, str) and PHONE.fullmatch(value) else None


async def resolve_caller_phone(participant_identity, *, home=None, client=None):
    prefix = "chert-bridge-"
    if not participant_identity.startswith(prefix):
        return None
    try:
        call_id = str(UUID(participant_identity[len(prefix):]))
        directory = Path(home or os.getenv("CHERT_HOME") or Path.home() / ".chert")
        credentials = json.loads((directory / "credentials.json").read_text())
        project_id, token = credentials["project_id"], credentials["access_token"]
        origin = credentials.get("origin") or "https://app.trychert.com"
        parsed = urlsplit(origin)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.path not in {"", "/"}:
            return None
        owns = client is None
        http = client or httpx.AsyncClient(timeout=3)
        try:
            response = await http.get(origin.rstrip("/") + f"/api/v1/calls/{call_id}",
                headers={"Authorization": f"Bearer {token}", "x-chert-project-id": project_id})
            response.raise_for_status()
            body = response.json()
            return caller_phone(body.get("data", body), call_id=call_id, project_id=project_id)
        finally:
            if owns:
                await http.aclose()
    except (OSError, KeyError, ValueError, TypeError, httpx.HTTPError):
        log.warning("Verified caller phone unavailable; enrollment will omit the phone field")
        return None
