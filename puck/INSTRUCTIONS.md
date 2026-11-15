# Puck (Matt) — online + offline emergency pipeline

Teammates need: mic (or `sine`) → online `POST /puck/segments`, or offline
voice-fingerprint → Bluetooth "who is talking" to the phone.

## Pipeline

1. systemd starts `calypso_puck` (`main.cpp`)
2. Load `config/.env`
3. Init mic (`Capture`), backend link, **Coral/NCS2 stubs** (`Accelerators`),
   **phone Bluetooth stub** (`PhoneLink`), offline models (`Models`, CPU default)
4. Try `GET /health` — start Online if it works, else Offline
5. Start listen + worker threads, plus the connection watcher
6. **Always:** listen thread: mic/sine → `CHUNK_MS` chunks → in-memory queue
7. Worker pops chunks and branches on mode

### Online
8. Buffer chunks until `SEGMENT_MS` (`BackendLink`)
9. `POST /puck/segments` (wav + meta + Bearer token)
10. On success: clear buffer; on fail: keep audio, mark disconnected → Offline

### Offline (emergency voice ID)
8. Feed the same `CHUNK_MS` frames into `OfflineBuffer` (concat to
   `OFFLINE_SEGMENT_MS` — **does not** touch the online upload buffer)
9. `Models::infer` on the concatenated clip (CPU now; `INFER_BACKEND` /
   `Models::set_backend` for Coral/NCS2 later)
10. `PhoneLink::send_who_is_talking(out.who)` → phone app

### Mode switching
11. Connection listener: if connected → Online; if not → wait, retry connect,
    set Offline/Online
12. Capture never stops; only the worker path changes. Switching to Online
    clears the offline concat buffer so partial clips do not leak.

### Shutdown
13. On SIGINT/SIGTERM: stop listener + state machine, shut down
    models / phone / accelerators / link / capture

## Stubs (empty bodies — fill later)

| Piece | Files | Role |
|---|---|---|
| `Accelerators` | `include/accelerators.hpp`, `src/accelerators.cpp` | `init_coral` / `init_ncs2` |
| `PhoneLink` | `include/phone_link.hpp`, `src/phone_link.cpp` | BT to app; `send_who_is_talking` |
| `OfflineBuffer` | `include/offline_buffer.hpp`, `src/offline_buffer.cpp` | Offline-only concat |
| `Models` | `include/models.hpp`, `src/models.cpp` | CPU infer + `set_backend` |
| `WhoIsTalking` | `include/types.hpp` | Identified / Uncertain / Unknown |

## Config (`config/.env`)

```bash
cp config/.env.example config/.env
# set BACKEND_IP, BACKEND_PORT, API_TOKEN (= CALYPSO_API_TOKEN), MIC_DEVICE
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
