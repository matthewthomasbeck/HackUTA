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

from .cards import CALL_SIZE, caption_cards, font, render
from .contract import Card

log = logging.getLogger("calypso.camera")
speech_log = logging.getLogger("calypso.speech")


def wav_bytes(pcm):
    out = BytesIO()
    with wave.open(out, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(pcm)
    return out.getvalue()


def group_frame_jpeg(image):
    """Preserve the whole group grid; do not select/crop one face locally."""
    image = image.convert("RGB")
    image.thumbnail((1280, 1280))
    out = BytesIO()
    image.save(out, "JPEG", quality=85)
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
        self.last_wav = None

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
        self.last_wav = None
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
        audio = wav_bytes(b"".join(chunks))
        text = await self.provider.transcribe(audio)
        self.last_wav = audio if text else None
        return text

    async def speak(self, text):
        self.caption(text)
        self.speaking = True
        self.clear()
        started = time.monotonic()
        stage = "synthesizing"
        speech_log.info("speech_synthesis_started characters=%d", len(text))
        try:
            audio = await self.provider.synthesize(text)
            with wave.open(BytesIO(audio), "rb") as wav:
                if (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) != (16000, 1, 2):
                    raise ValueError("Expected 16 kHz mono PCM16 TTS")
                stage = "playing"
                speech_log.info("speech_playback_started audio_s=%.2f", wav.getnframes() / wav.getframerate())
                while pcm := wav.readframes(320):
                    await self.source.capture_frame(rtc.AudioFrame(pcm, 16000, 1, len(pcm) // 2))
            await self.source.wait_for_playout()
            speech_log.info("speech_playback_complete elapsed_s=%.2f", time.monotonic() - started)
            await asyncio.sleep(0.25)
        except asyncio.CancelledError:
            speech_log.warning("speech_cancelled stage=%s elapsed_s=%.2f", stage, time.monotonic() - started)
            raise
        except Exception as error:
            speech_log.error("speech_failed stage=%s error_type=%s", stage, type(error).__name__)
            raise
        finally:
            self.speaking = False
            self.clear()


class Publisher:
    def __init__(self, room, scheduler=None, *, on_shown=lambda card: None):
        self.room, self.scheduler = room, scheduler
        self.status = Card(kind="memory", title="Connecting…", lines=[])
        self.source = rtc.VideoSource(*CALL_SIZE)
        self.audio = rtc.AudioSource(16000, 1)
        self.publications = []
        self.on_shown = on_shown
        self.camera_status = ""
        self.pinned_card = None
        self.caption_pages = []
        self.caption_started = 0

    def caption(self, text):
        self.caption_pages = caption_cards(text)
        self.caption_started = time.monotonic()
        self.status = self.caption_pages[0]

    async def start(self):
        for track, kind in [(rtc.LocalVideoTrack.create_video_track("calypso-cards", self.source), rtc.TrackSource.SOURCE_CAMERA),
                            (rtc.LocalAudioTrack.create_audio_track("calypso-voice", self.audio), rtc.TrackSource.SOURCE_MICROPHONE)]:
            options = rtc.TrackPublishOptions(source=kind)
            if kind == rtc.TrackSource.SOURCE_CAMERA:
                options.video_codec = rtc.VideoCodec.H264
                options.video_encoding.max_bitrate = 2_500_000
                options.video_encoding.max_framerate = 5
                options.simulcast = False
                options.degradation_preference = 2  # MAINTAIN_RESOLUTION
            pub = await self.room.local_participant.publish_track(track, options)
            self.publications.append(pub.sid)

    async def run(self):
        previous, previous_card, frame = None, None, None
        while True:
            card = self.scheduler.current() if self.scheduler else None
            if self.caption_pages:
                page = min(int((time.monotonic() - self.caption_started) / 5), len(self.caption_pages) - 1)
                caption = self.caption_pages[page]
            else:
                caption = self.status
            card = self.pinned_card or card or caption
            key = (card.model_dump_json() if card else "idle", self.camera_status)
            if key != previous:
                picture = render(card, {}, size=CALL_SIZE)
                draw = ImageDraw.Draw(picture)
                if self.camera_status:
                    status = self.camera_status.replace("Camera: ", "").replace(" clear face samples", " face samples")
                    draw.text((48, 1138), status, font=font(26), fill=(112, 224, 199), anchor="lt")
                draw.text((48, 1200), "TEST MODE", font=font(26), fill=(255, 206, 105), anchor="lt")
                frame = rtc.VideoFrame(*CALL_SIZE, rtc.VideoBufferType.RGB24, picture.tobytes())
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


async def wait_bridge_ready(room, timeout=60, *, confirmed_bridge=None):
    ready = asyncio.Event()
    def changed(*_):
        try:
            if json.loads(room.metadata or "{}").get("chert_bridge_ready") is True:
                ready.set()
        except (ValueError, TypeError):
            pass
    room.on("room_metadata_changed", changed)
    changed()
    async def metadata_ready():
        await ready.wait()
        return "room_metadata"

    tasks = [asyncio.create_task(metadata_ready())]
    if confirmed_bridge is not None:
        tasks.append(asyncio.create_task(confirmed_bridge()))
    try:
        done, _ = await asyncio.wait(tasks, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
        if not done:
            raise TimeoutError("No confirmed Chert bridge readiness arrived")
        source = next(iter(done)).result()
        logging.getLogger("calypso.live").info("bridge_ready source=%s", source)
        return source
    finally:
        room.off("room_metadata_changed", changed)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


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
