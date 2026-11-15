#!/usr/bin/env bash
# Smoke test: the app's real APIClient + Models, compiled for macOS, against the real backend.
# Doesn't touch Calypso.xcodeproj or DerivedData.
#
#   ios/scripts/smoke_test.sh              # starts backend/ on 127.0.0.1:8765 with a throwaway DB
#   ios/scripts/smoke_test.sh URL TOKEN    # a deployed backend; writes "Smoke …" people and smoke-* photos/visits
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
WORK="$(mktemp -d)"
DAY="$(date +%Y-%m-%d)"
PHOTO_ID="smoke-$(date +%s)"
PORT=8765
SERVER_PID=""
cleanup() {
  # uv runs uvicorn as a child, so stop whatever is listening on the port too.
  if [[ -n "$SERVER_PID" ]]; then kill "$SERVER_PID" $(lsof -ti tcp:$PORT -sTCP:LISTEN) 2>/dev/null || true; fi
  rm -rf "$WORK"
}
trap cleanup EXIT

if [[ $# -ge 2 ]]; then
  BASE="${1%/}"; TOKEN="$2"; LOCAL=0
else
  BASE="http://127.0.0.1:$PORT"; TOKEN="smoke"; LOCAL=1
  if lsof -ti tcp:$PORT -sTCP:LISTEN >/dev/null; then echo "port $PORT is busy"; exit 1; fi
  mkdir -p "$WORK/data"
  (cd "$ROOT/backend" && CALYPSO_API_TOKEN=$TOKEN CALYPSO_DATA_DIR="$WORK/data" CALYPSO_PUBLIC_URL="$BASE" \
    CALYPSO_JOBS=inline CALYPSO_STORAGE=local CALYPSO_STT=fake CALYPSO_TTS=fake \
    exec uv run uvicorn calypso.app:app --host 127.0.0.1 --port $PORT) > "$WORK/backend.log" 2>&1 &
  SERVER_PID=$!
  for _ in $(seq 60); do curl -sf "$BASE/health" >/dev/null && break; sleep 0.5; done
  curl -sf "$BASE/health" >/dev/null || { echo "backend didn't start:"; cat "$WORK/backend.log"; exit 1; }
fi

# 1x1 JPEG for face and photo uploads.
base64 -d > "$WORK/t.jpg" <<< '/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA='

# Seed: Sarah with a face photo and an unnamed visitor (plus the patient and a day event when local).
post() { curl -sf -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$2" "$BASE$1"; }
id_of() { python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])'; }
[[ $LOCAL == 1 ]] && post /people '{"name":"Margaret","is_patient":true}' >/dev/null
SARAH=$(post /people '{"name":"Smoke Sarah","relationship":"daughter","facts":["Lives in Austin"],"phone":"+15125550100"}' | id_of)
UNNAMED=$(post /people '{}' | id_of)
curl -sf -H "Authorization: Bearer $TOKEN" -F image=@"$WORK/t.jpg" "$BASE/people/$SARAH/faces" >/dev/null
if [[ $LOCAL == 1 ]]; then
  sqlite3 "$WORK/data/calypso.db" "INSERT INTO day_events VALUES ('smoke-ev','${DAY}T15:10:00Z','${DAY}T16:00:00Z',
    'Blue Bean Café',0.82,'[\"$SARAH\",\"$UNNAMED\"]','Coffee with Sarah','[]','[\"$PHOTO_ID\"]');"
fi

CORE="$ROOT/ios/Calypso/Core"
swiftc -target "$(uname -m)-apple-macos14" -module-cache-path "$WORK/mc" -suppress-warnings \
  "$CORE/Models.swift" "$CORE/APIClient.swift" "$CORE/Config.swift" "$ROOT/ios/scripts/smoke/main.swift" \
  -o "$WORK/smoke"
"$WORK/smoke" "$BASE" "$TOKEN" "$WORK/t.jpg" "$PHOTO_ID" "$DAY" "$LOCAL"
