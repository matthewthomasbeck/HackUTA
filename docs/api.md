# Calypso⁻¹ backend API

The contract for the puck (Matt), the Chert agent (Keanu), the iOS app (Eric), and the dashboard. Shapes live in [`backend/calypso/models.py`](../backend/calypso/models.py); tell the team before changing them. Live, clickable docs: `GET /docs` on any running backend.

**Status:** endpoints marked **stub** already have their final request and response shape but return placeholder results. Build against them now; they become real in the task noted, with no change for callers.

## Basics

| | |
|---|---|
| Base URL | `CALYPSO_PUBLIC_URL` on the server, e.g. `https://<host>`. The iOS `API_BASE_URL` must be the **same** value, and must be `https://` when deployed (iOS won't load `http://` images). |
| Auth | Every endpoint except `/health`, `/stream`, `/events/recent`, `/media/...` and `/dashboard` needs `Authorization: Bearer <CALYPSO_API_TOKEN>`. The iOS `API_TOKEN` must equal the server's `CALYPSO_API_TOKEN`. A missing or wrong token → `401`. |
| Success | Any `2xx`. The iOS app ignores response bodies. |
| Errors | JSON `{"detail": ...}`: `401` bad token, `404` unknown id, `413` file too large, `422` bad body, `503` try again later. |
| Times | ISO-8601 **with a zone**. Send `Z` or an offset: `2026-11-14T15:30:00.123Z`, `2026-11-14T09:30:00-06:00`. A time with no zone is treated as UTC (and logged), never rejected. Responses are always UTC with milliseconds and `Z`. |
| Days | A day is the patient's local calendar day (`CALYPSO_TZ`, default `America/Chicago`). The app asks for days by the phone's local date (`yyyy-MM-dd`), so this lines up as long as the demo phone is on Central time. |
| Ids in URLs | `segment_uuid` and photo ids use only `A-Z a-z 0-9 _ -` (max 128). Anything else → `422`. |
| Images | Public at unguessable URLs. `face_photo_url` is always a full link built from `CALYPSO_PUBLIC_URL`. Photos flagged sensitive return `404`. |

---

## Puck (Matt)

### `POST /puck/segments`
One voiced speech segment. The puck captures 30 ms frames for VAD, then uploads whole segments (0.5–15 s).

`multipart/form-data` with two parts:
- `audio`: WAV, **16 kHz, mono, 16-bit PCM**, ≤ 5 MB.
- `meta`: JSON string:
```json
{
  "segment_uuid": "0b6f2c1e-6f8e-4c1a-9d1e-3b2f5a7c9e10",
  "ts_start": "2026-11-14T15:30:00.000Z",
  "ts_end":   "2026-11-14T15:30:04.500Z",
  "sound_tags": [ { "ts": "2026-11-14T15:30:01.000Z", "label": "Espresso machine", "score": 0.81 } ],
  "local_text": "let me grab a coffee"
}
```
Response `200`:
```json
{ "segment_uuid": "0b6f2c1e-...", "duplicate": false, "utterance_ids": ["a9b4f008..."] }
```
Rules:
- Generate `segment_uuid` **once** when the segment is cut, store it in the queue, and **reuse it on every retry**. The server dedupes on it.
- Ack (remove from the queue) on any `2xx`, including `duplicate: true`. On a network error or `5xx`, keep it and retry with backoff. `503` means the server couldn't queue processing; retry later.
- `local_text` (whisper.cpp) is optional. It's the fallback text if server STT fails.
- The server never keeps the audio: it is deleted right after processing.

```bash
curl -H "Authorization: Bearer $TOKEN" \
  -F "audio=@segment.wav;type=audio/wav" \
  -F 'meta={"segment_uuid":"0b6f2c1e-6f8e-4c1a-9d1e-3b2f5a7c9e10","ts_start":"2026-11-14T15:30:00.000Z","ts_end":"2026-11-14T15:30:04.500Z","sound_tags":[],"local_text":null}' \
  https://<host>/puck/segments
```

### `POST /puck/health`
Every 30 s. Feeds the dashboard's "puck online" and queue depth.
```json
{ "ts": "2026-11-14T15:30:00Z", "queue_depth": 3, "sound_backend": "cpu",
  "ms_per_segment": 41.5, "time_synced": true, "battery_pct": 87, "last_upload_ok": true }
```
`battery_pct`, `ms_per_segment` and `last_upload_ok` may be `null`. Response `{"ok": true}`.
```bash
curl -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"ts":"2026-11-14T15:30:00Z","queue_depth":3,"sound_backend":"cpu","ms_per_segment":41.5,"time_synced":true}' \
  https://<host>/puck/health
```

---

## Agent (Keanu)

### Claude session gateway

The media transport now delegates decisions to Claude on the backend:

- `POST /agent/sessions`: `{mode: "setup"|"group"|"recognize"|"auto", participant: str,
  controlled: bool, outcome: "identified"|"learning"|"uncertain",
  enrolled_person_id?: str, caller_phone?: str}` → `{session_id, call_id}`.
- `POST /agent/sessions/{id}/events`: `{kind: "start"|"utterance"|"silence"|"frame"|"camera_ready"|"recognition_timeout",
  text?: str, face_jpegs_b64?: [str], jpeg_b64?: str, voice_wav_b64?: str}` →
  `{session_id, speech: [str], cards: [Card], done: bool, enrolled_person_id?: str,
  needs_face_crops: bool}`. When requested, the transport reports `camera_ready`
  with three recent crops. A confirmed introduction can then be saved without
  requiring a second spoken confirmation.
- `POST /agent/sessions/{id}/end`: ends the backend call and removes the session;
  repeated cleanup returns `{ok: true}`.

On `utterance` events, `voice_wav_b64` is the caller's audio for that utterance (the same WAV sent to
Grok). In setup calls the backend keeps up to 60 s of it, and `save_intro` sends it, with the
confirmed name/relationship/memory, in a single `/people/from_intro` call for the voiceprint.

