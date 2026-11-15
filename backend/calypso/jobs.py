"""Background jobs: inline (tests, laptops) or RQ on Redis (Vultr, Keanu's queue).

The RQ worker runs this repo's code on the host, from `backend/`:

    uv run --env-file ../.env rq worker --url "$CALYPSO_REDIS_URL" recordings

so it imports `calypso.jobs.process_segment` and opens the same SQLite file.
A worker can't reach the API's in-memory bus, so it reports progress by
POSTing to the API's `/events` endpoint.
"""
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

import httpx

from . import db
from .bus import emit
from .config import Settings
from .identity import ModelUnavailable
from .identity.audio import AudioError
from .identity.vectors import best_scores, ranked
from .identity.voice import embed_wav, get_voice_embedder
from .stt import SttPiece, get_stt
from .timeutil import iso_utc, now_iso, parse_iso

_log = logging.getLogger("calypso.jobs")


class InlineJobs:
    """Runs the job right away. A job error is logged, like a failed worker job;
    it is not a queuing error, so the upload is still acknowledged."""

    def enqueue(self, func: Callable, *args: Any) -> None:
        try:
            func(*args)
        except Exception:
            _log.exception("inline job %s failed", func.__name__)


class RQJobs:
    def __init__(self, redis_url: str, queue_name: str, queue_factory: Callable | None = None) -> None:
        if queue_factory is None:
            from redis import Redis
            from rq import Queue

            def queue_factory(name: str):
                return Queue(name, connection=Redis.from_url(redis_url))

        self.queue = queue_factory(queue_name)

    def enqueue(self, func: Callable, *args: Any) -> None:
        from rq import Retry

        self.queue.enqueue(
            f"{func.__module__}.{func.__name__}", *args,
            job_timeout=300, result_ttl=3600, retry=Retry(max=3, interval=[10, 30, 60]),
        )


def get_jobs(settings: Settings):
    if settings.jobs == "rq":
        return RQJobs(settings.redis_url, settings.rq_queue)
    return InlineJobs()


def notify(settings: Settings, stage: str, payload: dict) -> None:
    """Send an event to the dashboard, from the API process or from a worker."""
    if settings.jobs != "rq":
        emit(stage, payload)
        return
    try:
        httpx.post(
            f"{settings.backend_url}/events",
            json={"stage": stage, "payload": payload},
            headers={"Authorization": f"Bearer {settings.api_token}"},
            timeout=5,
        )
    except httpx.HTTPError as exc:  # the dashboard missing one event must not fail the job
        _log.warning("could not post %s event to the API: %s", stage, exc)


def mark_day_dirty(conn, day: date) -> None:
    """Task 4 replaces this: flag the day's timeline for rebuilding."""


def attribute_speaker(conn, wav: bytes, settings: Settings) -> str | None:
    """The person whose voiceprint clearly matches this clip, else None. The patient may match."""
    try:
        vec, _ = embed_wav(get_voice_embedder(settings), wav, settings.voice_min_speech_s)
    except (AudioError, ModelUnavailable) as exc:
        _log.warning("voice attribution skipped: %s", exc)
        return None
    if vec is None:
        return None
    top = ranked(best_scores(conn, "voice_prints", vec, exclude_patient=False))[:2]
    if not top or top[0][1] < settings.voice_match:
        return None
    if len(top) > 1 and top[0][1] - top[1][1] < settings.voice_margin:
        return None
    return top[0][0]


def process_segment(segment_uuid: str, wav_path: str) -> list[str]:
    """Turn one puck segment into utterances, then delete its audio.

    Text is the puck's `local_text` if it has any, else server STT. Each STT piece
    becomes one utterance at its capture time; the speaker is attributed once per
    segment, only when confident. On failure the WAV is kept so an RQ retry can try again.
    """
    settings = Settings.from_env()
    conn = db.connect(settings.db_path)
    try:
        seg = conn.execute("SELECT * FROM segments WHERE segment_uuid = ?", (segment_uuid,)).fetchone()
        if seg is None:
            raise LookupError(f"unknown segment {segment_uuid}")
        utterance_ids: list[str] = []
        try:
            wav = Path(wav_path).read_bytes()
            text = (seg["local_text"] or "").strip()
            if text:
                pieces = [SttPiece(text, 0.0, 0.0)]
                bounds = [(seg["ts_start"], seg["ts_end"])]
            else:
                pieces = get_stt(settings).transcribe(wav)
                base = parse_iso(seg["ts_start"])
                bounds = [(iso_utc(base + timedelta(seconds=p.t0)), iso_utc(base + timedelta(seconds=p.t1)))
                          for p in pieces]
            pieces = [(p, b) for p, b in zip(pieces, bounds) if p.text.strip()]
            person_id = attribute_speaker(conn, wav, settings) if pieces else None
            for p, (t0, t1) in pieces:
                uid = db.new_id()
                conn.execute(
                    "INSERT INTO utterances (id, segment_uuid, ts_start, ts_end, text, source, person_id)"
                    " VALUES (?, ?, ?, ?, ?, 'puck', ?)",
                    (uid, segment_uuid, t0, t1, p.text.strip(), person_id),
                )
                utterance_ids.append(uid)
            conn.execute(
                "UPDATE segments SET status = 'done', error = NULL, processed_at = ? WHERE segment_uuid = ?",
                (now_iso(), segment_uuid),
            )
            conn.commit()
        except Exception as exc:
            conn.rollback()
            conn.execute(
                "UPDATE segments SET status = 'failed', error = ? WHERE segment_uuid = ?",
                (str(exc)[:500], segment_uuid),
            )
            conn.commit()
            notify(settings, "puck.failed", {"segment_uuid": segment_uuid, "error": str(exc)[:200]})
            raise
        try:
            local_day = parse_iso(seg["ts_start"]).astimezone(ZoneInfo(settings.tz)).date()
            mark_day_dirty(conn, local_day)
        except Exception:
            _log.exception("mark_day_dirty failed for %s", segment_uuid)
        Path(wav_path).unlink(missing_ok=True)  # audio is never kept
        notify(settings, "puck.processed", {"segment_uuid": segment_uuid, "utterance_ids": utterance_ids})
        return utterance_ids
    finally:
        conn.close()
