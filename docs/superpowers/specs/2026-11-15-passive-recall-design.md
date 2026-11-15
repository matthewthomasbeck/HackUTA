# Passive puck collection → in-call recall (hand-off workflow 3)

Status: draft for approval · Owner: Eric · Branch: `feat/imessage-and-recall`
Source: `hand-off.md` §3 (full acceptance criteria are in scope). Workflow 2 (iMessage) gets its own design after this one.

## Intent

During an in-person visit, the puck that Mary wears records the conversation passively. Later on a FaceTime call, a relative asks "Mom, what did you do today?" and a card appears that is built **only** from what Mary's saved data supports. If nothing supports an answer, the card is neutral or no card appears. The card must never invent a visit, person, place or memory.

## Goals

1. **Durable capture.** Puck audio survives network loss and a device restart. Each segment keeps the same `segment_uuid` and capture timestamps across every retry.
2. **Server ingestion.**
   - Run STT on uploaded audio and write utterances.
   - Attribute a speaker only when the voice evidence clears the thresholds.
   - Skip duplicates by `segment_uuid`. This already works and must stay working.
3. **Day builder.** `POST /days/{date}/rebuild` turns the patient's local day into source-linked `day_events`. Inputs are utterances, sound tags, visits and non-sensitive photos.
4. **Grounded recall.**
   - `POST /recall` detects the intent (`today`, `person`, `memory`, `photo`, `none`) with Claude Haiku.
   - It retrieves the matching day events and memories and returns one `Card` or `null`.
5. **Fast in-call path.**
   - In group calls, the agent's utterances reach `/recall` without first going through the Sonnet controller.
   - Target: 2.5 s or less from the end of the sentence to the card on screen.
   - Responses arriving after 4 s are discarded.

## Non-goals

- Workflow 1 (Mary dialing a relative) and workflow 2 (iMessage).
- New UI in iOS or the dashboard, apart from showing the new bus stages that already fit `dashboard/`.
- Per-person diarization of mixed audio beyond what the voice prints support.

## Anti-goals (failure even if it "works")

- A Today card that names a person or place without evidence that clears `PLACE_CONF_MIN` or `VOICE_MATCH`/`VOICE_MARGIN`.
- A card triggered by an incidental mention ("the weather today is awful").
- A sensitive photo in any card or retrieval result.
- A late recall card cutting off a card still within its minimum display time.
- Saving events at upload time instead of capture time.

## Current state (verified 2026-11-15)

- **`backend/calypso/routes/puck.py`.** Idempotent on `segment_uuid` (`INSERT OR IGNORE`). Calls `jobs.process_segment`.
- **`backend/calypso/jobs.py` `process_segment`.**
  - Copies `local_text` into one utterance. There is no server STT.
  - Deletes the WAV after processing. Audio is never kept.
- **`routes/days.py`.** `rebuild` is a no-op stub. `events_for_day` reads `day_events` using `local_day_bounds(day, CALYPSO_TZ)`.
- **`routes/recall.py`.** A stub that always returns `{intent: none, card: null}`.
- **`claude_controller.py`.**
  - Every group utterance runs the Sonnet tool loop.
  - The `recall` tool posts the last 60 s of transcript to `/recall` with a 4 s timeout.
  - Returned cards go to `effects.cards`. The agent pushes them to `CardScheduler`, which already enforces the 6–10 s display window and the no-preempt rule.
- **`routes/people.py` `_memories`.** Already derives a person's memories from `day_events.people` and attributed utterances.
- **Puck (C++, `puck/src/backend_link.cpp`).**
  - Uploads fixed `SEGMENT_MS` buffers from memory.
  - On failure it puts the audio back and **generates a new uuid on the next attempt** (line ~128). This breaks dedupe.
  - The backlog is RAM-only, so it is lost on restart.
  - `local_text` is always `null`.
  - `OfflineBuffer` is the emergency offline voice-ID path, not an upload queue.
