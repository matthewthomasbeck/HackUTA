"""Real TitaNet / YuNet+SFace checks. Opt-in: skipped unless models and sample media are present.

    cd backend && uv run python scripts/fetch_models.py
    CALYPSO_LIVE_AUDIO=<dir of speaker-N.wav clips>  CALYPSO_LIVE_FACES=<dir with photos of 2+ people> \
      uv run --group dev pytest -m live -v

Audio clips are grouped by the text before the first "-" (e.g. sarah-1.wav, sarah-2.wav, tom-1.wav).
Face photos likewise (sarah-1.jpg, tom-1.jpg); each must contain exactly one face.
"""
import itertools
import os
from pathlib import Path

import pytest

from calypso.model_files import SFACE, TITANET_SMALL, YUNET, path_for

MODELS = Path(os.environ.get("CALYPSO_LIVE_MODELS", Path(__file__).resolve().parents[1] / "data" / "models"))
pytestmark = pytest.mark.live


def _groups(folder: str | None, patterns: tuple[str, ...]):
    if not folder or not Path(folder).is_dir():
        pytest.skip("sample media folder not set")
    files = sorted(f for p in patterns for f in Path(folder).glob(p))
    groups = {}
    for f in files:
        groups.setdefault(f.stem.split("-")[0], []).append(f)
    if len(groups) < 2:
        pytest.skip("need samples from at least 2 people")
    return files


def _separation(vectors: dict[Path, "object"]):
    same, diff = [], []
    for a, b in itertools.combinations(vectors, 2):
        s = float(vectors[a] @ vectors[b])
        (same if a.stem.split("-")[0] == b.stem.split("-")[0] else diff).append(s)
    return same, diff


def test_titanet_separates_speakers():
    if not path_for(MODELS, TITANET_SMALL).is_file():
        pytest.skip("voice model not downloaded")
    from calypso.identity.voice import SherpaVoiceEmbedder, embed_wav

    files = _groups(os.environ.get("CALYPSO_LIVE_AUDIO"), ("*.wav",))
    emb = SherpaVoiceEmbedder(str(path_for(MODELS, TITANET_SMALL)))
    vecs = {f: embed_wav(emb, f.read_bytes(), 1.0)[0] for f in files}
    vecs = {f: v for f, v in vecs.items() if v is not None}
    same, diff = _separation(vecs)
    print(f"\nvoice: same min {min(same):.2f}  different max {max(diff):.2f}")
    assert min(same) > max(diff)


def test_sface_separates_faces():
    if not (path_for(MODELS, YUNET).is_file() and path_for(MODELS, SFACE).is_file()):
        pytest.skip("face models not downloaded")
    from calypso.identity.face import OpenCvFaceEmbedder

    files = _groups(os.environ.get("CALYPSO_LIVE_FACES"), ("*.jpg", "*.jpeg", "*.png"))
    emb = OpenCvFaceEmbedder(str(path_for(MODELS, YUNET)), str(path_for(MODELS, SFACE)))
    vecs = {}
    for f in files:
        found = emb.embed_all(f.read_bytes())
        assert len(found) == 1, f"{f.name}: expected one face, found {len(found)}"
        vecs[f] = found[0][1]
    same, diff = _separation(vecs)
    print(f"\nface: same min {min(same) if same else float('nan'):.2f}  different max {max(diff):.2f}")
    assert max(diff) < 0.40 and (not same or min(same) > max(diff))
