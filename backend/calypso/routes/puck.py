"""Puck intake: speech segments (idempotent on segment_uuid), health, voice gallery."""
import sqlite3

import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import ValidationError

from ..auth import require_token
from ..bus import emit
from ..config import Settings
from ..deps import get_conn, get_jobs, get_settings
from ..identity.vectors import from_blob, normalize
from ..jobs import process_segment
from ..models import PuckGallery, PuckGallerySpeaker, PuckHealth, SegmentAck, SegmentMeta, iso_utc
from ..timeutil import now_iso

router = APIRouter(prefix="/puck", dependencies=[Depends(require_token)])


@router.post("/segments", response_model=SegmentAck)
def upload_segment(
    audio: UploadFile = File(...),
    meta: str = Form(...),
    conn: sqlite3.Connection = Depends(get_conn),
    settings: Settings = Depends(get_settings),
    jobs=Depends(get_jobs),
) -> SegmentAck:
    try:
        m = SegmentMeta.model_validate_json(meta)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors(include_url=False, include_context=False))

    data = audio.file.read(settings.max_audio_bytes + 1)
    if len(data) > settings.max_audio_bytes:
        raise HTTPException(status_code=413, detail="audio too large")
    if not data:
        raise HTTPException(status_code=422, detail="audio is empty")

    # Write the temp audio before recording the segment, so a stored segment
    # always has its audio waiting for the job.
    settings.tmp_dir.mkdir(parents=True, exist_ok=True)
    wav_path = settings.tmp_dir / f"{m.segment_uuid}.wav"

    cur = conn.execute(
        "INSERT OR IGNORE INTO segments (segment_uuid, ts_start, ts_end, local_text, status, received_at, time_synced)"
        " VALUES (?, ?, ?, ?, 'queued', ?, ?)",
        (m.segment_uuid, iso_utc(m.ts_start), iso_utc(m.ts_end), m.local_text, now_iso(), int(m.time_synced)),
    )
    if cur.rowcount == 0:  # already received: a retry from the puck's queue
        conn.rollback()
        return SegmentAck(segment_uuid=m.segment_uuid, duplicate=True)
    conn.executemany(
        "INSERT INTO sound_tags (segment_uuid, ts, label, score) VALUES (?, ?, ?, ?)",
        [(m.segment_uuid, iso_utc(t.ts), t.label, t.score) for t in m.sound_tags],
    )
    wav_path.write_bytes(data)
    conn.commit()

    emit("puck.segment", {
        "segment_uuid": m.segment_uuid,
        "ts_start": iso_utc(m.ts_start),
        "ts_end": iso_utc(m.ts_end),
        "seconds": round((m.ts_end - m.ts_start).total_seconds(), 2),
        "sound_tags": [t.model_dump(mode="json") for t in m.sound_tags],
        "has_local_text": bool(m.local_text),
    })
    try:
        jobs.enqueue(process_segment, m.segment_uuid, str(wav_path))
    except Exception as exc:
        # Undo, so the puck's retry is processed instead of being acked as a duplicate.
        conn.execute("DELETE FROM sound_tags WHERE segment_uuid = ?", (m.segment_uuid,))
        conn.execute("DELETE FROM utterances WHERE segment_uuid = ?", (m.segment_uuid,))
        conn.execute("DELETE FROM segments WHERE segment_uuid = ?", (m.segment_uuid,))
        conn.commit()
        wav_path.unlink(missing_ok=True)
        raise HTTPException(status_code=503, detail=f"could not queue processing, retry later: {exc}")

    rows = conn.execute("SELECT id FROM utterances WHERE segment_uuid = ?", (m.segment_uuid,)).fetchall()
    return SegmentAck(segment_uuid=m.segment_uuid, duplicate=False, utterance_ids=[r["id"] for r in rows])


@router.post("/health")
def puck_health(health: PuckHealth) -> dict:
    emit("puck.health", health.model_dump(mode="json"))
    return {"ok": True}


@router.get("/gallery", response_model=PuckGallery)
def puck_gallery(conn: sqlite3.Connection = Depends(get_conn)) -> PuckGallery:
    """Full voice-print snapshot for the puck. Mean of each person's Titanet prints.

    The puck replace-syncs from this: anyone missing here is dropped locally.
    People with no usable voice prints are omitted. Includes the patient.
    """
    people_rows = conn.execute(
        "SELECT id, name, relationship, is_patient FROM people ORDER BY created_at"
    ).fetchall()
    out: list[PuckGallerySpeaker] = []
    for person in people_rows:
        blobs = conn.execute(
            "SELECT vec FROM voice_prints WHERE person_id = ? ORDER BY created_at",
            (person["id"],),
        ).fetchall()
        vecs: list[np.ndarray] = []
        for row in blobs:
            stored = from_blob(row["vec"])
            if stored.size == 0:
                continue
            if vecs and stored.shape != vecs[0].shape:
                continue  # skip prints from a different model dim
            vecs.append(normalize(stored))
        if not vecs:
            continue
        mean = normalize(np.mean(np.stack(vecs, axis=0), axis=0))
        out.append(
            PuckGallerySpeaker(
                person_id=person["id"],
                display_name=person["name"],
                relationship=person["relationship"],
                is_patient=bool(person["is_patient"]),
                embedding=mean.astype(np.float32).tolist(),
            )
        )
    return PuckGallery(people=out)
