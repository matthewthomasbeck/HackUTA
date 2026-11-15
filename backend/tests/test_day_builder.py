import os
import sqlite3
from datetime import date, datetime, timezone

import pytest
from conftest import AUTH, post_segment

from calypso import db
from calypso.config import Settings
from calypso.day_builder import FakeSummarizer, is_home_day, rebuild_day

DAY = date(2026, 11, 14)


def utc(h, m=0, day=14):
    """Local (Chicago, UTC-6 in November) clock time on 2026-11-`day` as a UTC iso string."""
    return f"2026-11-{day:02d}T{h + 6:02d}:{m:02d}:00.000Z"


def seg(conn, uuid_, ts, synced=1):
    conn.execute(
        "INSERT INTO segments (segment_uuid, ts_start, ts_end, status, received_at, time_synced)"
        " VALUES (?, ?, ?, 'done', '2026-11-16T00:00:00.000Z', ?)", (uuid_, ts, ts, synced))


def utt(conn, ts, text="hello there", person=None, synced=1, source="puck"):
    uid = db.new_id()
    s = f"seg-{uid}"
    seg(conn, s, ts, synced)
    conn.execute(
        "INSERT INTO utterances (id, segment_uuid, ts_start, ts_end, text, source, person_id)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)", (uid, s, ts, ts, text, source, person))
    conn.commit()
    return uid


def visit(conn, a, d, name):
    conn.execute("INSERT INTO visits (id, arrived, departed, lat, lon, place_name) VALUES (?, ?, ?, 0, 0, ?)",
                 (db.new_id(), a, d, name))
    conn.commit()


def photo(conn, ts, sensitive=0):
    pid = db.new_id()
    conn.execute("INSERT INTO photos (id, taken_at, storage_key, sensitive, created_at) VALUES (?, ?, 'k', ?, ?)",
                 (pid, ts, sensitive, ts))
    conn.commit()
    return pid


def build(conn, day=DAY):
    return rebuild_day(conn, day, Settings.from_env(), FakeSummarizer())


def test_gap_splits_episodes(conn):
    for t in [utc(10), utc(10, 5), utc(10, 40)]:
        utt(conn, t)
    assert len(build(conn)) == 2


def test_visit_names_place(conn):
    visit(conn, utc(10), utc(11), "Blue Bean Café")
    utt(conn, utc(10, 10))
    (ev,) = build(conn)
    assert ev.place == "Blue Bean Café" and ev.place_confidence == 1.0


def test_no_visit_place_somewhere(conn):
    utt(conn, utc(10))
    (ev,) = build(conn)
    assert ev.place == "somewhere" and ev.place_confidence == 0.0


def test_patient_never_in_people(conn):
    pat = db.insert_person(conn, name="Pat", is_patient=True)["id"]
    sarah = db.insert_person(conn, name="Sarah")["id"]
    utt(conn, utc(10), person=pat)
    utt(conn, utc(10, 1), person=sarah)
    utt(conn, utc(14), person=pat)
    evs = build(conn)
    assert evs[0].people == [sarah]
    assert evs[1].people == []


def test_sensitive_photo_not_linked(conn):
    utt(conn, utc(10))
    utt(conn, utc(10, 10))
    ok = photo(conn, utc(10, 5))
    photo(conn, utc(10, 6), sensitive=1)
    (ev,) = build(conn)
    assert ev.photo_ids == [ok]


def test_unsynced_segments_excluded(conn):
    utt(conn, utc(10), synced=0)
    assert build(conn) == []


def test_late_upload_files_under_capture_day(conn):
    utt(conn, "2026-11-15T05:58:00.000Z")
    assert len(build(conn, date(2026, 11, 14))) == 1
    assert build(conn, date(2026, 11, 15)) == []


def test_call_utterances_excluded(conn):
    utt(conn, utc(10), source="call")
    assert build(conn) == []


def test_rebuild_twice_same_events(conn):
    utt(conn, utc(10))
    utt(conn, utc(12))
    a = build(conn)
    b = build(conn)
    assert [e.id for e in a] == [e.id for e in b] and len(b) == 2


