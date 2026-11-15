"""LiveKit media adapters used by the supervised stage 1 call test."""

import asyncio
from collections import deque
from io import BytesIO
import json
import logging
import subprocess
import sys
import time
import wave

from livekit import rtc
import numpy as np
from PIL import Image, ImageDraw

from .cards import font, idle_frame, render
from .contract import Card

log = logging.getLogger("calypso.camera")


def wav_bytes(pcm):
    out = BytesIO()
    with wave.open(out, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(pcm)
    return out.getvalue()


class FaceCropper:
    def crop(self, image):
        image = image.copy()
        image.thumbnail((640, 640))
        out = BytesIO()
        image.save(out, "JPEG", quality=90)
        try:
            result = subprocess.run([sys.executable, "-m", "calypso_agent.face_crop"],
                input=out.getvalue(), capture_output=True, timeout=5, check=True)
        except (subprocess.SubprocessError, OSError) as error:
            raise RuntimeError("Isolated face detector failed") from error
        return result.stdout or None


class CameraSamples:
    def __init__(self, cropper=None):
        self.cropper = cropper or FaceCropper()
        self.samples = deque(maxlen=3)

    async def add(self, image):
        crop = await asyncio.to_thread(self.cropper.crop, image)
        if crop is None:
            self.samples.clear()
        else:
            self.samples.append((time.monotonic(), crop))
        return crop

    async def collect(self):
        if len(self.samples) != 3 or time.monotonic() - self.samples[0][0] > 6:
            raise ValueError("Keep one face clearly visible for three seconds before confirming")
        return [crop for _, crop in self.samples]

    @property
    def progress(self):
        if self.samples and time.monotonic() - self.samples[0][0] > 6:
            return 0
        return len(self.samples)


class RoomSpeech:
    def __init__(self, provider, source, *, caption=lambda text: None, rms_threshold=0.012):
        self.provider, self.source, self.caption = provider, source, caption
        self.frames = asyncio.Queue(maxsize=100)
        self.rms_threshold = rms_threshold
        self.speaking = False

    def feed(self, pcm):
        if self.speaking:
            return
        if self.frames.full():
            self.frames.get_nowait()
        self.frames.put_nowait(pcm)

    def clear(self):
        while not self.frames.empty():
            self.frames.get_nowait()

    async def listen(self, timeout_s=20):
        self.clear()
        deadline = time.monotonic() + timeout_s
        chunks, voiced_s, quiet_s, total_s = [], 0, 0, 0
        while time.monotonic() < deadline:
            try:
                pcm = await asyncio.wait_for(self.frames.get(), max(0.001, deadline - time.monotonic()))
            except TimeoutError:
                break
            values = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768
            duration = len(values) / 16000
            voiced = bool(len(values)) and float(np.sqrt(np.mean(values * values))) >= self.rms_threshold
            if voiced:
                voiced_s += duration
                quiet_s = 0
            elif not chunks:
                continue
            else:
                quiet_s += duration
            chunks.append(pcm)
            total_s += duration
            if total_s >= 12 or (quiet_s >= 0.8 and voiced_s >= 0.3):
                break
        if voiced_s < 0.3:
            return None
        return await self.provider.transcribe(wav_bytes(b"".join(chunks)))

    async def speak(self, text):
        self.caption(text)
        self.speaking = True
        self.clear()
        try:
            audio = await self.provider.synthesize(text)
            with wave.open(BytesIO(audio), "rb") as wav:
                if (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) != (16000, 1, 2):
                    raise ValueError("Expected 16 kHz mono PCM16 TTS")
                while pcm := wav.readframes(320):
                    await self.source.capture_frame(rtc.AudioFrame(pcm, 16000, 1, len(pcm) // 2))
            await self.source.wait_for_playout()
            await asyncio.sleep(0.25)
        finally:
            self.speaking = False
            self.clear()


class Publisher:
    def __init__(self, room, scheduler=None, *, on_shown=lambda card: None):
        self.room, self.scheduler = room, scheduler
        self.status = Card(kind="memory", title="Connecting…", lines=[])
        self.source = rtc.VideoSource(1280, 720)
        self.audio = rtc.AudioSource(16000, 1)
        self.publications = []
        self.on_shown = on_shown
        self.camera_status = ""

    def caption(self, text):
        self.status = Card(kind="memory", title="Calypso⁻¹", lines=[text])

    async def start(self):
        for track, kind in [(rtc.LocalVideoTrack.create_video_track("calypso-cards", self.source), rtc.TrackSource.SOURCE_CAMERA),
                            (rtc.LocalAudioTrack.create_audio_track("calypso-voice", self.audio), rtc.TrackSource.SOURCE_MICROPHONE)]:
            options = rtc.TrackPublishOptions(source=kind)
            pub = await self.room.local_participant.publish_track(track, options)
            self.publications.append(pub.sid)

    async def run(self):
        previous, previous_card, frame = None, None, None
        while True:
            card = self.scheduler.current() if self.scheduler else None
            card = card or self.status
            key = (card.model_dump_json() if card else "idle", self.camera_status)
            if key != previous:
                picture = render(card, {}) if card else idle_frame()
                draw = ImageDraw.Draw(picture)
                if self.camera_status:
                    draw.text((64, 590), self.camera_status, font=font(28), fill=(112, 224, 199), anchor="lt")
                draw.text((64, 640), "STAGE 1 TEST · controlled recognition", font=font(30), fill=(255, 206, 105), anchor="lt")
                frame = rtc.VideoFrame(1280, 720, rtc.VideoBufferType.RGB24, picture.tobytes())
                previous = key
                if key[0] != previous_card:
                    self.on_shown(card)
                    previous_card = key[0]
            self.source.capture_frame(frame)
            await asyncio.sleep(0.2)

    async def close(self):
        for sid in self.publications:
            try:
                await self.room.local_participant.unpublish_track(sid)
            except Exception:
                pass  # Already disconnected rooms have no remaining publications.
        await self.audio.aclose()
        await self.source.aclose()


async def wait_bridge_ready(room, timeout=60):
    ready = asyncio.Event()
    def changed(*_):
        try:
            if json.loads(room.metadata or "{}").get("chert_bridge_ready") is True:
                ready.set()
        except (ValueError, TypeError):
            pass
    room.on("room_metadata_changed", changed)
    changed()
    try:
        await asyncio.wait_for(ready.wait(), timeout)
    finally:
        room.off("room_metadata_changed", changed)


async def video_frames(track, callback):
    stream = rtc.VideoStream(track, capacity=1, format=rtc.VideoBufferType.RGB24)
    last = float("-inf")
    try:
        async for event in stream:
            now = time.monotonic()
            if now - last < 1:
                continue
            last = now
            frame = event.frame
            image = Image.frombytes("RGB", (frame.width, frame.height), bytes(frame.data))
            await callback(image)
    finally:
        await stream.aclose()


async def audio_frames(track, speech):
    stream = rtc.AudioStream(track, sample_rate=16000, num_channels=1, frame_size_ms=20, capacity=100)
    try:
        async for event in stream:
            speech.feed(bytes(event.frame.data))
    finally:
        await stream.aclose()
