# Calypso⁻¹ Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Calypso⁻¹, a dementia memory companion. A wearable puck turns the patient's day into a timeline. A Chert agent in a group FaceTime recognizes relatives and shows identity, "today", and memory cards on its own video tile.

**Architecture:** One monorepo with five parts that talk only through the backend's HTTP API (`backend/calypso/models.py` is the shared contract):
- `puck/`: Pi capture, offline queue, upload
- `backend/`: FastAPI on Vultr; identity, day builder, recall
- `agent/`: Chert LiveKit agent; recognition loop, cards rendered as outgoing video
- `ios/`: SwiftUI app
- `dashboard/`: static web page served by the backend

Every model, provider, and hardware choice that is still open sits behind one small interface with a fake implementation, so all four tracks can build and test before those choices are made.

**Tech Stack:** Python 3.11 (uv, FastAPI, SQLite, pytest, pydantic v2), Anthropic SDK (Claude Sonnet for summaries, Claude Haiku for detection), xAI Grok STT/TTS, SpeechBrain ECAPA, insightface, sentence-transformers, open_clip, LiveKit Python SDK via the Chert starter, Pillow, SwiftUI (iOS 17+), plain HTML/JS dashboard with server-sent events (SSE).

**Spec:** Appendix A at the bottom of this file. Task 0 saves it to `docs/superpowers/specs/2026-11-14-calypso-inv-design.md`.

## Global Constraints

- Product name in all user-facing text: **Calypso⁻¹**. Contact name in Contacts: `Calypso⁻¹`. Code identifiers: `calypso` / `calypso_inv`.
- Never show the wrong person or a made-up place. Below threshold, show neutral wording: "Getting to know someone new…" or "somewhere with café sounds."
- The agent stays silent in group calls, except for one confirmation question when learning a new person. It speaks freely in 1:1 setup calls.
- At most one card on screen at a time. Cards show for 6–10 s.
- In-call target: ≤ 2.5 s from the end of a sentence to the card on screen.
- The patient is enrolled as a `Person` with `is_patient=True` and is never the subject of an identity card.
- The puck must keep recording and queueing with no network.
- Photos flagged sensitive (cards, IDs, screenshots) are never searchable or shown.
- Secrets come only from env: `ANTHROPIC_API_KEY`, `XAI_API_KEY`, `CHERT_*`, `CALYPSO_API_TOKEN`. Every non-dashboard API call carries `Authorization: Bearer $CALYPSO_API_TOKEN`.
- **Flexibility rule:** STT, TTS, sound classifier, accelerator, face model, voice model, and the call topology each sit behind one interface with a `Fake*` implementation. Swapping a provider changes one adapter file and one env var (`CALYPSO_STT`, `CALYPSO_TTS`, `PUCK_SOUND_BACKEND`, `AGENT_TRACK_MODE`).

## Review Focus

1. **Two relatives with similar faces, or poor lighting.** The scores are close, so the agent must say "uncertain", never pick one. Test: `test_recognize_ambiguous_top2_is_uncertain` in Task 4.
2. **Puck offline for hours, then reconnects.** The queue drains in order with no duplicates when an upload is retried. Test: `test_queue_retry_is_idempotent` in Task 9 (the server dedupes on `segment_uuid`, also asserted in Task 3).
3. **A day with no visits and no speech** (patient home alone). The Today card says "A quiet day at home" instead of being empty or invented. Test: `test_today_card_empty_day` in Task 7.
4. **Someone says "today" in an unrelated sentence** ("the weather today is awful"). No Today card. Test: an entry in the negatives of `test_detector_today_phrasings` in Task 8.
5. **A new person joins while a card is showing.** The card queue holds the newcomer and the current card isn't cut off mid-read. Test: `test_card_scheduler_no_preempt_under_min` in Task 12.

---

## Tracks and owners (4 people)

| Track | Owner | Tasks | Task file |
|---|---|---|---|
| Spikes (everyone, hour 1) | all | 0 | each person's file lists their spike |
| Backend + dashboard | **Vishnu** | 1–8, 18 | `docs/tasks/vishnu-backend.md` |
| Puck | **Matt** | 9–10 | `docs/tasks/matt-puck.md` |
| Agent | **Keanu** | 11–15 | `docs/tasks/keanu-agent.md` |
| iOS app | **Eric** | 16–17 | `docs/tasks/eric-ios.md` |
| Demo | all | 19 | `docs/tasks/all-demo.md` |

Spike owners: A (group tracks) + B (group dial) → Keanu; C (Grok speech) → Vishnu; D (mic + accelerator) → Matt; Eric sets up the repo and Xcode project.

