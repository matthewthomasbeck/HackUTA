"""Shared FastAPI dependencies and helpers for the route modules."""
import base64
import binascii
import sqlite3
from typing import Iterator

from fastapi import HTTPException, Request

from . import db
from .config import Settings
from .models import Person


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_conn(request: Request) -> Iterator[sqlite3.Connection]:
    conn = db.connect(request.app.state.settings.db_path, init=False)
    try:
        yield conn
    finally:
        conn.close()


def get_storage(request: Request):
    return request.app.state.storage


def get_jobs(request: Request):
    return request.app.state.jobs


def get_face_embedder(request: Request):
    return request.app.state.face_embedder


def get_voice_embedder(request: Request):
    return request.app.state.voice_embedder


def public_base(request: Request) -> str:
    """Base URL for links in responses: CALYPSO_PUBLIC_URL, else forwarded headers, else the request."""
    configured = request.app.state.settings.public_url
    if configured:
        return configured
    host = request.headers.get("X-Forwarded-Host") or request.headers.get("Host") or request.url.netloc
    proto = request.headers.get("X-Forwarded-Proto") or ("https" if host.endswith(".ts.net") else request.url.scheme)
    return f"{proto}://{host}"


def person_out(row: sqlite3.Row, base: str) -> Person:
    return Person(
        id=row["id"],
        name=row["name"],
        relationship=row["relationship"],
        is_patient=bool(row["is_patient"]),
        face_photo_url=f"{base}/media/faces/{row['id']}.jpg" if row["face_photo_key"] else None,
        facts=db.loads(row["facts"]),
        phone=row["phone"],
    )


def b64decode(value: str, what: str) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=422, detail=f"{what} is not valid base64")


def require_person(conn: sqlite3.Connection, person_id: str) -> sqlite3.Row:
    row = db.get_person(conn, person_id)
    if row is None:
        raise HTTPException(status_code=404, detail="person not found")
    return row
