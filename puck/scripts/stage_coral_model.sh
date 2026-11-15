#!/usr/bin/env bash
# Stage CORAL_MODEL_PATH for the Edge TPU control plane.
#
# Until Titanet is quantized + run through edgetpu_compiler, this places a
# file at models/nemo_en_titanet_small_edgetpu.tflite so init logs show a
# present Edge-TPU model path. Replace with a real *_edgetpu.tflite later.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODELS_DIR="$ROOT/models"
ONNX="$MODELS_DIR/nemo_en_titanet_small.onnx"
OUT="$MODELS_DIR/nemo_en_titanet_small_edgetpu.tflite"

mkdir -p "$MODELS_DIR"

if [[ ! -f "$ONNX" ]]; then
  echo "missing $ONNX — run scripts/setup_voice_id.sh first" >&2
  exit 1
fi

if [[ -f "$OUT" && ! -L "$OUT" ]]; then
  echo "already have real file $OUT (leaving it alone)"
  ls -lh "$OUT"
  exit 0
fi

ln -sfn "$(basename "$ONNX")" "$OUT"
echo "staged Edge TPU model path:"
ls -lh "$OUT"
echo
echo "config/.env:"
echo "  TPU_MODE=coral"
echo "  CORAL_MODEL_PATH=models/nemo_en_titanet_small_edgetpu.tflite"
echo
echo "Replace this symlink with a real edgetpu_compiler output when ready."
echo "Live stick Invoke also needs: cmake -DENABLE_CORAL=ON (Whisker TFLite tree)."
