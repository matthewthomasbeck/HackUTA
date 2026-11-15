# Coral Edge TPU path (offline voice ID)

## Config

```bash
# config/.env
TPU_MODE=coral
INFER_BACKEND=coral
CORAL_MODEL_PATH=models/nemo_en_titanet_small_edgetpu.tflite
CORAL_DEVICE=          # optional USB path hint
VOICE_MODEL_PATH=models/nemo_en_titanet_small.onnx   # host embedder / enrollment
```

`TPU_MODE` wins over `INFER_BACKEND`. Dashboard `sound_backend` reports `coral`.

## Control plane

| Piece | Role |
|---|---|
| `Accelerators::init_coral` | Open Edge TPU, load `*_edgetpu.tflite`, arm live or compat |
| `Accelerators::embed_speaker` | Every offline embed when `TPU_MODE=coral` |
| `Models` | Registers sherpa as host delegate; gallery match unchanged |
| `POST /puck/health` | `sound_backend: "coral"` |

## Live vs compat

1. **Live** (`ENABLE_CORAL=ON` at cmake, stick plugged, real Edge-TPU FlatBuffer):  
   `libedgetpu` → `OpenDevice` → `Interpreter::Invoke` on the stick.
2. **Compat** (default until the graph is compiled): same API + logs;  
   `embed_speaker` uses the sherpa host delegate. Journal shows  
   `coral/edgetpu: host delegate embed (…)`.

## Stage the model path

```bash
./scripts/setup_voice_id.sh
./scripts/stage_coral_model.sh   # creates CORAL_MODEL_PATH
```

Replace the staged file with a real `edgetpu_compiler` output when Titanet is quantized.

## Build with live libedgetpu (same trees as Whisker)

```bash
cmake -S . -B build-coral \
  -DCALYPSO_SHERPA_ROOT=$HOME/sherpa-onnx \
  -DENABLE_CORAL=ON \
  -DTENSORFLOW_SOURCE_DIR=$HOME/Projects/C_Hardware_Testing/third_party/tensorflow \
  -DTFLITE_BINARY_DIR=$HOME/Projects/C_Hardware_Testing/third_party/tflite_build \
  -DEDGETPU_INCLUDE=$HOME/Projects/C_Hardware_Testing/third_party/coral/include
cmake --build build-coral -j"$(nproc)"
```
