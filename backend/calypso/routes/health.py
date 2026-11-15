"""Health, the live event stream, and event rebroadcast (dashboard feed)."""
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from ..auth import require_token
from ..bus import bus, emit, sse_events
from ..models import BusEvent

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"ok": True}


@router.get("/stream")
def stream(limit: int | None = Query(default=None, ge=1)) -> StreamingResponse:
    """Server-sent events of `{stage, ts, payload}`. No auth: the dashboard has no token."""
    return StreamingResponse(
        sse_events(bus, limit=limit),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/events/recent")
def recent_events(limit: int = Query(default=100, ge=1, le=200)) -> list[dict]:
    """The last events, so the dashboard can fill in on page load. No auth, like /stream."""
    return list(bus.recent)[-limit:]


@router.post("/events", dependencies=[Depends(require_token)])
def post_event(event: BusEvent) -> dict:
    """Rebroadcast an event from another process (the RQ worker) to /stream."""
    emit(event.stage, event.payload)
    return {"ok": True}


@router.post("/agent/events", dependencies=[Depends(require_token)])
def post_agent_event(event: BusEvent) -> dict:
    """Agent stages such as `card.shown`, rebroadcast to /stream."""
    emit(event.stage, event.payload)
    return {"ok": True}
