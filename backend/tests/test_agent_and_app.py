"""Agent-facing stubs (recognize, recall, calls), days, and iOS uploads."""
import base64
import io
from datetime import date

from calypso import db

from conftest import AUTH, JPEG


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


# --- recognize / recall stubs -------------------------------------------------

def test_recognize_unknown_face_is_learning(client):
    r = client.post("/recognize", headers=AUTH, json={"face_jpeg_b64": b64(JPEG), "participant_key": "p1"})
    assert r.status_code == 200
    assert r.json() == {"faces": [{"bbox": {"x": 0, "y": 0, "w": 100, "h": 100},
                                   "result": {"status": "learning", "person_id": None,
                                              "face_score": None, "voice_score": None}}],
                        "voice_only": None}


def test_recognize_stub_voice_only(client):
    r = client.post("/recognize", headers=AUTH, json={"voice_wav_b64": b64(b"RIFF")}).json()
    assert r["faces"] == [] and r["voice_only"]["status"] == "learning"


def test_recognize_emits_for_dashboard(client):
    client.post("/recognize", headers=AUTH, json={"face_jpeg_b64": b64(JPEG), "participant_key": "sarah-phone"})
    ev = [e for e in client.get("/events/recent").json() if e["stage"] == "recognize"][-1]
    assert ev["payload"]["participant_key"] == "sarah-phone"


def test_recognize_requires_token(client):
    assert client.post("/recognize", json={}).status_code == 401


def test_recall_stub_shape(client):
    r = client.post("/recall", headers=AUTH, json={"lines": [{"speaker": "Sarah", "text": "Mom, what did you do today?"}]})
    assert r.status_code == 200
    assert r.json() == {"intent": {"intent": "none", "query": None, "date_hint": None, "place_hint": None},
                        "card": None}


# --- calls --------------------------------------------------------------------

def test_call_lifecycle_logs_utterances(client, conn):
    call = client.post("/calls", headers=AUTH, json={"kind": "group", "participants": ["mary", "sarah"]}).json()
    assert call["kind"] == "group" and call["ended"] is None and call["started"].endswith("Z")
    line = client.post(f"/calls/{call['id']}/lines", headers=AUTH,
                       json={"speaker": "sarah", "text": "Hi Mom!", "ts": "2026-11-14T20:00:00.000Z"})
    assert line.status_code == 201
    ended = client.post(f"/calls/{call['id']}/end", headers=AUTH).json()
    assert ended["ended"] is not None
    utt = conn.execute("SELECT text, source, call_id, ts_start FROM utterances").fetchone()
    assert (utt["text"], utt["source"], utt["call_id"], utt["ts_start"]) == (
        "Hi Mom!", "call", call["id"], "2026-11-14T20:00:00.000Z")


def test_call_unknown_404(client):
    assert client.post("/calls/nope/lines", headers=AUTH, json={"speaker": "x", "text": "y"}).status_code == 404


# --- days ---------------------------------------------------------------------

def _event(conn, eid, start, end, people=()):
    conn.execute(
        "INSERT INTO day_events (id, start_ts, end_ts, place, place_confidence, people, summary)"
        " VALUES (?, ?, ?, 'Home', 0.95, ?, 'Dinner')", (eid, start, end, db.dumps(people)))
    conn.commit()


def test_day_events_use_local_day(client, conn):
    # 19:00 CST on Nov 14 is 01:00Z on Nov 15: it belongs to Nov 14 for the patient.
    _event(conn, "evening", "2026-11-15T01:00:00.000Z", "2026-11-15T02:00:00.000Z")
    _event(conn, "next_morning", "2026-11-15T15:00:00.000Z", "2026-11-15T16:00:00.000Z")
    nov14 = client.get("/days/2026-11-14/events", headers=AUTH).json()
    nov15 = client.get("/days/2026-11-15/events", headers=AUTH).json()
    assert [e["id"] for e in nov14] == ["evening"]
    assert [e["id"] for e in nov15] == ["next_morning"]
    assert nov14[0]["start"] == "2026-11-15T01:00:00.000Z"


def test_day_events_json_matches_ios_shape(client, conn):
    _event(conn, "e1", "2026-11-14T15:00:00.000Z", "2026-11-14T16:00:00.000Z", people=["p_sarah"])
    e = client.get("/days/2026-11-14/events", headers=AUTH).json()[0]
    assert set(e) == {"id", "start", "end", "place", "place_confidence", "people", "summary", "evidence", "photo_ids"}
    assert e["people"] == ["p_sarah"]


def test_empty_day_is_empty_list(client):
    assert client.get("/days/2026-01-01/events", headers=AUTH).json() == []


def test_rebuild_stub(client):
    r = client.post(f"/days/{date(2026, 11, 14).isoformat()}/rebuild", headers=AUTH)
    assert r.status_code == 200 and r.json()["ok"] is True


# --- iOS uploads --------------------------------------------------------------

def test_visits_accept_fractional_z_and_null_departed(client, conn):
    visits = [{"id": "v1", "arrived": "2026-11-14T15:10:00.123Z", "departed": None, "lat": 32.73, "lon": -97.11}]
    assert client.post("/app/visits", headers=AUTH, json=visits).status_code == 200
    row = conn.execute("SELECT arrived, departed FROM visits WHERE id='v1'").fetchone()
    assert (row["arrived"], row["departed"]) == ("2026-11-14T15:10:00.123Z", None)


def test_visit_upsert_idempotent(client, conn):
    v = {"id": "v1", "arrived": "2026-11-14T15:10:00.000Z", "departed": None, "lat": 32.73, "lon": -97.11,
         "place_name": "Blue Bean Café"}
    client.post("/app/visits", headers=AUTH, json=[v])
    client.post("/app/visits", headers=AUTH, json=[{**v, "departed": "2026-11-14T15:40:00.000Z", "place_name": None}])
    rows = conn.execute("SELECT departed, place_name FROM visits").fetchall()
    assert len(rows) == 1
    assert (rows[0]["departed"], rows[0]["place_name"]) == ("2026-11-14T15:40:00.000Z", "Blue Bean Café")


def test_photo_multipart_meta_and_image(client, conn):
    meta = '{"id": "ABC-123-L0-001", "taken_at": "2026-11-14T15:30:00.123Z", "lat": 32.7, "lon": -97.1}'
    r = client.post("/app/photos", headers=AUTH, data={"meta": meta},
                    files={"image": ("p.jpg", io.BytesIO(JPEG), "image/jpeg")})
    assert r.status_code == 200 and r.json()["duplicate"] is False
    again = client.post("/app/photos", headers=AUTH, data={"meta": meta},
                        files={"image": ("p.jpg", io.BytesIO(JPEG), "image/jpeg")})
    assert again.json()["duplicate"] is True
    assert conn.execute("SELECT COUNT(*) FROM photos").fetchone()[0] == 1
    assert client.get("/media/photos/ABC-123-L0-001.jpg").content == JPEG
