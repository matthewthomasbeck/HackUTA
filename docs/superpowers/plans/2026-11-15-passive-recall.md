# Passive Puck Collection → In-Call Recall Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Puck audio captured during an in-person visit becomes grounded day events. A later FaceTime question like "what did you do today?" then shows a card built only from that saved data.

**Architecture:**
- **Puck.** A durable on-disk spool gives every segment a stable uuid and correct capture time.
- **Backend jobs.** STT, voice attribution and a Sonnet day builder turn segments into `day_events`.
- **Recall.** `/recall` runs a Haiku intent detector plus deterministic retrieval.
- **Calls.** In group calls the Claude controller calls recall directly on every utterance, without Sonnet. The agent drops cards that arrive more than 4 s after the sentence ended.

**Tech Stack:** C++17 + libcurl (puck), FastAPI + SQLite + pydantic v2 + anthropic SDK + httpx (backend), LiveKit Python agent.

**Spec:** `docs/superpowers/specs/2026-11-15-passive-recall-design.md` (approved). Also read `CLAUDE.md` and `hand-off.md` §3.

## Global Constraints

- Days are the patient's local calendar day, `CALYPSO_TZ` (default `America/Chicago`). Capture time always beats upload time.
- Never show the wrong person or a made-up place.
  - Below `PLACE_CONF_MIN` (0.6) the place is `"somewhere"`.
  - Speaker attribution needs `VOICE_MATCH`, `VOICE_MARGIN` and `VOICE_MIN_SPEECH_S`. Anything else stays null.
- The patient is never in `DayEvent.people` and never the subject of an identity card.
- Photos with `sensitive=1` are never returned, linked or shown.
- One card at a time, 6–10 s, no preemption. `agent/calypso_agent/scheduler.py` already enforces this; don't change it. Recall cards arriving more than 4 s after the sentence end are dropped.
- Secrets come only from env. Every non-dashboard API call carries `Authorization: Bearer $CALYPSO_API_TOKEN`.
- Swappable providers each have a `Fake*`. Tests use the fakes, and tests that hit real APIs get `@pytest.mark.live` and skip without keys.
  - Env vars: `CALYPSO_STT=grok|fake`, `CALYPSO_SUMMARIZER=claude|fake`, `CALYPSO_DETECTOR=claude|fake`.
- Models: Claude Sonnet for summaries (`CALYPSO_SUMMARY_MODEL`, default `claude-sonnet-4-6`). Claude Haiku for detection (`CALYPSO_DETECT_MODEL`, default `claude-haiku-4-5`). xAI Grok for STT.
- **The only `models.py` change** is `SegmentMeta.time_synced: bool = True`. No other shared-contract edits.
- Commit style: `feat(puck): …`, `feat(backend): …`, `feat(agent): …`, `docs: …`. End each commit message with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Commands:
  - Backend tests: `cd backend && uv run --group dev pytest -m "not live"`
  - Agent tests: `cd agent && uv run --group dev pytest -m "not live"`
  - Puck tests: `cd puck && cmake -S . -B build -DCALYPSO_BUILD_TESTS=ON && cmake --build build && ctest --test-dir build --output-on-failure`

## Review Focus

1. **Day boundary.** A segment captured at 23:58 local and uploaded at 00:03 belongs to the earlier day. Test in Task 4: `test_late_upload_files_under_capture_day`.
2. **Repeat delivery.** The puck re-sends a segment after the server committed it but before the 2xx reached the puck. The spool must delete it on the `duplicate:true` ack, and the backend must not double-count it. Tests: `test_drain_deletes_on_duplicate_ack` (Task 1) and `test_rebuild_twice_same_events` (Task 4).
3. **Spool damage.** A crash leaves `*.tmp` or a `.wav` without its `.json`. The rescan must skip it and not wedge the uploader. Test: `test_rescan_ignores_tmp_and_orphans` (Task 1).
4. **Photos.** A sensitive photo taken during an episode must not end up in `photo_ids` or `image_urls`. Tests: `test_sensitive_photo_not_linked` (Task 4) and `test_recall_photo_excludes_sensitive` (Task 5).
5. **Patient detection.** A patient-only day ("I'm going to water the plants", attributed to Mary) must not put Mary in `people`, and a "person" recall naming the patient returns no card. Tests: `test_patient_never_in_people` (Task 4) and `test_person_recall_patient_none` (Task 5).

---

### Task 1: Puck durable segment spool

**Files:**
- Create: `puck/include/segment_spool.hpp`, `puck/src/segment_spool.cpp`
- Create: `puck/tests/test_segment_spool.cpp`, `puck/tests/test_main.hpp`. Use a tiny assert-and-count harness, with no third-party framework.
- Modify: `puck/CMakeLists.txt`.
  - Add `option(CALYPSO_BUILD_TESTS OFF)`.
  - Move every `src/*.cpp` except `main.cpp` into a static library `calypso_core`, which both `calypso_puck` and the test executable link.
  - Register the test with `enable_testing()` + `add_test`.

