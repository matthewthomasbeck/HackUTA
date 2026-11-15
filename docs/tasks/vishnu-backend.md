# Vishnu: Backend + judge dashboard

Your tasks from the [implementation plan](../superpowers/plans/2026-11-14-calypso-inv.md). Read the [design spec](../superpowers/specs/2026-11-14-calypso-inv-design.md) first.

**Your hour-1 spike:** Spike C (Grok speech): Task 0, Step 4. Write the results in [`docs/spikes.md`](../spikes.md).

Check off steps here as you go (`- [x]`). Shared data shapes live in `backend/calypso/models.py`, so don't change them without telling the team.

## Global constraints (apply to every task)

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

## Hour-1 spikes (Task 0)

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

## Status and notes

- **M1 done (branch `feat/backend-skeleton`):** the full API surface with its final shapes. The contract is in [`docs/api.md`](../api.md), and 57 tests pass.
  - Real now: health, the SSE stream, people CRUD and memories, media, puck intake (dedupe, sound tags, inline/RQ job, temp audio deleted), puck health, calls, days by local day, iOS visits and photos.
  - Stubs with their final shape: `/recognize` (always `learning`), `/recall` (always `none`), `/people/from_intro` (unnamed person and photo), `/days/{date}/rebuild`.
- **Team decisions** (since the plan was written):
  - Calls are face first, voice second (unchanged).
  - Voice also links puck conversations to people: the puck has no camera.
  - Audio is never stored. It's processed, then deleted. S3 is only for face crops and photos.
  - Slow processing runs on Keanu's RQ worker (`CALYPSO_JOBS=rq`), using the same SQLite file in WAL mode.
  - Grok does STT and diarization only. Voiceprints come from SpeechBrain ECAPA, and face prints from insightface.
- **iOS contract** (agreed with Eric):
  - `GET /people/{id}` is a flat Person plus `memories: [str]`.
  - `DayEvent.people` holds ids.
  - Images are public at `/media/...` with absolute https URLs.
  - Days are the patient's local day (`CALYPSO_TZ`).
  - The app's `API_BASE_URL` = `CALYPSO_PUBLIC_URL`, and `API_TOKEN` = `CALYPSO_API_TOKEN`.
- **Times:** stored as fixed-width UTC (`2026-11-14T15:30:00.123Z`). A time with no zone is treated as UTC, never rejected, so the puck queue can't stall.
- **Next:** M2 enrollment and fusion (Tasks 4–5 with fake embedders), M3 real models, M4 puck pipeline (Grok and ECAPA on the worker), M5 linking and memories, M6 day builder, recall, dashboard and deploy.
