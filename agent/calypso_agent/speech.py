"""Speech interfaces; provider implementations plug in without changing scripts."""

from collections import deque
from dataclasses import dataclass
from io import BytesIO
from typing import Protocol
import wave


@dataclass
class TranscriptSegment:
    start_s: float
    end_s: float
    text: str


class STT(Protocol):
    def transcribe(self, wav: bytes) -> list[TranscriptSegment]: ...


class TTS(Protocol):
    def synthesize(self, text: str) -> bytes:
        """Return 16 kHz mono 16-bit PCM WAV."""
        ...


class SpeechInput(Protocol):
    async def listen(self, timeout_s: float = 20) -> str | None:
        """Return a final utterance, or None on silence/timeout."""
        ...


class SpeechOutput(Protocol):
    async def speak(self, text: str) -> None: ...


class FakeSTT:
    def __init__(self, lines):
        self.lines = deque(lines)

    async def listen(self, timeout_s=20):
        return self.lines.popleft() if self.lines else None

    def transcribe(self, wav):
        text = self.lines.popleft() if self.lines else None
        return [TranscriptSegment(0, 1, text)] if text else []


class FakeTTS:
    def __init__(self):
        self.spoken: list[str] = []

    async def speak(self, text):
        self.spoken.append(text)

    def synthesize(self, text):
        self.spoken.append(text)
        out = BytesIO()
        with wave.open(out, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(b"\0\0" * 1600)
        return out.getvalue()