These routes require the existing bearer token. `ANTHROPIC_API_KEY` stays on the
server; `CALYPSO_AGENT_MODEL` defaults to `claude-sonnet-4-6`. Claude tool calls
are executed by backend code with confirmation/identity guards. `503` indicates
missing model configuration or model failure; reconnect after failure. Sessions
are in memory and need a single backend worker. Controlled recognition is a
visibly labeled integration-test mode, not actual recognition.

For enrollment, the media transport resolves the `chert-bridge-<call UUID>` against
Chert's authenticated call record and sends the inbound `from.value` only when
`from.type` is `phone_number` and the call/project match. This is persisted in the
existing `Person.phone` field via `/people/from_intro`. Masked callers, email
identities or failed lookups leave it null; Claude never supplies the number.

### Face prints and voiceprints (open-source models)
- **Faces:** OpenCV **YuNet** finds each face and its landmarks, then **SFace** turns the aligned face into 128 numbers. Tight crops (like the agent's Haar crops) are padded before detection.
- **Voices:** NVIDIA NeMo **TitaNet-small** (via sherpa-onnx) turns 16 kHz speech into 192 numbers. Silence is trimmed first, and a voiceprint needs **≥ 2 s of speech**.
- Model files: `cd backend && uv run python scripts/fetch_models.py` downloads them into `data/models/`, with SHA-256 checks. Without them the backend still runs: matching returns `learning`, and enrollment notes what it skipped.
- Only the numbers are stored (plus one display photo per person). Audio is never stored.
- Provisional thresholds, to tune on real calls: `FACE_MATCH=0.40`, `FACE_MARGIN=0.08`, `VOICE_MATCH=0.50`, `VOICE_MARGIN=0.08`.

### `POST /recognize`
Face first, voice second. Send a frame and/or a voice clip (≥ 2 s of that participant's speech, 16 kHz mono WAV) as base64.
```json
{ "face_jpeg_b64": "/9j/4AAQ...", "voice_wav_b64": "UklGR...", "exclude_patient": true,
  "participant_key": "sarah-phone", "call_id": "c1" }
```
Response: one entry per face found in the frame (composite grids give several), plus `voice_only` when audio came without a face:
```json
{ "faces": [ { "bbox": {"x": 120, "y": 80, "w": 220, "h": 220},
               "result": { "status": "identified", "person_id": "p_sarah", "face_score": 0.71, "voice_score": 0.66 } } ],
  "voice_only": null }
```
- `status`: `identified` (show the identity card), `learning` ("Getting to know someone new…"), `uncertain` (show nothing).
- **identified** needs a face score ≥ `FACE_MATCH` that beats the second-best person by ≥ `FACE_MARGIN`. If the voice clearly belongs to someone *else*, the result is `uncertain`.
- With **no face**, voice alone can identify, but only at `VOICE_MATCH + 0.1`.
- The patient is never returned. Every call emits a `recognize` event with the top-3 face/voice scores and the thresholds (for the dashboard and tuning).

### `POST /people/from_intro`
End of a 1:1 setup call. Enrolls the caller's face prints and voiceprint.
```json
{ "transcript": "Hi, I'm Sarah, Mary's daughter. We bake together on Sundays.",
  "name": "Sarah", "relationship": "daughter", "facts": ["Baking on Sundays"],
  "face_jpegs_b64": ["/9j/...", "/9j/...", "/9j/..."],
  "voice_wav_b64": "UklGR...", "phone": "+15555550123", "call_id": "c1" }
```
- `name`/`relationship`/`facts` are what the caller confirmed aloud. `voice_wav_b64` is their speech from the call (joined clips are fine).
- **No duplicates:** if the verified `phone`, the face, or the voice matches someone already enrolled (never the patient), that person is **updated**: prints are added, facts merged, and missing name/relationship/phone filled in. If face and voice point to different people, nothing is merged.
- Response: `201` for a new person, `200` when an existing one was updated. The body is the `Person` plus:
```json
{ "matched_existing": false, "matched_by": null, "face_prints_added": 3, "voice_prints_added": 1,
  "notes": ["only 1.4 s of speech; need 2.0 s for a voiceprint"] }
```
- Unusable media (no face, too little speech, missing models) never blocks enrollment; `notes` says what was skipped.

### `POST /people/{id}/faces`, `POST /people/{id}/voice`
Extra enrollment, e.g. an iMessage photo, or learning someone during a call.
- **Faces:** multipart `image` (JPEG). `422` if no face is found.
- **Voice:** multipart `audio` (WAV), `422` with less than 2 s of speech. The audio is never stored.

Both return `{"ok": true, "face_prints": n, "voice_prints": m}`.

### `POST /calls`, `POST /calls/{id}/lines`, `POST /calls/{id}/end`
Log a call and its transcript lines. Lines become `source: "call"` utterances, so they turn into memories later.
```json
POST /calls                → {"kind": "group", "participants": ["mary", "sarah"]}
                           ← {"id": "c1", "kind": "group", "started": "...Z", "ended": null, "participants": [...]}
POST /calls/c1/lines       → {"speaker": "sarah", "text": "Hi Mom!", "ts": "2026-11-14T20:00:00.000Z", "person_id": "p_sarah"}
POST /calls/c1/end         ← the Call with "ended" set
```

### `POST /recall`  (stub → Task 8)
```json
{ "lines": [ { "speaker": "Sarah", "text": "Mom, what did you do today?" } ] }
```
Response: `{"intent": {"intent": "today", ...}, "card": {"kind": "today", "title": "Today", "lines": ["9:10 · Blue Bean Café · coffee with Sarah"], "image_urls": []}}`. **Stub today:** always `{"intent": {"intent": "none", ...}, "card": null}`.

### `POST /agent/events`
Dashboard events from the agent, e.g. `card.shown`. Body `{"stage": "card.shown", "payload": {...}}`.

### `GET /people?is_patient=true`
Finds the patient (for "I help **Mary** remember…").

---

## iOS app (Eric)

| Endpoint | Body | Response |
|---|---|---|
| `GET /people` | | `[Person]` |
| `GET /people/{id}` | | `PersonDetail`: a flat Person plus `memories: [String]` (up to 5, newest first, e.g. `"Nov 14 · Blue Bean Café · Coffee with Sarah"`) |
| `PATCH /people/{id}` | `{"name": "Eric"}` (also `relationship`, `facts`, `phone`) | `Person` |
| `GET /days/{yyyy-MM-dd}/events` | | `[DayEvent]` for that local day; `people` holds person ids, patient excluded |
| `POST /days/{yyyy-MM-dd}/rebuild` | | `{"ok": true, ...}` (stub → Task 7) |
| `POST /app/visits` | JSON array of `Visit`; `departed: null` while the visit is still going on | `{"ok": true, "count": n}`; upserts by `id` |
| `POST /app/photos` | multipart: `meta` (JSON `{id, taken_at, lat, lon}`) + `image` (JPEG) | `{"ok": true, "id": ..., "duplicate": bool}`; a repeat `id` is ignored |
| `GET /media/faces/{person_id}.jpg` | public | JPEG or `404` |
| `GET /media/photos/{photo_id}.jpg` | public | JPEG, or `404` if missing or sensitive |

`Person`:
```json
{ "id": "p_sarah", "name": "Sarah", "relationship": "daughter", "is_patient": false,
  "face_photo_url": "https://<host>/media/faces/p_sarah.jpg", "facts": ["Lives in Austin"], "phone": null }
```
`DayEvent`:
```json
{ "id": "e1", "start": "2026-11-14T15:10:00.000Z", "end": "2026-11-14T15:40:00.000Z",
  "place": "Blue Bean Café", "place_confidence": 0.95, "people": ["p_sarah"],
  "summary": "Coffee with Sarah", "evidence": ["visit:v2"], "photo_ids": ["ph1"] }
```

---

## Dashboard and everyone

| Endpoint | Notes |
|---|---|
| `GET /health` | `{"ok": true}`, no auth |
| `GET /stream` | Server-sent events, no auth. Each message is `data: {"stage", "ts", "payload"}`. Stages so far: `puck.segment`, `puck.processed`, `puck.failed`, `puck.health`, `recognize`, `recall.detect`, `person.created`, `person.updated`, `person.enrolled`, `call.started`, `call.line`, `call.ended`, `day.built`, `app.visits`, `app.photo`, plus anything sent to `/events` or `/agent/events`. `?limit=N` closes the stream after N events. |
| `GET /events/recent?limit=100` | The last events, so the dashboard can fill in on load, no auth |
| `POST /events` | Rebroadcast `{"stage", "payload"}` to `/stream` (the RQ worker uses this) |
| `GET /dashboard/` | The judge dashboard (static files) |

---

## Running it

From `backend/` (copy `.env.example` to `.env` at the repo root first):
```bash
uv run --group dev pytest                                                   # tests
uv run uvicorn calypso.app:app --host 127.0.0.1 --port 8000 --env-file ../.env   # API
uv run --env-file ../.env rq worker --url "$CALYPSO_REDIS_URL" recordings  # worker (when CALYPSO_JOBS=rq)
```
- `CALYPSO_JOBS=inline` (default) processes uploads inside the API, with no Redis needed. Use it on laptops and in tests.
- `CALYPSO_JOBS=rq` queues them on Redis for the worker. Use it on Vultr.
- `CALYPSO_STORAGE=local` (default) keeps face crops and photos under `data/files/`. `s3` uses the Vultr enrollment bucket.
- On Vultr, uvicorn runs on `127.0.0.1:8000` behind Caddy for HTTPS.

In `auto` sessions, effects include the current `mode` (`recognize` then `setup` if unmatched). The transport sends `recognition_timeout` after the five-second opening window; the backend enforces the elapsed-time guard and ignores repeated/early timeout events. A confident face match completes the flow with an identity card and hang-up instruction. No-match transitions reuse the same session and call log for enrollment.
