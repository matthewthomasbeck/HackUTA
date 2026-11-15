"""xAI REST speech adapter. WAV in/out; no credentials or audio logged."""

from io import BytesIO
import wave

import httpx


class GrokSpeech:
    def __init__(self, key, *, voice="eve", client=None):
        if not key:
            raise ValueError("XAI_API_KEY is required")
        self.http = client or httpx.AsyncClient(timeout=15)
        self.owns = client is None
        self.headers = {"Authorization": f"Bearer {key}"}
        self.voice = voice

    async def transcribe(self, audio):
        response = await self.http.post("https://api.x.ai/v1/stt", headers=self.headers,
            files={"file": ("speech.wav", audio, "audio/wav")}, data={"language": "en"})
        response.raise_for_status()
        text = response.json()["text"]
        if not isinstance(text, str):
            raise ValueError("Invalid STT response")
        return text.strip() or None

    async def synthesize(self, text):
        response = await self.http.post("https://api.x.ai/v1/tts", headers=self.headers,
            json={"text": text, "voice_id": self.voice, "language": "en",
                  "output_format": {"codec": "wav", "sample_rate": 16000}})
        response.raise_for_status()
        with wave.open(BytesIO(response.content), "rb") as wav:
            if (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) != (16000, 1, 2):
                raise ValueError("TTS must return 16 kHz mono PCM16 WAV")
        return response.content

    async def close(self):
        if self.owns:
            await self.http.aclose()
