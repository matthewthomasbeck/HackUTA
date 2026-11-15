"""Face prints: JPEG -> every face found, each as (bbox, normalized vector).

- `OpenCvFaceEmbedder`: OpenCV YuNet (detect + 5 landmarks) -> align -> SFace (128-d).
- `FakeFaceEmbedder`: deterministic stand-in for tests.
Pick with CALYPSO_FACE=opencv|fake.

The agent sends tight face crops (Haar boxes with no margin), so images are padded
before detection; YuNet needs some context around a face to find its landmarks.
"""
import hashlib
import logging
import threading
from typing import Protocol

import numpy as np

from ..config import Settings
from ..model_files import SFACE, YUNET, path_for
from ..models import BBox
from . import ModelUnavailable
from .vectors import normalize

_log = logging.getLogger("calypso.face")

MAX_SIDE = 640


class FaceEmbedder(Protocol):
    def embed_all(self, jpeg: bytes) -> list[tuple[BBox, np.ndarray]]: ...


def largest(faces: list[tuple[BBox, np.ndarray]]) -> np.ndarray | None:
    return max(faces, key=lambda f: f[0].w * f[0].h)[1] if faces else None


class OpenCvFaceEmbedder:
    def __init__(self, yunet_path: str, sface_path: str, score_threshold: float = 0.7) -> None:
        self.paths = (yunet_path, sface_path)
        self.score_threshold = score_threshold
        self._det = self._rec = None
        self._lock = threading.Lock()

    def _models(self):
        if self._det is None:
            try:
                import cv2
            except ImportError as exc:
                raise ModelUnavailable("opencv-python-headless is not installed") from exc
            yunet, sface = self.paths
            try:
                self._det = cv2.FaceDetectorYN.create(yunet, "", (320, 320), self.score_threshold, 0.3, 50)
                self._rec = cv2.FaceRecognizerSF.create(sface, "")
            except cv2.error as exc:
                self._det = self._rec = None
                raise ModelUnavailable(f"face models missing or invalid ({yunet}, {sface}); "
                                       "run: uv run python scripts/fetch_models.py") from exc
            _log.info("loaded face models %s, %s", yunet, sface)
        return self._det, self._rec

    def embed_all(self, jpeg: bytes) -> list[tuple[BBox, np.ndarray]]:
        with self._lock:
            self._models()  # raises ModelUnavailable (not ImportError) if OpenCV/models are missing
        import cv2

        img = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            return []
        h, w = img.shape[:2]
        scale = min(1.0, MAX_SIDE / max(h, w))
        if scale < 1.0:
            img = cv2.resize(img, (int(w * scale), int(h * scale)))
        pad = int(0.4 * max(img.shape[:2]))
        padded = cv2.copyMakeBorder(img, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=(0, 0, 0))
        with self._lock:  # OpenCV DNN objects are not thread-safe
            det, rec = self._models()
            det.setInputSize((padded.shape[1], padded.shape[0]))
            _, found = det.detect(padded)
            out = []
            for row in (found if found is not None else []):
                vec = rec.feature(rec.alignCrop(padded, row)).ravel()
                x, y, bw, bh = (float(v) for v in row[:4])
                box = BBox(x=int(max(0, (x - pad) / scale)), y=int(max(0, (y - pad) / scale)),
                           w=int(bw / scale), h=int(bh / scale))
                out.append((box, normalize(vec)))
        return out


class FakeFaceEmbedder:
    """`FAKEFACE:a,b` -> two faces with identities a and b; other bytes -> one face keyed on the bytes."""

    dim = 64

    def _vec(self, key: str) -> np.ndarray:
        seed = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "little")
        return normalize(np.random.default_rng(seed).standard_normal(self.dim))

    def embed_all(self, jpeg: bytes) -> list[tuple[BBox, np.ndarray]]:
        if not jpeg:
            return []
        if jpeg.startswith(b"FAKEFACE:"):
            keys = [k for k in jpeg[9:].decode().split(",") if k]
        elif jpeg.startswith(b"NOFACE"):
            keys = []
        else:
            keys = [hashlib.sha256(jpeg).hexdigest()]
        return [(BBox(x=i * 120, y=0, w=100, h=100), self._vec(k)) for i, k in enumerate(keys)]


def get_face_embedder(settings: Settings) -> FaceEmbedder:
    if settings.face == "fake":
        return FakeFaceEmbedder()
    return OpenCvFaceEmbedder(str(path_for(settings.models_dir, YUNET)), str(path_for(settings.models_dir, SFACE)))
