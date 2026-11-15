# Calypso⁻¹ backend: how the skeleton works

This is the server that every other part of Calypso⁻¹ talks to. The puck (Matt), the Chert FaceTime agent (Keanu), the iOS app (Eric) and the judge dashboard never talk to each other directly. They all go through this HTTP API.

- **Endpoint contract** (exact request and response JSON, with `curl` examples): [`docs/api.md`](../docs/api.md)
- **Shared data shapes:** [`calypso/models.py`](calypso/models.py). Tell the team before changing a field.
- **Live API docs:** open `/docs` on any running backend, e.g. `http://127.0.0.1:8000/docs`.

---

## 1. The big picture

```
 Puck (C++, on the patient) ──POST /puck/segments, /puck/health──┐
 iOS app ──────────────POST /app/visits, /app/photos; GET /people, /days──┤
 Chert agent ──POST /recognize, /recall, /people/from_intro, /calls…──────┤
                                                                         ▼
                        ┌──────────────── FastAPI backend ────────────────┐
                        │ routes/  →  SQLite (data/calypso.db)            │
                        │          →  storage (face crops, photos)        │
                        │          →  jobs (inline, or Redis + RQ worker) │
                        │          →  bus.emit() ──► GET /stream (SSE)    │
                        └─────────────────────────────────────────────────┘
                                                          │
                                         Judge dashboard ◄┘ (/dashboard)
```

It covers two use cases:
1. **First call:** a relative FaceTimes the agent 1:1. The backend creates their **Person** and enrolls their face and voice. In later group calls with the patient, the agent recognizes them, **face first, voice second**.
2. **Always-listening puck:** in-person conversations are transcribed and each voice is fingerprinted. Once a voice is linked to a person, those conversations become that person's memories on their identity card.

---

## 2. Folder layout

```
backend/
├── pyproject.toml        dependencies (uv), pytest settings
├── uv.lock               exact versions; commit it whenever it changes
├── calypso/
│   ├── app.py            builds the FastAPI app, mounts routes and the dashboard
│   ├── config.py         every setting and threshold, read from env vars
│   ├── models.py         shared contract (pydantic): Person, DayEvent, Card, request bodies…
│   ├── db.py             SQLite connection, full schema, people helpers
│   ├── bus.py            in-process event bus + server-sent events for the dashboard
│   ├── auth.py           bearer-token check
│   ├── deps.py           FastAPI dependencies: DB connection, settings, storage, URL building
│   ├── jobs.py           background jobs (inline or RQ) + process_segment
│   ├── storage.py        file storage: local folder or Vultr Object Storage
│   ├── timeutil.py       UTC helpers and the patient's local-day boundaries
│   └── routes/           one file per area of the API
│       ├── health.py     /health, /stream, /events, /events/recent, /agent/events
│       ├── puck.py       /puck/segments, /puck/health
│       ├── people.py     /people CRUD, memories, /from_intro, /faces, /voice
│       ├── media.py      /media/faces/{id}.jpg, /media/photos/{id}.jpg (public)
│       ├── recognize.py  /recognize   (stub)
│       ├── recall.py     /recall      (stub)
│       ├── calls.py      /calls, /calls/{id}/lines, /calls/{id}/end
│       ├── days.py       /days/{date}/events, /days/{date}/rebuild (stub)
│       └── app_ingest.py /app/visits, /app/photos
└── tests/                pytest suite (57 tests), uses fakes only
```

**Design rule:** each later task (Tasks 2–8 in the plan) changes mostly **its own route file** plus a new module (e.g. `identity/fuse.py`), so we don't step on each other.

---

## 3. The core pieces, one by one

### `config.py`: settings
`Settings.from_env()` reads environment variables once when the app starts. Nothing else reads `os.environ`, so tests can swap settings freely. Key ones:

| Variable | Default | Meaning |
|---|---|---|
| `CALYPSO_API_TOKEN` | *(empty)* | The shared secret. If it's empty, every authenticated request gets 401. |
| `CALYPSO_DB` | `data/calypso.db` | The SQLite file |
| `CALYPSO_DATA_DIR` | `data` | Holds the DB, `tmp/` (audio waiting to be processed) and `files/` (local storage) |
| `CALYPSO_TZ` | `America/Chicago` | The patient's time zone; days split at local midnight |
| `CALYPSO_PUBLIC_URL` | *(empty)* | Base for image links. **Must equal the iOS `API_BASE_URL`**, and be `https://` when deployed. |
| `CALYPSO_JOBS` | `inline` | `inline` = process uploads inside the API. `rq` = queue them on Redis for a worker. |
| `CALYPSO_STORAGE` | `local` | `local` = `data/files/`. `s3` = Vultr Object Storage (see below). |
| `CALYPSO_REDIS_URL` | `redis://127.0.0.1:6379/0` | Keanu's Redis (in `rq` mode) |
| `CALYPSO_BACKEND_URL` | `http://127.0.0.1:8000` | Where the worker sends dashboard events |
| `S3_ENDPOINT_URL`, `ENROLLMENT_BUCKET` | Vultr Atlanta endpoint | Vultr Object Storage location |
| `FACE_MATCH`, `FACE_MARGIN`, `VOICE_MATCH`, `VOICE_MIN_SPEECH_S`, `PLACE_CONF_MIN`, `RECALL_MIN` | 0.45, 0.08, 0.60, 2.0, 0.6, 0.35 | Safety thresholds. These are starting values to tune. |

