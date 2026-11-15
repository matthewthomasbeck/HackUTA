"""Voiceprints: 16 kHz speech -> a normalized vector.

- `SherpaVoiceEmbedder`: NVIDIA NeMo TitaNet-small via sherpa-onnx (CPU, no PyTorch).
- `FakeVoiceEmbedder`: deterministic stand-in for tests (keyed on the clip's dominant pitch).
Pick with CALYPSO_VOICE=sherpa|fake.
"""
import hashlib
import logging
import threading
from typing import Protocol

import numpy as np

from ..config import Settings
from ..model_files import TITANET_SMALL, path_for
from . import ModelUnavailable
from .audio import RATE, decode_wav, trim_silence
from .vectors import normalize

_log = logging.getLogger("calypso.voice")


class VoiceEmbedder(Protocol):
    dim: int

    def embed_samples(self, x: np.ndarray) -> np.ndarray: ...


def embed_wav(embedder: VoiceEmbedder, wav: bytes, min_speech_s: float) -> tuple[np.ndarray | None, float]:
    """WAV -> (voiceprint or None, seconds of speech). None when there's too little speech.

    Raises `AudioError` for unreadable audio and `ModelUnavailable` if the model can't load.
    """
    speech, seconds = trim_silence(decode_wav(wav))
    if seconds < min_speech_s:
        return None, seconds
    return normalize(embedder.embed_samples(speech)), seconds


class SherpaVoiceEmbedder:
    dim = 192

    def __init__(self, model_path: str, num_threads: int = 2) -> None:
        self.model_path = model_path
        self.num_threads = num_threads
        self._ex = None
        self._lock = threading.Lock()

    def _extractor(self):
        if self._ex is None:
            try:
                import sherpa_onnx
            except ImportError as exc:
                raise ModelUnavailable("sherpa-onnx is not installed") from exc
            cfg = sherpa_onnx.SpeakerEmbeddingExtractorConfig(
                model=self.model_path, num_threads=self.num_threads, provider="cpu")
            if not cfg.validate():
                raise ModelUnavailable(f"voice model missing or invalid: {self.model_path} "
                                       "(run: uv run python scripts/fetch_models.py)")
            self._ex = sherpa_onnx.SpeakerEmbeddingExtractor(cfg)
            self.dim = self._ex.dim
            _log.info("loaded voice model %s (dim=%d)", self.model_path, self.dim)
        return self._ex

    def embed_samples(self, x: np.ndarray) -> np.ndarray:
        with self._lock:  # one extractor, used from the API thread pool and the worker
            ex = self._extractor()
            stream = ex.create_stream()
            stream.accept_waveform(sample_rate=RATE, waveform=np.ascontiguousarray(x, dtype=np.float32))
            stream.input_finished()
            return np.asarray(ex.compute(stream), dtype=np.float32)


class FakeVoiceEmbedder:
    """Same dominant pitch -> same vector; different pitch -> a near-orthogonal vector."""

    dim = 64

    def embed_samples(self, x: np.ndarray) -> np.ndarray:
        spectrum = np.abs(np.fft.rfft(x))
        peak_hz = float(np.argmax(spectrum[1:]) + 1) * RATE / len(x)
        key = str(int(round(peak_hz / 25.0)))
        seed = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "little")
        return np.random.default_rng(seed).standard_normal(self.dim).astype(np.float32)


def get_voice_embedder(settings: Settings) -> VoiceEmbedder:
    if settings.voice == "fake":
        return FakeVoiceEmbedder()
    return SherpaVoiceEmbedder(str(path_for(settings.models_dir, TITANET_SMALL)))
