"""Server STT, time_synced, migration, and confident voice attribution."""
import hashlib
import os
import sqlite3

import numpy as np
import pytest

from calypso import db
from calypso.config import Settings
from calypso.identity.vectors import to_blob
from calypso.identity.voice import FakeVoiceEmbedder, embed_wav
from calypso.stt import FakeSTT, GrokSTT, SttPiece

from conftest import post_segment, tone_wav, wav_bytes


@pytest.fixture(autouse=True)
def _clean_script():
    FakeSTT.script.clear()
    yield
    FakeSTT.script.clear()


def _script(text):
    FakeSTT.script[hashlib.sha1(wav_bytes()).hexdigest()] = text


def test_stt_text_becomes_utterance_at_capture_time(client, conn):
    _script("we had coffee at the café")
    post_segment(client, "stt-1", ts_start="2026-11-14T15:30:00.000Z")
    rows = conn.execute("SELECT text, ts_start, source FROM utterances").fetchall()
    assert len(rows) == 1
    assert (rows[0]["text"], rows[0]["ts_start"], rows[0]["source"]) == (
        "we had coffee at the café", "2026-11-14T15:30:00.000Z", "puck")


def test_local_text_wins_over_stt(client, conn):
    _script("from the server")
    post_segment(client, "stt-2", local_text="from the puck")
    assert [r["text"] for r in conn.execute("SELECT text FROM utterances")] == ["from the puck"]


def test_empty_stt_no_utterance_segment_done(client, conn):
    post_segment(client, "stt-3")
    assert conn.execute("SELECT status FROM segments").fetchone()["status"] == "done"
    assert conn.execute("SELECT COUNT(*) FROM utterances").fetchone()[0] == 0


def test_time_synced_false_stored(client, conn):
    post_segment(client, "ts-0", time_synced=False)
    post_segment(client, "ts-1")
    rows = {r["segment_uuid"]: r["time_synced"] for r in conn.execute("SELECT * FROM segments")}
    assert rows == {"ts-0": 0, "ts-1": 1}


def test_migrate_adds_time_synced_column(tmp_path):
    path = str(tmp_path / "old.db")
    old = sqlite3.connect(path)
    old.execute("CREATE TABLE segments (segment_uuid TEXT PRIMARY KEY, ts_start TEXT NOT NULL, "
                "ts_end TEXT NOT NULL, local_text TEXT, status TEXT NOT NULL DEFAULT 'queued', "
                "error TEXT, received_at TEXT NOT NULL, processed_at TEXT)")
    old.commit()
    old.close()
    c = db.connect(path)
    cols = [r["name"] for r in c.execute("PRAGMA table_info(segments)")]
    assert "time_synced" in cols
    c.close()


def _person(conn, pid, freq=None, patient=False):
    conn.execute("INSERT INTO people (id, name, is_patient, created_at) VALUES (?, ?, ?, 'x')",
                 (pid, pid, int(patient)))
    if freq:
        vec, _ = embed_wav(FakeVoiceEmbedder(), tone_wav(freq), 1.0)
        conn.execute("INSERT INTO voice_prints (id, person_id, vec, source, created_at) VALUES (?, ?, ?, 'test', 'x')",
                     (db.new_id(), pid, to_blob(vec)))
    conn.commit()


def test_voice_attribution_confident_only(conn):
    from calypso.jobs import attribute_speaker

    s = Settings.from_env()
    assert attribute_speaker(conn, tone_wav(220), s) is None  # no prints
    _person(conn, "ann", 220)
    _person(conn, "bob", 440)
    assert attribute_speaker(conn, tone_wav(220), s) == "ann"
    assert attribute_speaker(conn, tone_wav(440), s) == "bob"
    assert attribute_speaker(conn, wav_bytes(), s) is None  # too little speech
    # two near-identical prints for different people: within the margin -> None
    _person(conn, "cat", 220)
    assert attribute_speaker(conn, tone_wav(220), s) is None


def test_get_stt_selection():
    from calypso.stt import get_stt
    import dataclasses
    s = Settings.from_env()
    assert isinstance(get_stt(dataclasses.replace(s, stt="fake", xai_api_key="k")), FakeSTT)
    assert isinstance(get_stt(dataclasses.replace(s, stt="grok", xai_api_key="k")), GrokSTT)
    assert isinstance(get_stt(dataclasses.replace(s, stt="", xai_api_key="")), FakeSTT)


@pytest.mark.live
def test_grok_stt_live():
    key = os.environ.get("XAI_API_KEY")
    if not key:
        pytest.skip("XAI_API_KEY not set")
    pieces = GrokSTT(key).transcribe(tone_wav(220, 1.0))
    assert isinstance(pieces, list) and all(isinstance(p, SttPiece) for p in pieces)