At startup, `warn_if_misconfigured()` logs a warning for an empty token, a non-https public URL, or S3 mode with no bucket.

### `models.py`: the shared contract
Pydantic models for every shape that crosses the network. Two rules are built into the types:
- **Every datetime has a zone.** The `ZonedDatetime` type converts incoming times to UTC. A time **with no zone is treated as UTC and logged, never rejected**, because rejecting it would make the puck's upload queue retry the same segment forever.
- **Outgoing times are fixed-width UTC:** `2026-11-14T15:30:00.123Z`. The same format is used in the database, so sorting text = sorting time.

### `db.py`: SQLite
- One file, opened in **WAL mode**, so the API and the RQ worker can use it at the same time.
- `busy_timeout` makes a writer wait briefly instead of failing.
- Each request gets its own connection (`deps.get_conn`), closed afterwards.
- Lists are stored as JSON text, embeddings as float32 BLOBs.

| Table | What it holds |
|---|---|
| `people` | name, relationship, `is_patient`, phone, face photo key, facts |
| `face_embeddings` | face prints (512 numbers each), several per person; filled in M2 |
| `voice_prints` | voiceprints (192 numbers each) from setup calls; filled in M2 |
| `voice_clusters` | "unknown voice #N" groups from the puck, linked to a person once identified |
| `segments` | one row per puck upload: times, `local_text`, status `queued/done/failed` |
| `utterances` | what was said: text, times, `source` (`puck`/`call`), speaker, person |
| `sound_tags` | YAMNet background sounds ("Espresso machine", 0.81) |
| `calls` | FaceTime calls the agent logged |
| `visits`, `photos` | from the iOS app |
| `day_events` | the timeline ("9:10 · Blue Bean Café · coffee with Sarah"); filled by the day builder (Task 7) |

### `bus.py`: live events for the dashboard
- `emit(stage, payload)` sends `{stage, ts, payload}` to every open `/stream` connection. It's safe to call from any thread.
- It also keeps the last 200 events, so the dashboard can fill in when it first loads (`/events/recent`).
- The RQ worker runs in a different process and can't reach this in-memory bus, so it POSTs its events to `/events` and the API rebroadcasts them.

### `auth.py`: the lock
Every endpoint except `/health`, `/stream`, `/events/recent`, `/media/...` and `/dashboard` requires `Authorization: Bearer <CALYPSO_API_TOKEN>`. The comparison is constant-time (`hmac.compare_digest`).

### `storage.py`: files
A small interface (`put`, `get`, `delete`) with two implementations:
- **`LocalStorage`:** writes under `data/files/`. It refuses keys that try to escape that folder.
- **`S3Storage`:** **Vultr Object Storage**. Vultr's storage speaks the "S3" API, the standard that many providers use, so we use `boto3`, the standard Python client for it, pointed at Vultr's endpoint (`https://atl2.vultrobjects.com`). Nothing goes to Amazon. The setting names `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` and `AWS_PROFILE` are just what the library reads; their values are our **Vultr** keys.

Only **face crops and photos** are stored. **Audio is never stored.**

### `jobs.py`: background processing
Some work is too slow to do while the puck waits for its upload response: Grok speech-to-text and voice fingerprinting.
- `CALYPSO_JOBS=inline` runs the job right away, inside the request. It's simple, needs no Redis, and is used in tests and on laptops.
- `CALYPSO_JOBS=rq` puts the job on Keanu's Redis queue `recordings`. An RQ worker started from this repo picks it up, imports `calypso.jobs.process_segment`, and writes to the same SQLite file.

`process_segment(segment_uuid, wav_path)` today does this:
1. Turns the puck's `local_text` into an utterance.
2. Marks the segment `done`.
3. **Deletes the temporary WAV.**
4. Sends `puck.processed` to the dashboard.

If anything fails, the segment is marked `failed` and the WAV is **kept**, so an RQ retry can try again. Later milestones add Grok transcription, speaker separation and voice fingerprinting here.

### `deps.py`: shared helpers for routes
- Gives each route its DB connection, settings, storage and job runner.
- `public_base()` picks the base URL for links, in this order: `CALYPSO_PUBLIC_URL`, then the `X-Forwarded-Proto`/`X-Forwarded-Host` headers (for `tailscale serve` during dev), then the request's own address.
- `person_out()` turns a DB row into the `Person` JSON, building the **full** `face_photo_url`. The database only stores a storage key.

---

## 4. Walkthrough: one puck upload

