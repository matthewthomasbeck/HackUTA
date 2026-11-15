"""Store and compare embeddings (face prints, voiceprints) as float32 BLOBs."""
import sqlite3

import numpy as np


def normalize(vec) -> np.ndarray:
    v = np.asarray(vec, dtype=np.float32).ravel()
    n = float(np.linalg.norm(v))
    return v / n if n > 0 else v


def to_blob(vec: np.ndarray) -> bytes:
    return normalize(vec).tobytes()


def from_blob(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32)


def best_scores(conn: sqlite3.Connection, table: str, vec: np.ndarray, exclude_patient: bool = True) -> dict[str, float]:
    """Highest cosine similarity per person over all of their stored prints in `table`.

    Prints with a different length (e.g. from an older model) are skipped.
    """
    if table not in ("face_embeddings", "voice_prints"):
        raise ValueError(table)
    q = normalize(vec)
    sql = f"SELECT e.person_id, e.vec FROM {table} e JOIN people p ON p.id = e.person_id"
    if exclude_patient:
        sql += " WHERE p.is_patient = 0"
    scores: dict[str, float] = {}
    for row in conn.execute(sql):
        stored = from_blob(row["vec"])
        if stored.shape != q.shape:
            continue
        s = float(stored @ q)
        if s > scores.get(row["person_id"], -2.0):
            scores[row["person_id"]] = s
    return scores


def ranked(scores: dict[str, float] | None) -> list[tuple[str, float]]:
    return sorted((scores or {}).items(), key=lambda kv: kv[1], reverse=True)