**Interfaces:**
- Produces (namespace `calypso`):
  ```cpp
  struct SpoolItem {
    std::string uuid;
    std::string ts_start_iso, ts_end_iso;   // UTC, format_iso8601_utc
    bool time_synced = true;
    std::string boot_id;                    // only meaningful when !time_synced
    std::int64_t boot_ms_start = 0, boot_ms_end = 0;  // CLOCK_BOOTTIME ms
    std::filesystem::path wav_path, json_path;
  };
  class SegmentSpool {
   public:
    SegmentSpool(std::filesystem::path dir, std::uint64_t max_bytes);
    // Writes <ts_start_compact>_<uuid>.wav + .json atomically (tmp + fsync + rename). Evicts oldest if over max_bytes.
    SpoolItem enqueue(const std::vector<std::int16_t>& pcm, SpoolItem meta);
    std::vector<SpoolItem> pending() const;   // oldest first, by filename; skips *.tmp and wav/json orphans
    void remove(const SpoolItem& item);       // deletes both files
    void rewrite_times(const SpoolItem& item, const std::string& ts_start_iso, const std::string& ts_end_iso); // sets time_synced=true
    std::string meta_json(const SpoolItem& item) const;  // exact body for the multipart "meta" part
    std::uint64_t evicted_count() const;
    std::size_t depth() const;
  };
  ```
- `meta_json` is `{"segment_uuid","ts_start","ts_end","sound_tags":[],"local_text":null,"time_synced":<bool>}`. It never includes `boot_id` or the boot ms values; those are puck-local. Persist them in the `.json` file under a separate `"_local"` object that `meta_json` strips.
- Uses the existing `make_segment_uuid`, `format_iso8601_utc` (`util.hpp`) and `pcm16_to_wav` (`wav.hpp`).

- [ ] **Step 1: Write failing tests** in `puck/tests/test_segment_spool.cpp`. Each test uses a fresh temp dir.
  - `test_enqueue_then_pending_roundtrip`: enqueue 1 item. `pending()` returns 1 with the same uuid, ts and `time_synced`. `meta_json` contains `"segment_uuid":"<uuid>"` and `"time_synced":true`, and does not contain `boot_id`.
  - `test_uuid_stable_across_reopen`: enqueue, destroy the spool, construct a new `SegmentSpool` on the same dir. `pending()[0].uuid` equals the original uuid. This simulates a restart.
  - `test_pending_oldest_first`: enqueue items with ts 10:00:06, 10:00:00 and 10:00:03 in that order. `pending()` returns them ordered by ts.
  - `test_rescan_ignores_tmp_and_orphans`: create `x.wav.tmp`, a lone `y.wav` and a lone `z.json` in the dir. `pending()` is empty and nothing throws.
  - `test_cap_evicts_oldest`: set `max_bytes` to fit about 2 items, then enqueue 3. `pending()` holds the newest 2 and `evicted_count()==1`.
  - `test_rewrite_times_marks_synced`: enqueue with `time_synced=false`, call `rewrite_times`, reopen. The item is synced with the new ts.
  - `test_remove_deletes_both_files`.
- [ ] **Step 2: Build and run.** `ctest` reports FAIL or a compile error, because `segment_spool.hpp` is missing.
- [ ] **Step 3: Implement `SegmentSpool`.**
  - Filename stem: `YYYYMMDDTHHMMSSmmmZ_<uuid>`, so lexical order is chronological.
  - Write `.wav` first, then `.json`; each goes through `*.tmp` + `fsync` + `rename`. The `.json` is the commit marker, so a `.wav` without its `.json` is an orphan.
  - Use minimal hand-written JSON read/write for the fixed fields; there's no JSON library in the tree.
- [ ] **Step 4: Run tests.** All 7 pass.
- [ ] **Step 5: Commit:** `feat(puck): durable on-disk segment spool`.

### Task 2: Puck uploader, clock-sync correction and wiring

**Files:**
- Create: `puck/include/clock_sync.hpp`, `puck/src/clock_sync.cpp`, `puck/include/uploader.hpp`, `puck/src/uploader.cpp`
- Create: `puck/tests/test_uploader.cpp`
- Modify: `puck/include/backend_link.hpp`, `puck/src/backend_link.cpp`
  - `BackendLink` keeps only `connect()` / `GET /health`, the new `post_segment(wav_bytes, meta_json) -> int` (returns the HTTP status, or -1 on a transport error) and `post_health(...)`.
  - The in-memory retry buffer and the retry uuid (line ~128) go away.
