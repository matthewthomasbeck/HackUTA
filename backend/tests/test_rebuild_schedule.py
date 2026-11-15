"""C1: the day rebuild is rate-limited from the first new speech, in both job modes."""
from datetime import date, timedelta

from conftest import AUTH, post_segment

from calypso import day_builder, jobs
from calypso.config import Settings
from calypso.day_builder import mark_day_dirty, rebuild_dirty_days
from calypso.timeutil import iso_utc

DAY = date(2026, 11, 14)


class FakeQueue:
    def __init__(self):
        self.delayed = []

    def enqueue(self, func, *args):
        func(*args)

    def enqueue_in(self, delay_s, func, *args):
        self.delayed.append((delay_s, func, args))


def dirty(conn):
    return {r["day"]: r["marked_at"] for r in conn.execute("SELECT day, marked_at FROM dirty_days")}


def events(client):
    return client.get("/days/2026-11-14/events", headers=AUTH).json()


def test_silent_segment_does_not_mark_day(client, conn, monkeypatch):
    monkeypatch.setenv("CALYPSO_REBUILD_DELAY_S", "60")
    q = FakeQueue()
    monkeypatch.setattr(jobs, "get_jobs", lambda settings: q)
    assert post_segment(client).status_code == 200  # FakeSTT: no text, so no utterances
    assert dirty(conn) == {} and q.delayed == []


def test_repeated_marks_keep_first_marked_at(conn, monkeypatch):
    t0 = day_builder.now_utc()
    monkeypatch.setattr(day_builder, "now_utc", lambda: t0)
    assert mark_day_dirty(conn, DAY) is True
    first = dirty(conn)["2026-11-14"]
    monkeypatch.setattr(day_builder, "now_utc", lambda: t0 + timedelta(seconds=3))
    assert mark_day_dirty(conn, DAY) is False
    monkeypatch.setattr(day_builder, "now_utc", lambda: t0 + timedelta(seconds=6))
    assert mark_day_dirty(conn, DAY) is False
    assert dirty(conn)["2026-11-14"] == first


def test_one_delayed_job_per_dirty_period(client, conn, monkeypatch):
    monkeypatch.setenv("CALYPSO_REBUILD_DELAY_S", "60")
    q = FakeQueue()
    monkeypatch.setattr(jobs, "get_jobs", lambda settings: q)
    t0 = day_builder.now_utc()
    for i in range(5):  # the puck uploads every 3 s while someone is talking
        monkeypatch.setattr(day_builder, "now_utc", lambda i=i: t0 + timedelta(seconds=3 * i))
        assert post_segment(client, local_text=f"hello {i}").status_code == 200
    assert len(q.delayed) == 1
    delay, func, args = q.delayed[0]
    assert delay == 60 and func is rebuild_dirty_days
    assert events(client) == []  # not built yet

    # The one delayed job runs once, 60 s after the first mark, and builds the day despite later marks.
    monkeypatch.setattr(day_builder, "now_utc", lambda: t0 + timedelta(seconds=60))
    assert rebuild_dirty_days(*args) == 1
    assert len(events(client)) == 1 and dirty(conn) == {}
    assert len(q.delayed) == 1  # nothing left over, so no follow-up job

    # New speech after the build starts a new dirty period with exactly one new job.
    monkeypatch.setattr(day_builder, "now_utc", lambda: t0 + timedelta(seconds=63))
    post_segment(client, local_text="more talk")
    post_segment(client, local_text="even more talk")
    assert len(q.delayed) == 2


def test_failed_rebuild_remarks_day(conn, monkeypatch):
    s = Settings.from_env()
    q = FakeQueue()
    monkeypatch.setattr(jobs, "get_jobs", lambda settings: q)
    mark_day_dirty(conn, DAY)

    def boom(*a, **k):
        raise RuntimeError("summarizer down")

    monkeypatch.setattr(day_builder, "rebuild_day", boom)
    try:
        rebuild_dirty_days(s)
    except RuntimeError:
        pass
    assert "2026-11-14" in dirty(conn) and len(q.delayed) == 1


def test_inline_zero_delay_rebuilds_synchronously(client, conn):
    # conftest sets CALYPSO_REBUILD_DELAY_S=0 with inline jobs
    assert post_segment(client, local_text="hi there").status_code == 200
    assert len(events(client)) == 1 and dirty(conn) == {}


