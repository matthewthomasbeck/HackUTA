"""Speech-to-text behind one interface. Pick with CALYPSO_STT=grok|fake."""
import hashlib
import io
import logging
import wave
from dataclasses import dataclass
from typing import ClassVar, Protocol

import httpx

from .config import Settings

_log = logging.getLogger("calypso.stt")


@dataclass(frozen=True)
class SttPiece:
    text: str
    t0: float  # seconds from segment start
    t1: float


class SpeechToText(Protocol):
    def transcribe(self, wav: bytes) -> list[SttPiece]: ...


class FakeSTT:
    """Tests register text by the sha1 of the WAV: `FakeSTT.script[sha1] = "text"`."""

    script: ClassVar[dict[str, str]] = {}

    def transcribe(self, wav: bytes) -> list[SttPiece]:
        text = self.script.get(hashlib.sha1(wav).hexdigest())
        if not text:
            return []
        try:
            with wave.open(io.BytesIO(wav), "rb") as w:
                duration = w.getnframes() / float(w.getframerate())
        except (wave.Error, EOFError):
            duration = 0.0
        return [SttPiece(text, 0.0, duration)]


class GrokSTT:
    def __init__(self, key: str) -> None:
        if not key:
            raise ValueError("XAI_API_KEY is required")
        self._headers = {"Authorization": f"Bearer {key}"}

    def transcribe(self, wav: bytes) -> list[SttPiece]:
        r = httpx.post("https://api.x.ai/v1/stt", headers=self._headers,
                       files={"file": ("speech.wav", wav, "audio/wav")},
                       data={"language": "en"}, timeout=15)
        r.raise_for_status()
        text = r.json().get("text")
        if not isinstance(text, str):
            raise ValueError("invalid STT response")
        text = text.strip()
        if not text:
            return []
        try:
            with wave.open(io.BytesIO(wav), "rb") as w:
                duration = w.getnframes() / float(w.getframerate())
        except (wave.Error, EOFError):
            duration = 0.0
        return [SttPiece(text, 0.0, duration)]


def get_stt(settings: Settings) -> SpeechToText:
    if settings.stt == "grok":
        if settings.xai_api_key:
            return GrokSTT(settings.xai_api_key)
        _log.warning("CALYPSO_STT=grok but XAI_API_KEY is empty: using the fake STT")
    return FakeSTT()