- Create: `puck/include/segmenter.hpp`, `puck/src/segmenter.cpp`. This holds the fixed `SEGMENT_MS` buffer logic moved out of `BackendLink`.
- Modify: `puck/src/state_machine.cpp`, `puck/include/state_machine.hpp`
  - Every chunk goes to the `Segmenter` → `SegmentSpool` in **both** modes. Offline mode also still feeds `OfflineBuffer`.
  - The `Uploader` thread runs for the life of the process.
- Modify: `puck/src/config.cpp`, `puck/include/config.hpp`, `puck/config/.env.example`. Add `PUCK_SPOOL_DIR` (default `/var/lib/calypso-puck/spool`) and `PUCK_SPOOL_MAX_MB` (default `512`).
- Modify: `puck/INSTRUCTIONS.md`. Describe the spool, the uploader and clock handling in place of the "keep audio, retry" text.

**Interfaces:**
- Consumes: `SegmentSpool` (Task 1).
- Produces:
  ```cpp
  struct ClockSnapshot { bool synced; std::chrono::system_clock::time_point realtime; std::int64_t boot_ms; std::string boot_id; };
  class ClockSource { public: virtual ~ClockSource() = default; virtual ClockSnapshot now() const = 0; };
  class SystemClock : public ClockSource { /* adjtimex(): synced = !(status & STA_UNSYNC); clock_gettime(CLOCK_BOOTTIME); /proc/sys/kernel/random/boot_id; on macOS: synced=true, boot_id="darwin" */ };
  // Rewrites pending unsynced items from the current boot once synced; returns how many were corrected.
  int correct_unsynced(SegmentSpool& spool, const ClockSnapshot& now);
  class Segmenter { public: Segmenter(int segment_ms, const ClockSource& clock); std::optional<std::pair<std::vector<std::int16_t>, SpoolItem>> push(const AudioChunk& c); };
  using PostFn = std::function<int(const std::string& wav, const std::string& meta_json)>;
  class Uploader {
   public:
    Uploader(SegmentSpool& spool, PostFn post, const ClockSource& clock);
    // One pass: correct_unsynced, then post pending oldest-first; stop at first failure. Returns items removed.
    int drain_once();
    std::chrono::milliseconds next_backoff();  // 1s doubling to 60s cap; reset on success
    void run(std::atomic<bool>& stop);          // loop: drain_once, sleep backoff or 1s
  };
  ```
- Correction formula (from the spec): `ts = realtime_now − (boot_ms_now − boot_ms_capture)`. Apply it to both start and end, only when `item.boot_id == now.boot_id`.
- An item is removed on HTTP 200. Any 2xx counts, and `duplicate:true` comes back as a 200. On 4xx other than 409, log the error, move the item to `<spool>/rejected/` and keep going, so a bad item can't wedge the queue. On a 5xx or -1, stop the pass.
- `post_health` sends the real `time_synced` (from `ClockSource`) and `queue_depth = spool.depth()`.

- [ ] **Step 1: Write failing tests** in `puck/tests/test_uploader.cpp`, using a `FakeClock` and a `PostFn` lambda that records calls.
  - `test_drain_posts_oldest_first_and_removes`: 3 items, post returns 200. Calls arrive in ts order and `spool.depth()==0`.
  - `test_drain_stops_on_failure_keeps_uuid`: post returns -1 on call 2. Items 2 and 3 stay. On the next `drain_once` with post→200, the uuid posted for item 2 is the same as before.
  - `test_drain_deletes_on_duplicate_ack`: post returns 200 with a body ignored. The item is removed.
  - `test_rejected_4xx_moved_aside`: post returns 422 for item 1. It's moved to `rejected/`, item 2 still posts, and `drain_once` returns 1.
  - `test_correct_unsynced_same_boot`:
    - Capture at boot_ms 10,000 with `realtime` 2020-01-01, not synced.
    - Then clock now = synced, realtime 2026-11-15T16:00:00Z, boot_ms 70,000.
    - The corrected `ts_start` is `2026-11-15T15:59:00.000Z` and `meta_json` has `"time_synced":true`.
  - `test_unsynced_other_boot_uploaded_unsynced`: the item's boot_id differs from now's. It's posted with `"time_synced":false` and its ts unchanged.
  - `test_backoff_doubles_and_caps`: the sequence is 1,2,4,…,60,60 s, and it resets to 1 s after a success.
  - `test_segmenter_assigns_ts_at_close`: push 3×1000 ms chunks with `segment_ms=3000`. You get one item with `ts_start` equal to the first chunk's ts, `ts_end = start + 3000 ms`, and a non-empty uuid.
