"""`POST /recall`: in-call "what did you do today?" (Task 8).

M1 stub with the final shape: always `{intent: none, card: null}`, so the
agent's recall loop can be wired up. Task 8 adds the Haiku detector and search.
"""
from fastapi import APIRouter, Depends

from ..auth import require_token
from ..bus import emit
from ..models import Intent, RecallRequest, RecallResponse

router = APIRouter(dependencies=[Depends(require_token)])


@router.post("/recall", response_model=RecallResponse)
def recall(body: RecallRequest) -> RecallResponse:
    resp = RecallResponse(intent=Intent(intent="none"), card=None)
    last = body.lines[-1].text if body.lines else ""
    emit("recall.detect", {"last_line": last[:200], "intent": resp.intent.model_dump(), "stub": True})
    return resp
