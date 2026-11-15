"""Resolve caller metadata from Chert, never from speech or model output."""

import asyncio
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


async def wait_chert_bridge(participant_identity, *, home=None, client=None, poll_s=1):
    """Wait for this active call's worker-confirmed bridge_ready event.

    The outer media gate supplies the deadline and cancels this poller when
    metadata wins or the caller hangs up. Failures never count as readiness.
    """
    http = None
    owns = client is None
    try:
        prefix = "chert-bridge-"
        if not participant_identity.startswith(prefix):
            raise ValueError("Not a Chert bridge participant")
        call_id = str(UUID(participant_identity[len(prefix):]))
        directory = Path(home or os.getenv("CHERT_HOME") or Path.home() / ".chert")
        credentials = json.loads((directory / "credentials.json").read_text())
        project_id, token = credentials["project_id"], credentials["access_token"]
        origin = credentials.get("origin") or "https://app.trychert.com"
        parsed = urlsplit(origin)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.path not in {"", "/"}:
            raise ValueError("Invalid Chert origin")
        http = client or httpx.AsyncClient(timeout=3)
        while True:
            try:
                response = await http.get(origin.rstrip("/") + f"/api/v1/calls/{call_id}",
                    headers={"Authorization": f"Bearer {token}", "x-chert-project-id": project_id})
                response.raise_for_status()
                body = response.json()
                record = body.get("data", body)
                if record.get("id") != call_id or record.get("project_id") != project_id:
                    raise ValueError("Chert call identity mismatch")
                if record.get("status") in {"ended", "failed", "rejected", "canceled", "cancelled", "ending"}:
                    raise ConnectionError("Chert call ended before bridge readiness")
                if record.get("status") == "active" and any(
                    e.get("event_type") == "bridge_ready" and e.get("source") == "worker"
                    for e in record.get("facetime_call_events", [])):
                    return "chert_call_api"
            except (httpx.HTTPError, ValueError, TypeError, AttributeError):
                # Transient API failures/malformed records cannot unblock audio.
                log.warning("Chert bridge readiness check unavailable; awaiting confirmation")
            await asyncio.sleep(poll_s)
    except ConnectionError:
        raise
    except (OSError, KeyError, ValueError, TypeError):
        log.warning("Chert readiness API unavailable; waiting for room metadata")
        await asyncio.Event().wait()
    finally:
        if owns and http is not None:
            await http.aclose()