- [ ] **Step 2: Run.** Tests fail to compile.
- [ ] **Step 3: Implement** `clock_sync`, `segmenter` and `uploader`, then rewire `BackendLink` and `StateMachine` as the Files list describes. `main.cpp` builds the spool from config and starts the uploader thread. `SIGINT`/`SIGTERM` set `stop`, so the uploader finishes its in-flight POST and exits.
- [ ] **Step 4: Run puck tests and a smoke build.**
  - `ctest` passes.
  - `cmake --build build` builds `calypso_puck` on macOS, without ALSA.
- [ ] **Step 5: Commit:** `feat(puck): spool-backed uploader with stable uuids and clock-sync correction`.

### Task 3: Backend STT, `time_synced`, and voice attribution

**Files:**
- Modify: `backend/calypso/models.py`. Add `time_synced: bool = True` to `SegmentMeta`. **This is the one shared-model change.**
- Modify: `backend/calypso/db.py`.
  - Add `time_synced INTEGER NOT NULL DEFAULT 1` to `segments` in `SCHEMA`.
  - In `connect`, after `executescript`, add a small `_migrate(conn)` that does `ALTER TABLE segments ADD COLUMN time_synced INTEGER NOT NULL DEFAULT 1` when `PRAGMA table_info(segments)` lacks it. Deployed DBs already exist.
- Modify: `backend/calypso/routes/puck.py`. Store `m.time_synced`.
- Create: `backend/calypso/stt.py`
- Modify: `backend/calypso/jobs.py` (`process_segment`), `backend/calypso/config.py` (add `stt: str`, `xai_api_key: str`), `.env.example`
- Test: `backend/tests/test_stt_ingest.py`

**Interfaces:**
- Produces:
  ```python
  @dataclass(frozen=True)
  class SttPiece: text: str; t0: float; t1: float   # seconds from segment start
  class SpeechToText(Protocol):
      def transcribe(self, wav: bytes) -> list[SttPiece]: ...
  class FakeSTT:  # returns [SttPiece(text, 0, duration)] from a registry: FakeSTT.script[wav_sha1] = "text"; else []
      script: ClassVar[dict[str, str]]
  class GrokSTT:  # sync httpx POST https://api.x.ai/v1/stt, files={"file": ("speech.wav", wav, "audio/wav")}, data={"language":"en"}; one piece spanning the clip; timeout 15 s
      def __init__(self, key: str): ...
  def get_stt(settings: Settings) -> SpeechToText   # "grok" if settings.stt=="grok" (default when XAI_API_KEY set) else FakeSTT
  def attribute_speaker(conn, wav: bytes, settings: Settings) -> str | None  # in jobs.py
  ```
- `process_segment` rules:
  - Text: if `local_text` is non-empty, use it as one piece and skip STT. Otherwise call `get_stt(settings).transcribe(wav)`.
  - Each piece becomes one utterance, with `ts_start = seg.ts_start + t0` and `ts_end = seg.ts_start + t1`.
  - `person_id = attribute_speaker(...)` is computed once per segment and applied to all of its utterances.
- `attribute_speaker`:
  - `embed_wav(get_voice_embedder(settings), wav, settings.voice_min_speech_s)`. If that returns None, return None.
  - Compute `best_scores(conn, "voice_prints", vec, exclude_patient=False)` and take the top two.
  - Return the top id only if `top >= voice_match` and `top - second >= voice_margin`, otherwise None.
  - The patient may match; that's the spec's decision.
  - `AudioError` / `ModelUnavailable` → None, logged at warning.
- After success, call `mark_day_dirty(conn, local_date_of(seg.ts_start))` from Task 4. **Task 3 calls a no-op stub with this name in `jobs.py`. Task 4 replaces it.**

- [ ] **Step 1: Write failing tests** in `backend/tests/test_stt_ingest.py`, using `client`, `conn` and `post_segment` from conftest and `FakeSTT.script` keyed on the sha1 of `conftest.wav_bytes()`.
  - `test_stt_text_becomes_utterance_at_capture_time`: script "we had coffee at the café". Post with `ts_start` `2026-11-14T15:30:00.000Z`. There's one utterance with that text, `ts_start=="2026-11-14T15:30:00.000Z"` and `source=="puck"`.
  - `test_local_text_wins_over_stt`.
  - `test_empty_stt_no_utterance_segment_done`: the status is `done` and there are 0 utterances.
  - `test_time_synced_false_stored`: post with `time_synced=False`, so the `segments.time_synced` column is 0. Omitting it gives 1.
  - `test_migrate_adds_time_synced_column`: create a DB with the old `segments` DDL, which lacks the column. Then `db.connect`, and the column exists.
  - `test_voice_attribution_confident_only`, using the `tone_wav` + fake voice embedder from conftest and two people with voice prints:
    - a clear tone match sets `person_id`;
    - two prints within the margin give None;
    - no prints gives None.
  - `test_duplicate_segment_uuid_ignored` already exists. Keep it passing.
  - `@pytest.mark.live test_grok_stt_live`: skip without `XAI_API_KEY`. Transcribe a short WAV fixture, assert the type is `list[SttPiece]`.
