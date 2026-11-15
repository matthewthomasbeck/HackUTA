# Puck (Matt) — C++17 pipeline stubs

Full task checklist: [`docs/tasks/matt-puck.md`](../docs/tasks/matt-puck.md)

## Threads

| Thread | Role |
|---|---|
| **0 main** | Load `config/.env`, init mic + backend link + NCS2 models, wait `CONNECT_RETRY_SEC`, start SM + listener. Run via **systemd**. |
| **1 connection listener** | Poll link; on drop wait `n` s, set Offline, keep reconnecting every `n` s. |
| **2 state machine** | Sole mic owner. **Online:** chunk → backend. **Offline:** chunk → local models → discard output (for now). |

Online and offline are **modes**, not two mic threads (ALSA can’t be shared that way).

## Layout

```
puck/
  main.cpp                 # THREAD 0
  include/*.hpp
  src/*.cpp
  config/.env.example      # copy → config/.env
  systemd/calypso-puck.service
  spikes/mic_check.sh      # hour-1 only
```

## Build / run

```bash
cp config/.env.example config/.env   # edit IP, port, MIC_DEVICE
cmake -S . -B build && cmake --build build
./build/calypso_puck

# on the Pi:
sudo cp systemd/calypso-puck.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now calypso-puck
```

## Stub status

Everything compiles as a skeleton: `Capture` / `BackendLink` / `Models` init & I/O return failure until you fill them in. Offline `infer` output is intentionally unused.
