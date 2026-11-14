# Keanu: Chert FaceTime agent

Your tasks from the [implementation plan](../superpowers/plans/2026-11-14-calypso-inv.md). Read the [design spec](../superpowers/specs/2026-11-14-calypso-inv-design.md) first.

**Your hour-1 spike:** Spike A (group tracks) and Spike B (group dial): Task 0, Steps 2–3. Write the results in [`docs/spikes.md`](../spikes.md).

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
