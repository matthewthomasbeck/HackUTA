import os
from datetime import date

import pytest

from calypso import db
from calypso.config import Settings
from calypso.models import CallLine, Intent
from calypso.recall import ClaudeDetector, Detection, FakeDetector, recall
from tests.conftest import AUTH

DAY = date(2026, 11, 15)


@pytest.fixture(autouse=True)
def _reset():
    FakeDetector.script = {}
    yield
    FakeDetector.script = {}


def L(text):
    return [CallLine(speaker="Sarah", text=text)]


def script(text, intent="today", conf=0.9, **kw):
    FakeDetector.script[text] = Detection(Intent(intent=intent, **kw), conf)


def event(conn, id, start, place="Blue Bean Café", summary="Coffee with Sarah", people=(), photos=()):
    conn.execute(
        "INSERT INTO day_events (id, start_ts, end_ts, place, place_confidence, people, summary, evidence, photo_ids)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        (id, start, start, place, 1.0, db.dumps(list(people)), summary, "[]", db.dumps(list(photos))))
    conn.commit()


def photo(conn, id, sensitive=0):
    conn.execute("INSERT INTO photos (id, taken_at, storage_key, sensitive, created_at) VALUES (?,?,?,?,?)",
                 (id, "2026-11-15T16:00:00.000Z", f"photos/{id}.jpg", sensitive, "2026-11-15T16:00:00.000Z"))
    conn.commit()


def run(conn, text):
    return recall(L(text), conn, Settings.from_env(), FakeDetector(), today=DAY)


def test_today_with_events_card(conn):
    event(conn, "e1", "2026-11-15T16:30:00.000Z")
    event(conn, "e2", "2026-11-15T19:00:00.000Z", place="Home", summary="Lunch")
    script("what did you do today?")
    r = run(conn, "what did you do today?")
    assert r.card.kind == "today"
    assert r.card.lines[0] == "10:30 AM · Blue Bean Café · Coffee with Sarah"
    assert len(r.card.lines) == 2


def test_weather_today_no_card(conn):
    r = run(conn, "the weather today is awful")
    assert r.intent.intent == "none" and r.card is None


def test_low_confidence_is_none(conn):
    script("x", conf=0.2)
    r = run(conn, "x")
    assert r.intent.intent == "none" and r.card is None


def test_empty_day_home(conn):
    conn.execute("INSERT INTO visits (id, arrived, departed, lat, lon, place_name) VALUES (?,?,?,?,?,?)",
                 ("v1", "2026-11-15T14:00:00.000Z", None, 0, 0, "Home"))
    conn.commit()
    script("t")
    assert run(conn, "t").card.lines == ["A quiet day at home"]


def test_empty_day_unknown(conn):
    script("t")
    assert run(conn, "t").card.lines == ["Nothing saved yet today"]


def test_person_recall_unique_match(conn):
    pid = db.insert_person(conn, name="Sarah")["id"]
    db.insert_person(conn, name="Mary", is_patient=True)
    event(conn, "e1", "2026-11-14T16:30:00.000Z", people=[pid])
    script("with Sarah", intent="person", query="Sarah")
    r = run(conn, "with Sarah")
    assert r.card.kind == "memory" and r.card.title == "Sarah" and r.card.lines


def test_person_recall_ambiguous_none(conn):
    for _ in range(2):
        pid = db.insert_person(conn, name="Sam")["id"]
        event(conn, f"e{pid}", "2026-11-14T16:30:00.000Z", people=[pid])
    script("Sam?", intent="person", query="Sam")
    assert run(conn, "Sam?").card is None


def test_person_recall_patient_none(conn):
    pid = db.insert_person(conn, name="Mary", is_patient=True)["id"]
    event(conn, "e1", "2026-11-14T16:30:00.000Z", people=[pid])
    script("Mary?", intent="person", query="Mary")
    assert run(conn, "Mary?").card is None


def test_recall_photo_excludes_sensitive(conn):
    photo(conn, "ok1")
    photo(conn, "bad1", sensitive=1)
    event(conn, "e1", "2026-11-15T16:30:00.000Z", photos=["ok1", "bad1"])
    script("pics", intent="photo")
    r = run(conn, "pics")
    assert r.card.image_urls == ["https://calypso.example.com/media/photos/ok1.jpg"]


def test_detector_exception_is_none(conn):
    class Boom:
        def detect(self, lines):
            raise TimeoutError

    r = recall(L("hi"), conn, Settings.from_env(), Boom(), today=DAY)
    assert r.intent.intent == "none" and r.card is None


def test_route_uses_injected_detector(client):
    script("what did you do today?")
    client.app.state.recall_detector = FakeDetector()
    r = client.post("/recall", headers=AUTH, json={"lines": [{"speaker": "S", "text": "what did you do today?"}]})
    assert r.status_code == 200
    assert r.json()["intent"]["intent"] == "today" and r.json()["card"]["kind"] == "today"


@pytest.mark.live
@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="no ANTHROPIC_API_KEY")
def test_haiku_detector_live():
    d = ClaudeDetector()
    for text, want in [("Mom, what did you do today?", "today"), ("the weather today is awful", "none"),
                       ("how was your morning?", "today")]:
        assert d.detect(L(text)).intent.intent == want
