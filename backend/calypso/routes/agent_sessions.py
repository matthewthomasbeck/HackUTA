"""Authenticated media-to-Claude gateway. No model secrets leave this server."""

from contextlib import asynccontextmanager
import asyncio
import logging
import os
import time
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
import httpx
from pydantic import BaseModel, Field

from ..auth import require_token
from ..bus import emit
from ..claude_controller import ClaudeController, Effects, MediaEvent, Session, StartSession

router = APIRouter(prefix="/agent/sessions", dependencies=[Depends(require_token)])
log = logging.getLogger("calypso.gateway")


@asynccontextmanager
async def backend_api(request):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=request.app),
        base_url="http://calypso-internal", timeout=5,
        headers={"Authorization": f"Bearer {request.app.state.settings.api_token}"}) as client:
        async def call(method, path, body=None):
            response = await client.request(method, path, json=body)
            response.raise_for_status()
            return response.json()
        yield call


def get_session(request, session_id):
    session = request.app.state.agent_sessions.get(session_id)
    if session is None:
        raise HTTPException(404, "Unknown agent session; reconnect the call")
    if time.monotonic() - session.touched > 3600:
        raise HTTPException(410, "Agent session expired; reconnect the call")
    return session


class RouteRequest(BaseModel):
    caller_phone: str | None = Field(default=None, pattern=r"^\+[1-9]\d{7,14}$")


@router.post("/route")
async def route(body: RouteRequest, request: Request):
    """Which flow a call gets, so no server-wide mode is needed.

    Mary (the patient) adding Calypso to a call with family → the silent group overlay.
    Anyone else calling → the 1:1 flow (recognize, or interview a new relative).
    """
    async with backend_api(request) as api:
        patients = await api("GET", "/people?is_patient=true")
    patient_phone = patients[0].get("phone") if len(patients) == 1 else None
    if body.caller_phone and patient_phone and body.caller_phone == patient_phone:
        mode, reason = "group_intro", "patient_phone"
    else:
        mode, reason = "auto", ("caller" if body.caller_phone else "no_phone")
    emit("agent.route", {"mode": mode, "reason": reason})  # never the phone number itself
    log.info("route mode=%s reason=%s", mode, reason)
    return {"mode": mode, "reason": reason}


@router.post("", status_code=201)
async def start(body: StartSession, request: Request):
    if request.app.state.claude_controller is None and not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(503, "ANTHROPIC_API_KEY is not configured on the backend")
    if len(request.app.state.agent_sessions) >= 32:
        raise HTTPException(503, "Agent session capacity reached")
    async with backend_api(request) as api:
        patients = await api("GET", "/people?is_patient=true")
        if len(patients) != 1:
            raise HTTPException(409, "Exactly one patient is required")
        if body.mode == "group_intro" and patients[0].get("name") != "Mary":
            raise HTTPException(409, "Manual group introductions require the fixed demo patient Mary")
        if body.mode == "group_intro" and body.controlled:
            raise HTTPException(422, "Manual group introductions require real recognition")
        if body.enrolled_person_id:
            person = await api("GET", f"/people/{body.enrolled_person_id}")
            if person["is_patient"]:
                raise HTTPException(422, "Patient cannot be a recognition fixture")
        call = await api("POST", "/calls", {"kind": "group" if body.mode in {"recognize", "auto", "group_intro"} else body.mode, "participants": [body.participant]})
    sid = uuid4().hex
    session = Session(sid, call["id"], body, patients[0])
    request.app.state.agent_sessions[sid] = session
    # The call log stores recognize calls as kind "group"; tell the dashboard the real mode.
    emit("agent.session", {"session_id": sid, "call_id": call["id"], "mode": body.mode,
                           "participant": body.participant, "controlled": body.controlled})
    return {"session_id": sid, "call_id": call["id"]}


@router.post("/{session_id}/events", response_model=Effects)
async def event(session_id: str, body: MediaEvent, request: Request):
    session = get_session(request, session_id)
    if any(len(crop) > 2_000_000 for crop in body.face_jpegs_b64) or (body.jpeg_b64 and len(body.jpeg_b64) > 2_000_000):
        raise HTTPException(413, "Camera sample too large")
    # voice_wav_b64 is capped at 2,000,000 chars (~45 s of 16 kHz speech) by MediaEvent itself.
    async with session.lock:
        log.info("session=%s event=%s crops=%d text_present=%s", session_id, body.kind,
                 len(body.face_jpegs_b64), bool(body.text))
        async with backend_api(request) as api:
            controller = request.app.state.claude_controller or ClaudeController()
            before = session.config.mode
            try:
                async with asyncio.timeout(30):
                    effects = await controller.respond(session, body, api)
                if session.config.mode != before:
                    # An auto call starts recognizing, then may switch to the setup interview.
                    emit("agent.mode", {"session_id": session_id, "call_id": session.call_id,
                                        "mode": session.config.mode, "previous": before,
                                        "participant": session.config.participant})
                for card in effects.cards:
                    emit("card.queued", {"session_id": session_id, "call_id": session.call_id,
                        "card": card.model_dump(mode="json"), "controlled": session.config.controlled})
                log.info("session=%s speech=%d cards=%d done=%s needs_face_crops=%s", session_id,
                         len(effects.speech), len(effects.cards), effects.done, effects.needs_face_crops)
                return effects
            except Exception as error:
                # Don't replay a partially executed write after a model/network failure.
                session.done = True
                raise HTTPException(503, "Claude controller failed; reconnect the call") from error


@router.post("/{session_id}/end")
async def end(session_id: str, request: Request):
    session = request.app.state.agent_sessions.get(session_id)
    if session is None:
        return {"ok": True}
    async with session.lock:
        async with backend_api(request) as api:
            await api("POST", f"/calls/{session.call_id}/end")
        request.app.state.agent_sessions.pop(session_id, None)
    return {"ok": True}
