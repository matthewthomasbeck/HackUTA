#!/usr/bin/env bash
# Download Titanet-small ONNX for offline voice ID (sherpa-onnx).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODELS_DIR="$ROOT/models"
GALLERY_DIR="$ROOT/gallery"
URL="https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/nemo_en_titanet_small.onnx"

mkdir -p "$MODELS_DIR" "$GALLERY_DIR"
OUT="$MODELS_DIR/nemo_en_titanet_small.onnx"

if [[ -f "$OUT" ]]; then
  echo "already have $OUT"
else
  echo "downloading nemo_en_titanet_small.onnx (~38 MB)…"
  curl -L --fail -o "$OUT" "$URL"
  echo "saved $OUT"
fi

mkdir -p "$GALLERY_DIR/Sarah"
cat > "$GALLERY_DIR/README.md" <<'EOF'
Put enrollment WAVs here:

  gallery/<PersonName>/clip1.wav
  gallery/<PersonName>/clip2.wav

Requirements: 16 kHz mono PCM WAV, ≥ 1–2 s of that person's speech each.
PersonName is what journalctl will print when they are recognized.
EOF

echo
echo "Next:"
echo "  1. Install sherpa-onnx C libs and pass -DCALYPSO_SHERPA_ROOT=... to cmake"
echo "     (see https://k2-fsa.github.io/sherpa/onnx/install/index.html)"
echo "  2. Add enrollment WAVs under gallery/<Name>/"
echo "  3. Set MODE=offline and VOICE_MODEL_PATH=models/nemo_en_titanet_small.onnx in config/.env"
echo "  4. Build and run; watch: journalctl -u calypso-puck -f"
