"""In-call recall: Haiku decides what was asked, then deterministic SQL builds the card.

The model never writes card text. Every line comes from saved day events, people and memories.
"""
import json
import logging
import os
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import ClassVar, Protocol
from zoneinfo import ZoneInfo

from . import bus
from .models import Card, CallLine, Intent, RecallResponse
from .routes.days import events_for_day
from .routes.people import _memories
from .day_builder import is_home_day

_log = logging.getLogger("calypso.recall")
WINDOW = 6
HINT_MAX_DAYS = 7  # a date_hint further back than this (or in the future) is ignored


@dataclass(frozen=True)
class Detection:
    intent: Intent
    confidence: float


class Detector(Protocol):
    def detect(self, lines: list[CallLine], today: date | None = None) -> Detection: ...


NONE = Detection(Intent(intent="none"), 0.0)


class FakeDetector:
    script: ClassVar[dict[str, Detection]] = {}

    def __init__(self) -> None:
        self.last_prompt: str | None = None

    def detect(self, lines: list[CallLine], today: date | None = None) -> Detection:
        self.last_prompt = detector_prompt(lines, today)
        return self.script.get(lines[-1].text, NONE) if lines else NONE


SYSTEM = (
    "You listen to a family call with a person who has dementia. Decide whether the LAST line asks the "
    "patient to recall something. Reply with JSON only: "
    '{"intent": "today|person|memory|photo|none", "query": str|null, "date_hint": "YYYY-MM-DD"|null, '
    '"place_hint": str|null, "confidence": 0..1}.\n'
    "today = asks what the patient did today or this morning. person/memory = asks about a named person or "
    "relationship (query = the name). photo = asks to see pictures. none = anything else.\n"
    "date_hint: null unless the line names a specific past day (\"yesterday\", \"on Saturday\"); resolve it "
    "against the patient's local date given on the first line. Never guess a date.\n"
    'Positive: "Mom, what did you do today?" -> today. "How was your morning?" -> today. '
    '"Remember when you saw Sarah?" -> person, query Sarah. "Do you have pictures from today?" -> photo.\n'
    'Negative: "the weather today is awful" -> none. "what time is dinner?" -> none. "Hi everyone" -> none.'
)


def detector_prompt(lines: list[CallLine], today: date | None) -> str:
    """The detector's user message: the patient's local date, then the last WINDOW lines."""
    head = f"Patient's local date: {today:%A} {today.isoformat()}\n" if today else ""
    return head + "\n".join(f"{l.speaker}: {l.text}" for l in lines[-WINDOW:])


class ClaudeDetector:
    def __init__(self, settings=None) -> None:
        import anthropic

        self.client = anthropic.Anthropic(timeout=2.5, max_retries=0)
        self.model = (os.environ.get("CALYPSO_DETECT_MODEL") or os.environ.get("CALYPSO_DETECTOR_MODEL")
                      or "claude-haiku-4-5")

    def detect(self, lines: list[CallLine], today: date | None = None) -> Detection:
        convo = detector_prompt(lines, today)
        msg = self.client.messages.create(
            model=self.model, max_tokens=100, system=SYSTEM, timeout=2.5,
            messages=[{"role": "user", "content": convo}],
        )
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        data = json.loads(text[text.index("{"): text.rindex("}") + 1])
        intent = data.get("intent")
        if intent not in ("today", "person", "memory", "photo", "none"):
            return NONE
        return Detection(
            Intent(intent=intent, query=data.get("query"), date_hint=data.get("date_hint"),
                   place_hint=data.get("place_hint")),
            float(data.get("confidence") or 0.0),
        )


def get_detector(settings) -> Detector:
    return ClaudeDetector(settings) if settings.detector == "claude" else FakeDetector()


def _local_today(settings) -> date:
    return datetime.now(ZoneInfo(settings.tz)).date()


def _day(intent: Intent, today: date) -> date:
    """The day asked about: a `date_hint` only within the last HINT_MAX_DAYS, else today."""
    if intent.date_hint:
        try:
            d = date.fromisoformat(intent.date_hint)
        except ValueError:
            return today
        if today - timedelta(days=HINT_MAX_DAYS) <= d <= today:
            return d
    return today


def _day_title(day: date, today: date) -> str:
    return "Today" if day == today else f"{day:%A}, {day:%b} {day.day}"


def _today_card(conn, settings, day: date, today: date) -> Card:
    title = _day_title(day, today)
    events = events_for_day(conn, day, settings.tz)
    if not events:
        if is_home_day(conn, day, settings):
            line = "A quiet day at home"
        else:
            line = "Nothing saved yet today" if day == today else "Nothing saved for that day"
        return Card(kind="today", title=title, lines=[line])
    zone = ZoneInfo(settings.tz)
    return Card(kind="today", title=title, lines=[  # the latest three, in time order
        f"{e.start.astimezone(zone):%-I:%M %p} · {e.place} · {e.summary}" for e in events[-3:]])


def _person_card(conn, settings, query: str | None) -> Card | None:
    q = (query or "").strip().casefold()
    if not q:
        return None
    rows = [r for r in conn.execute("SELECT id, name, relationship FROM people WHERE is_patient = 0")
            if q in ((r["name"] or "").casefold(), (r["relationship"] or "").casefold())]
    if len(rows) != 1:
        return None
    lines = _memories(conn, rows[0]["id"], settings.tz)[:3]
    return Card(kind="memory", title=rows[0]["name"] or query, lines=lines) if lines else None


def _photo_card(conn, settings, day: date, today: date) -> Card | None:
    events = events_for_day(conn, day, settings.tz)
    ids = [p for e in events for p in e.photo_ids]
    if not ids:
        return None
    marks = ",".join("?" * len(ids))
    ok = {r["id"] for r in conn.execute(
        f"SELECT id FROM photos WHERE sensitive = 0 AND id IN ({marks})", ids)}
    keep = [p for p in dict.fromkeys(ids) if p in ok][:3]
    if not keep:
        return None
    first = next(e.summary for e in events if any(p in ok for p in e.photo_ids))
    when = "today" if day == today else _day_title(day, today)
    return Card(kind="memory", title=f"Photos from {when}", lines=[first],
                image_urls=[f"{settings.public_url}/media/photos/{p}.jpg" for p in keep])


def recall(lines: list[CallLine], conn: sqlite3.Connection, settings, detector: Detector, *,
           today: date | None = None) -> RecallResponse:
    window = lines[-WINDOW:]
    last = window[-1].text if window else ""
    today = today or _local_today(settings)
    try:
        det = detector.detect(window, today) if window else NONE
    except Exception as exc:
        _log.warning("detector failed: %s", exc)
        det = NONE
    if det.confidence < settings.recall_min:
        det = NONE
    intent = det.intent
    bus.emit("recall.detect", {"last_line": last[:200], "intent": intent.model_dump(), "confidence": det.confidence})
    card: Card | None = None
    if intent.intent == "today":
        card = _today_card(conn, settings, _day(intent, today), today)
    elif intent.intent in ("person", "memory"):
        card = _person_card(conn, settings, intent.query)
    elif intent.intent == "photo":
        card = _photo_card(conn, settings, _day(intent, today), today)
    if intent.intent != "none":
        bus.emit("recall.search", {"intent": intent.intent, "hits": len(card.lines) if card else 0})
    return RecallResponse(intent=intent, card=card)
