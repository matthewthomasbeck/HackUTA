#!/usr/bin/env bash
# Convert Titanet-small → int8 TFLite → Edge TPU (*_edgetpu.tflite).
#
# Pipeline:
#   1) ensure models/nemo_en_titanet_small.onnx
#   2) ONNX → TFLite via onnx2tf (prefers *_integer_quant.tflite)
#   3) edgetpu_compiler → models/nemo_en_titanet_small_edgetpu.tflite
#
# Prefer an x86_64 Linux box/VM (edgetpu_compiler + TF wheels). On a Pi, run
# steps 1–2 if you can, or convert elsewhere and copy the .tflite over.
#
# Usage:
#   ./convert_titanet_coral.sh
#   ONNX_IN=/path/to/encoder.onnx ./convert_titanet_coral.sh
#   ./convert_titanet_coral.sh --skip-edgetpu
#   ./convert_titanet_coral.sh --force
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
MODELS_DIR="$ROOT/models"
BUILD_DIR="$MODELS_DIR/coral_build"
VENV_DIR="$BUILD_DIR/venv"
ONNX_URL="https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/nemo_en_titanet_small.onnx"

ONNX_IN="${ONNX_IN:-$MODELS_DIR/nemo_en_titanet_small.onnx}"
FLOAT_TFLITE="${FLOAT_TFLITE:-$BUILD_DIR/titanet_float.tflite}"
INT8_TFLITE="${INT8_TFLITE:-$BUILD_DIR/titanet_int8.tflite}"
EDGETPU_OUT="${EDGETPU_OUT:-$MODELS_DIR/nemo_en_titanet_small_edgetpu.tflite}"
SKIP_EDGETPU=0
FORCE=0

for arg in "$@"; do
  case "$arg" in
    --skip-edgetpu) SKIP_EDGETPU=1 ;;
    --force) FORCE=1 ;;
    -h|--help)
      sed -n '2,18p' "$0"
      exit 0
      ;;
    *)
      echo "unknown arg: $arg (try --help)" >&2
      exit 2
      ;;
  esac
done

