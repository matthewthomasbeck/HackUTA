"""The day timeline. Days are the patient's local calendar day (`CALYPSO_TZ`)."""
import sqlite3
from datetime import date

from fastapi import APIRouter, Depends

from .. import db
from ..auth import require_token
from ..config import Settings
from ..day_builder import rebuild_day
from ..deps import get_conn, get_settings
from ..models import DayEvent, iso_utc
from ..timeutil import local_day_bounds, parse_iso

router = APIRouter(prefix="/days", dependencies=[Depends(require_token)])


def events_for_day(conn: sqlite3.Connection, day: date, tz: str) -> list[DayEvent]:
    start, end = local_day_bounds(day, tz)
    rows = conn.execute(
        "SELECT * FROM day_events WHERE start_ts >= ? AND start_ts < ? ORDER BY start_ts",
        (iso_utc(start), iso_utc(end)),
    ).fetchall()
    return [
        DayEvent(
            id=r["id"], start=parse_iso(r["start_ts"]), end=parse_iso(r["end_ts"]), place=r["place"],
            place_confidence=r["place_confidence"], people=db.loads(r["people"]), summary=r["summary"],
            evidence=db.loads(r["evidence"]), photo_ids=db.loads(r["photo_ids"]),
        )
        for r in rows
    ]


@router.get("/{day}/events", response_model=list[DayEvent])
def get_events(day: date, conn: sqlite3.Connection = Depends(get_conn),
               settings: Settings = Depends(get_settings)) -> list[DayEvent]:
    return events_for_day(conn, day, settings.tz)


@router.post("/{day}/rebuild")
def rebuild(day: date, conn: sqlite3.Connection = Depends(get_conn),
            settings: Settings = Depends(get_settings)) -> dict:
    n = len(rebuild_day(conn, day, settings))
    return {"ok": True, "day": day.isoformat(), "events": n}
