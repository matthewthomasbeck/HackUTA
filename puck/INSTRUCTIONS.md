# Puck (Matt) — online + offline emergency pipeline

Teammates need: mic (or `sine`) → online `POST /puck/segments`, or offline
voice-fingerprint → Bluetooth "who is talking" to the phone.

## Pipeline

1. systemd starts `calypso_puck` (`main.cpp`)
2. Load `config/.env`
3. Init mic (`Capture`), backend link, **Coral/NCS2 stubs** (`Accelerators`),
   **phone Bluetooth stub** (`PhoneLink`), offline models (`Models`, CPU default)
4. `MODE=offline` → start Offline and pin it (listener will not promote).
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
9. The `Uploader` thread runs for the life of the process: it drains the spool
   oldest-first via `POST /puck/segments`. 2xx (incl. `duplicate:true`) and 409
   remove the item; other 4xx move it to `<spool>/rejected/`; 5xx or a
   transport error stops the pass and backs off 1s doubling to 60s.
10. Clock: if the Pi booted without NTP, segments are saved `time_synced=false`
    with boot-relative times. Once synced, pending items from the same boot are
    corrected (`ts = realtime_now - (boot_ms_now - boot_ms_capture)`); items
    from an earlier boot upload as `time_synced=false`. `/puck/health` reports
    the real `time_synced` and `queue_depth`.

### Offline (emergency voice ID)
11. Feed the same `CHUNK_MS` frames into `OfflineBuffer` (concat to
   `OFFLINE_SEGMENT_MS` — **does not** touch the online upload buffer)
12. `Models::infer` on the concatenated clip (CPU now; `INFER_BACKEND` /
   `Models::set_backend` for Coral/NCS2 later)
13. `PhoneLink::send_who_is_talking(out.who)` → phone app

### Mode switching
11. Connection listener: if connected → Online; if not → wait, retry connect,
    set Offline/Online
12. Capture never stops; only the worker path changes. Switching to Online
    clears the offline concat buffer so partial clips do not leak.

### Shutdown
13. On SIGINT/SIGTERM: stop listener + state machine, shut down
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

## Still stubbed

| Piece | Files | Role |
|---|---|---|
| `Accelerators` | `accelerators.*` | Coral / NCS2 |
| `PhoneLink` | `phone_link.*` | BT to app |

## Config (`config/.env`)

```bash
cp config/.env.example config/.env
# set BACKEND_IP, BACKEND_PORT, API_TOKEN (= CALYPSO_API_TOKEN), MIC_DEVICE
# MODE=offline to force-test emergency path; MODE=online for normal ops
# optional: OFFLINE_SEGMENT_MS, INFER_BACKEND=cpu, BT_ADAPTER, BT_PEER_NAME
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

## systemd

See `systemd/calypso-puck.service` — set `MIC_DEVICE` to the real ALSA name on the Pi.