log() { printf '==> %s\n' "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

arch="$(uname -m)"
os="$(uname -s)"
log "host $os/$arch"
if [[ "$os" != "Linux" ]]; then
  log "warning: edgetpu_compiler is Linux/x86_64-oriented; may stop before Edge TPU"
fi
if [[ "$arch" != "x86_64" && "$arch" != "amd64" ]]; then
  log "warning: converting on $arch is fragile (TF / edgetpu_compiler)"
fi

mkdir -p "$MODELS_DIR" "$BUILD_DIR"

# ── 1) ONNX ──────────────────────────────────────────────────────────────
if [[ ! -f "$ONNX_IN" ]]; then
  log "downloading Titanet ONNX → $ONNX_IN"
  curl -L --fail -o "$ONNX_IN" "$ONNX_URL"
fi
[[ -f "$ONNX_IN" ]] || die "missing $ONNX_IN"
log "ONNX: $ONNX_IN ($(wc -c <"$ONNX_IN" | tr -d ' ') bytes)"

# ── 2) venv + deps ───────────────────────────────────────────────────────
if [[ ! -d "$VENV_DIR" ]]; then
  log "creating venv $VENV_DIR"
  python3 -m venv "$VENV_DIR"
fi
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
pip install -q --upgrade pip wheel
log "installing onnx / onnx2tf / tensorflow (can take a few minutes)"
pip install -q "onnx>=1.15" "onnx2tf>=1.22" "tensorflow>=2.15,<2.20" numpy

# ── 3) ONNX → TFLite ─────────────────────────────────────────────────────
ONNX2TF_OUT="$BUILD_DIR/onnx2tf_out"
if [[ "$FORCE" -eq 1 || ! -f "$INT8_TFLITE" ]]; then
  log "onnx2tf: $ONNX_IN → $ONNX2TF_OUT"
  rm -rf "$ONNX2TF_OUT"
  if ! onnx2tf -i "$ONNX_IN" -o "$ONNX2TF_OUT" -b 1; then
    cat >&2 <<'EOF'

onnx2tf failed. The sherpa Titanet ONNX often has awkward I/O (waveform /
dynamic shapes). Export a NeMo encoder-only ONNX with fixed mel [1,80,T]:

  # on a machine with nemo_toolkit[asr]
  python - <<'PY'
  from nemo.collections.asr.models import EncDecSpeakerLabelModel
  import torch
  m = EncDecSpeakerLabelModel.from_pretrained("titanet_small").eval().cpu()
  T = 300
  mel = torch.randn(1, 80, T)
  length = torch.tensor([T])
  torch.onnx.export(
      m.encoder, (mel, length), "titanet_encoder.onnx",
      input_names=["audio_signal", "length"],
      output_names=["embs"], opset_version=17, dynamo=False,
  )
  PY

Then:
  ONNX_IN=./titanet_encoder.onnx ./convert_titanet_coral.sh --force

EOF
    exit 1
  fi

  shopt -s nullglob
  int8_candidates=(
    "$ONNX2TF_OUT"/*_full_integer_quant.tflite
    "$ONNX2TF_OUT"/*_integer_quant.tflite
  )
  float_candidates=("$ONNX2TF_OUT"/*.tflite)
  shopt -u nullglob

  if [[ ${#int8_candidates[@]} -gt 0 ]]; then
    cp -f "${int8_candidates[0]}" "$INT8_TFLITE"
    log "int8 TFLite: $INT8_TFLITE (from $(basename "${int8_candidates[0]}"))"
  else
    die "onnx2tf produced no *_integer_quant.tflite under $ONNX2TF_OUT — inspect that dir"
  fi

  # Keep a float copy for debugging when present.
  for f in "${float_candidates[@]}"; do
    case "$f" in
      *integer_quant*) continue ;;
    esac
    cp -f "$f" "$FLOAT_TFLITE"
    log "float TFLite: $FLOAT_TFLITE"
    break
  done
else
  log "reusing $INT8_TFLITE (--force to rebuild)"
fi
[[ -f "$INT8_TFLITE" ]] || die "missing $INT8_TFLITE"

# ── 4) edgetpu_compiler ──────────────────────────────────────────────────
if [[ "$SKIP_EDGETPU" -eq 1 ]]; then
  log "skipping edgetpu_compiler (--skip-edgetpu)"
  log "int8 model ready: $INT8_TFLITE"
  exit 0
fi

COMPILER="$(command -v edgetpu_compiler || true)"
if [[ -z "$COMPILER" ]]; then
  cat >&2 <<EOF

edgetpu_compiler not found on PATH.

Debian/Ubuntu x86_64:
  curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg \\
    | sudo gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg
  echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt coral-edgetpu-stable main" \\
    | sudo tee /etc/apt/sources.list.d/coral-edgetpu.list
  sudo apt-get update && sudo apt-get install -y edgetpu-compiler

Then re-run:
  $0
Or on that machine:
  edgetpu_compiler -s -o $BUILD_DIR $INT8_TFLITE
  cp $BUILD_DIR/*_edgetpu.tflite $EDGETPU_OUT

Int8 artifact is ready at:
  $INT8_TFLITE

EOF
  exit 1
fi

log "edgetpu_compiler → $BUILD_DIR"
rm -f "$BUILD_DIR"/*_edgetpu.tflite
"$COMPILER" -s -o "$BUILD_DIR" "$INT8_TFLITE"

shopt -s nullglob
compiled=("$BUILD_DIR"/*_edgetpu.tflite)
shopt -u nullglob
[[ ${#compiled[@]} -gt 0 ]] || die "edgetpu_compiler produced no *_edgetpu.tflite — see logs in $BUILD_DIR"

cp -f "${compiled[0]}" "$EDGETPU_OUT"
log "staged $EDGETPU_OUT"

shopt -s nullglob
logs=("$BUILD_DIR"/*_edgetpu.log "$BUILD_DIR"/*.log)
shopt -u nullglob
if [[ ${#logs[@]} -gt 0 ]]; then
  log "compiler report (ops on TPU vs CPU):"
  for lg in "${logs[@]}"; do
    [[ -f "$lg" ]] || continue
    echo "--- $lg ---"
    sed -n '1,80p' "$lg" || true
  done
fi

cat <<EOF

Done.
  int8:    $INT8_TFLITE
  edgetpu: $EDGETPU_OUT

config/.env:
  TPU_MODE=coral
  CORAL_MODEL_PATH=models/nemo_en_titanet_small_edgetpu.tflite

Rebuild puck with -DENABLE_CORAL=ON for live stick Invoke, then re-enroll
the gallery (int8 embeddings ≠ float sherpa).

EOF
