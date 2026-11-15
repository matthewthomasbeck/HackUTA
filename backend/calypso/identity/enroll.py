"""Turn face crops and caller speech into stored prints, and find who someone already is."""
import logging
import sqlite3

import numpy as np

from .. import db
from ..config import Settings
from ..timeutil import now_iso
from . import ModelUnavailable
from .audio import AudioError
from .face import FaceEmbedder, largest
from .fuse import fuse
from .vectors import best_scores, to_blob
from .voice import VoiceEmbedder, embed_wav

_log = logging.getLogger("calypso.enroll")


def face_vectors(embedder: FaceEmbedder, jpegs: list[bytes], notes: list[str]) -> list[np.ndarray]:
    """One print per image (the largest face in it). Images with no face are skipped."""
    vecs = []
    for i, jpeg in enumerate(jpegs):
        try:
            vec = largest(embedder.embed_all(jpeg))
        except ModelUnavailable as exc:
            notes.append(f"face model unavailable: {exc}")
            _log.warning("face model unavailable: %s", exc)
            return []
        if vec is None:
            notes.append(f"no face found in image {i + 1}")
        else:
            vecs.append(vec)
    return vecs


def voice_vector(embedder: VoiceEmbedder, wav: bytes | None, settings: Settings,
                 notes: list[str]) -> tuple[np.ndarray | None, float]:
    if not wav:
        return None, 0.0
    try:
        vec, seconds = embed_wav(embedder, wav, settings.voice_min_speech_s)
    except AudioError as exc:
        notes.append(f"voice audio unreadable: {exc}")
        return None, 0.0
    except ModelUnavailable as exc:
        notes.append(f"voice model unavailable: {exc}")
        _log.warning("voice model unavailable: %s", exc)
        return None, 0.0
    if vec is None:
        notes.append(f"only {seconds:.1f} s of speech; need {settings.voice_min_speech_s:.1f} s for a voiceprint")
    return vec, seconds


def mean_face_scores(conn: sqlite3.Connection, vecs: list[np.ndarray]) -> dict[str, float] | None:
    """Average each person's best score over all crops, so one odd crop can't decide."""
    if not vecs:
        return None
    per = [best_scores(conn, "face_embeddings", v) for v in vecs]
    people = set().union(*per)
    return {p: sum(s.get(p, 0.0) for s in per) / len(per) for p in people}


def find_existing(conn: sqlite3.Connection, settings: Settings, phone: str | None,
                  face_vecs: list[np.ndarray], voice_vec: np.ndarray | None) -> tuple[str | None, str | None]:
    """Who is this caller already? Returns (person_id, matched_by). Patient never matches."""
    if phone:
        row = conn.execute("SELECT id FROM people WHERE phone = ? AND is_patient = 0 ORDER BY created_at LIMIT 1",
                           (phone,)).fetchone()
        if row:
            return row["id"], "phone"
    face = mean_face_scores(conn, face_vecs)
    voice = best_scores(conn, "voice_prints", voice_vec) if voice_vec is not None else None
    if face:
        result = fuse(face, voice, settings)
        if result.status == "identified":
            return result.person_id, "face"
        if result.status == "uncertain" and max(face.values()) >= settings.face_match:
            return None, None  # conflicting or too-close evidence: don't merge into the wrong person
    if voice:
        result = fuse(None, voice, settings)
        if result.status == "identified":
            return result.person_id, "voice"
    return None, None


def store_prints(conn: sqlite3.Connection, person_id: str, face_vecs: list[np.ndarray],
                 voice_vec: np.ndarray | None, speech_s: float, face_source: str, voice_source: str) -> tuple[int, int]:
    for vec in face_vecs:
        conn.execute("INSERT INTO face_embeddings (id, person_id, vec, source, created_at) VALUES (?, ?, ?, ?, ?)",
                     (db.new_id(), person_id, to_blob(vec), face_source, now_iso()))
    if voice_vec is not None:
        conn.execute("INSERT INTO voice_prints (id, person_id, vec, source, speech_s, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                     (db.new_id(), person_id, to_blob(voice_vec), voice_source, round(speech_s, 2), now_iso()))
    conn.commit()
    return len(face_vecs), int(voice_vec is not None)


def print_counts(conn: sqlite3.Connection, person_id: str) -> tuple[int, int]:
    f = conn.execute("SELECT COUNT(*) FROM face_embeddings WHERE person_id = ?", (person_id,)).fetchone()[0]
    v = conn.execute("SELECT COUNT(*) FROM voice_prints WHERE person_id = ?", (person_id,)).fetchone()[0]
    return f, v
