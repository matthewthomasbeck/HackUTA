"""Shared contract for every Calypso⁻¹ component.

The puck, agent, iOS app, and dashboard all speak these shapes over HTTP.
Change a field here only after telling the whole team.

Conventions:
- Every datetime is timezone-aware. Incoming times without a zone are treated
  as UTC (with a logged warning) instead of being rejected, so a puck upload
  queue can never stall on one bad timestamp. Outgoing JSON times are UTC with
  millisecond precision and a `Z`, e.g. `2026-11-14T15:30:00.123Z`.
- `DayEvent.people` holds person ids (never names), and never the patient.
- Ids that end up in URLs (`segment_uuid`, photo ids) use only `A-Z a-z 0-9 _ -`.
"""
import logging
from datetime import datetime, timezone
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, Field, PlainSerializer

_log = logging.getLogger("calypso.models")

SAFE_ID = r"^[A-Za-z0-9_-]{1,128}$"


def to_utc(dt: datetime) -> datetime:
    """Normalize to an aware UTC datetime. Naive means UTC (logged, not rejected)."""
    if dt.tzinfo is None:
        _log.warning("timestamp without a zone treated as UTC: %s", dt.isoformat())
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def iso_utc(dt: datetime) -> str:
    """Fixed-width UTC string, e.g. 2026-11-14T15:30:00.123Z (also sorts correctly as text)."""
    return to_utc(dt).isoformat(timespec="milliseconds").replace("+00:00", "Z")


ZonedDatetime = Annotated[
    datetime,
    AfterValidator(to_utc),
    PlainSerializer(iso_utc, return_type=str, when_used="json"),
]


# --- Core records -------------------------------------------------------------

class Person(BaseModel):
    id: str
    name: str | None = None
    relationship: str | None = None
    is_patient: bool = False
    face_photo_url: str | None = None  # absolute https URL, built by the backend
    facts: list[str] = []
    phone: str | None = None


class PersonDetail(Person):
    """`GET /people/{id}`: a flat Person plus up to 5 memory lines, newest first."""
    memories: list[str] = []


class Utterance(BaseModel):
    id: str
    segment_uuid: str
    ts_start: ZonedDatetime
    ts_end: ZonedDatetime
    text: str
    source: Literal["puck", "call"]
    voice_cluster_id: str | None = None
    person_id: str | None = None


class SoundTag(BaseModel):
    ts: ZonedDatetime
    label: str
    score: float


class Visit(BaseModel):
    id: str
    arrived: ZonedDatetime
    departed: ZonedDatetime | None = None  # null while the visit is still going on
    lat: float
    lon: float
    place_name: str | None = None


class Photo(BaseModel):
    id: str
    taken_at: ZonedDatetime
    lat: float | None = None
    lon: float | None = None
    path: str
    sensitive: bool = False
    caption: str | None = None
    event_id: str | None = None


class DayEvent(BaseModel):
    id: str
    start: ZonedDatetime
    end: ZonedDatetime
    place: str
    place_confidence: float
    people: list[str] = []  # person ids, patient excluded
    summary: str
    evidence: list[str] = []
    photo_ids: list[str] = []


class RecognitionResult(BaseModel):
    status: Literal["identified", "learning", "uncertain"]
    person_id: str | None = None
    face_score: float | None = None
    voice_score: float | None = None


class Intent(BaseModel):
    intent: Literal["today", "person", "memory", "photo", "none"]
    query: str | None = None
    date_hint: str | None = None
    place_hint: str | None = None


class Card(BaseModel):
    kind: Literal["identity", "learning", "today", "memory"]
    title: str
    lines: list[str]
    image_urls: list[str] = []


class CallLine(BaseModel):
    speaker: str
    text: str


# --- Request / response bodies ------------------------------------------------

class PersonCreate(BaseModel):
    name: str | None = None
    relationship: str | None = None
    is_patient: bool = False
    facts: list[str] = []
    phone: str | None = None


class PersonPatch(BaseModel):
    """`PATCH /people/{id}`: only the fields sent are changed."""
    name: str | None = None
    relationship: str | None = None
    is_patient: bool | None = None
    facts: list[str] | None = None
    phone: str | None = None


class SegmentMeta(BaseModel):
    """The `meta` JSON part of `POST /puck/segments`."""
    segment_uuid: str = Field(pattern=SAFE_ID)
    ts_start: ZonedDatetime
    ts_end: ZonedDatetime
    sound_tags: list[SoundTag] = []
    local_text: str | None = None


class SegmentAck(BaseModel):
    segment_uuid: str
    duplicate: bool
    utterance_ids: list[str] = []


class PuckHealth(BaseModel):
    ts: ZonedDatetime
    queue_depth: int
    sound_backend: str
    ms_per_segment: float | None = None
    time_synced: bool
    battery_pct: float | None = None
    last_upload_ok: bool | None = None


class BBox(BaseModel):
    x: int
    y: int
    w: int
    h: int


class FaceResult(BaseModel):
    bbox: BBox | None = None  # None means "the whole frame" (stub / unknown size)
    result: RecognitionResult


class RecognizeRequest(BaseModel):
    face_jpeg_b64: str | None = None
    voice_wav_b64: str | None = None
    exclude_patient: bool = True
    participant_key: str | None = None
    call_id: str | None = None


class RecognizeResponse(BaseModel):
    faces: list[FaceResult] = []  # one entry per face found in the frame
    voice_only: RecognitionResult | None = None  # set when audio was sent without a face


class IntroRequest(BaseModel):
    """`POST /people/from_intro`, sent by the agent at the end of a 1:1 setup call."""
    transcript: str
    face_jpegs_b64: list[str] = []
    voice_wav_b64: str | None = None
    phone: str | None = None
    call_id: str | None = None


class CallCreate(BaseModel):
    kind: Literal["setup", "group"]
    participants: list[str] = []


class Call(BaseModel):
    id: str
    kind: Literal["setup", "group"]
    started: ZonedDatetime
    ended: ZonedDatetime | None = None
    participants: list[str] = []


class CallLineIn(BaseModel):
    speaker: str
    text: str
    ts: ZonedDatetime | None = None
    person_id: str | None = None


class RecallRequest(BaseModel):
    lines: list[CallLine]


class RecallResponse(BaseModel):
    intent: Intent
    card: Card | None = None


class PhotoMeta(BaseModel):
    """The `meta` JSON part of `POST /app/photos`."""
    id: str = Field(pattern=SAFE_ID)
    taken_at: ZonedDatetime
    lat: float | None = None
    lon: float | None = None


class BusEvent(BaseModel):
    stage: str = Field(min_length=1, max_length=64)
    payload: dict[str, Any] = {}
