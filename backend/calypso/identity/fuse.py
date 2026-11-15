"""Face first, voice second. Never guess: close or conflicting scores mean "uncertain".

Inputs are per-person best scores (patient already excluded):
- `face`: dict when a face was seen (may be empty if nobody has face prints), None if no face.
- `voice`: dict when there was enough speech, None otherwise.
"""
from ..config import Settings
from ..models import RecognitionResult
from .vectors import ranked

FACE_LEARN_MAX = 0.30  # below this nobody's face is even close: a newcomer


def _top2(scores):
    r = ranked(scores)
    top_id, top = r[0] if r else (None, 0.0)
    second = r[1][1] if len(r) > 1 else 0.0
    return top_id, top, second


def fuse(face: dict[str, float] | None, voice: dict[str, float] | None, s: Settings) -> RecognitionResult:
    v_id, v_top, v_second = _top2(voice)
    voice_clear = voice is not None and v_top >= s.voice_match and v_top - v_second >= s.voice_margin

    if face is not None:
        f_id, f_top, f_second = _top2(face)
        if f_id and f_top >= s.face_match and f_top - f_second >= s.face_margin:
            if voice is not None and v_id and v_id != f_id and v_top >= s.voice_match:
                return RecognitionResult(status="uncertain", face_score=f_top, voice_score=v_top)
            return RecognitionResult(status="identified", person_id=f_id, face_score=f_top,
                                     voice_score=(voice or {}).get(f_id))
        if f_top < FACE_LEARN_MAX and (voice is None or v_top < s.voice_learn_max):
            return RecognitionResult(status="learning", face_score=f_top if f_id else None,
                                     voice_score=v_top if v_id else None)
        return RecognitionResult(status="uncertain", face_score=f_top if f_id else None,
                                 voice_score=v_top if v_id else None)

    if voice is None:
        return RecognitionResult(status="learning")
    if voice_clear and v_top >= s.voice_match + 0.1:
        return RecognitionResult(status="identified", person_id=v_id, voice_score=v_top)
    if v_top < s.voice_learn_max:
        return RecognitionResult(status="learning", voice_score=v_top if v_id else None)
    return RecognitionResult(status="uncertain", voice_score=v_top)
