# Puck (Matt) — online pipeline

Teammates need: mic (or `sine`) → buffer `SEGMENT_MS` → `POST /puck/segments` with Bearer token. Same contract as `backend/calypso/models.py`.

## Online path (done)

1. `Capture` — ALSA on Linux, or `MIC_DEVICE=sine` anywhere  
2. `BackendLink` — `GET /health` to connect; buffer audio; multipart `POST /puck/segments`; `POST /puck/health` on connect  
3. `StateMachine` online tick — `read_chunk` → `send_audio_chunk`  
4. `ConnectionListener` — flips Offline on drop, retries every `CONNECT_RETRY_SEC`

Offline / Coral / NCS2 still stubbed.

## Config (`config/.env`)

```bash
cp config/.env.example config/.env
# set BACKEND_IP, BACKEND_PORT, API_TOKEN (= CALYPSO_API_TOKEN), MIC_DEVICE
```

## Build / run

```bash
# macOS smoke (no ALSA): brew install curl; MIC_DEVICE=sine
# Pi: sudo apt install cmake g++ libasound2-dev libcurl4-openssl-dev

cmake -S . -B build && cmake --build build
# backend must be up: cd backend && uv run uvicorn calypso.app:app --host 0.0.0.0 --port 8000
./build/calypso_puck
```

Dashboard should show `puck.segment` / `puck.health` on `/stream`.

## systemd

See `systemd/calypso-puck.service` — set `MIC_DEVICE` to the real ALSA name on the Pi.