def test_inline_delay_uses_timer(monkeypatch):
    started = []

    class FakeTimer:
        def __init__(self, delay, fn, args=()):
            self.delay, self.fn, self.args = delay, fn, args
            self.daemon = False

        def start(self):
            started.append(self)

    monkeypatch.setattr(jobs.threading, "Timer", FakeTimer)
    ran = []
    jobs.InlineJobs().enqueue_in(60, lambda x: ran.append(x), "go")
    assert ran == [] and started[0].delay == 60 and started[0].daemon
    started[0].fn(*started[0].args)
    assert ran == ["go"]


def test_late_visit_upload_rebuilds_day(client):
    post_segment(client, local_text="coffee time")  # 2026-11-14 09:30 local
    assert events(client)[0]["place"] == "somewhere"
    r = client.post("/app/visits", headers=AUTH, json=[{
        "id": "v1", "arrived": "2026-11-14T15:00:00Z", "departed": "2026-11-14T16:00:00Z",
        "lat": 0, "lon": 0, "place_name": "Blue Bean Café"}])
    assert r.status_code == 200
    assert events(client)[0]["place"] == "Blue Bean Café"


def _age(conn, seconds, monkeypatch):
    t0 = day_builder.now_utc()
    marked = iso_utc(t0 - timedelta(seconds=seconds))
    conn.execute("INSERT OR REPLACE INTO dirty_days (day, marked_at) VALUES (?, ?)", (DAY.isoformat(), marked))
    conn.commit()
    monkeypatch.setattr(day_builder, "now_utc", lambda: t0)
    return t0, marked


def _delay60(monkeypatch):
    monkeypatch.setenv("CALYPSO_REBUILD_DELAY_S", "60")
    q = FakeQueue()
    monkeypatch.setattr(jobs, "get_jobs", lambda settings: q)
    return Settings.from_env(), q


def test_stale_dirty_row_requeues(conn, monkeypatch):
    s, q = _delay60(monkeypatch)
    t0, old = _age(conn, 300, monkeypatch)
    assert day_builder.schedule_rebuild(conn, DAY, s, q) is True
    assert len(q.delayed) == 1 and q.delayed[0][0] == 60
    assert dirty(conn)["2026-11-14"] == iso_utc(t0) != old


def test_fresh_dirty_row_does_not_requeue(conn, monkeypatch):
    s, q = _delay60(monkeypatch)
    _age(conn, 10, monkeypatch)
    assert day_builder.schedule_rebuild(conn, DAY, s, q) is False
    assert q.delayed == []


def test_early_run_requeues_for_remaining_time(conn, monkeypatch):
    s, q = _delay60(monkeypatch)
    _age(conn, 30, monkeypatch)
    assert rebuild_dirty_days(s) == 0
    assert len(q.delayed) == 1
    delay, func, _ = q.delayed[0]
    assert func is rebuild_dirty_days and abs(delay - 30) <= 2
    assert "2026-11-14" in dirty(conn)


def test_startup_sweep_queues_job_when_dirty_rows_exist(env, monkeypatch):
    from fastapi.testclient import TestClient

    from calypso import app as app_mod
    from calypso import db

    monkeypatch.setenv("CALYPSO_REBUILD_DELAY_S", "60")
    c = db.connect(Settings.from_env().db_path)
    c.execute("INSERT INTO dirty_days (day, marked_at) VALUES (?, ?)", (DAY.isoformat(), iso_utc(day_builder.now_utc())))
    c.commit()
    c.close()
    q = FakeQueue()
    monkeypatch.setattr(app_mod, "get_jobs", lambda settings: q)
    with TestClient(app_mod.create_app()):
        pass
    assert len(q.delayed) == 1 and q.delayed[0][0] == 60 and q.delayed[0][1] is rebuild_dirty_days


def test_startup_sweep_queues_nothing_when_table_empty(env, monkeypatch):
    from fastapi.testclient import TestClient

    from calypso import app as app_mod

    monkeypatch.setenv("CALYPSO_REBUILD_DELAY_S", "60")
    q = FakeQueue()
    monkeypatch.setattr(app_mod, "get_jobs", lambda settings: q)
    with TestClient(app_mod.create_app()):
        pass
    assert q.delayed == []


def test_manual_rebuild_clears_dirty_row(client, conn):
    mark_day_dirty(conn, DAY)
    assert "2026-11-14" in dirty(conn)
    assert client.post("/days/2026-11-14/rebuild", headers=AUTH).status_code == 200
    assert dirty(conn) == {}
