"""`POST /recognize`: face first, voice second (Task 4).

M1 stub with the final request/response shape: every face (and voice-only
clip) comes back as "learning", so the agent can wire up its card flow.
M2 replaces this with real matching through `identity/fuse.py`.
"""
from fastapi import APIRouter, Depends

from ..auth import require_token
from ..bus import emit
from ..deps import b64decode
from ..models import FaceResult, RecognitionResult, RecognizeRequest, RecognizeResponse

router = APIRouter(dependencies=[Depends(require_token)])


@router.post("/recognize", response_model=RecognizeResponse)
def recognize(body: RecognizeRequest) -> RecognizeResponse:
    has_face = bool(body.face_jpeg_b64) and bool(b64decode(body.face_jpeg_b64, "face_jpeg_b64"))
    has_voice = bool(body.voice_wav_b64) and bool(b64decode(body.voice_wav_b64, "voice_wav_b64"))
    learning = RecognitionResult(status="learning")
    resp = RecognizeResponse(
        faces=[FaceResult(bbox=None, result=learning)] if has_face else [],
        voice_only=learning if (has_voice and not has_face) else None,
    )
    emit("recognize", {
        "participant_key": body.participant_key,
        "call_id": body.call_id,
        "faces": [f.model_dump(mode="json") for f in resp.faces],
        "voice_only": resp.voice_only.model_dump(mode="json") if resp.voice_only else None,
        "stub": True,
    })
    return resp