## Baseplate (created in the repo before the tracks start)
Repo: `github.com/matthewthomasbeck/HackUTA`, cloned to `~/coding/personal/HackUTA`.
- `README.md` (what Calypso⁻¹ is, layout, how to run each part, owners)
- `docs/superpowers/specs/2026-11-14-calypso-inv-design.md` (Appendix A) and `docs/superpowers/plans/2026-11-14-calypso-inv.md` (this plan)
- `docs/tasks/{vishnu-backend,matt-puck,keanu-agent,eric-ios,all-demo}.md` (each person's tasks copied verbatim from this plan, plus their spike and the interfaces they consume)
- `docs/spikes.md` (a template with the decision keys from Task 0)
- Scaffolds that run but do nothing yet:
  - `backend/`: `pyproject.toml`, `calypso/__init__.py`, `calypso/models.py` (the full shared contract from Task 1), `tests/`
  - `puck/`: `pyproject.toml`, `calypso_puck/__init__.py`, `tests/`
  - `agent/`: `pyproject.toml`, `calypso_agent/__init__.py`, `tests/`
  - `ios/`: a README with the Xcode setup steps (Eric creates the project in Xcode)
  - `dashboard/index.html` (placeholder)
  - `scripts/`
  - `.env.example` (all env keys), `.gitignore`
- One commit, `chore: Calypso⁻¹ baseplate, plan, and per-person tasks`, pushed to `main` (or a branch, if the repo already has content on `main` that would conflict)

Tasks 1 and 11 unblock others. The agent and iOS tracks use `FakeBackend` / fixture JSON until Task 1's API is deployed.

---

### Task 0: Repo, spec, and hour-1 spikes

**Files:**
- Create: `README.md`, `docs/superpowers/specs/2026-11-14-calypso-inv-design.md` (Appendix A), `docs/spikes.md`
- Create: `agent/spikes/log_tracks.py`, `puck/spikes/mic_check.sh`, `backend/spikes/grok_speech.py`

**Interfaces:**
- Produces: `docs/spikes.md` with the recorded decisions, which later tasks read:
  - `AGENT_TRACK_MODE` = `per_participant` | `composite`
  - `GROUP_CALL_START` = `agent_dials_both` | `agent_dials_relative_then_add` | `manual_only`
  - Grok STT mode = `streaming` | `batch_only`; Grok TTS = `ok` | `fallback:<name>`
  - Accelerator = `coral` | `hailo` | `none`
  - Mic device name

- [x] **Step 1:** Baseplate repo created (this repo): folders, spec, plan, and per-person task files.
- [ ] **Step 2: Spike A (group tracks).** Set up Chert from the starter (`chert dev`). Write `log_tracks.py`, which joins the room and prints, every 2 s: each remote participant's `identity`, its audio and video track sids, and video resolution. Three phones join a group FaceTime: the Chert line plus two teammates.
  Expected: either 2 remote participants, each with its own tracks → `per_participant`; or 1 participant with a grid video → `composite`. Record which one.
- [ ] **Step 3: Spike B (agent starts the group call).** Try `POST /calls` to teammate 1. Once connected, try adding teammate 2: a second `POST /calls`, then teammate 1 using Add People. Record what works as `GROUP_CALL_START`. Also record whether a call drops at 5 minutes.
- [ ] **Step 4: Spike C (Grok speech).** `grok_speech.py` transcribes `fixtures/two_speakers.wav` and synthesizes "Hi, I'm Calypso." Record the latency of each, and whether streaming STT exists.
- [ ] **Step 5: Spike D (puck).** `mic_check.sh` runs `arecord -l`, records 5 s from the Saramonic, and plays it back. If the accelerator has arrived, run its YAMNet demo. Record the device name and accelerator.
- [ ] **Step 6:** Fill in `docs/spikes.md`, then commit `chore: hour-1 spike results`.

---

### Task 1: Backend skeleton, shared models, DB, event bus

**Files:**
- Create: `backend/pyproject.toml`, `backend/calypso/{__init__,app,models,db,bus,auth,config}.py`
- Test: `backend/tests/test_skeleton.py`

**Interfaces:**
- Produces, in `calypso/models.py` (pydantic):
  - `Person(id:str, name:str|None, relationship:str|None, is_patient:bool=False, face_photo_url:str|None, facts:list[str]=[])`
  - `Utterance(id:str, segment_uuid:str, ts_start:datetime, ts_end:datetime, text:str, source:Literal["puck","call"], voice_cluster_id:str|None, person_id:str|None)`
  - `SoundTag(ts:datetime, label:str, score:float)`
  - `Visit(id:str, arrived:datetime, departed:datetime|None, lat:float, lon:float, place_name:str|None)`
  - `Photo(id:str, taken_at:datetime, lat:float|None, lon:float|None, path:str, sensitive:bool, caption:str|None, event_id:str|None)`
  - `DayEvent(id:str, start:datetime, end:datetime, place:str, place_confidence:float, people:list[str], summary:str, evidence:list[str], photo_ids:list[str])`
  - `RecognitionResult(status:Literal["identified","learning","uncertain"], person_id:str|None, face_score:float|None, voice_score:float|None)`
  - `Intent(intent:Literal["today","person","memory","photo","none"], query:str|None, date_hint:str|None, place_hint:str|None)`
  - `Card(kind:Literal["identity","learning","today","memory"], title:str, lines:list[str], image_urls:list[str]=[])`
- Produces:
  - `db.connect(path:str) -> sqlite3.Connection` (creates the schema for every model above, plus `face_embeddings(person_id, vec BLOB)` and `voice_clusters(id, centroid BLOB, person_id NULL)`)
  - `bus.emit(stage:str, payload:dict) -> None`
  - `GET /stream` (SSE of `{stage, ts, payload}`)
  - `GET /health`
  - the `require_token` dependency
- Config (`config.py`, env with defaults): `FACE_MATCH=0.45`, `FACE_MARGIN=0.08`, `VOICE_MATCH=0.60`, `PLACE_CONF_MIN=0.6`, `RECALL_MIN=0.35`. These are starting values to tune in Tasks 4 and 8.

- [ ] **Step 1: Write the failing tests.**
  - `test_health_ok`: `GET /health` → 200 `{"ok": true}`
  - `test_requires_token`: `GET /people` with no header → 401
  - `test_bus_stream_receives_emit`: subscribe to `/stream` (TestClient stream), `bus.emit("test", {"a":1})` → the first event has `stage=="test"`
  - `test_db_roundtrip_person`: insert a `Person`, read it back, fields equal
- [ ] **Step 2:** `uv run pytest backend/tests/test_skeleton.py -v` → FAIL (import errors).
- [ ] **Step 3:** Implement the models, `db.connect`, the in-process `bus` (an asyncio fan-out queue), and the app with `/health`, `/stream`, `GET /people`. Serve `dashboard/` as static files at `/dashboard`.
- [ ] **Step 4:** Run the tests → PASS.
- [ ] **Step 5:** Deploy to Vultr: `uv run uvicorn calypso.app:app --host 0.0.0.0 --port 8000` behind Caddy for HTTPS. Then `curl https://<host>/health` → `{"ok":true}`. Commit `feat(backend): skeleton, models, bus`.

---

### Task 2: Speech adapters (STT/TTS), swappable

**Files:**
- Create: `backend/calypso/speech/{__init__,base,grok,whisper_local,fake}.py`
- Test: `backend/tests/test_speech.py`

**Interfaces:**
- Produces:
  - `class STT(Protocol): def transcribe(self, wav: bytes) -> list[TranscriptSegment]`, where `TranscriptSegment(start_s:float, end_s:float, text:str)`
  - `class TTS(Protocol): def synthesize(self, text:str) -> bytes` (16 kHz mono PCM WAV)
  - `get_stt() / get_tts()` pick an implementation from `CALYPSO_STT` / `CALYPSO_TTS` ∈ {`grok`, `whisper`, `fake`}; default `grok`
- **Flexibility:** if Spike C says Grok can only stream, `GrokSTT` wraps the stream to fill the batch interface. If Grok TTS fails, add another provider as a new file and add one env value. Nothing else changes.

- [ ] **Step 1: Write the failing tests.**
  - `test_fake_stt_returns_segments`: `FakeSTT(["hi"]).transcribe(b"...")[0].text == "hi"`
  - `test_get_stt_env_switch`: monkeypatch `CALYPSO_STT=fake` → `isinstance(get_stt(), FakeSTT)`
  - `test_grok_stt_live` (marked `@pytest.mark.live`, skipped without `XAI_API_KEY`): on `fixtures/hello.wav`, the text contains "hello"
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement `base`, `fake`, `grok` (using the endpoints confirmed in Spike C), and `whisper_local` (faster-whisper `base.en`; it runs on the Vultr GPU if one is available).
- [ ] **Step 4:** `pytest backend/tests/test_speech.py -v` → PASS (live test skipped or passing).
- [ ] **Step 5:** Commit `feat(backend): swappable STT/TTS`.

---

### Task 3: Puck ingestion → transcripts → voice clusters

**Files:**
- Create: `backend/calypso/identity/voice.py`, `backend/calypso/routes/puck.py`
- Test: `backend/tests/test_puck_ingest.py`, fixtures `fixtures/spk_a_*.wav`, `fixtures/spk_b_*.wav` (record 3 × 5 s clips each of two teammates)

**Interfaces:**
- Consumes: `get_stt()`, `db`, `bus.emit`
- Produces:
  - `class VoiceEmbedder(Protocol): def embed(self, wav:bytes) -> np.ndarray` (`EcapaEmbedder`, `FakeVoiceEmbedder`)
  - `assign_cluster(conn, vec) -> str`: nearest centroid if cosine ≥ `VOICE_MATCH`, else a new cluster; updates the centroid as a running mean
  - `POST /puck/segments`: multipart `audio` (wav) plus a `meta` JSON field with `{segment_uuid, ts_start, ts_end, sound_tags:[SoundTag], local_text:str|None}`. Returns `{utterance_ids:[str], duplicate:bool}`. Emits `puck.segment`.

- [ ] **Step 1: Write the failing tests.**
  - `test_same_speaker_same_cluster`: 3 clips of speaker A → 1 cluster id
  - `test_two_speakers_two_clusters`: A and B clips → 2 distinct ids
  - `test_duplicate_segment_uuid_ignored`: posting the same `segment_uuid` twice → second response `duplicate==True`, utterance count unchanged
  - `test_sound_tags_stored`
  - `test_stt_failure_keeps_local_text`: `FakeSTT` raises → the utterance stores `local_text`
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement. Server STT is preferred and `local_text` is the fallback. Store the audio file under `data/audio/<segment_uuid>.wav`. When the cluster has a `person_id`, set `person_id` on its utterances.
- [ ] **Step 4:** Run → PASS. If the A/B clips don't separate at 0.60, tune `VOICE_MATCH` and write the chosen value in `config.py`.
- [ ] **Step 5:** Commit `feat(backend): puck ingest + voice clustering`.

---

### Task 4: Face identity and `/recognize` fusion

**Files:**
- Create: `backend/calypso/identity/{face,fuse}.py`, `backend/calypso/routes/recognize.py`
- Test: `backend/tests/test_recognize.py`, fixtures `fixtures/faces/<name>_{1..3}.jpg` (3 teammates plus one stranger)

**Interfaces:**
- Produces:
  - `class FaceEmbedder(Protocol): def embed_all(self, jpeg:bytes) -> list[tuple[BBox, np.ndarray]]` (`InsightFaceEmbedder`, `FakeFaceEmbedder`). It returns all faces, so composite grid video works too.
  - `fuse(face_scores:dict[str,float], voice_scores:dict[str,float]) -> RecognitionResult`
  - `POST /recognize` with `{face_jpeg_b64:str|None, voice_wav_b64:str|None, exclude_patient:bool=True}` → `{faces:[{bbox, result:RecognitionResult}]}`
  - `POST /people/{id}/faces` (enroll a jpeg)
- `fuse` rule:
  - **identified** if the top face score ≥ `FACE_MATCH` and (top − second) ≥ `FACE_MARGIN`, and voice doesn't disagree (voice top is a different person with ≥ `VOICE_MATCH` → uncertain)
  - **learning** if no face score ≥ 0.30
  - **uncertain** otherwise
  - With no face, voice alone ≥ `VOICE_MATCH` + 0.1 → identified

- [ ] **Step 1: Write the failing tests.**
  - `test_enrolled_face_identified`
  - `test_stranger_is_learning`
  - `test_recognize_ambiguous_top2_is_uncertain`: scores {a:0.50, b:0.47} → uncertain
  - `test_voice_disagreement_uncertain`
  - `test_patient_never_returned`
  - `test_composite_frame_two_faces`: a two-face image → 2 entries
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement. Store embeddings in `face_embeddings` and match against each person's max cosine. Emit `recognize` with all scores, for the dashboard.
- [ ] **Step 4:** Run → PASS. Tune `FACE_MATCH` / `FACE_MARGIN` on the fixtures so the stranger is never identified, and record the values.
- [ ] **Step 5:** Commit `feat(backend): face recognition + fusion`.

---

### Task 5: People from setup calls (Claude extraction)

**Files:**
- Create: `backend/calypso/llm.py`, `backend/calypso/routes/people.py`
- Test: `backend/tests/test_people.py`

**Interfaces:**
- Produces:
  - `llm.extract_intro(transcript:str) -> IntroFacts(name:str|None, relationship:str|None, facts:list[str])`. Claude Sonnet, JSON-only output parsed with pydantic. Any parse failure returns all-None.
  - `POST /people/from_intro` with `{transcript, face_jpegs_b64:[str], voice_wav_b64:str|None}` → `Person` (enrolls the faces, links the voice cluster)
  - `PATCH /people/{id}`, `GET /people/{id}` (includes the last 5 memories: utterance summaries)
  - `llm.client` is injectable, and tests use `FakeLLM`

- [ ] **Step 1: Write the failing tests.**
  - `test_extract_intro_parses`: FakeLLM returns `{"name":"Gary","relationship":"friend from HackUTA","facts":["builds AI"]}` → fields match
  - `test_extract_intro_garbage_returns_none`
  - `test_from_intro_enrolls_face_and_links_cluster`: afterwards, `/recognize` on the same face → identified as that person
  - `test_unnamed_visitor`: name None → Person.name == None, and the dashboard and app show "Unnamed visitor"
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(backend): people from setup-call intros`.

---

### Task 6: Visits and photos ingestion

**Files:**
- Create: `backend/calypso/routes/app_ingest.py`, `backend/calypso/photos.py`
- Test: `backend/tests/test_app_ingest.py`

**Interfaces:**
- Produces:
  - `POST /app/visits` with `[Visit]`. Upserts by `id`. Fills `place_name` via reverse geocoding if missing (a Nominatim call, cached by about 100 m cell; a fake in tests).
  - `POST /app/photos`: multipart `image` plus `meta {id, taken_at, lat, lon}`. Resizes to 1024 px, computes a CLIP embedding, and sets the `sensitive` flag via Claude Haiku vision ("does this show a card, ID, document, or screenshot? yes/no").
  - `photos.attach_to_event(conn, photo_id)` is called by Task 7.

- [ ] **Step 1: Write the failing tests.**
  - `test_visit_upsert_idempotent`
  - `test_photo_resized_to_1024`
  - `test_sensitive_photo_flagged`: FakeLLM says yes → `sensitive=True`
  - `test_photo_duplicate_id_ignored`
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(backend): visits + photos`.

---

### Task 7: Day builder (timeline events) and Today card data

**Files:**
- Create: `backend/calypso/day/builder.py`, `backend/calypso/routes/days.py`
- Test: `backend/tests/test_day_builder.py`

**Interfaces:**
- Consumes: utterances, sound tags, visits, photos, people
- Produces:
  - `gather_window(conn, start, end) -> WindowEvidence` (utterances with speaker names, top sound tags, overlapping visits, photos)
  - `build_events(conn, day:date, llm) -> list[DayEvent]`. Windows split at visit boundaries, otherwise every 15 minutes, and silent windows merge. Claude writes `place`, `place_confidence`, `summary`, and `evidence`.
  - `GET /days/{yyyy-mm-dd}/events`
  - `POST /days/{date}/rebuild`
  - `today_card(conn, day) -> Card`: the 3–5 most notable events, each "h:mm · Place · summary"; a photo URL per event when one exists
- Rules, enforced in code after the LLM step, not trusted to the prompt:
  - If `place_confidence < PLACE_CONF_MIN`, `place` is rewritten to a neutral `"somewhere with {top_sound_tag} sounds"`, or `"somewhere"`.
  - A visit's `place_name` sets `place_confidence = max(llm, 0.9)`.
- The builder runs on a 15-minute background loop and on demand.

- [ ] **Step 1: Write the failing tests** (FakeLLM):
  - `test_visit_sets_place`: a visit "Blue Bean Café" 9:10–9:40 plus utterances "let me grab a coffee" → one event with place "Blue Bean Café", confidence ≥ 0.9
  - `test_low_confidence_place_is_neutral`: no visit, the LLM says "Starbucks" at 0.3, top tag "Espresso machine" → place `"somewhere with espresso machine sounds"`
  - `test_photo_attached_by_time`
  - `test_today_card_empty_day`: no data → `Card(kind="today", title="Today", lines=["A quiet day at home"])`
  - `test_today_card_max_five`
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(backend): day builder + today card`.

---

### Task 8: In-call recall: detector and search

**Files:**
- Create: `backend/calypso/recall/{detector,search}.py`, `backend/calypso/routes/recall.py`
- Test: `backend/tests/test_recall.py`, `backend/tests/fixtures/detector_cases.yaml` (~30 labeled lines)

**Interfaces:**
- Produces:
  - `detect(lines:list[CallLine], llm) -> Intent`, where `CallLine(speaker:str, text:str)`. The prompt puts earlier lines under "context only" and the newest under "LAST LINE", and judges only the last line, so older mentions don't leak into new queries.
  - `search(conn, intent:Intent) -> Card|None`. `today` → `today_card`. `person` → identity card for the named person. `memory`/`photo` → sentence-transformers over event summaries, plus CLIP text→image over non-sensitive photos, filtered by date/place hints. Returns `None` below `RECALL_MIN`.
  - `POST /recall` with `{lines:[CallLine]}` → `{intent:Intent, card:Card|None}`. Emits `recall.detect` and `recall.search` (top-3 scores plus threshold) for the dashboard.

- [ ] **Step 1: Write the failing tests.**
  - `test_detector_today_phrasings` (live, Haiku). Positives, all → `today`: "what did you do today?", "how was your day, Mom?", "did you go anywhere this morning?", "what have you been up to?", "tell me about your day". Negatives, all → `none`: "the weather today is awful", "I'm busy today", "today traffic was bad", "see you today at 5", "what time is it?"
  - `test_detector_only_last_line`: context "remember the beach?" then last line "anyway how are you" → `none`
  - `test_search_below_threshold_returns_none`
  - `test_search_skips_sensitive_photos`
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. Use Claude Haiku with JSON output and a `max_tokens` around 100.
- [ ] **Step 4:** Run → PASS. Run the full `detector_cases.yaml`: precision ≥ 0.85 on `none` vs. not-none. Adjust the prompt until it passes.
- [ ] **Step 5:** Commit `feat(backend): in-call recall`.

---

### Task 9: Puck capture, VAD, offline queue, uploader

**Files:**
- Create: `puck/pyproject.toml`, `puck/calypso_puck/{capture,vad,queue,uploader,main,config}.py`, `puck/systemd/calypso-puck.service`
- Test: `puck/tests/test_queue.py`, `puck/tests/test_uploader.py`, `puck/tests/test_vad.py`

**Interfaces:**
- Consumes: `POST /puck/segments` (Task 3 contract)
- Produces:
  - `capture.frames(device:str) -> Iterator[bytes]`: 30 ms 16 kHz mono frames via `sounddevice`. The device name comes from Spike D (`PUCK_MIC`).
  - `vad.segments(frames) -> Iterator[Segment(uuid, ts_start, ts_end, wav:bytes)]`: webrtcvad, ≥ 0.5 s of speech, splits at 1 s of silence or 15 s maximum
  - `Queue(path)` with `.put(segment, tags, local_text)`, `.peek_batch(n)`, `.ack(uuid)`, `.depth()`. SQLite with WAL, stored on disk.
  - `Uploader(queue, base_url, token).drain_once() -> int`: oldest first. It acks on 2xx or `duplicate:true` and stops at the first network error (exponential backoff in `main`).
  - Timestamps use the system clock. `main` logs a warning if the time isn't synced yet (the Pi has no battery-backed clock, so it relies on NTP over the hotspot).

- [ ] **Step 1: Write the failing tests.**
  - `test_queue_survives_restart`: put, close, reopen → depth 1
  - `test_queue_retry_is_idempotent`: the server (fake) returns 500 then 200 → the item is uploaded once and acked
  - `test_drain_in_order`
  - `test_offline_stops_and_keeps_items`: a connection error → returns 0, depth unchanged
  - `test_vad_splits_on_silence`: a speech/silence/speech fixture → 2 segments
- [ ] **Step 2:** `cd puck && uv run pytest -v` → FAIL. **Step 3:** Implement. **Step 4:** Run → PASS.
- [ ] **Step 5:** On the Pi: install the systemd unit, start it, and talk for 30 s with the hotspot off. Check that `depth()` > 0. Turn the hotspot on. Within 30 s the dashboard `/stream` shows `puck.segment` events.
- [ ] **Step 6:** Commit `feat(puck): capture, offline queue, uploader`.

---

### Task 10: Puck sound classifier (accelerator-agnostic) and local transcript fallback

**Files:**
- Create: `puck/calypso_puck/sounds/{__init__,base,cpu_tflite,coral,hailo,fake}.py`, `puck/calypso_puck/local_stt.py`
- Test: `puck/tests/test_sounds.py`

**Interfaces:**
- Produces:
  - `classify_sounds(wav:bytes) -> list[SoundTag]`: top 3 YAMNet labels with score ≥ 0.2, timestamped. The backend is picked by `PUCK_SOUND_BACKEND` ∈ {`cpu`, `coral`, `hailo`, `fake`}; default `cpu` (tflite-runtime YAMNet).
  - `local_transcribe(wav) -> str|None`: whisper.cpp `tiny.en` via a subprocess. Returns None if the binary is missing or it takes over 5 s.
  - `main` calls both for each segment before `Queue.put`.
- **Flexibility:** `coral.py` / `hailo.py` are written only once the hardware lead chooses (Spike D or later). Until then they raise `NotImplementedError` and the factory falls back to `cpu` with a logged warning. If the CPU can't keep up on the Pi 4, set `PUCK_SOUND_EVERY_N=3` to classify every third segment.

- [ ] **Step 1: Write the failing tests.**
  - `test_factory_fallback_to_cpu`: `PUCK_SOUND_BACKEND=coral` with no device → a `CpuTflite` instance
  - `test_cpu_tags_cafe` (skipped if the model file is missing): `fixtures/cafe.wav` → the top-3 labels include any of {"Espresso machine", "Dishes, pots, and pans", "Chatter"}
  - `test_local_transcribe_missing_binary_none`
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run → PASS.
- [ ] **Step 5:** On the Pi: measure ms per segment for `cpu` (and for the accelerator once chosen). Note it in `docs/spikes.md`.
- [ ] **Step 6:** Commit `feat(puck): sound tags + local transcript fallback`.

---

### Task 11: Card renderer

**Files:**
- Create: `agent/pyproject.toml`, `agent/calypso_agent/cards.py`, `agent/calypso_agent/assets/` (font, logo)
- Test: `agent/tests/test_cards.py`

**Interfaces:**
- Consumes: the `Card` model (copy `backend/calypso/models.py` into `agent/calypso_agent/contract.py`, or import it as a path dependency)
- Produces:
  - `render(card:Card, images:dict[str,PIL.Image]) -> PIL.Image`: 1280×720 RGB with large type (title ≥ 72 px, lines ≥ 40 px) and high contrast for elderly viewers
  - `idle_frame() -> PIL.Image`: the Calypso⁻¹ logo plus a soft "Listening…" label

- [ ] **Step 1: Write the failing tests.**
  - `test_render_size`: every kind → (1280, 720)
  - `test_long_lines_wrap_not_overflow`: a 200-character line → no text pixels in the outer 40 px margin
  - `test_identity_with_missing_photo_uses_placeholder`
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement with Pillow. **Step 4:** Run → PASS.
- [ ] **Step 5:** `uv run python -m calypso_agent.cards --demo` writes `out/*.png`. Check them by eye, then commit `feat(agent): card renderer`.

---

### Task 12: Agent core: tracks, recognition loop, card scheduler

**Files:**
- Create: `agent/calypso_agent/{main,tracks,video_out,scheduler,backend_client,state}.py`
- Test: `agent/tests/test_scheduler.py`, `agent/tests/test_state.py`

**Interfaces:**
- Consumes: `POST /recognize` (Task 4), `render` (Task 11), `AGENT_TRACK_MODE` (Spike A)
- Produces:
  - `tracks.FrameSource` yields `(participant_key:str, jpeg:bytes)` at 1 fps. In `per_participant` mode the key is the participant identity. In `composite` mode one frame produces several keys, one per face bbox from `/recognize`.
  - `CallState` holds `participants: dict[key, RecognitionResult]` and `on_result(key, result) -> list[Card]`. It produces an identity card the first time a key becomes `identified`, and a learning card the first time a key is `learning` for ≥ 3 consecutive frames (debounced).
  - `CardScheduler(min_show_s=6, max_show_s=10)` with `.push(card)` and `.current(now) -> Card|None`. FIFO, no preemption before `min_show_s`, no duplicate cards within 60 s.
  - `video_out.Publisher(room)` publishes a 1280×720 track at 5 fps from `scheduler.current()`, or `idle_frame()`.
  - `BackendClient` wraps the HTTP calls; `FakeBackendClient` serves the tests.

- [ ] **Step 1: Write the failing tests.**
  - `test_identified_emits_identity_card_once`
  - `test_learning_debounced_three_frames`
  - `test_patient_ignored` (the backend returns nothing for the patient → no card)
  - `test_card_scheduler_no_preempt_under_min`: push A at t=0 and B at t=2 → current(4) is A, current(7) is B
  - `test_no_duplicate_within_60s`
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. `main.py` starts from the Chert starter's entrypoint and connects FrameSource → backend → CallState → scheduler → Publisher. **Step 4:** Run → PASS.
- [ ] **Step 5 (live):** Enroll a teammate's face with `POST /people/{id}/faces`. Run a group FaceTime with Calypso⁻¹. The identity card appears within 5 s; a non-enrolled teammate gets the learning card. Watch it on the dashboard.
- [ ] **Step 6:** Commit `feat(agent): recognition loop + cards on video`.

---

### Task 13: Setup call and learn-in-call conversation

**Files:**
- Create: `agent/calypso_agent/{conversation,speech}.py`
- Test: `agent/tests/test_conversation.py`

**Interfaces:**
- Consumes: Grok STT/TTS (agent-side adapters with the same `STT`/`TTS` protocol as Task 2), `POST /people/from_intro` (Task 5), `CallState`
- Produces:
  - `SetupScript`: a state machine for 1:1 calls with an unknown caller. Steps: `greet` ("Hi, I'm Calypso⁻¹. I help Mary remember the people she loves. Who are you to her?") → `ask_memory` ("What's something you two share?") → `confirm` → `done`. On `done` it calls `/people/from_intro` with the transcript and 3 face crops.
  - `LearnInCall`: in a group call, once a `learning` key hears an intro line (via `llm.extract_intro` on the last 30 s), it speaks once: "Nice to meet you, {name}. How do you know Mary?" It enrolls after the answer. If nothing comes after 90 s, it saves an unnamed visitor.
  - The patient's name comes from `GET /people?is_patient=true`.

- [ ] **Step 1: Write the failing tests** (fake STT/TTS/backend):
  - `test_setup_script_happy_path_creates_person`
  - `test_setup_script_silence_reprompts_once_then_ends`
  - `test_learn_in_call_speaks_once`
  - `test_learn_in_call_timeout_unnamed_visitor`
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run → PASS.
- [ ] **Step 5 (live):** A new teammate FaceTimes Calypso⁻¹ 1:1, completes setup, hangs up, and calls again → identity card. Commit `feat(agent): setup call + learn-in-call`.

---

### Task 14: In-call recall loop

**Files:**
- Create: `agent/calypso_agent/recall_loop.py`
- Test: `agent/tests/test_recall_loop.py`

**Interfaces:**
- Consumes: agent STT (per-participant tracks if `per_participant`, mixed audio with voice attribution if `composite`), `POST /recall` (Task 8), `CardScheduler`
- Produces: `RecallLoop(window_s=60)`. On each final transcript line it posts the last 60 s of lines and pushes the returned card. Drops it if the round trip takes over 4 s. Emits a latency log.

- [ ] **Step 1: Write the failing tests.**
  - `test_today_line_pushes_today_card`
  - `test_none_intent_pushes_nothing`
  - `test_slow_backend_dropped`: the fake sleeps 5 s → no card
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run → PASS.
- [ ] **Step 5 (live):** In a group call, say "Mom, what did you do today?" → Today card within 2.5 s (check the dashboard latency panel). Commit `feat(agent): in-call recall`.

---

### Task 15: iMessage intake and agent-started group call

**Files:**
- Create: `agent/calypso_agent/{imessage,dialer}.py`
- Test: `agent/tests/test_imessage.py`, `agent/tests/test_dialer.py`

**Interfaces:**
- Consumes: Chert `GET/POST /shared-messages`, `POST /calls`, `GROUP_CALL_START` (Spike B)
- Produces:
  - `handle_message(msg) -> Action`. A photo attachment from a known relative → `POST /people/{id}/faces` or a memory note. Text "call mom with me" (any phrasing, via Claude Haiku) → `Dial(relative_phone, patient_phone)`. Anything else → a short reply.
  - `Dialer.start_group(relative, patient)` uses whichever `GROUP_CALL_START` strategy Spike B recorded:
    - `agent_dials_both`: two `POST /calls`
    - `agent_dials_relative_then_add`: calls the relative and texts them "Tap Add People → Mom"
    - `manual_only`: texts the relative the steps
- Note: Chert only lets the agent text phones that have joined a call, so relatives must do the setup call (Task 13) first.

- [ ] **Step 1: Write the failing tests.**
  - `test_call_request_variants_detected` ("call mom with me", "can you get mom on facetime with me", "start a call with grandma")
  - `test_dialer_strategy_from_env` (each of the 3 strategies produces the expected API calls or texts against a fake Chert client)
  - `test_unknown_sender_ignored`
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement with polling every 3 s; no webhooks are documented. **Step 4:** Run → PASS.
- [ ] **Step 5 (live):** Text "call mom with me" → a group call forms (or the fallback text arrives). Commit `feat(agent): iMessage intake + group dial`.

---

### Task 16: iOS app: onboarding and add contact

**Files:**
- Create: `ios/Calypso/` (Xcode project, SwiftUI, iOS 17), `ios/Calypso/Onboarding/{OnboardingView,AddContactView,GroupCallHowToView,PermissionsView}.swift`, `ios/Calypso/Core/{APIClient,Models,Config}.swift`
- Test: `ios/CalypsoTests/{ModelsDecodingTests,ContactBuilderTests}.swift`

**Interfaces:**
- Consumes: the JSON shapes from Task 1 (`Person`, `DayEvent`, `Card`). Until the backend is live, use the fixture files in `ios/CalypsoTests/Fixtures/*.json`.
- Produces:
  - `APIClient(baseURL:token:)` with async `people()`, `events(day:)`, `uploadPhoto(_:)`, `uploadVisits(_:)`
  - `ContactBuilder.calypso(phone:) -> CNMutableContact` with given name "Calypso⁻¹", the phone number from `Config.chertPhone`, and the app logo as its image
  - Onboarding flow: Welcome → "Add Calypso⁻¹ to Contacts" (`CNContactViewController(forNewContact:)`, prefilled) → "How to start a group FaceTime" (3 illustrated steps: FaceTime → New FaceTime → add Mom + Calypso⁻¹ → Video, plus the "Or text Calypso⁻¹: *call Mom with me*" shortcut) → permissions (Photos, Location Always for Visits) → done. Completion is stored in `@AppStorage("onboarded")`.

- [ ] **Step 1: Write the failing tests.**
  - `testDecodePerson`, `testDecodeDayEvent` (from fixtures, including ISO-8601 dates)
  - `testCalypsoContactHasNameAndPhone`
- [ ] **Step 2:** Run with `xcodebuild test -scheme Calypso -destination 'platform=iOS Simulator,name=iPhone 16'` → FAIL.
- [ ] **Step 3:** Implement the models, `APIClient`, `ContactBuilder`, and the onboarding views.
- [ ] **Step 4:** Run the tests → PASS. On a device, the onboarding adds the contact and it shows up in FaceTime search.
- [ ] **Step 5:** Commit `feat(ios): onboarding + add Calypso⁻¹ contact`.

---

### Task 17: iOS app: People, Today timeline, photo and visit uploaders

**Files:**
- Create: `ios/Calypso/People/{PeopleListView,PersonDetailView}.swift`, `ios/Calypso/Today/{TodayView,EventRow}.swift`, `ios/Calypso/Sync/{PhotoSync,VisitSync}.swift`
- Test: `ios/CalypsoTests/{PhotoSyncTests,VisitSyncTests}.swift`

**Interfaces:**
- Consumes: `APIClient` (Task 16)
- Produces:
  - `PhotoSync.newAssets(since:) -> [PHAsset]` (excludes screenshots and hidden photos) and `.upload(asset)`, sending the image plus `taken_at` and EXIF lat/lon. The last-sync date is kept in UserDefaults.
  - `VisitSync`: a `CLLocationManager.startMonitoringVisits()` delegate that queues visits and uploads them on arrival and departure. An open visit has `departed = nil`.
  - `TodayView`: date picker plus a list of `EventRow` ("9:10 · Blue Bean Café · summary", people chips, photo thumbs). Pull to refresh.
  - `PeopleListView` / `PersonDetailView`: face, name (or "Unnamed visitor", with an edit-name action through `PATCH`), relationship, and recent memories.

- [ ] **Step 1: Write the failing tests.**
  - `testVisitMapsDistantFutureToNilDeparture` (CLVisit uses `.distantFuture` for "still here")
  - `testPhotoSyncSkipsScreenshots` (mediaSubtypes filter)
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run → PASS.
- [ ] **Step 5:** On a device: take a photo, then pull to refresh in Today 15 minutes later (or after `POST /days/{date}/rebuild`) → the photo shows up under the right event. Commit `feat(ios): people, today timeline, sync`.

---

### Task 18: Judge dashboard

**Files:**
- Create: `dashboard/index.html`, `dashboard/app.js`, `dashboard/style.css`
- Modify: the backend modules already emit to `bus` (Tasks 3–8). Add `bus.emit` calls to any stage that's missing them.
- Test: `backend/tests/test_dashboard_feed.py`

**Interfaces:**
- Consumes: `GET /stream` (SSE), `GET /days/{date}/events`, `GET /people`
- Event stages the page renders: `puck.segment`, `puck.health` (queue depth, sound backend, ms/segment, sent by the puck every 30 s via `POST /puck/health`, which is added in this task), `recognize`, `recall.detect`, `recall.search`, `card.shown` (the agent posts `POST /agent/events`, added in this task), `day.built`
- Panels:
  1. **Day timeline:** swimlanes for speakers, place events (opacity = confidence, with the evidence on hover), sound tags, photos, and calls
  2. **Live call:** participant list with face/voice scores and status, the latest intent, top-3 matches against the threshold line, the current card thumbnail
  3. **Pipeline health:** per-stage latency sparkline, puck online (last health < 60 s ago) or offline, queue depth, counts

- [ ] **Step 1: Write the failing tests.**
  - `test_agent_event_rebroadcast`: `POST /agent/events {stage:"card.shown"}` → appears on `/stream`
  - `test_puck_health_rebroadcast`
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement the endpoints and the page (vanilla JS `EventSource`, plus a CDN chart library for the sparklines if wanted). **Step 4:** Run → PASS.
- [ ] **Step 5:** Open `https://<host>/dashboard`, talk near the puck, and run a call → all three panels update live. Commit `feat(dashboard): judge dashboard`.

---

### Task 19: Demo seed and dry runs

**Files:**
- Create: `scripts/seed_demo.py`, `docs/demo-runbook.md`

**Interfaces:**
- Consumes: all of the APIs above
- Produces: `seed_demo.py --patient "Mary" --relative "Sarah:daughter:sarah1.jpg,sarah2.jpg"` enrolls the patient and relative and posts sample puck segments, a café visit, and a photo. Then it triggers `/days/{today}/rebuild`.

- [ ] **Step 1:** Write the runbook, with the exact phone roles, the order of steps, and a fallback for each step:
  - The puck is offline → seeded data.
  - The group dial fails → start the call by hand.
  - Recognition is slow → the dashboard shows the scores while you narrate.
- [ ] **Step 2:** On the morning of the demo, a teammate wears the puck through a real café visit, chats, and takes a photo. Confirm the Today card shows the café event.
- [ ] **Step 3:** Run the full dry run twice on the venue network, timing each card's latency on the dashboard. Fix anything over 2.5 s or anything that shows a wrong name.
- [ ] **Step 4:** Commit `docs: demo runbook + seed script`.

---

## Appendix A: Design spec (saved to `docs/superpowers/specs/2026-11-14-calypso-inv-design.md` in Task 0)

**Name:** Calypso⁻¹. In the Odyssey, Calypso held Odysseus and made him forget home; the inverse brings people home to memory.

**Why:** People with dementia often can't recognize relatives or recall their own day, which makes family calls painful ("What did you do today, Mom?" → blank). Primary goal: win Chert's "Best Use of FaceTime" (fresh use of video ×2, wow, usefulness; live judging by Gary Gao on a real FaceTime). Also HackUTA (robustness, Odyssey theme, creativity). The Chert rep confirmed the group-call concept.

**Goals**
1. **Recognize the relative.** In a group FaceTime (patient + relative + Calypso⁻¹), the agent identifies the relative (face first, voice second). It shows an identity card on its own video: photo, name, relationship, recent memories.
2. **Cold start:**
   - Each relative does a 1-minute setup call with the agent. Relatives can also iMessage photos and facts.
   - Learn-in-call: an unknown face gets "Getting to know someone new…". The agent hears the intro, asks one confirmation question aloud, and creates a profile; otherwise it saves an unnamed visitor.
   - The puck's unnamed voice clusters are attached to a person once identified.
   - Name, face, and relationship are useful on day one.
3. **"My day" timeline.** Events with time, place, people, and a summary, built from speech cues, background sounds (YAMNet), and **phone location (iOS Visits)**. Location gives the *where*, audio gives the *what*. Places below the confidence threshold get neutral wording. In calls, "what did you do today?" → Today card.
4. **Photos placed on the timeline** by time and place, not by narration.
5. **iOS app** (SwiftUI): onboarding that adds Calypso⁻¹ as a contact and explains group FaceTime; People; Today timeline; photo and visit sync.
6. **Judge dashboard:** day timeline with evidence, live call scores and decisions, pipeline latency and health.
7. **Agent-started group call:** "call Mom with me" by iMessage. In scope; the method depends on the spike, with manual start as the fallback.

**Non-goals:** medical claims, reminders, medication; overlays inside Apple's FaceTime UI; multiple patients.

**Anti-goals:** a wrong person or an invented place; random popups; talking over family in group calls.

**Constraints**
- 4 people, about 24 hours.
- Hardware: Pi 4/5, a tensor accelerator (Coral or Hailo, undecided), Saramonic USB-C lavalier (clipped to the collar, plugged into the Pi's USB-A port via adapter), power bank, MagSafe.
- AI: Claude (reasoning), Grok/xAI (STT and TTS), self-hosted models on Vultr.
- Chert: LiveKit + `chert dev`, 5-minute call cap on the trial, one call per line, the agent can only text phones that have joined a call.
- The venue Wi-Fi isolates clients, so the public Vultr backend works around it, with Tailscale for SSH.

**Left to builders:** exact thresholds (starting values in Task 1), card visual design, prompt wording, Swift styling, event window size.