```
POST /puck/segments  (audio WAV + meta JSON)
  1. auth check
  2. validate meta (segment_uuid format, times → UTC)           bad → 422
  3. read audio (≤ 5 MB)                                        too big → 413
  4. INSERT OR IGNORE into segments
        already there? → {"duplicate": true}  (the puck acks it and moves on)
  5. store sound tags, write the temp WAV to data/tmp/<uuid>.wav, commit
  6. emit "puck.segment" → dashboard
  7. jobs.enqueue(process_segment)
        can't queue (e.g. Redis down)? → undo steps 4–5 and return 503,
        so the puck's retry is processed instead of being acked as a duplicate
  8. return {"segment_uuid", "duplicate": false, "utterance_ids"}
```
This is how the review-focus rule "puck offline for hours, then reconnects → no duplicates, nothing lost" is met.

---

## 5. What's real vs. stubbed (M1)

| Area | Status |
|---|---|
| Health, SSE stream, event rebroadcast | ✅ real |
| Puck upload intake + health | ✅ real (processing uses `local_text` until Grok is added) |
| People list/create/rename, memories, patient filter | ✅ real |
| Media (faces, photos; sensitive → 404) | ✅ real |
| Calls + transcript lines | ✅ real |
| Days by local day, iOS visits and photos | ✅ real (no geocoding, resizing or sensitive check yet) |
| `/recognize` | 🟡 stub: always `learning` (final shape) |
| `/recall` | 🟡 stub: always `none`, `card: null` (final shape) |
| `/people/from_intro` | 🟡 stub: unnamed person + first face crop as their photo |
| `/days/{date}/rebuild` | 🟡 stub: reports the event count |

Teammates can build against the stubs now. When they become real, the request and response shapes don't change.

---

## 6. Running it

From `backend/`, after copying `.env.example` to `.env` at the repo root:

```bash
uv run --group dev pytest -v                                                     # all tests
uv run uvicorn calypso.app:app --host 127.0.0.1 --port 8000 --env-file ../.env  # the API
```
Then open:
- `http://127.0.0.1:8000/health`: should return `{"ok": true}`
- `http://127.0.0.1:8000/docs`: interactive API docs
- `http://127.0.0.1:8000/dashboard/`: the dashboard (placeholder for now)

Quick checks with `curl`, using the token from your `.env`:
```bash
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/people
curl -N http://127.0.0.1:8000/stream          # watch live events; leave it open
```

**Worker mode** (on the Vultr box, with Keanu's Redis reachable at `127.0.0.1:6379`):
```bash
# in .env: CALYPSO_JOBS=rq
uv run --env-file ../.env rq worker --url redis://127.0.0.1:6379/0 recordings
```

**Deploying (planned):** uvicorn listens on `127.0.0.1:8000`, and **Caddy** in front of it provides HTTPS on a domain. `CALYPSO_PUBLIC_URL` and the app's `API_BASE_URL` are both that `https://` address.

---

## 7. Tests

The `tests/` folder runs entirely on fakes: no network, no Redis, no API keys. `conftest.py` gives every test:
- a temporary DB and data folder
- local storage
- inline jobs
- the token `test-token`

| File | Covers |
|---|---|
| `test_models.py` | model defaults and validation |
| `test_skeleton.py` | health, auth, bus + SSE, DB round trip, time rules (no-zone = UTC, fixed-width format, Central-time day bounds) |
| `test_puck_ingest.py` | duplicate uploads ignored, sound tags, processing, temp audio deleted, 413/422, queue failure rolls back so the retry works, RQ queue name |
| `test_people_media.py` | people CRUD, memories, full https face URLs (and the forwarded-header fallback), media, sensitive photo 404, from_intro stub |
| `test_agent_and_app.py` | recognize/recall stub shapes, calls, days split by local day (7 pm CST lands on the right day), visits upsert, photo upload |

Run a single test: `uv run --group dev pytest tests/test_puck_ingest.py::test_duplicate_segment_uuid_ignored -v`

---

## 8. Adding the next pieces

1. **Write the tests first** in `tests/`, using fakes (`FakeLLM`, `FakeFaceEmbedder`, `FakeVoiceEmbedder`, `FakeSTT`).
2. **Put the logic in a new module:** `identity/face.py`, `identity/voice.py`, `identity/fuse.py`, `llm.py`, `speech/`.
3. **Swap the stub body in the matching route file.** Keep the request and response models unchanged.
4. **Emit a bus event** for anything the dashboard should show.
5. If you need new settings, add them to `config.py` **and** `.env.example`. Never commit secrets.

**Roadmap:**
- **M2:** enrollment and the face-first fuse rule
- **M3:** real models (insightface, SpeechBrain ECAPA) and threshold tuning
- **M4:** the puck pipeline on the RQ worker (Grok STT and speaker separation, voice clustering)
- **M5:** linking puck voices to people, and memories
- **M6:** day builder, recall, dashboard, deploy

---

## 9. Safety rules this code must keep

- **Never show the wrong person or a made-up place.** Close scores mean "uncertain", never a guess.
- **The patient is never the subject of an identity card.**
- **Sensitive photos are never served** (`/media/photos` returns 404).
- **Audio is never stored.** Temp WAVs are deleted after processing.
- **Secrets come only from env vars;** `.env` is git-ignored.
