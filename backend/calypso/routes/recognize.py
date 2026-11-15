"""`POST /recognize`: face first, voice second (see identity/fuse.py).

Every face in the frame gets its own result (composite grids work). Missing
models or unusable media degrade to "learning" (never a guess, never an error
that would end the agent's call).
"""
import logging
import sqlite3

from fastapi import APIRouter, Depends

from ..auth import require_token
from ..bus import emit
from ..config import Settings
from ..deps import b64decode, get_conn, get_face_embedder, get_settings, get_voice_embedder
from ..identity import ModelUnavailable
from ..identity.audio import AudioError
from ..identity.fuse import fuse
from ..identity.vectors import best_scores, ranked
from ..identity.voice import embed_wav
from ..models import FaceResult, RecognizeRequest, RecognizeResponse

router = APIRouter(dependencies=[Depends(require_token)])
_log = logging.getLogger("calypso.recognize")


def _top3(scores):
    return [{"person_id": p, "score": round(s, 3)} for p, s in ranked(scores)[:3]]


@router.post("/recognize", response_model=RecognizeResponse)
def recognize(
    body: RecognizeRequest,
    conn: sqlite3.Connection = Depends(get_conn),
    settings: Settings = Depends(get_settings),
    face_embedder=Depends(get_face_embedder),
    voice_embedder=Depends(get_voice_embedder),
) -> RecognizeResponse:
    notes: list[str] = []
    faces = []
    if body.face_jpeg_b64:
        try:
            faces = face_embedder.embed_all(b64decode(body.face_jpeg_b64, "face_jpeg_b64"))
        except ModelUnavailable as exc:
            notes.append(f"face model unavailable: {exc}")
    voice, speech_s = None, 0.0
    if body.voice_wav_b64:
        try:
            vec, speech_s = embed_wav(voice_embedder, b64decode(body.voice_wav_b64, "voice_wav_b64"),
                                      settings.voice_min_speech_s)
            if vec is not None:
                voice = best_scores(conn, "voice_prints", vec, body.exclude_patient)
            else:
                notes.append(f"only {speech_s:.1f} s of speech")
        except (AudioError, ModelUnavailable) as exc:
            notes.append(f"voice skipped: {exc}")

    results, debug = [], []
    for bbox, vec in faces:
        face = best_scores(conn, "face_embeddings", vec, body.exclude_patient)
        result = fuse(face, voice, settings)
        results.append(FaceResult(bbox=bbox, result=result))
        debug.append({"bbox": bbox.model_dump(), "status": result.status, "person_id": result.person_id,
                      "face_top3": _top3(face)})
    voice_only = fuse(None, voice, settings) if (body.voice_wav_b64 and not faces) else None
    if notes:
        _log.info("recognize notes: %s", "; ".join(notes))

    emit("recognize", {
        "participant_key": body.participant_key, "call_id": body.call_id,
        "faces": debug, "voice_top3": _top3(voice), "speech_s": round(speech_s, 1),
        "voice_only": voice_only.model_dump(mode="json") if voice_only else None,
        "thresholds": {"face_match": settings.face_match, "face_margin": settings.face_margin,
                       "voice_match": settings.voice_match, "voice_margin": settings.voice_margin},
        "notes": notes,
    })
    return RecognizeResponse(faces=results, voice_only=voice_only)
