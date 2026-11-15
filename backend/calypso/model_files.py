"""Open-source model files the backend downloads (not built by the team).

- TitaNet-small (NVIDIA NeMo, exported to ONNX by the sherpa-onnx project): voiceprints.
- YuNet (OpenCV Zoo): face detection + 5 landmarks.
- SFace (OpenCV Zoo): face prints from an aligned face.

`uv run python scripts/fetch_models.py` downloads them into CALYPSO_MODELS_DIR
and checks each SHA-256 against the value pinned here.
"""
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ModelFile:
    filename: str
    url: str
    sha256: str
    size: int


TITANET_SMALL = ModelFile(
    "nemo_en_titanet_small.onnx",
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/nemo_en_titanet_small.onnx",
    "ad4a1802485d8b34c722d2a9d04249662f2ece5d28a7a039063ca22f515a789e",
    40257283,
)
YUNET = ModelFile(
    "face_detection_yunet_2023mar.onnx",
    "https://huggingface.co/opencv/face_detection_yunet/resolve/main/face_detection_yunet_2023mar.onnx",
    "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
    232589,
)
SFACE = ModelFile(
    "face_recognition_sface_2021dec.onnx",
    "https://huggingface.co/opencv/face_recognition_sface/resolve/main/face_recognition_sface_2021dec.onnx",
    "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
    38696353,
)
ALL = (TITANET_SMALL, YUNET, SFACE)


def path_for(models_dir: str | Path, model: ModelFile) -> Path:
    return Path(models_dir) / model.filename
