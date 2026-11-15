# Puck (Matt) — online + offline emergency pipeline

Teammates need: mic (or `sine`) → online `POST /puck/segments`, or offline
voice-fingerprint → Bluetooth "who is talking" to the phone.

## Pipeline

1. systemd starts `calypso_puck` (`main.cpp`)
2. Load `config/.env`
3. Init mic (`Capture`), backend link, **Coral/NCS2 stubs** (`Accelerators`),
   **phone Bluetooth stub** (`PhoneLink`), offline models (`Models`, CPU default)
4. `MODE=offline` → start Offline and pin it (listener will not promote), so
   the worker runs the offline voice-ID path. **Uploads still continue:** the
   spool uploader below runs in every mode, so set a wrong `BACKEND_IP` (or stop
   the backend) if you need a truly offline test.
   `MODE=online` (default) → try `GET /health`; Online if up, else Offline
5. Start listen + worker threads, plus the connection watcher
6. **Always:** listen thread: mic/sine → `CHUNK_MS` chunks → in-memory queue
7. Worker pops chunks and branches on mode

### Spool + uploader (both modes)
8. Every `CHUNK_MS` chunk goes to the `Segmenter`; after `SEGMENT_MS` of audio
   it emits a segment with a fresh uuid, ts, and clock metadata (`time_synced`,
   `boot_id`, boot ms), written atomically to the on-disk `SegmentSpool`
   (`PUCK_SPOOL_DIR`, capped at `PUCK_SPOOL_MAX_MB`, oldest evicted first).
   The uuid is fixed at enqueue, so retries and restarts are idempotent.
   The spool dir must exist or be creatable and writable by the puck's user.
   The default `/var/lib/calypso-puck/spool` is created by the systemd unit's
   `StateDirectory=calypso-puck`; for a manual run (or macOS dev) set e.g.
   `PUCK_SPOOL_DIR=./spool`. If it can't be used, the puck exits at start with
   `cannot use spool dir …` rather than crash-looping.
