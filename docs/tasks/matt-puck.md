# Matt: Puck (Raspberry Pi)

Your tasks from the [implementation plan](../superpowers/plans/2026-11-14-calypso-inv.md). Read the [design spec](../superpowers/specs/2026-11-14-calypso-inv-design.md) first.

**Your hour-1 spike:** Spike D (mic + accelerator): Task 0, Step 5. Write the results in [`docs/spikes.md`](../spikes.md).

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
