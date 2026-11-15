#!/usr/bin/env bash
# Spike D: list ALSA devices, record 5 s from PUCK_MIC (or default), play back.
set -euo pipefail

echo "== arecord -l =="
arecord -l || true

DEVICE="${PUCK_MIC:-}"
OUT="${TMPDIR:-/tmp}/calypso_mic_check.wav"

if [[ -n "$DEVICE" ]]; then
  echo "== recording 5 s from PUCK_MIC=$DEVICE =="
  arecord -D "$DEVICE" -f S16_LE -r 16000 -c 1 -d 5 "$OUT"
else
  echo "== PUCK_MIC unset; recording 5 s from default device =="
  arecord -f S16_LE -r 16000 -c 1 -d 5 "$OUT"
fi

echo "== playback =="
aplay "$OUT" || true
echo "wrote $OUT — set PUCK_MIC in docs/spikes.md / .env"