- [ ] **Step 2: Run.** `cd backend && uv run --group dev pytest tests/test_stt_ingest.py -m "not live"` gives FAIL with ImportError on `calypso.stt`.
- [ ] **Step 3: Implement** the Files list: `stt.py`, settings, migration, puck route, `process_segment`, and `attribute_speaker`.
- [ ] **Step 4: Run the full backend suite.** `uv run --group dev pytest -m "not live"` passes, including the existing `test_puck_ingest.py` and `test_models.py`.
- [ ] **Step 5: Commit:** `feat(backend): server STT, time_synced, and confident voice attribution for puck segments`.

### Task 4: Day builder

**Files:**
- Create: `backend/calypso/day_builder.py`, `backend/calypso/summarizer.py`
- Modify: `backend/calypso/routes/days.py`. `rebuild` calls `rebuild_day`, and the `stub` flag goes away.
- Modify: `backend/calypso/jobs.py`.
  - Replace the `mark_day_dirty` stub.
  - Add `rebuild_dirty_days()`.
- Modify: `backend/calypso/db.py`. Add `CREATE TABLE IF NOT EXISTS dirty_days (day TEXT PRIMARY KEY, marked_at TEXT NOT NULL)`.
- Modify: `backend/calypso/config.py`. Add `summarizer: str` (`CALYPSO_SUMMARIZER`, default `claude` when `ANTHROPIC_API_KEY` is set, else `fake`) and `home_label: str` (`CALYPSO_HOME_LABEL`, default `"Home"`).
- Test: `backend/tests/test_day_builder.py`

**Interfaces:**
- Consumes: utterances from Task 3, the `visits`, `photos` and `people` tables, and `events_for_day` (`routes/days.py`).
- Produces:
  ```python
  @dataclass
  class Episode: start: datetime; end: datetime; utterances: list[sqlite3.Row]; visit: sqlite3.Row | None
  class Summarizer(Protocol):
      def summarize(self, lines: list[str], people: list[str], place: str) -> str: ...
  class FakeSummarizer:   # "Talked with " + ", ".join(people) if people else "Talked with someone"; if lines and not people: first line truncated to 60 chars
  class ClaudeSummarizer: # anthropic sync client, model CALYPSO_SUMMARY_MODEL, max_tokens 60, timeout 10 s; system prompt: one line ≤ 12 words, only facts present in lines/people/place, else "Talked with someone"
  def get_summarizer(settings) -> Summarizer
  def place_from_sound_tags(conn, start, end) -> tuple[str, float] | None   # returns None while sound_tags are empty/unused (dormant per spec)
  def episodes_for_day(conn, day: date, tz: str) -> list[Episode]
  def rebuild_day(conn, day: date, settings, summarizer: Summarizer | None = None) -> list[DayEvent]
  def is_home_day(conn, day: date, settings) -> bool   # an iOS visit whose place_name equals home_label (case-insensitive) overlaps the local day
  def mark_day_dirty(conn, day: date) -> None
  def rebuild_dirty_days(settings) -> int   # rebuilds days marked ≥ 60 s ago, clears them, returns count
  ```
- `episodes_for_day` rules:
  - Input: `source='puck'` utterances whose `ts_start` falls in `local_day_bounds(day, tz)` and whose segment has `time_synced=1`, ordered by time. Call utterances are excluded.
  - A gap of more than 20 minutes starts a new episode.
  - A visit that overlaps an episode bounds it, and an episode never spans two visits.
- Per episode:
  - `place, conf = visit.place_name, 1.0` when the visit has a name. Otherwise use `place_from_sound_tags`, or failing that `("somewhere", 0.0)`.
  - If `conf < settings.place_conf_min`, set `place="somewhere"`.
  - `people` = distinct non-null `person_id`s that aren't the patient.
  - `evidence` = utterance ids. `photo_ids` = photos with `sensitive=0` and `taken_at` in `[start, end]`.
  - `summary = summarizer.summarize(texts, names, place)`.
- `rebuild_day` deletes `day_events` whose `start_ts` falls in the day bounds and inserts the new ones in one transaction. It emits `day.built` `{"day", "events"}`, without `stub`. Event ids are deterministic: `sha1(day + first evidence id)[:32]`.
- `mark_day_dirty` upserts `dirty_days`. With `InlineJobs`, `process_segment` calls `rebuild_day` directly instead. With RQ, `mark_day_dirty` enqueues `rebuild_dirty_days` via `queue.enqueue_in(timedelta(seconds=60), …)`.

