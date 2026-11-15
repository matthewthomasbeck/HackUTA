"""Settings from environment variables, with defaults.

Read once per app (and once per worker job) via `Settings.from_env()`, so tests
can set env vars with monkeypatch before building the app.
"""
import logging
import os
from dataclasses import dataclass
from pathlib import Path

_log = logging.getLogger("calypso.config")

REPO_ROOT = Path(__file__).resolve().parents[2]


def _f(key: str, default: float) -> float:
    return float(os.environ.get(key, default))


@dataclass(frozen=True)
class Settings:
    api_token: str
    db_path: str
    data_dir: str
    tz: str
    public_url: str  # must equal the iOS app's API_BASE_URL (https:// when deployed)
    jobs: str  # inline | rq
    storage: str  # local | s3
    redis_url: str
    rq_queue: str
    backend_url: str  # where the RQ worker posts dashboard events
    s3_endpoint: str
    enrollment_bucket: str
    dashboard_dir: str
    max_audio_bytes: int
    max_image_bytes: int
    face: str  # opencv | fake
    voice: str  # sherpa | fake
    models_dir: str
    stt: str  # grok | fake
    xai_api_key: str
    summarizer: str  # claude | fake
    detector: str  # claude | fake
    home_label: str
    # Thresholds: provisional starting values, tuned on real FaceTime/puck data.
    face_match: float
    face_margin: float
    voice_match: float
    voice_margin: float
    voice_learn_max: float
    voice_min_speech_s: float
    place_conf_min: float
    recall_min: float

    @classmethod
    def from_env(cls) -> "Settings":
        e = os.environ.get
        data_dir = e("CALYPSO_DATA_DIR", "data")
        return cls(
            api_token=e("CALYPSO_API_TOKEN", ""),
            db_path=e("CALYPSO_DB", str(Path(data_dir) / "calypso.db")),
            data_dir=data_dir,
            tz=e("CALYPSO_TZ", "America/Chicago"),
            public_url=e("CALYPSO_PUBLIC_URL", "").rstrip("/"),
            jobs=e("CALYPSO_JOBS", "inline"),
            storage=e("CALYPSO_STORAGE", "local"),
            redis_url=e("CALYPSO_REDIS_URL", "redis://127.0.0.1:6379/0"),
            rq_queue=e("CALYPSO_RQ_QUEUE", "recordings"),
            backend_url=e("CALYPSO_BACKEND_URL", "http://127.0.0.1:8000").rstrip("/"),
            s3_endpoint=e("S3_ENDPOINT_URL", "https://atl2.vultrobjects.com"),
            enrollment_bucket=e("ENROLLMENT_BUCKET", ""),
            dashboard_dir=e("CALYPSO_DASHBOARD_DIR", str(REPO_ROOT / "dashboard")),
            max_audio_bytes=int(e("CALYPSO_MAX_AUDIO_BYTES", 5 * 1024 * 1024)),
            max_image_bytes=int(e("CALYPSO_MAX_IMAGE_BYTES", 15 * 1024 * 1024)),
            face=e("CALYPSO_FACE", "opencv"),
            voice=e("CALYPSO_VOICE", "sherpa"),
            models_dir=e("CALYPSO_MODELS_DIR", str(Path(data_dir) / "models")),
            stt=e("CALYPSO_STT") or ("grok" if e("XAI_API_KEY") else "fake"),
            xai_api_key=e("XAI_API_KEY", ""),
            summarizer=e("CALYPSO_SUMMARIZER") or ("claude" if e("ANTHROPIC_API_KEY") else "fake"),
            detector=e("CALYPSO_DETECTOR") or ("claude" if e("ANTHROPIC_API_KEY") else "fake"),
            home_label=e("CALYPSO_HOME_LABEL", "Home"),
            # SFace reference same-person cosine is 0.363; TitaNet sample test: same >= 0.66, different <= 0.37.
            face_match=_f("FACE_MATCH", 0.40),
            face_margin=_f("FACE_MARGIN", 0.08),
            voice_match=_f("VOICE_MATCH", 0.50),
            voice_margin=_f("VOICE_MARGIN", 0.08),
            voice_learn_max=_f("VOICE_LEARN_MAX", 0.30),
            voice_min_speech_s=_f("VOICE_MIN_SPEECH_S", 2.0),
            place_conf_min=_f("PLACE_CONF_MIN", 0.6),
            recall_min=_f("RECALL_MIN", 0.35),
        )

    @property
    def tmp_dir(self) -> Path:
        return Path(self.data_dir) / "tmp"

    def warn_if_misconfigured(self) -> None:
        if not self.api_token:
            _log.warning("CALYPSO_API_TOKEN is empty: every authenticated request will get 401")
        url = self.public_url
        local = any(h in url for h in ("localhost", "127.0.0.1", "192.168.", "10.", ".ts.net"))
        if url and not url.startswith("https://") and not local:
            _log.warning("CALYPSO_PUBLIC_URL is not https (%s): iOS will not load images", url)
        if self.jobs not in ("inline", "rq"):
            _log.warning("unknown CALYPSO_JOBS=%r, using inline", self.jobs)
        if self.storage == "s3" and not self.enrollment_bucket:
            _log.warning("CALYPSO_STORAGE=s3 but ENROLLMENT_BUCKET is empty")
        from .model_files import SFACE, TITANET_SMALL, YUNET, path_for

        needed = ([TITANET_SMALL] if self.voice == "sherpa" else []) + ([YUNET, SFACE] if self.face == "opencv" else [])
        missing = [m.filename for m in needed if not path_for(self.models_dir, m).is_file()]
        if missing:
            _log.warning("model files missing in %s: %s. Face/voice matching is off until you run "
                         "`uv run python scripts/fetch_models.py`", self.models_dir, ", ".join(missing))
