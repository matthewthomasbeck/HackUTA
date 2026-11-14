"""Shared contract for every Calypso⁻¹ component.

The puck, agent, iOS app, and dashboard all speak these shapes over HTTP.
Change a field here only after telling the whole team.
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class Person(BaseModel):
    id: str
    name: str | None = None
    relationship: str | None = None
    is_patient: bool = False
    face_photo_url: str | None = None
    facts: list[str] = []


class Utterance(BaseModel):
    id: str
    segment_uuid: str
    ts_start: datetime
    ts_end: datetime
    text: str
    source: Literal["puck", "call"]
    voice_cluster_id: str | None = None
    person_id: str | None = None


class SoundTag(BaseModel):
    ts: datetime
    label: str
    score: float


class Visit(BaseModel):
    id: str
    arrived: datetime
    departed: datetime | None = None
    lat: float
    lon: float
    place_name: str | None = None


class Photo(BaseModel):
    id: str
    taken_at: datetime
    lat: float | None = None
    lon: float | None = None
    path: str
    sensitive: bool = False
    caption: str | None = None
    event_id: str | None = None


class DayEvent(BaseModel):
    id: str
    start: datetime
    end: datetime
    place: str
    place_confidence: float
    people: list[str] = []
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
