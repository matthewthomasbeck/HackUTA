"""WAV decoding, 16 kHz mono conversion, silence trimming, and joining clips.

Pure numpy + stdlib `wave`, so it works the same on laptops and the server.
"""
import io
import wave

import numpy as np

RATE = 16000
FRAME_S = 0.03  # 30 ms analysis frames (same as the puck's VAD frames)


class AudioError(ValueError):
    """Not a readable PCM WAV."""


def decode_wav(data: bytes) -> np.ndarray:
    """Any PCM WAV (8/16/24/32-bit, any rate, any channels) -> 16 kHz mono float32 in [-1, 1]."""
    try:
        with wave.open(io.BytesIO(data), "rb") as w:
            channels, width, rate, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
            raw = w.readframes(n)
    except (wave.Error, EOFError, ValueError) as exc:
        raise AudioError(f"not a PCM WAV: {exc}") from exc
    if width == 1:
        x = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128) / 128
    elif width == 2:
        x = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768
    elif width == 3:
        b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
        v = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
        x = np.where(v >= 1 << 23, v - (1 << 24), v).astype(np.float32) / (1 << 23)
    elif width == 4:
        x = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2**31
    else:
        raise AudioError(f"unsupported sample width {width}")
    if channels > 1:
        x = x[: len(x) - len(x) % channels].reshape(-1, channels).mean(axis=1)
    return resample(x, rate)


def resample(x: np.ndarray, rate: int) -> np.ndarray:
    if rate == RATE or len(x) == 0:
        return x.astype(np.float32)
    if rate > RATE:  # crude anti-alias: moving average over the decimation factor
        k = int(round(rate / RATE))
        if k > 1:
            x = np.convolve(x, np.ones(k, dtype=np.float32) / k, mode="same")
    n_out = int(round(len(x) * RATE / rate))
    src = np.arange(len(x), dtype=np.float64) * (RATE / rate)
    return np.interp(np.arange(n_out, dtype=np.float64), src, x).astype(np.float32)


def trim_silence(x: np.ndarray, min_rms: float = 0.008) -> tuple[np.ndarray, float]:
    """Keep only voiced 30 ms frames (energy above an adaptive threshold).

    Returns (voiced audio, seconds of speech). Pure silence or a flat signal gives 0 s.
    """
    n = int(RATE * FRAME_S)
    frames = len(x) // n
    if frames == 0:
        return x[:0], 0.0
    f = x[: frames * n].reshape(frames, n)
    rms = np.sqrt((f * f).mean(axis=1))
    floor = float(np.percentile(rms, 10))  # background level (quietest frames)
    loud = float(np.percentile(rms, 90))   # speech level (loudest frames)
    # Above the background, but never above 30% of the speech level: a clip that's all
    # speech (no pauses) must not count as silence.
    thr = max(min_rms, min(floor * 2.5, loud * 0.3))
    voiced = rms > thr
    # One frame of hangover on each side so word edges aren't clipped (no wrap-around).
    keep = voiced.copy()
    keep[1:] |= voiced[:-1]
    keep[:-1] |= voiced[1:]
    return f[keep].ravel(), float(voiced.sum()) * FRAME_S


def encode_wav(x: np.ndarray) -> bytes:
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())
    return out.getvalue()


def concat_wavs(clips: list[bytes], max_seconds: float = 60.0) -> bytes | None:
    """Join several WAV clips into one 16 kHz mono WAV (unreadable clips are skipped)."""
    parts, total = [], 0
    for clip in clips:
        try:
            x = decode_wav(clip)
        except AudioError:
            continue
        room = int(max_seconds * RATE) - total
        if room <= 0:
            break
        parts.append(x[:room])
        total += len(parts[-1])
    return encode_wav(np.concatenate(parts)) if parts else None


def wav_seconds(data: bytes) -> float:
    try:
        with wave.open(io.BytesIO(data), "rb") as w:
            return w.getnframes() / float(w.getframerate())
    except (wave.Error, EOFError, ValueError):
        return 0.0