- **Models (`models.py`).** `Intent`, `RecallRequest`, `RecallResponse`, `Card(kind=today|memory|…)` and `DayEvent` already exist.

## Approaches considered

- **A. Direct recall (chosen; Eric did not object to the recommendation).**
  - In group mode, each `utterance` event first calls the backend recall service in-process: Haiku detect, then retrieve, then build a card.
  - Any card it returns is added to `effects.cards`. Sonnet is not involved in recall.
  - One model call, so it fits the 2.5 s target.
- **B. Keep Sonnet choosing the `recall` tool.** The smallest change, but the two model calls in sequence (Sonnet, then Haiku) would often exceed the 4 s limit.
- **C. Keyword prefilter before Haiku.** The fastest option, but it misses phrasings such as "how was your morning?" and adds hand-tuned rules.

## Design

### 1. Puck: durable on-disk queue (`puck/`)

- **Assign once.** A segment gets its `segment_uuid` and `ts_start`/`ts_end` when its buffer closes, never at upload time.
- **New `UploadQueue` (`puck/include/upload_queue.hpp`, `src/upload_queue.cpp`).**
  - Each closed segment is written atomically to a spool directory (`PUCK_SPOOL_DIR`, default `/var/lib/calypso-puck/spool`) as `<ts_start>_<uuid>.wav` plus `.json` (the meta). Write each file to `*.tmp`, fsync, then rename.
  - An uploader thread drains the spool oldest-first. It deletes a segment only on HTTP 2xx, which includes a `duplicate:true` ack.
  - On failure it backs off exponentially, capped at 60 s, and keeps the same files.
  - On startup it rescans the spool, so a restart resumes where it left off.
