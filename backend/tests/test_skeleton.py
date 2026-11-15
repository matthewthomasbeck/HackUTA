"""Task 1: health, auth, bus/stream, DB round trip, time rules."""
import asyncio
import json
import threading
from datetime import date, datetime, timezone

from calypso import db
from calypso.bus import Bus, sse_events
from calypso.models import Person, SegmentMeta, iso_utc
from calypso.timeutil import local_day_bounds

from conftest import AUTH, TOKEN


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json() == {"ok": True}


def test_requires_token(client):
    assert client.get("/people").status_code == 401
    assert client.get("/people", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/people", headers={"Authorization": f"Bearer {TOKEN}"}).status_code == 200


def test_empty_server_token_rejects_everyone(monkeypatch, env):
    monkeypatch.setenv("CALYPSO_API_TOKEN", "")
    from fastapi.testclient import TestClient

    from calypso.app import create_app

    with TestClient(create_app()) as c:
        assert c.get("/people", headers={"Authorization": "Bearer "}).status_code == 401


def test_bus_stream_receives_emit():
    async def run():
        b = Bus()
        gen = sse_events(b, limit=1)
        assert (await gen.__anext__()).startswith(": connected")  # subscribed now
        b.emit("test", {"a": 1})
        chunk = await asyncio.wait_for(gen.__anext__(), timeout=2)
        await gen.aclose()
        return json.loads(chunk.removeprefix("data: ").strip())

    event = asyncio.run(run())
    assert event["stage"] == "test" and event["payload"] == {"a": 1} and event["ts"].endswith("Z")


def test_emit_from_another_thread_reaches_subscriber():
    async def run():
        b = Bus()
        async with b.subscribe() as q:
            t = threading.Thread(target=b.emit, args=("from.thread", {"x": 2}))
            t.start()
            t.join()
            return await asyncio.wait_for(q.get(), timeout=2)

    assert asyncio.run(run())["stage"] == "from.thread"


def test_stream_endpoint_is_sse(client):
    from calypso.bus import bus

    stop = threading.Event()

    def emitter():
        while not stop.is_set():
            bus.emit("tick", {})
            stop.wait(0.05)

    t = threading.Thread(target=emitter, daemon=True)
    t.start()
    try:
        r = client.get("/stream?limit=1")
    finally:
        stop.set()
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    data = [line for line in r.text.splitlines() if line.startswith("data: ")]
    assert json.loads(data[0][6:])["stage"] == "tick"


def test_events_rebroadcast_and_recent(client):
    assert client.post("/events", json={"stage": "worker.test", "payload": {"n": 1}}).status_code == 401
    assert client.post("/events", headers=AUTH, json={"stage": "worker.test", "payload": {"n": 1}}).status_code == 200
    recent = client.get("/events/recent").json()
    assert any(e["stage"] == "worker.test" and e["payload"] == {"n": 1} for e in recent)


def test_recent_events_keeps_call_history_under_puck_load(client):
    from calypso.bus import bus

    bus.emit("call.started", {"call_id": "c-keep"})
    for i in range(600):  # a busy puck: 3 s segments for 30 min
        bus.emit("puck.segment", {"segment_uuid": f"s{i}"})
    recent = client.get("/events/recent?limit=1000").json()
    assert any(e["stage"] == "call.started" and e["payload"].get("call_id") == "c-keep" for e in recent)
    assert client.get("/events/recent?limit=1001").status_code == 422


def test_agent_event_rebroadcast(client):
    r = client.post("/agent/events", headers=AUTH, json={"stage": "card.shown", "payload": {"kind": "identity"}})
    assert r.status_code == 200
    assert any(e["stage"] == "card.shown" for e in client.get("/events/recent").json())


def test_db_roundtrip_person(tmp_path):
    conn = db.connect(str(tmp_path / "t.db"))
    row = db.insert_person(conn, name="Sarah", relationship="daughter", facts=["Lives in Austin"])
    back = db.get_person(conn, row["id"])
    assert (back["name"], back["relationship"], db.loads(back["facts"]), back["is_patient"]) == (
        "Sarah", "daughter", ["Lives in Austin"], 0)


def test_naive_timestamp_treated_as_utc():
    m = SegmentMeta(segment_uuid="abc", ts_start="2026-11-14T15:30:00", ts_end="2026-11-14T15:30:04")
    assert m.ts_start == datetime(2026, 11, 14, 15, 30, tzinfo=timezone.utc)


def test_fractional_z_and_offsets_normalize_to_utc_json():
    m = SegmentMeta(segment_uuid="abc", ts_start="2026-11-14T09:30:00.123-06:00", ts_end="2026-11-14T15:30:04.5Z")
    j = json.loads(m.model_dump_json())
    assert j["ts_start"] == "2026-11-14T15:30:00.123Z"
    assert j["ts_end"] == "2026-11-14T15:30:04.500Z"


def test_iso_utc_is_fixed_width_and_sortable():
    a = iso_utc(datetime(2026, 11, 14, 15, 30, 0, tzinfo=timezone.utc))
    b = iso_utc(datetime(2026, 11, 14, 15, 30, 0, 123000, tzinfo=timezone.utc))
    assert len(a) == len(b) and a < b


def test_local_day_bounds_central_time():
    start, end = local_day_bounds(date(2026, 11, 14), "America/Chicago")
    assert iso_utc(start) == "2026-11-14T06:00:00.000Z"  # CST is UTC-6
    assert iso_utc(end) == "2026-11-15T06:00:00.000Z"


def test_person_model_backward_compatible():
    p = Person(id="p1")
    assert p.phone is None and p.facts == [] and p.face_photo_url is None
