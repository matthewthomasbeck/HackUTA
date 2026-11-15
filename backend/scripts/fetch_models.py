"""Download the open-source face/voice model files and verify their SHA-256.

    cd backend && uv run python scripts/fetch_models.py          # into CALYPSO_MODELS_DIR (default data/models)
    uv run python scripts/fetch_models.py --dir /some/other/dir

Files that already exist with the right checksum are skipped.
"""
import argparse
import hashlib
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from calypso.config import Settings  # noqa: E402
from calypso.model_files import ALL, path_for  # noqa: E402


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def fetch(url: str, dest: Path) -> None:
    tmp = dest.with_suffix(dest.suffix + ".part")
    with httpx.stream("GET", url, follow_redirects=True, timeout=120) as r:
        r.raise_for_status()
        with tmp.open("wb") as f:
            for chunk in r.iter_bytes(1 << 20):
                f.write(chunk)
    tmp.replace(dest)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dir", default=Settings.from_env().models_dir)
    args = parser.parse_args()
    out = Path(args.dir)
    out.mkdir(parents=True, exist_ok=True)
    ok = True
    for model in ALL:
        dest = path_for(out, model)
        if dest.is_file() and sha256(dest) == model.sha256:
            print(f"ok       {dest}")
            continue
        print(f"download {model.filename} ({model.size / 1e6:.1f} MB)...", flush=True)
        fetch(model.url, dest)
        got = sha256(dest)
        if got != model.sha256:
            dest.unlink(missing_ok=True)
            print(f"FAILED   {model.filename}: checksum {got} != {model.sha256}", file=sys.stderr)
            ok = False
        else:
            print(f"ok       {dest}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
