"""People: list, detail with memories, create, rename, and enrollment entry points."""
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile

from .. import db
from ..auth import require_token
from ..bus import emit
from ..config import Settings
from ..deps import (b64decode, get_conn, get_face_embedder, get_settings, get_storage, get_voice_embedder,
                    person_out, public_base, require_person)
from ..identity.enroll import face_vectors, find_existing, print_counts, store_prints, voice_vector
from ..models import IntroRequest, IntroResult, Person, PersonCreate, PersonDetail, PersonPatch
from ..timeutil import parse_iso

router = APIRouter(prefix="/people", dependencies=[Depends(require_token)])

MEMORY_LIMIT = 5


def _memories(conn: sqlite3.Connection, person_id: str, tz: str) -> list[str]:
    """Up to 5 lines, newest first: 'Nov 14 · Blue Bean Café · Coffee with Sarah'.

    Day events that include the person come first; utterances fill in the rest.
    """
    zone = ZoneInfo(tz)
    out: list[str] = []
    for ev in conn.execute(
        "SELECT start_ts, place, summary FROM day_events WHERE people LIKE ? ORDER BY start_ts DESC LIMIT ?",
        (f'%"{person_id}"%', MEMORY_LIMIT),
    ):
        local = parse_iso(ev["start_ts"]).astimezone(zone)
        out.append(f"{local:%b} {local.day} · {ev['place']} · {ev['summary']}")
    if len(out) < MEMORY_LIMIT:
        for u in conn.execute(
            "SELECT ts_start, text FROM utterances WHERE person_id = ? ORDER BY ts_start DESC LIMIT ?",
            (person_id, MEMORY_LIMIT - len(out)),
        ):
            local = parse_iso(u["ts_start"]).astimezone(zone)
            out.append(f"{local:%b} {local.day} · “{u['text']}”")
    return out


@router.get("", response_model=list[Person])
def list_people(
    request: Request,
    is_patient: bool | None = Query(default=None),
    conn: sqlite3.Connection = Depends(get_conn),
) -> list[Person]:
    base = public_base(request)
    return [person_out(r, base) for r in db.list_people(conn, is_patient)]


@router.post("", response_model=Person, status_code=201)
def create_person(body: PersonCreate, request: Request, conn: sqlite3.Connection = Depends(get_conn)) -> Person:
    """Create someone directly (e.g. the patient, or the demo seed script)."""
    row = db.insert_person(conn, **body.model_dump())
    emit("person.created", {"person_id": row["id"], "name": row["name"]})
    return person_out(row, public_base(request))


@router.get("/{person_id}", response_model=PersonDetail)
def get_person(
    person_id: str,
    request: Request,
    conn: sqlite3.Connection = Depends(get_conn),
    settings: Settings = Depends(get_settings),
) -> PersonDetail:
    row = require_person(conn, person_id)
    person = person_out(row, public_base(request))
    return PersonDetail(**person.model_dump(), memories=_memories(conn, person_id, settings.tz))


@router.patch("/{person_id}", response_model=Person)
def patch_person(
    person_id: str, body: PersonPatch, request: Request, conn: sqlite3.Connection = Depends(get_conn)
) -> Person:
    require_person(conn, person_id)
    row = db.update_person(conn, person_id, body.model_dump(exclude_unset=True))
    emit("person.updated", {"person_id": person_id, "name": row["name"]})
    return person_out(row, public_base(request))


def _save_face_photo(storage, conn: sqlite3.Connection, person_id: str, jpeg: bytes) -> None:
    key = f"faces/{person_id}.jpg"
    storage.put(key, jpeg, "image/jpeg")
    db.update_person(conn, person_id, {"face_photo_key": key})


def _merge_facts(existing: list[str], new: list[str]) -> list[str]:
    seen = {f.strip().casefold() for f in existing}
    return existing + [f.strip() for f in new if f.strip() and f.strip().casefold() not in seen]


