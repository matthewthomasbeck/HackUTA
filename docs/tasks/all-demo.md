# Everyone: Demo

Your tasks from the [implementation plan](../superpowers/plans/2026-11-14-calypso-inv.md). Read the [design spec](../superpowers/specs/2026-11-14-calypso-inv-design.md) first.

**Your hour-1 spike:** All spikes: Task 0. Write the results in [`docs/spikes.md`](../spikes.md).

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