- **Size cap.** `PUCK_SPOOL_MAX_MB`, default 512, which holds about 4.5 h of continuous 3 s chunks. When the cap is hit, drop the **oldest** segments and record the count in `PuckHealth.queue_depth` and logs.
- **Segmentation.** Fixed `SEGMENT_MS=3000` chunks stay as they are (Eric's decision). Speech-based segmentation is proposed to Matt separately in `puck/docs/VAD_PROPOSAL.md` and is not part of this build.
- **Clock correctness.** *My call; Eric asked whether the kernel clock works.*
  - The Pi has no battery-backed RTC. After an offline reboot, the Linux clock restarts from `fake-hwclock`'s last saved time, so it runs behind by however long the Pi was off. It stays wrong until NTP syncs.
  - **Detect sync.** At capture, the puck checks whether the kernel clock is synced (`adjtimex` status, i.e. `STA_UNSYNC` cleared, the same signal `timedatectl` reports).
  - **Unsynced segments** go into the spool marked unsynced. They also record `boot_id` (`/proc/sys/kernel/random/boot_id`) and `CLOCK_BOOTTIME` at buffer start and end.
  - **Correct after sync.** When the clock syncs later in the same boot, the uploader rewrites each pending unsynced segment from the same boot: `ts = realtime_now − (boottime_now − boottime_capture)`. It then marks the segment synced, before upload.
  - **No correction possible.** Unsynced segments from an earlier boot are uploaded with `time_synced: false`.
  - **Puck health.** `PuckHealth.time_synced` reports the real sync state instead of the hardcoded `true`.
- **`BackendLink`** stops buffering and retrying itself. It only builds segments and enqueues them, and the uploader posts them.
- **Offline behaviour.** Capture keeps spooling while offline, and the offline voice-ID path keeps running unchanged.
- **Tests.** C++ unit tests in `puck/tests/`:
  - the uuid is stable across retries;
  - a rescan after a simulated restart finds pending items;
  - items are drained in order;
  - the cap evicts the oldest;
  - a torn `.tmp` file is ignored.
- **Hardware test.** The restart proof on the Pi is a live acceptance step for Matt and Eric together.

### 2. Backend: STT and attribution (`process_segment`)

- **STT adapter.** `backend/calypso/stt.py` defines `SpeechToText.transcribe(wav: bytes) -> list[Segment(text, t0, t1)]`.
  - Implementations: `FakeSTT`, which replays text from a fixture or uses `local_text`, and `GrokSTT`, which calls xAI batch STT the same way `agent/calypso_agent/grok.py` does.
  - Selected by `CALYPSO_STT=fake|grok`, defaulting to `grok` when `XAI_API_KEY` is set, otherwise `fake`.
  - A `local_text` from the puck still wins if one is present.
- **Utterances.** `ts_start`/`ts_end` come from the segment's capture time plus each piece's offset. They never use upload time.
- **Attribution.**
  - Embed the voice with the existing `identity/voice.py` (`embed_wav`) and score it against `voice_prints` using the same top-2 and margin logic as `identity/fuse.py`.
  - Set `utterances.person_id` only on a confident match (`VOICE_MATCH`, `VOICE_MARGIN`, `VOICE_MIN_SPEECH_S`).
  - A match to the patient sets `person_id` to the patient's id (*my call*). `_memories` is keyed per person, and the patient never gets an identity card, so this leaks nothing.
  - Uncertain matches leave `person_id` null.
  - Names are expected to be rare. Puck audio differs from the FaceTime-enrolled prints, and Eric accepted neutral cards. This work adds no calibration or puck-audio enrollment.
  - There is no attempt to split speakers within a segment. Mixed audio stays unattributed, which is the neutral outcome.
- **Failure and retry.** A failure keeps the WAV for the RQ retry, as today, and the WAV is deleted after success.
- **Rebuild trigger.** After success, mark the affected local day(s) dirty and enqueue `rebuild_day(day)`, debounced to at most one rebuild per day every 60 s, or run it inline for `InlineJobs`.

### 3. Backend: day builder (`backend/calypso/day_builder.py`)

- **`rebuild_day(conn, day, tz, summarizer)`**, called by `POST /days/{day}/rebuild` and by the job.
- **Grouping** is deterministic. A new episode starts after a gap of more than 20 minutes between utterances. iOS visits (`visits`) bound episodes when they exist.
- **Place** (Eric's decision: no sound tags yet, use iOS visits).
  - Use the overlapping iOS visit's `place_name` when it exists, with confidence 1.0.
  - Otherwise the place is `"somewhere"`, with confidence 0.
  - A visit whose `place_name` matches the configured home label (`CALYPSO_HOME_LABEL`, default `"Home"`) counts as home.
  - Sound-tag place wording sits behind a small function that returns nothing while `sound_tags` is empty, so it can light up when YAMNet lands. It is not built or tested beyond that.
- **Unsynced time.** Utterances from segments with `time_synced: false` are kept but **excluded from the day builder**, because their times can't be trusted.
- **People.** Only attributed `person_id`s, never the patient.
- **Summary.**
  - Claude Sonnet writes one short line per episode from **only** the episode's utterances, people names and place. The system prompt says: no new facts; if the content is unclear, write a neutral summary ("Talked with someone").
  - `Summarizer` sits behind an interface with a `FakeSummarizer` for tests.
- **Evidence and photos.** `evidence` holds the utterance ids. `photo_ids` holds non-sensitive photos taken within the episode.
- **Idempotency.** A rebuild replaces that day's `day_events` in a single transaction, so re-running it or re-uploading creates no duplicates.
- **Bus.** Emits `day.built` with the count and without `stub`.

### 4. Backend: recall service (`backend/calypso/recall.py` + `routes/recall.py`)

- **`recall(lines, conn, settings, detector) -> RecallResponse`.**
- **Detect.** Haiku (`claude-haiku-4-5`, env `CALYPSO_DETECT_MODEL`) looks at the last 6 lines and returns an `Intent`.
  - The prompt has positive and negative examples, including "what did you do today?" against "the weather today is awful".
  - Below `RECALL_MIN` confidence the intent is `none`.
  - Detection has a 2.5 s timeout. A timeout counts as `none`.
  - `FakeDetector` is used for tests.
- **Retrieve.**
  - `today` → `events_for_day(today or date_hint)` builds `Card(kind="today", title="Today", lines=[up to 3 "10:30 · Blue Bean Café · Coffee with Sarah"])`. With no events, the card reads `"A quiet day at home"` only when an iOS home visit covers part of that day; otherwise `"Nothing saved yet today"`.
  - `person` / `memory` → find the named person (name or relationship match among non-patient people, excluding uncertain ones) and use `_memories`. The result is `Card(kind="memory")`, with no card if nothing matches.
  - `photo` → only non-sensitive photos linked to matched events. `image_urls` are built through the existing media URL helper.
- **Bus.** Emits `recall.detect` and `recall.search`.
- **Contract.** The `RecallRequest`/`RecallResponse` HTTP contract does not change.
- **The only shared-model change** is in `SegmentMeta`: an optional `time_synced: bool = True`. Old pucks stay compatible. It is stored on `segments` as a new column with default 1. Announce it to the team before merging.

### 5. Controller / agent: direct recall path

- In `ClaudeController.respond`, for `mode == "group"` and `event.kind == "utterance"`:
  - Call `/recall` (via `api`, timeout 4 s) with the session's last 60 s of transcript, and add any card to `effects.cards`.
  - **Skip the Sonnet loop for every group utterance** (*my call*). In group mode Sonnet only drives `show_identity` and `show_learning`, which come from `frame` events, plus the one newcomer confirmation question.
  - **Exception:** an utterance that arrives while that newcomer question is pending still goes to Sonnet, so the answer can be handled.
  - This keeps `session.lock` from holding a recall behind a 12 s Sonnet call.
- **Debounce.** At most one recall card per 10 s per session. A recall card with the same title and lines is not repeated within 60 s; `CardScheduler` already dedupes that.
- **Stale responses.** The agent records `t_sentence_end` with each utterance event and drops cards from effects that arrive more than 4 s after it. Latency is logged on `card.queued` and `card.shown` for the live measurement.
- The Sonnet `recall` tool stays for setup mode, but the system prompt no longer offers it in group mode.

## Constraints

- One-card / 6–10 s / no-preempt rules come from `CardScheduler` and are unchanged.
- Secrets come only from the environment. Every new call uses the bearer token.
- Tests use the fakes. Real xAI and Anthropic tests are marked `@pytest.mark.live`.
- Days are the patient's local day (`CALYPSO_TZ`, default America/Chicago), and capture time always beats upload time.

## Acceptance (from the hand-off) and how each is proven

| Criterion | Proof |
|---|---|
| Captured segment → event → later recall card | Backend integration test (FakeSTT → rebuild → `/recall`), plus a live run on the Pi and a FaceTime call |
| Re-upload creates no duplicate | Test: post the same uuid twice and rebuild twice, giving the same event count; puck test for the stable uuid |
| Offline then reconnect keeps data and timestamps; restart proof | C++ spool tests, plus a live Pi test: unplug network, record, reboot, reconnect, check timestamps |
| "What did you do today?" → grounded card; "weather today is awful" → none | Detector fixture tests, plus a `@live` Haiku test |
| Empty-day and uncertain identity → neutral | Tests |
| Response after 4 s discarded; live latency measured | Agent unit test with a fake clock; live call log |

## Left to the builder

- Exact Haiku prompt wording, episode gap tuning and the card line format, within the rules above.
- How the debounced rebuild is scheduled (RQ delayed job against a simple "dirty days" table).
- C++ structure inside `UploadQueue`.

## Needs other people

- **Matt (puck).** Review the `BackendLink`/`UploadQueue` change and run the restart test on the Pi.
- **Team.** No shared-model change is planned. If one turns out to be necessary, announce it before merging.
- **Live tests.** Need `XAI_API_KEY`, `ANTHROPIC_API_KEY`, the deployed Vultr backend and a Chert line slot.
