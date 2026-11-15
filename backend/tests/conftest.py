import io
import json
import struct
import uuid

import pytest
from fastapi.testclient import TestClient

TOKEN = "test-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def env(monkeypatch, tmp_path):
    """Isolated settings: temp DB and data dir, local storage, inline jobs."""
    monkeypatch.setenv("CALYPSO_API_TOKEN", TOKEN)
    monkeypatch.setenv("CALYPSO_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("CALYPSO_DB", str(tmp_path / "data" / "calypso.db"))
    monkeypatch.setenv("CALYPSO_JOBS", "inline")
    monkeypatch.setenv("CALYPSO_STORAGE", "local")
    monkeypatch.setenv("CALYPSO_TZ", "America/Chicago")
    monkeypatch.setenv("CALYPSO_PUBLIC_URL", "https://calypso.example.com")
    monkeypatch.setenv("CALYPSO_FACE", "fake")
    monkeypatch.setenv("CALYPSO_VOICE", "fake")
    return tmp_path


@pytest.fixture
def client(env):
    from calypso.app import create_app

    with TestClient(create_app()) as c:
        yield c


@pytest.fixture
def conn(env, client):
    from calypso import db
    from calypso.config import Settings

    c = db.connect(Settings.from_env().db_path)
    yield c
    c.close()


def wav_bytes(seconds: float = 0.5, rate: int = 16000) -> bytes:
    """A silent 16 kHz mono 16-bit PCM WAV, the format the puck uploads."""
    n = int(seconds * rate)
    data = b"\x00\x00" * n
    header = b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVEfmt " + struct.pack(
        "<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16) + b"data" + struct.pack("<I", len(data))
    return header + data


JPEG = b"\xff\xd8\xff\xe0fake-jpeg-bytes\xff\xd9"


def tone_wav(freq: float, seconds: float = 3.0, rate: int = 16000, channels: int = 1, amp: float = 0.3) -> bytes:
    """A steady tone. With the fake voice embedder, one pitch = one 'speaker'."""
    import numpy as np
    import wave

    t = np.arange(int(seconds * rate)) / rate
    x = (amp * np.sin(2 * np.pi * freq * t) * 32767).astype("<i2")
    if channels > 1:
        x = np.repeat(x[:, None], channels, axis=1).ravel()
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(x.tobytes())
    return out.getvalue()


def face(name: str) -> bytes:
    """A fake 'photo' the fake face embedder reads as one face of `name` (comma-separate for several)."""
    return f"FAKEFACE:{name}".encode()


def post_segment(client, segment_uuid=None, **meta):
    meta = {
        "segment_uuid": segment_uuid or uuid.uuid4().hex,
        "ts_start": "2026-11-14T15:30:00.000Z",
        "ts_end": "2026-11-14T15:30:04.500Z",
        "sound_tags": [],
        "local_text": None,
        **meta,
    }
    return client.post(
        "/puck/segments",
        headers=AUTH,
        files={"audio": ("seg.wav", io.BytesIO(wav_bytes()), "audio/wav")},
        data={"meta": json.dumps(meta)},
    )
