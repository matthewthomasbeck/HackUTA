"""Passive recall end to end: puck segment -> STT -> voice attribution -> day event -> recall card."""
import hashlib
import io
import json
from datetime import date

import pytest

from calypso import db
from calypso.config import Settings
from calypso.identity.vectors import to_blob
from calypso.identity.voice import FakeVoiceEmbedder, embed_wav
from calypso.models import CallLine, Intent
from calypso.recall import Detection, FakeDetector, recall
from calypso.stt import FakeSTT

from conftest import AUTH, tone_wav

SARAH_HZ = 220


@pytest.fixture(autouse=True)
def _fakes(monkeypatch):
    monkeypatch.setenv("CALYPSO_STT", "fake")
    monkeypatch.setenv("CALYPSO_SUMMARIZER", "fake")
    monkeypatch.setenv("CALYPSO_DETECTOR", "fake")
    FakeSTT.script.clear()
    FakeDetector.script = {}
    yield
    FakeSTT.script.clear()
    FakeDetector.script = {}


def test_passive_recall_end_to_end(client, conn):
    mary = db.insert_person(conn, name="Mary", is_patient=True)["id"]
    sarah = db.insert_person(conn, name="Sarah")["id"]
    vec, _ = embed_wav(FakeVoiceEmbedder(), tone_wav(SARAH_HZ), 1.0)
    conn.execute("INSERT INTO voice_prints (id, person_id, vec, source, created_at) VALUES (?, ?, ?, 'test', 'x')",
                 (db.new_id(), sarah, to_blob(vec)))
    # Blue Bean Café visit 10:00-11:00 Chicago (UTC-6) on 2026-11-14
    conn.execute("INSERT INTO visits (id, arrived, departed, lat, lon, place_name) VALUES (?, ?, ?, 0, 0, ?)",
                 (db.new_id(), "2026-11-14T16:00:00.000Z", "2026-11-14T17:00:00.000Z", "Blue Bean Café"))
    conn.commit()

    wav = tone_wav(SARAH_HZ)
    FakeSTT.script[hashlib.sha1(wav).hexdigest()] = "Sarah and I had coffee"
    FakeDetector.script["Mom, what did you do today?"] = Detection(Intent(intent="today"), 0.9)

    meta = {"segment_uuid": "e2e-1", "ts_start": "2026-11-14T16:15:00.000Z",
            "ts_end": "2026-11-14T16:15:03.000Z", "sound_tags": [], "local_text": None}
    for _ in range(2):  # the second post is a retry with the same uuid
        r = client.post("/puck/segments", headers=AUTH,
                        files={"audio": ("seg.wav", io.BytesIO(wav), "audio/wav")},
                        data={"meta": json.dumps(meta)})
        assert r.status_code == 200

    assert conn.execute("SELECT COUNT(*) FROM utterances").fetchone()[0] == 1
    evs = client.get("/days/2026-11-14/events", headers=AUTH).json()
    assert len(evs) == 1
    assert evs[0]["place"] == "Blue Bean Café"
    assert evs[0]["people"] == [sarah]
    assert mary not in evs[0]["people"]

    res = recall([CallLine(speaker="Sarah", text="Mom, what did you do today?")], conn,
                 Settings.from_env(), FakeDetector(), today=date(2026, 11, 14))
    assert res.card is not None and res.card.kind == "today"
    assert any("Blue Bean Café" in line for line in res.card.lines)
