"""iOS uploads: visits (upsert by id) and photos (idempotent by id).

Task 6 later adds reverse geocoding, resizing, CLIP embeddings and the
Haiku "sensitive" check. M1 stores what the app sends.
"""
import logging
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import ValidationError

from ..auth import require_token
from ..bus import emit
from ..config import Settings
from ..day_builder import schedule_rebuild
from ..deps import get_conn, get_jobs, get_settings, get_storage
from ..models import PhotoMeta, Visit, iso_utc
from ..timeutil import now_iso

router = APIRouter(prefix="/app", dependencies=[Depends(require_token)])
_log = logging.getLogger("calypso.app_ingest")


def _rebuild_days(conn, settings: Settings, jobs, times: list[datetime]) -> None:
    """Late iOS uploads change days already built: queue a rate-limited rebuild for each."""
    zone = ZoneInfo(settings.tz)
    for day in sorted({t.astimezone(zone).date() for t in times}):
        try:
            schedule_rebuild(conn, day, settings, jobs)
        except Exception:
            _log.exception("could not schedule a rebuild of %s", day)


@router.post("/visits")
def upload_visits(
    visits: list[Visit],
    conn: sqlite3.Connection = Depends(get_conn),
    settings: Settings = Depends(get_settings),
    jobs=Depends(get_jobs),
) -> dict:
    conn.executemany(
        "INSERT INTO visits (id, arrived, departed, lat, lon, place_name) VALUES (?, ?, ?, ?, ?, ?)"
        " ON CONFLICT(id) DO UPDATE SET arrived = excluded.arrived, departed = excluded.departed,"
        " lat = excluded.lat, lon = excluded.lon,"
        " place_name = COALESCE(excluded.place_name, visits.place_name)",
        [(v.id, iso_utc(v.arrived), iso_utc(v.departed) if v.departed else None, v.lat, v.lon, v.place_name)
         for v in visits],
    )
    conn.commit()
    _rebuild_days(conn, settings, jobs, [t for v in visits for t in (v.arrived, v.departed) if t is not None])
    emit("app.visits", {"count": len(visits), "ids": [v.id for v in visits][:20]})
    return {"ok": True, "count": len(visits)}


@router.post("/photos")
def upload_photo(
    image: UploadFile = File(...),
    meta: str = Form(...),
    conn: sqlite3.Connection = Depends(get_conn),
    storage=Depends(get_storage),
    settings: Settings = Depends(get_settings),
    jobs=Depends(get_jobs),
) -> dict:
    try:
        m = PhotoMeta.model_validate_json(meta)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors(include_url=False, include_context=False))
    if conn.execute("SELECT 1 FROM photos WHERE id = ?", (m.id,)).fetchone():
        return {"ok": True, "id": m.id, "duplicate": True}
    data = image.file.read(settings.max_image_bytes + 1)
    if len(data) > settings.max_image_bytes:
        raise HTTPException(status_code=413, detail="image too large")
    key = f"photos/{m.id}.jpg"
    storage.put(key, data, "image/jpeg")
    conn.execute(
        "INSERT OR IGNORE INTO photos (id, taken_at, lat, lon, storage_key, sensitive, created_at)"
        " VALUES (?, ?, ?, ?, ?, 0, ?)",
        (m.id, iso_utc(m.taken_at), m.lat, m.lon, key, now_iso()),
    )
    conn.commit()
    _rebuild_days(conn, settings, jobs, [m.taken_at])
    emit("app.photo", {"id": m.id, "taken_at": iso_utc(m.taken_at)})
    return {"ok": True, "id": m.id, "duplicate": False}
