"""`POST /recall`: in-call "what did you do today?". Detection and grounded retrieval live in `recall.py`."""
import sqlite3

from fastapi import APIRouter, Depends, Request

from .. import recall as recall_service
from ..auth import require_token
from ..deps import get_conn, get_settings
from ..models import RecallRequest, RecallResponse

router = APIRouter(dependencies=[Depends(require_token)])


@router.post("/recall", response_model=RecallResponse)
def recall(body: RecallRequest, request: Request, conn: sqlite3.Connection = Depends(get_conn),
           settings=Depends(get_settings)) -> RecallResponse:
    detector = getattr(request.app.state, "recall_detector", None)
    if detector is None:
        detector = request.app.state.recall_detector = recall_service.get_detector(settings)
    return recall_service.recall(body.lines, conn, settings, detector)
