#!/usr/bin/env bash
# Start BLE who-peripheral + calypso_puck together (one systemd unit).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PUCK_BIN="${PUCK_BIN:-$ROOT/build/calypso_puck}"
BLE_SCRIPT="${BLE_SCRIPT:-$ROOT/scripts/ble_who_peripheral.py}"
WHO_DROP="${WHO_DROP_PATH:-/tmp/calypso_who.json}"
PYTHON="${PYTHON:-python3}"

if [[ ! -x "$PUCK_BIN" ]]; then
  echo "missing puck binary: $PUCK_BIN (cmake --build build first)" >&2
  exit 1
fi
if [[ ! -f "$BLE_SCRIPT" ]]; then
  echo "missing BLE script: $BLE_SCRIPT" >&2
  exit 1
fi

ble_pid=""

cleanup() {
  if [[ -n "$ble_pid" ]] && kill -0 "$ble_pid" 2>/dev/null; then
    echo "stopping BLE peripheral (pid $ble_pid)" >&2
    kill "$ble_pid" 2>/dev/null || true
    wait "$ble_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

# Pairing agent: iOS asks to pair with the puck, and without an agent BlueZ never
# completes it, so the phone keeps prompting and dropping the link (no `who`
# updates arrive). This accepts pairing automatically (no PIN, like headphones):
# any nearby phone can pair while the puck runs. Set PUCK_BT_AUTOPAIR=0 to disable.
# The unit's KillMode=control-group stops it with the puck.
if [[ "${PUCK_BT_AUTOPAIR:-1}" == "1" ]]; then
  echo "starting Bluetooth auto-pair agent" >&2
  { echo "agent NoInputNoOutput"; sleep 1; echo "default-agent"; sleep 1; echo "pairable on"
    while true; do sleep 1; echo yes; done; } | bluetoothctl >/dev/null 2>&1 &
fi

echo "starting BLE peripheral → $WHO_DROP" >&2
"$PYTHON" "$BLE_SCRIPT" --drop "$WHO_DROP" --name "Calypso Puck" &
ble_pid=$!
sleep 1
if ! kill -0 "$ble_pid" 2>/dev/null; then
  echo "BLE peripheral exited early — is bluetooth up? (systemctl status bluetooth)" >&2
  wait "$ble_pid" || true
  exit 1
fi

echo "starting calypso_puck" >&2
exec "$PUCK_BIN"