@router.post("/from_intro", response_model=IntroResult, status_code=201)
def from_intro(
    body: IntroRequest,
    request: Request,
    response: Response,
    conn: sqlite3.Connection = Depends(get_conn),
    storage=Depends(get_storage),
    settings: Settings = Depends(get_settings),
    face_embedder=Depends(get_face_embedder),
    voice_embedder=Depends(get_voice_embedder),
) -> IntroResult:
    """End of a 1:1 setup call: enroll the caller's face prints and voiceprint.

    If the verified phone, the face, or the voice matches someone already enrolled,
    that person is updated (prints added, facts merged) instead of creating a duplicate.
    Missing models or unusable media never block enrollment; `notes` says what was skipped.
    """
    faces = [b64decode(f, "face_jpegs_b64") for f in body.face_jpegs_b64]
    wav = b64decode(body.voice_wav_b64, "voice_wav_b64") if body.voice_wav_b64 else None
    notes: list[str] = []
    face_vecs = face_vectors(face_embedder, faces, notes)
    voice_vec, speech_s = voice_vector(voice_embedder, wav, settings, notes)

    person_id, matched_by = find_existing(conn, settings, body.phone, face_vecs, voice_vec)
    if person_id:
        row = db.get_person(conn, person_id)
        updates = {"facts": _merge_facts(db.loads(row["facts"]), body.facts)}
        for field in ("name", "relationship", "phone"):
            if getattr(body, field) and not row[field]:
                updates[field] = getattr(body, field)
        row = db.update_person(conn, person_id, updates)
        response.status_code = 200
    else:
        row = db.insert_person(conn, name=body.name, relationship=body.relationship,
                               phone=body.phone, facts=_merge_facts([], body.facts))
    added_faces, added_voice = store_prints(conn, row["id"], face_vecs, voice_vec, speech_s, "setup", "call")
    if faces and not row["face_photo_key"]:
        _save_face_photo(storage, conn, row["id"], faces[0])
        row = db.get_person(conn, row["id"])

    emit("person.enrolled", {"person_id": row["id"], "name": row["name"], "matched_existing": bool(person_id),
                             "matched_by": matched_by, "face_prints_added": added_faces,
                             "voice_prints_added": added_voice, "speech_s": round(speech_s, 1),
                             "notes": notes, "call_id": body.call_id})
    return IntroResult(**person_out(row, public_base(request)).model_dump(), matched_existing=bool(person_id),
                       matched_by=matched_by, face_prints_added=added_faces,
                       voice_prints_added=added_voice, notes=notes)


@router.post("/{person_id}/faces")
def add_face(
    person_id: str,
    image: UploadFile = File(...),
    conn: sqlite3.Connection = Depends(get_conn),
    storage=Depends(get_storage),
    settings: Settings = Depends(get_settings),
    face_embedder=Depends(get_face_embedder),
) -> dict:
    """Enroll one face image (iMessage photo, learn-in-call): stores a face print."""
    row = require_person(conn, person_id)
    data = image.file.read(settings.max_image_bytes + 1)
    if len(data) > settings.max_image_bytes:
        raise HTTPException(status_code=413, detail="image too large")
    notes: list[str] = []
    vecs = face_vectors(face_embedder, [data], notes)
    if not vecs:
        raise HTTPException(status_code=422, detail="; ".join(notes) or "no face found")
    store_prints(conn, person_id, vecs, None, 0.0, "upload", "")
    if not row["face_photo_key"]:
        _save_face_photo(storage, conn, person_id, data)
    faces, voices = print_counts(conn, person_id)
    return {"ok": True, "face_prints": faces, "voice_prints": voices}


@router.post("/{person_id}/voice")
def add_voice(
    person_id: str,
    audio: UploadFile = File(...),
    conn: sqlite3.Connection = Depends(get_conn),
    settings: Settings = Depends(get_settings),
    voice_embedder=Depends(get_voice_embedder),
) -> dict:
    """Enroll a voice sample: stores a voiceprint. The audio itself is never stored."""
    require_person(conn, person_id)
    data = audio.file.read(settings.max_audio_bytes + 1)
    if len(data) > settings.max_audio_bytes:
        raise HTTPException(status_code=413, detail="audio too large")
    notes: list[str] = []
    vec, speech_s = voice_vector(voice_embedder, data, settings, notes)
    if vec is None:
        raise HTTPException(status_code=422, detail="; ".join(notes) or "no usable speech")
    store_prints(conn, person_id, [], vec, speech_s, "", "upload")
    faces, voices = print_counts(conn, person_id)
    return {"ok": True, "face_prints": faces, "voice_prints": voices, "speech_s": round(speech_s, 1)}
