"""Puck intake: idempotent uploads, sound tags, inline processing, audio deletion."""
import json
import uuid
from pathlib import Path

from calypso.config import Settings

from conftest import AUTH, post_segment


def test_segment_ack_shape(client):
    r = post_segment(client, "seg-1")
    assert r.status_code == 200
    assert r.json() == {"segment_uuid": "seg-1", "duplicate": False, "utterance_ids": []}


def test_duplicate_segment_uuid_ignored(client, conn):
    first = post_segment(client, "dup-1", local_text="let me grab a coffee")
    second = post_segment(client, "dup-1", local_text="let me grab a coffee")
    assert first.json()["duplicate"] is False and second.json()["duplicate"] is True
    assert conn.execute("SELECT COUNT(*) FROM segments").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM utterances").fetchone()[0] == 1


def test_sound_tags_stored(client, conn):
    tags = [{"ts": "2026-11-14T15:30:01Z", "label": "Espresso machine", "score": 0.81},
            {"ts": "2026-11-14T15:30:02Z", "label": "Chatter", "score": 0.4}]
    post_segment(client, "tags-1", sound_tags=tags)
    rows = conn.execute("SELECT label, score, ts FROM sound_tags ORDER BY ts").fetchall()
    assert [(r["label"], r["score"]) for r in rows] == [("Espresso machine", 0.81), ("Chatter", 0.4)]
    assert rows[0]["ts"] == "2026-11-14T15:30:01.000Z"


def test_segment_processed_inline_from_local_text(client, conn):
    r = post_segment(client, "txt-1", local_text="  let me grab a coffee ")
    assert len(r.json()["utterance_ids"]) == 1
    seg = conn.execute("SELECT status FROM segments WHERE segment_uuid='txt-1'").fetchone()
    utt = conn.execute("SELECT text, source, ts_start FROM utterances").fetchone()
    assert seg["status"] == "done"
    assert (utt["text"], utt["source"], utt["ts_start"]) == ("let me grab a coffee", "puck", "2026-11-14T15:30:00.000Z")


def test_temp_audio_deleted_after_processing(client):
    post_segment(client, "del-1")
    tmp = Settings.from_env().tmp_dir
    assert not (tmp / "del-1.wav").exists()


def test_events_emitted_for_dashboard(client):
    post_segment(client, "ev-1", local_text="hi")
    stages = [(e["stage"], e["payload"].get("segment_uuid")) for e in client.get("/events/recent").json()]
    assert ("puck.segment", "ev-1") in stages and ("puck.processed", "ev-1") in stages
    assert stages.index(("puck.segment", "ev-1")) < stages.index(("puck.processed", "ev-1"))


def test_naive_timestamp_upload_accepted(client, conn):
    r = post_segment(client, "naive-1", ts_start="2026-11-14T15:30:00", ts_end="2026-11-14T15:30:03")
    assert r.status_code == 200
    assert conn.execute("SELECT ts_start FROM segments").fetchone()[0] == "2026-11-14T15:30:00.000Z"


def test_bad_segment_uuid_rejected(client):
    assert post_segment(client, "../../etc/passwd").status_code == 422


def test_audio_too_large_rejected(client):
    import io
    from dataclasses import replace

    client.app.state.settings = replace(client.app.state.settings, max_audio_bytes=10)
    r = client.post("/puck/segments", headers=AUTH,
                    files={"audio": ("a.wav", io.BytesIO(b"x" * 100), "audio/wav")},
                    data={"meta": json.dumps({"segment_uuid": "big", "ts_start": "2026-11-14T15:30:00Z",
                                              "ts_end": "2026-11-14T15:30:01Z"})})
    assert r.status_code == 413


def test_enqueue_failure_rolls_back_so_retry_processes(client, conn):
    class Broken:
        def enqueue(self, *a):
            raise ConnectionError("redis down")

    good = client.app.state.jobs
    client.app.state.jobs = Broken()
    r1 = post_segment(client, "retry-1", local_text="hello")
    assert r1.status_code == 503
    assert conn.execute("SELECT COUNT(*) FROM segments").fetchone()[0] == 0
    assert not (Settings.from_env().tmp_dir / "retry-1.wav").exists()

    client.app.state.jobs = good
    r2 = post_segment(client, "retry-1", local_text="hello")
    assert r2.status_code == 200 and r2.json()["duplicate"] is False
    assert len(r2.json()["utterance_ids"]) == 1


def test_puck_health_rebroadcast(client):
    body = {"ts": "2026-11-14T15:30:00Z", "queue_depth": 3, "sound_backend": "cpu",
            "ms_per_segment": 41.5, "time_synced": True, "battery_pct": 87}
    assert client.post("/puck/health", headers=AUTH, json=body).status_code == 200
    ev = [e for e in client.get("/events/recent").json() if e["stage"] == "puck.health"][-1]
    assert ev["payload"]["queue_depth"] == 3 and ev["payload"]["ts"] == "2026-11-14T15:30:00.000Z"


def test_rq_enqueue_uses_queue_and_dotted_path():
    from calypso.jobs import RQJobs, process_segment

    calls = []

    class FakeQueue:
        def __init__(self, name):
            self.name = name

        def enqueue(self, path, *args, **kw):
            calls.append((self.name, path, args, kw["retry"].max))

    jobs = RQJobs("redis://unused", "recordings", queue_factory=FakeQueue)
    jobs.enqueue(process_segment, "u1", "/tmp/u1.wav")
    assert calls == [("recordings", "calypso.jobs.process_segment", ("u1", "/tmp/u1.wav"), 3)]