- [ ] **Step 1: Write failing tests** in `backend/tests/test_day_builder.py`. Seed utterances, visits, photos and people directly through `conn`, and use `FakeSummarizer`.
  - `test_gap_splits_episodes`: utterances at 10:00, 10:05 and 10:40 local → 2 events.
  - `test_visit_names_place`: a visit "Blue Bean Café" over 10:00–11:00 gives `place=="Blue Bean Café"` and `place_confidence==1.0`.
  - `test_no_visit_place_somewhere`: gives `place=="somewhere"` and confidence `0.0`.
  - `test_patient_never_in_people`: utterances attributed to the patient and to Sarah give `people==[sarah_id]`. A patient-only episode gives `people==[]`.
  - `test_sensitive_photo_not_linked`: two photos inside the episode, one sensitive → `photo_ids==[non_sensitive_id]`.
  - `test_unsynced_segments_excluded`: utterances from a `time_synced=0` segment give no event.
  - `test_late_upload_files_under_capture_day`: a segment with `ts_start` 2026-11-14 23:58 local (`2026-11-15T05:58:00Z`) belongs to day 2026-11-14, not 11-15, whatever `received_at` says.
  - `test_rebuild_twice_same_events`: rebuild twice and the same ids and count come back.
  - `test_rebuild_route_real`: `POST /days/2026-11-14/rebuild` returns an `events` count > 0, and `GET /days/2026-11-14/events` returns them.
  - `test_is_home_day`: a visit "home" (any case) on the day → True. "Blue Bean Café" → False.
  - `test_inline_ingest_triggers_rebuild`: `post_segment` with `local_text` gives a day event from `GET /days/2026-11-14/events`.
  - `@pytest.mark.live test_claude_summarizer_live`: skip without `ANTHROPIC_API_KEY`. The summary is ≤ 12 words and doesn't contain a name absent from the inputs.
- [ ] **Step 2: Run** `uv run --group dev pytest tests/test_day_builder.py -m "not live"`. It fails with ImportError.
- [ ] **Step 3: Implement** the Files list.
- [ ] **Step 4: Run the full backend suite.** It passes.
- [ ] **Step 5: Commit:** `feat(backend): day builder with visit-grounded places and Sonnet summaries`.

### Task 5: Recall service

**Files:**
- Create: `backend/calypso/recall.py`
- Modify: `backend/calypso/routes/recall.py`. Replace the stub; the request and response models stay the same.
- Modify: `backend/calypso/config.py`. Add `detector: str` (`CALYPSO_DETECTOR`, defaulting the same way as the summarizer).
- Test: `backend/tests/test_recall.py`. Update `backend/tests/test_agent_and_app.py::test_recall_stub_shape` so it uses `FakeDetector` and asserts the real behaviour.

**Interfaces:**
- Consumes: `events_for_day` (`routes/days.py`), `_memories` (`routes/people.py`), `is_home_day` (Task 4).
- Produces:
  ```python
  @dataclass(frozen=True)
  class Detection: intent: Intent; confidence: float
  class Detector(Protocol):
      def detect(self, lines: list[CallLine]) -> Detection: ...
  class FakeDetector:   # FakeDetector.script: ClassVar[dict[str, Detection]] keyed on last line text; default Detection(Intent(intent="none"), 0.0)
  class ClaudeDetector: # Haiku, max_tokens 100, timeout 2.5 s, tool/JSON output {"intent","query","date_hint","place_hint","confidence"}; prompt holds the last 6 lines and positive/negative examples incl. "what did you do today?" vs "the weather today is awful"
  def get_detector(settings) -> Detector
  def recall(lines: list[CallLine], conn, settings, detector: Detector, *, today: date | None = None) -> RecallResponse
  ```
- `recall` rules:
  - **Detection.** Pass only the last 6 lines. A detector exception or timeout gives `none`. `confidence < settings.recall_min` gives `none`.
  - **`today`.** Use `date_hint` if it parses as an ISO date, otherwise today's local date.
    - With events: `Card(kind="today", title="Today", lines=[f"{local:%-I:%M %p} · {place} · {summary}" for up to 3 events])`.
    - With no events: `lines=["A quiet day at home"]` if `is_home_day`, else `["Nothing saved yet today"]`.
  - **`person` / `memory`.**
    - Match `query` case-insensitively against `people.name` or `relationship`, non-patient only.
    - Exactly one match gives `Card(kind="memory", title=name, lines=_memories(...)[:3])`.
    - Zero or several matches, or a match with no memories, give `card=None`.
  - **`photo`.** Take today's events' `photo_ids`, re-check `sensitive=0` in SQL, and build `image_urls = [f"{settings.public_url}/media/photos/{id}.jpg"]` (up to 3). This gives `Card(kind="memory", title="Photos from today", lines=[first event summary])`, or `None` when there are none.
