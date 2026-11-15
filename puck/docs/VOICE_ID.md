# Offline voice fingerprint (MVP)

## Decision

| Piece | Choice | Why |
|---|---|---|
| Model | **`nemo_en_titanet_small.onnx`** | English, ~38 MB, 192-d embedding, already exported for sherpa |
| Runtime | **sherpa-onnx** (CPU, `provider=cpu`) | Handles mel features + embedding; C API fits this puck |
| Match | Cosine similarity vs local gallery, threshold **0.55** (tunable) | Same idea as backend `VOICE_MATCH`; uncertain below threshold |
| Accelerator | **Coral via `TPU_MODE=coral`** | Edge TPU control plane in `Accelerators`; see [`CORAL_TPU.md`](CORAL_TPU.md) |

Not using WeSpeaker/CAM++ for now (also fine later). Not tying to backend ECAPA until we need cloud↔device embedding parity.

## How we use it

1. At startup, load the ONNX model via sherpa `SpeakerEmbeddingExtractor` (host embedder).
2. If `TPU_MODE=coral`, arm `Accelerators` with `CORAL_MODEL_PATH` (`*_edgetpu.tflite`) and route every embed through `embed_speaker`.
3. Enroll everyone under `GALLERY_DIR/<Name>/*.wav` (average embeddings per person).
4. Offline path: concat mic chunks to `OFFLINE_SEGMENT_MS` → embed → search gallery.
5. Print `who is talking: <Name> (score=…)` to **stderr** (shows in `journalctl -u calypso-puck`).
6. Bluetooth / phone send remain stubs.

## Setup

```bash
cd puck
./scripts/setup_voice_id.sh          # model + notes for sherpa libs
# put 16 kHz mono WAVs in gallery/Sarah/*.wav etc.
# config/.env:
#   MODE=offline
#   VOICE_MODEL_PATH=models/nemo_en_titanet_small.onnx
#   GALLERY_DIR=gallery
#   VOICE_MATCH_THRESHOLD=0.55
```

Build with sherpa (Pi / Linux example):

```bash
cmake -S . -B build -DCALYPSO_SHERPA_ROOT=/path/to/sherpa-onnx-install
cmake --build build
./build/calypso_puck
```
