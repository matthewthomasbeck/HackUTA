"""Build the patient's day timeline (`day_events`) from utterances, visits and photos."""
import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from . import db
from .config import Settings
from .models import DayEvent
from .summarizer import ClaudeSummarizer, FakeSummarizer, Summarizer, get_summarizer  # noqa: F401
from .timeutil import iso_utc, local_day_bounds, now_utc, parse_iso

GAP = timedelta(minutes=20)


@dataclass
class Episode:
    start: datetime
    end: datetime
    utterances: list[sqlite3.Row]
    visit: sqlite3.Row | None


def place_from_sound_tags(conn, start: datetime, end: datetime) -> tuple[str, float] | None:
    """Dormant: sound tags are not yet trusted to name a place."""
    return None


def _visit_at(visits: list[sqlite3.Row], ts: datetime) -> sqlite3.Row | None:
    for v in visits:
        arrived = parse_iso(v["arrived"])
        departed = parse_iso(v["departed"]) if v["departed"] else None
        if arrived <= ts and (departed is None or ts <= departed):
            return v
    return None


def episodes_for_day(conn, day: date, tz: str) -> list[Episode]:
    lo, hi = local_day_bounds(day, tz)
    utts = conn.execute(
        "SELECT u.* FROM utterances u JOIN segments s ON s.segment_uuid = u.segment_uuid"
        " WHERE u.source = 'puck' AND s.time_synced = 1 AND u.ts_start >= ? AND u.ts_start < ?"
        " ORDER BY u.ts_start, u.id", (iso_utc(lo), iso_utc(hi))).fetchall()
    visits = conn.execute("SELECT * FROM visits ORDER BY arrived").fetchall()
    episodes: list[Episode] = []
    cur_vid = None
    for u in utts:
        t0, t1 = parse_iso(u["ts_start"]), parse_iso(u["ts_end"])
        v = _visit_at(visits, t0)
        vid = v["id"] if v else None
        last = episodes[-1] if episodes else None
        if last is None or vid != cur_vid or t0 - last.end > GAP:
            episodes.append(Episode(t0, t1, [u], v))
        else:
            last.utterances.append(u)
            last.end = max(last.end, t1)
        cur_vid = vid
    return episodes


def is_home_day(conn, day: date, settings: Settings) -> bool:
    lo, hi = local_day_bounds(day, settings.tz)
    for v in conn.execute("SELECT * FROM visits WHERE place_name IS NOT NULL"):
        if v["place_name"].strip().lower() != settings.home_label.strip().lower():
            continue
        departed = parse_iso(v["departed"]) if v["departed"] else None
        if parse_iso(v["arrived"]) < hi and (departed is None or departed >= lo):
            return True
    return False


def rebuild_day(conn, day: date, settings: Settings, summarizer: Summarizer | None = None) -> list[DayEvent]:
    summarizer = summarizer or get_summarizer(settings)
    patient_ids = {r["id"] for r in conn.execute("SELECT id FROM people WHERE is_patient = 1")}
    names = {r["id"]: r["name"] for r in conn.execute("SELECT id, name FROM people")}
    events: list[DayEvent] = []
    for ep in episodes_for_day(conn, day, settings.tz):
        if ep.visit is not None and ep.visit["place_name"]:
            place, conf = ep.visit["place_name"], 1.0
        else:
            place, conf = place_from_sound_tags(conn, ep.start, ep.end) or ("somewhere", 0.0)
        if conf < settings.place_conf_min:
            place = "somewhere"
        people: list[str] = []
        for u in ep.utterances:
            pid = u["person_id"]
            if pid and pid not in patient_ids and pid not in people:
                people.append(pid)
        evidence = [u["id"] for u in ep.utterances]
        photo_ids = [r["id"] for r in conn.execute(
            "SELECT id FROM photos WHERE sensitive = 0 AND taken_at >= ? AND taken_at <= ? ORDER BY taken_at, id",
            (iso_utc(ep.start), iso_utc(ep.end)))]
        person_names = [names[p] for p in people if names.get(p)]
        summary = summarizer.summarize([u["text"] for u in ep.utterances], person_names, place)
        events.append(DayEvent(
            id=hashlib.sha1((day.isoformat() + evidence[0]).encode()).hexdigest()[:32],
            start=ep.start, end=ep.end, place=place, place_confidence=conf, people=people,
            summary=summary, evidence=evidence, photo_ids=photo_ids))
    lo, hi = local_day_bounds(day, settings.tz)
    try:
        conn.execute("DELETE FROM day_events WHERE start_ts >= ? AND start_ts < ?", (iso_utc(lo), iso_utc(hi)))
        for e in events:
            conn.execute(
                "INSERT INTO day_events (id, start_ts, end_ts, place, place_confidence, people, summary, evidence,"
                " photo_ids) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (e.id, iso_utc(e.start), iso_utc(e.end), e.place, e.place_confidence, db.dumps(e.people),
                 e.summary, db.dumps(e.evidence), db.dumps(e.photo_ids)))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    from .jobs import notify  # lazy: jobs imports this module

    notify(settings, "day.built", {"day": day.isoformat(), "events": len(events)})
    return events


def mark_day_dirty(conn, day: date) -> bool:
    """Mark `day` as needing a rebuild. True only when this starts a new dirty period.

    The first mark's time is kept (later marks don't refresh it), so the rebuild is a
    rate limit, not a trailing debounce: it runs about `rebuild_delay_s` after the
    first new speech even while the puck keeps uploading.
    """
    cur = conn.execute(
        "INSERT INTO dirty_days (day, marked_at) VALUES (?, ?) ON CONFLICT(day) DO NOTHING",
        (day.isoformat(), iso_utc(now_utc())))
    conn.commit()
    return cur.rowcount == 1


def schedule_rebuild(conn, day: date, settings: Settings, jobs=None) -> bool:
    """Mark `day` dirty and, if that starts a new dirty period, queue one delayed
    `rebuild_dirty_days` job. Returns True when a job was queued."""
    if not mark_day_dirty(conn, day):
        return False
    if jobs is None:
        from .jobs import get_jobs  # lazy: jobs imports this module

        jobs = get_jobs(settings)
    jobs.enqueue_in(settings.rebuild_delay_s, rebuild_dirty_days, None)
    return True


def rebuild_dirty_days(settings: Settings | None = None) -> int:
    """Rebuild every day first marked at least `rebuild_delay_s` ago. Returns how many.

    Each row is claimed (deleted) before its build, so a mark that arrives during the
    build starts a new dirty period with its own delayed job. A failed build re-marks
    the day so it is retried.
    """
    settings = settings or Settings.from_env()
    conn = db.connect(settings.db_path)
    try:
        cutoff = iso_utc(now_utc() - timedelta(seconds=settings.rebuild_delay_s))
        days = [r["day"] for r in conn.execute("SELECT day FROM dirty_days WHERE marked_at <= ?", (cutoff,))]
        summarizer = get_summarizer(settings) if days else None
        n = 0
        for d in days:
            claimed = conn.execute("DELETE FROM dirty_days WHERE day = ? AND marked_at <= ?", (d, cutoff))
            conn.commit()
            if claimed.rowcount != 1:
                continue  # another worker took it
            try:
                rebuild_day(conn, date.fromisoformat(d), settings, summarizer)
            except Exception:
                schedule_rebuild(conn, date.fromisoformat(d), settings)
                raise
            n += 1
        return n
    finally:
        conn.close()