9. The `Uploader` thread runs for the life of the process: it drains the spool
   oldest-first via `POST /puck/segments`. 2xx (incl. `duplicate:true`) and 409
   remove the item. 5xx, 401, 403, 408, 429 or a transport error stop the pass
   and back off 1s doubling to 60s, keeping every item (a wrong `API_TOKEN`
   pauses uploads; it doesn't discard audio). Any other 4xx (400, 413, 422…)
   moves that one item to `<spool>/rejected/`, which keeps at most 200 items
   (oldest pruned); its size is logged by the health thread when it changes.
10. Clock: if the Pi booted without NTP, segments are saved `time_synced=false`
    with boot-relative times. Unsynced items from the current boot are **held**
    in the spool until the clock syncs, then corrected
    (`ts = realtime_now - (boot_ms_now - boot_ms_capture)`) and uploaded as
    synced. Only items from an earlier boot upload as `time_synced=false`. With
    no NTP at all, audio waits in the spool (up to `PUCK_SPOOL_MAX_MB`). `/puck/health` reports
    the real `time_synced` and `queue_depth`.

### Who is talking (voice ID → phone, online AND offline)
1. Feed the same `CHUNK_MS` frames into `OfflineBuffer` (concat to
   `OFFLINE_SEGMENT_MS` — **does not** touch the online upload buffer)
2. `Models::infer` on the concatenated clip (CPU now; `INFER_BACKEND` /
   `Models::set_backend` for Coral/NCS2 later)
3. `PhoneLink::send_who_is_talking(out.who)` → phone app

### Gallery sync (cloud → Pi)
1. Backend stores Titanet voice prints in SQLite (`voice_prints`) at enroll time
2. `GET /puck/gallery` returns a full snapshot (mean embedding + person meta)
3. Connection listener, whenever the backend is reachable, GETs that snapshot
   and **replace-alls** the in-memory `VoiceGallery` (missing people = deleted)
4. Local `GALLERY_DIR/<Name>/*.wav` is only a bootstrap until the first sync
5. Works in `MODE=offline` too (listener still probes HTTP for gallery; run
   path stays Offline)

### Mode switching
1. Connection listener: if connected → Online; if not → wait, retry connect,
    set Offline/Online. While reachable, also syncs `/puck/gallery`.
2. Capture never stops; only the worker path changes. Switching to Online
    clears the offline concat buffer so partial clips do not leak.

### Shutdown
1. On SIGINT/SIGTERM: stop listener + state machine, shut down
    models / phone / accelerators / link / capture

## Offline voice ID (MVP — implemented)

**Model:** `nemo_en_titanet_small.onnx` (192-d) via **sherpa-onnx** on CPU.  
Details: [`docs/VOICE_ID.md`](docs/VOICE_ID.md).

```bash
./scripts/setup_voice_id.sh
# add gallery/<Name>/*.wav  (16 kHz mono)
cmake -S . -B build -DCALYPSO_SHERPA_ROOT=/path/to/sherpa-onnx
cmake --build build && ./build/calypso_puck
# journalctl -u calypso-puck -f   →  who is talking: Sarah (score=0.72)
```

## Coral Edge TPU

```bash
# config/.env
TPU_MODE=coral
CORAL_MODEL_PATH=models/nemo_en_titanet_small_edgetpu.tflite
./scripts/stage_coral_model.sh
# details: docs/CORAL_TPU.md
```

Offline embeds go through `Accelerators::embed_speaker` (live stick or compat host delegate). Health reports `sound_backend: coral`.

## Still stubbed

| Piece | Files | Role |
|---|---|---|
| `PhoneLink` | `phone_link.*` | BT to app |
| NCS2 | `accelerators.*` | OpenVINO MYRIAD reserved |

## Config (`config/.env`)

```bash
cp config/.env.example config/.env
# set BACKEND_IP, BACKEND_PORT, API_TOKEN (= CALYPSO_API_TOKEN), MIC_DEVICE
# MODE=offline to force-test emergency path (spool uploads still run); MODE=online for normal ops
# PUCK_SPOOL_DIR (default /var/lib/calypso-puck/spool; use ./spool for manual runs), PUCK_SPOOL_MAX_MB
# optional: OFFLINE_SEGMENT_MS, TPU_MODE=coral, CORAL_MODEL_PATH, BT_ADAPTER, BT_PEER_NAME
```

## Build / run

```bash
# macOS smoke (no ALSA): brew install curl; MIC_DEVICE=sine
# Pi: sudo apt install cmake g++ libasound2-dev libcurl4-openssl-dev

cmake -S . -B build && cmake --build build
# backend must be up: cd backend && uv run uvicorn calypso.app:app --host 0.0.0.0 --port 8000
./build/calypso_puck
```

Dashboard should show `puck.segment` / `puck.health` on `/stream` when online.

## Enroll a voice from the puck mic

Voice prints made from FaceTime audio don't match the lav mic. Enroll through the puck mic instead (the person must already exist in the app):

```bash
sudo systemctl stop calypso-puck          # the puck owns the mic
./build/calypso_enroll --name Keanu --samples 3 --seconds 8
sudo systemctl start calypso-puck
```

Each sample is uploaded to `POST /people/{id}/voice`. Samples quieter than `MIN_SPEECH_RMS` are skipped: clip the mic closer or raise `MIC_GAIN`. Options: `--config config/.env` (default).

## systemd (puck + BLE together)

One unit runs `scripts/start_puck.sh`, which starts `ble_who_peripheral.py` then `build/calypso_puck`.
It also starts a Bluetooth pairing agent that accepts pairing automatically (no PIN): iOS needs a completed pairing or it keeps prompting and dropping the link. Disable with `PUCK_BT_AUTOPAIR=0`. The Pi also needs a proper power supply: under-voltage (`vcgencmd get_throttled` ≠ `0x0`) makes Bluetooth drop.
The unit's `StateDirectory=calypso-puck` creates `/var/lib/calypso-puck` (owned
by `User=`) for the default spool dir. Set `MIC_DEVICE` in `config/.env`. `MIC_GAIN` (1-32, default 1.0) applies software gain to quiet mics.

```bash
# on the Pi
chmod +x scripts/start_puck.sh
sudo cp systemd/calypso-puck.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now bluetooth
sudo systemctl enable --now calypso-puck
journalctl -u calypso-puck -f
```

Stop manual terminals first (`pkill -f calypso_puck`; stop the Python BLE script) so the mic isn’t busy.
After editing the unit: `sudo systemctl daemon-reload && sudo systemctl restart calypso-puck`.
