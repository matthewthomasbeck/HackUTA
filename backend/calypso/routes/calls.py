"""Calls: the agent logs each FaceTime call and its transcript lines (as utterances)."""
import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from .. import db
from ..auth import require_token
from ..bus import emit
from ..deps import get_conn
from ..models import Call, CallCreate, CallLineIn, iso_utc
from ..timeutil import now_iso, now_utc, parse_iso

router = APIRouter(prefix="/calls", dependencies=[Depends(require_token)])


def _call_out(row: sqlite3.Row) -> Call:
    return Call(
        id=row["id"], kind=row["kind"], started=parse_iso(row["started"]),
        ended=parse_iso(row["ended"]) if row["ended"] else None, participants=db.loads(row["participants"]),
    )


def _require_call(conn: sqlite3.Connection, call_id: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM calls WHERE id = ?", (call_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="call not found")
    return row


@router.post("", response_model=Call, status_code=201)
def start_call(body: CallCreate, conn: sqlite3.Connection = Depends(get_conn)) -> Call:
    cid = db.new_id()
    conn.execute(
        "INSERT INTO calls (id, kind, started, participants) VALUES (?, ?, ?, ?)",
        (cid, body.kind, now_iso(), db.dumps(body.participants)),
    )
    conn.commit()
    emit("call.started", {"call_id": cid, "kind": body.kind})
    return _call_out(_require_call(conn, cid))


@router.post("/{call_id}/end", response_model=Call)
def end_call(call_id: str, conn: sqlite3.Connection = Depends(get_conn)) -> Call:
    _require_call(conn, call_id)
    conn.execute("UPDATE calls SET ended = COALESCE(ended, ?) WHERE id = ?", (now_iso(), call_id))
    conn.commit()
    emit("call.ended", {"call_id": call_id})
    return _call_out(_require_call(conn, call_id))


@router.post("/{call_id}/lines", status_code=201)
def add_line(call_id: str, line: CallLineIn, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    _require_call(conn, call_id)
    ts = iso_utc(line.ts or now_utc())
    uid = db.new_id()
    conn.execute(
        "INSERT INTO utterances (id, call_id, ts_start, ts_end, text, source, person_id)"
        " VALUES (?, ?, ?, ?, ?, 'call', ?)",
        (uid, call_id, ts, ts, line.text, line.person_id),
    )
    conn.commit()
    emit("call.line", {"call_id": call_id, "speaker": line.speaker, "text": line.text[:200]})
    return {"id": uid}