def test_rebuild_route_real(client, conn):
    utt(conn, utc(10), "coffee")
    r = client.post("/days/2026-11-14/rebuild", headers=AUTH)
    assert r.json()["events"] > 0
    assert len(client.get("/days/2026-11-14/events", headers=AUTH).json()) == r.json()["events"]


def test_is_home_day(conn):
    s = Settings.from_env()
    visit(conn, utc(9), utc(10), "Blue Bean Café")
    assert not is_home_day(conn, DAY, s)
    visit(conn, utc(12), utc(13), "hOmE")
    assert is_home_day(conn, DAY, s)


def test_inline_ingest_triggers_rebuild(client):
    post_segment(client, local_text="hi there")
    evs = client.get("/days/2026-11-14/events", headers=AUTH).json()
    assert len(evs) == 1


@pytest.mark.live
def test_claude_summarizer_live():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("no ANTHROPIC_API_KEY")
    from calypso.day_builder import ClaudeSummarizer
    out = ClaudeSummarizer(Settings.from_env()).summarize(["I love the coffee here"], ["Sarah"], "Blue Bean Café")
    assert len(out.split()) <= 12
    for bad in ("Mike", "John", "Emma"):
        assert bad not in out
    # A name and a place heard in passing, but not in People or Place, must not be named.
    out = ClaudeSummarizer(Settings.from_env()).summarize(
        ["Bob says we should try Olive Garden on Friday", "that sounds lovely"], [], "somewhere")
    for bad in ("Bob", "Olive", "Garden"):
        assert bad not in out


# I4: a summary may only name the people and place that cleared the evidence gates.
class ScriptedSummarizer:
    def __init__(self, out):
        self.out = out

    def summarize(self, lines, people, place):
        return self.out


def test_summary_naming_unknown_person_is_neutral(conn):
    utt(conn, utc(10), "Bob is coming over later")
    (ev,) = rebuild_day(conn, DAY, Settings.from_env(), ScriptedSummarizer("Bob came by for coffee"))
    assert ev.summary == "Talked with someone"
    (ev,) = rebuild_day(conn, DAY, Settings.from_env(), ScriptedSummarizer("Coffee and a chat with Bob"))
    assert ev.summary == "Talked with someone"


def test_summary_naming_place_heard_in_passing_is_neutral(conn):
    utt(conn, utc(10), "let's go to Olive Garden on Friday")
    (ev,) = rebuild_day(conn, DAY, Settings.from_env(), ScriptedSummarizer("Lunch at Olive Garden"))
    assert ev.place == "somewhere" and ev.summary == "Talked with someone"


def test_summary_with_allowed_names_kept(conn):
    sarah = db.insert_person(conn, name="Sarah", relationship="daughter")["id"]
    visit(conn, utc(9), utc(11), "Blue Bean Café")
    utt(conn, utc(10), "I love the coffee here", person=sarah)
    out = "Coffee with Sarah at Blue Bean Café"
    (ev,) = rebuild_day(conn, DAY, Settings.from_env(), ScriptedSummarizer(out))
    assert ev.summary == out


# I5: an open visit (no departure yet) must not cover all later time.
def test_open_visit_does_not_name_later_utterance(conn):
    visit(conn, utc(8), None, "Blue Bean Café")
    utt(conn, utc(8, 30))
    utt(conn, "2026-11-15T03:30:00.000Z")  # 21:30 local, 13 h after arrival
    evs = build(conn)
    assert [e.place for e in evs] == ["Blue Bean Café", "somewhere"]


def test_open_visit_ends_at_next_visit(conn):
    visit(conn, utc(8), None, "Blue Bean Café")
    visit(conn, utc(10), utc(11), "Library")
    utt(conn, utc(12))
    (ev,) = build(conn)
    assert ev.place == "somewhere"


def test_open_home_visit_not_next_day(conn):
    s = Settings.from_env()
    visit(conn, utc(8), None, "Home")
    assert is_home_day(conn, DAY, s)
    assert not is_home_day(conn, date(2026, 11, 15), s)
    assert not is_home_day(conn, date(2026, 11, 20), s)