- **Bus:** `recall.detect` `{"last_line", "intent", "confidence"}` and `recall.search` `{"intent", "hits"}`.
- The route reads `request.app.state` for an injectable detector (`app.state.recall_detector`, default `get_detector(settings)`), so tests can inject one.

- [ ] **Step 1: Write failing tests** in `backend/tests/test_recall.py`.
  - `test_today_with_events_card`: seed 2 day events today → `kind=="today"`, 2 lines formatted `"10:30 AM · Blue Bean Café · Coffee with Sarah"`.
  - `test_weather_today_no_card`: the detector script gives none → `intent=="none"` and `card is None`.
  - `test_low_confidence_is_none`: confidence 0.2 → none.
  - `test_empty_day_home`: a home visit and no events → `lines==["A quiet day at home"]`.
  - `test_empty_day_unknown`: no visits and no events → `["Nothing saved yet today"]`.
  - `test_person_recall_unique_match`: "what did you do with Sarah" with `query="Sarah"` → a memory card titled "Sarah".
  - `test_person_recall_ambiguous_none`: two people named Sam → `card is None`.
  - `test_person_recall_patient_none`: `query="Mary"`, where Mary is the patient → `card is None`.
  - `test_recall_photo_excludes_sensitive`: `image_urls` contains only the non-sensitive id.
  - `test_detector_exception_is_none`.
  - `test_route_uses_injected_detector`.
  - `@pytest.mark.live test_haiku_detector_live`, skipped without a key:
    - "Mom, what did you do today?" → `today`;
    - "the weather today is awful" → `none`;
    - "how was your morning?" → `today`.
- [ ] **Step 2: Run** `uv run --group dev pytest tests/test_recall.py -m "not live"`. It fails.
- [ ] **Step 3: Implement** the Files list.
- [ ] **Step 4: Run the full backend suite.** It passes.
- [ ] **Step 5: Commit:** `feat(backend): grounded recall with Haiku intent detection`.

### Task 6: Controller direct-recall path (group mode)

**Files:**
- Modify: `backend/calypso/claude_controller.py`
- Test: `backend/tests/test_claude_gateway.py`. Add tests; the existing ones must keep passing.

**Interfaces:**
- Consumes: `POST /recall` (Task 5) through the existing `api` callable.
- Produces:
  - New session fields:
    - `last_recall_card_at: float = 0.0`;
    - `awaiting_newcomer_reply: bool = False`. Set it True in `execute("speak")` when `mode == "group"`. Clear it after the next group utterance has gone through the Sonnet loop.
  - `Effects` is unchanged.
- In `respond`, for `session.config.mode == "group"` and `event.kind == "utterance"` with non-empty text, after the existing `/calls/{id}/lines` post:
  1. If `session.awaiting_newcomer_reply`, fall through to the Sonnet loop as today, then clear the flag.
  2. Otherwise send the lines from the last 60 s of `session.transcript` with `await asyncio.wait_for(api("POST", "/recall", {"lines": recent}), timeout=4)`.
     - On a card, and if `time.monotonic() - session.last_recall_card_at >= 10`, append it to `effects.cards` and set `last_recall_card_at`.
     - Return `effects` **without** calling `_loop`.
     - Timeouts and HTTP errors return the empty `effects`. They don't raise, so a recall failure can't end the call.
- `SYSTEM` prompt: replace "Use recall when the conversation actually asks for memory help…" with wording that says recall is handled automatically in group calls. Keep the `recall` tool for setup mode.

- [ ] **Step 1: Write failing tests**, using `FakeClaude`, a fake `api` that records calls, and a session in group mode.
  - `test_group_utterance_calls_recall_not_sonnet`: `FakeClaude([])` would raise if it were called. The `api` stub returns a today card, so `effects.cards` has 1 card and `model.requests == []`.
  - `test_group_recall_none_no_sonnet`: `/recall` returns `card: None` → no cards, `model.requests == []`.
  - `test_group_recall_timeout_returns_empty`: the `api` stub sleeps 5 s → effects are empty, there's no exception, and it takes ≤ 4.5 s.
  - `test_group_recall_debounced_10s`: two utterances 1 s apart, both with cards → only 1 card. Use monkeypatched `time.monotonic`.
  - `test_pending_newcomer_reply_goes_to_sonnet`: with `awaiting_newcomer_reply=True`, `FakeClaude` receives one request and the flag is cleared afterwards. The next utterance goes to `/recall` with no Sonnet request.
  - `test_setup_mode_unchanged`: the existing setup tests pass.
