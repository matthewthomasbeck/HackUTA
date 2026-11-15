"""Public images at unguessable URLs (ids are random). Sensitive photos are never served."""
import re
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Response

from ..deps import get_conn, get_storage

router = APIRouter(prefix="/media")

_JPG = re.compile(r"^([A-Za-z0-9_-]{1,128})\.jpg$")


def _jpeg(data: bytes | None) -> Response:
    if data is None:
        raise HTTPException(status_code=404, detail="not found")
    return Response(content=data, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=300"})


def _id(filename: str) -> str:
    m = _JPG.match(filename)
    if not m:
        raise HTTPException(status_code=404, detail="not found")
    return m[1]


@router.get("/faces/{filename}")
def face(filename: str, conn: sqlite3.Connection = Depends(get_conn), storage=Depends(get_storage)) -> Response:
    row = conn.execute("SELECT face_photo_key FROM people WHERE id = ?", (_id(filename),)).fetchone()
    if row is None or not row["face_photo_key"]:
        raise HTTPException(status_code=404, detail="not found")
    return _jpeg(storage.get(row["face_photo_key"]))


@router.get("/photos/{filename}")
def photo(filename: str, conn: sqlite3.Connection = Depends(get_conn), storage=Depends(get_storage)) -> Response:
    row = conn.execute("SELECT storage_key, sensitive FROM photos WHERE id = ?", (_id(filename),)).fetchone()
    if row is None or row["sensitive"]:
        raise HTTPException(status_code=404, detail="not found")
    return _jpeg(storage.get(row["storage_key"]))
