"""SQLite storage. One file, WAL mode so the API and the RQ worker can share it.

Datetimes are stored as fixed-width UTC text (`iso_utc`), so text comparison
orders them correctly. Lists are stored as JSON text. Vectors are float32 BLOBs.
"""
import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Iterable

from .timeutil import now_iso

SCHEMA = """
CREATE TABLE IF NOT EXISTS people (
  id TEXT PRIMARY KEY,
  name TEXT,
  relationship TEXT,
  is_patient INTEGER NOT NULL DEFAULT 0,
  phone TEXT,
  face_photo_key TEXT,
  facts TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS face_embeddings (
  id TEXT PRIMARY KEY,
  person_id TEXT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
  vec BLOB NOT NULL,
  source TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_face_person ON face_embeddings(person_id);
CREATE TABLE IF NOT EXISTS voice_prints (
  id TEXT PRIMARY KEY,
  person_id TEXT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
  vec BLOB NOT NULL,
  source TEXT NOT NULL,
  speech_s REAL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_voice_person ON voice_prints(person_id);
CREATE TABLE IF NOT EXISTS voice_clusters (
  id TEXT PRIMARY KEY,
  centroid BLOB NOT NULL,
  n_samples INTEGER NOT NULL DEFAULT 1,
  person_id TEXT REFERENCES people(id) ON DELETE SET NULL,
  candidate_name TEXT,
  is_patient_candidate INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS segments (
  segment_uuid TEXT PRIMARY KEY,
  ts_start TEXT NOT NULL,
  ts_end TEXT NOT NULL,
  local_text TEXT,
  status TEXT NOT NULL DEFAULT 'queued',
  error TEXT,
  received_at TEXT NOT NULL,
  processed_at TEXT,
  time_synced INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS utterances (
  id TEXT PRIMARY KEY,
  segment_uuid TEXT,
  call_id TEXT,
  ts_start TEXT NOT NULL,
  ts_end TEXT NOT NULL,
  text TEXT NOT NULL,
  source TEXT NOT NULL CHECK (source IN ('puck', 'call')),
  speaker_idx INTEGER,
  voice_cluster_id TEXT,
  person_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_utt_ts ON utterances(ts_start);
CREATE INDEX IF NOT EXISTS idx_utt_person ON utterances(person_id);
CREATE TABLE IF NOT EXISTS sound_tags (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  segment_uuid TEXT NOT NULL,
  ts TEXT NOT NULL,
  label TEXT NOT NULL,
  score REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tags_ts ON sound_tags(ts);
CREATE TABLE IF NOT EXISTS calls (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  started TEXT NOT NULL,
  ended TEXT,
  participants TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS visits (
  id TEXT PRIMARY KEY,
  arrived TEXT NOT NULL,
  departed TEXT,
  lat REAL NOT NULL,
  lon REAL NOT NULL,
  place_name TEXT
);
CREATE TABLE IF NOT EXISTS photos (
  id TEXT PRIMARY KEY,
  taken_at TEXT NOT NULL,
  lat REAL,
  lon REAL,
  storage_key TEXT NOT NULL,
  sensitive INTEGER NOT NULL DEFAULT 0,
  caption TEXT,
  event_id TEXT,
  clip_vec BLOB,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS day_events (
  id TEXT PRIMARY KEY,
  start_ts TEXT NOT NULL,
  end_ts TEXT NOT NULL,
  place TEXT NOT NULL,
  place_confidence REAL NOT NULL,
  people TEXT NOT NULL DEFAULT '[]',
  summary TEXT NOT NULL,
  evidence TEXT NOT NULL DEFAULT '[]',
  photo_ids TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_events_start ON day_events(start_ts);
"""


def new_id() -> str:
    return uuid.uuid4().hex


def connect(path: str, init: bool = True) -> sqlite3.Connection:
    """Open the database (creating the folder and schema if needed)."""
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    if init:
        conn.executescript(SCHEMA)
        _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Add columns that deployed databases predate."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(segments)")}
    if "time_synced" not in cols:
        conn.execute("ALTER TABLE segments ADD COLUMN time_synced INTEGER NOT NULL DEFAULT 1")
        conn.commit()


def dumps(value: Iterable[Any]) -> str:
    return json.dumps(list(value))


def loads(text: str | None) -> list:
    return json.loads(text) if text else []


# --- people -------------------------------------------------------------------

PERSON_FIELDS = ("name", "relationship", "is_patient", "phone", "face_photo_key", "facts")


def insert_person(conn: sqlite3.Connection, *, name=None, relationship=None, is_patient=False,
                  phone=None, face_photo_key=None, facts=(), person_id=None) -> sqlite3.Row:
    pid = person_id or new_id()
    conn.execute(
        "INSERT INTO people (id, name, relationship, is_patient, phone, face_photo_key, facts, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (pid, name, relationship, int(is_patient), phone, face_photo_key, dumps(facts), now_iso()),
    )
    conn.commit()
    return get_person(conn, pid)


def get_person(conn: sqlite3.Connection, person_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM people WHERE id = ?", (person_id,)).fetchone()


def list_people(conn: sqlite3.Connection, is_patient: bool | None = None) -> list[sqlite3.Row]:
    if is_patient is None:
        return conn.execute("SELECT * FROM people ORDER BY created_at").fetchall()
    return conn.execute(
        "SELECT * FROM people WHERE is_patient = ? ORDER BY created_at", (int(is_patient),)
    ).fetchall()


def update_person(conn: sqlite3.Connection, person_id: str, fields: dict[str, Any]) -> sqlite3.Row | None:
    sets, args = [], []
    for key, value in fields.items():
        if key not in PERSON_FIELDS:
            raise ValueError(f"unknown person field {key!r}")
        if key == "facts":
            value = dumps(value or [])
        elif key == "is_patient":
            value = int(bool(value))
        sets.append(f"{key} = ?")
        args.append(value)
    if sets:
        conn.execute(f"UPDATE people SET {', '.join(sets)} WHERE id = ?", (*args, person_id))
        conn.commit()
    return get_person(conn, person_id)