- [ ] **Step 2: Run** `uv run --group dev pytest tests/test_claude_gateway.py`. The new tests fail.
- [ ] **Step 3: Implement** as specified.
- [ ] **Step 4: Run the full backend suite.** It passes.
- [ ] **Step 5: Commit:** `feat(backend): direct recall for group-call utterances`.

### Task 7: Agent stale-card discard and latency logging

**Files:**
- Modify: `agent/calypso_agent/main.py` (`workflow` / `apply`)
- Create: `agent/calypso_agent/latency.py`
- Modify: `agent/calypso_agent/gateway.py`. `shown()` adds `latency_ms` to the `card.shown` payload when it's known.
- Test: `agent/tests/test_latency.py`

**Interfaces:**
- Produces:
  ```python
  RECALL_STALE_S = 4.0
  def fresh_cards(cards: list[dict], sentence_end: float, now: float, *, kinds=("today", "memory")) -> list[dict]
      # drops cards whose kind is in `kinds` when now - sentence_end > RECALL_STALE_S; other kinds pass through
  def latency_ms(sentence_end: float, now: float) -> int
  ```
- In `workflow`:
  - Record `sentence_end = time.monotonic()` right after `speech.listen()` returns text.
  - After `gateway.event(...)`, run `fresh_cards` on `effects["cards"]` before `apply`.
  - Log `recall_latency_ms` for each recall card kept or dropped.
- The latency of a shown card is carried into `gateway.shown` through a small dict keyed by the card's JSON.

- [ ] **Step 1: Write failing tests** in `agent/tests/test_latency.py`:
  - `test_fresh_card_kept` (3.9 s);
  - `test_stale_recall_card_dropped` (4.1 s);
  - `test_identity_card_never_dropped` (10 s, kind identity);
  - `test_latency_ms_rounds`.
- [ ] **Step 2: Run** `cd agent && uv run --group dev pytest tests/test_latency.py`. It fails.
- [ ] **Step 3: Implement** `latency.py` and wire it into `main.py` / `gateway.py`.
- [ ] **Step 4: Run the full agent suite.** `uv run --group dev pytest -m "not live"` passes.
- [ ] **Step 5: Commit:** `feat(agent): drop recall cards older than 4 s and log recall latency`.

### Task 8: End-to-end test, docs, and live acceptance checklist

**Files:**
- Create: `backend/tests/test_passive_recall_e2e.py`
- Modify: `docs/api.md`.
  - Document `SegmentMeta.time_synced`, the real `/days/{day}/rebuild` and the `/recall` behaviour.
  - Document the new env vars: `CALYPSO_STT`, `CALYPSO_SUMMARIZER`, `CALYPSO_DETECTOR`, `CALYPSO_SUMMARY_MODEL`, `CALYPSO_DETECT_MODEL`, `CALYPSO_HOME_LABEL`, `PUCK_SPOOL_DIR` and `PUCK_SPOOL_MAX_MB`.
- Modify: `.env.example`. Add the same env vars with their defaults.
- Create: `docs/passive-recall-acceptance.md`, a live checklist with blanks for results:
  1. A Pi capture → `puck.segment` → day event → a FaceTime "what did you do today?" card.
  2. A re-upload creates no duplicate.
  3. Unplug the network, record 2 min, reboot the Pi offline, reconnect, and check event times against a wall clock.
  4. "The weather today is awful" gives no card.
  5. Empty-day and uncertain-identity cards.
  6. Record the measured `recall_latency_ms` values from the agent log in a live call. The 4 s discard is proven by `test_stale_recall_card_dropped`; add no test-only delay flag.
  - Also note the team-facing model change (`SegmentMeta.time_synced`) at the top.

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1: Write `test_passive_recall_e2e.py`.**
  - Setup:
    - Seed a patient (Mary) and Sarah with a voice print, using the fake voice embedder.
    - Seed a "Blue Bean Café" visit 10:00–11:00 local on 2026-11-14.
    - Set `FakeSTT.script` to "Sarah and I had coffee".
    - Set `FakeDetector.script["Mom, what did you do today?"] = Detection(Intent(intent="today"), 0.9)`.
  - Action: post the segment (`tone_wav` matching Sarah) at 10:15 local, twice with the same uuid.
  - Assertions:
    - one utterance;
    - one day event with `place=="Blue Bean Café"` and `people==[sarah_id]`;
    - Calling `calypso.recall.recall(lines, conn, settings, FakeDetector(), today=date(2026, 11, 14))` directly returns a today card whose line contains "Blue Bean Café".
- [ ] **Step 2: Run** it and the full backend and agent suites. Everything passes.
- [ ] **Step 3: Write the docs.** `docs/api.md`, `.env.example` and `docs/passive-recall-acceptance.md` as listed.
- [ ] **Step 4: Commit:** `docs: passive-recall API, env, and live acceptance checklist`.
