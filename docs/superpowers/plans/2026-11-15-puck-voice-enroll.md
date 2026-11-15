# Puck Mic Gain + Puck-Mic Voice Enrollment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The puck recognizes enrolled people from its own microphone, so the phone's "Talking with …" card can name them.

**Architecture:**
- **Software gain.** A `MIC_GAIN` setting amplifies captured audio in `Capture`, because the LavMicro-U is already at 100% ALSA capture and is very quiet. The gain applies everywhere downstream: uploads, offline voice ID, and the speech-RMS gate.
- **Enrollment tool.** A new C++ executable, `calypso_enroll`, records samples through the same `Capture` path and uploads each one to the existing backend endpoint `POST /people/{id}/voice`. The puck's gallery sync (`GET /puck/gallery`, the mean of each person's prints, pulled every ~2 s) then picks the new prints up with no other change.

**Tech Stack:** C++17, CMake, libcurl, ALSA (on the Pi), and the puck's own tiny test harness (`puck/tests/test_main.hpp`).

**Spec / context:**
- Live test, 2026-11-15:
  - Speech RMS was about 0.005–0.01, against a silence floor of about 0.0008.
  - Best voice-match scores were 0.12–0.37, against `VOICE_MATCH_THRESHOLD=0.45`.
  - The enrolled prints come from FaceTime call audio, which doesn't match the puck mic.
- The puck is C++ only. Don't add Python.

## Global Constraints

- C++17, no new third-party dependencies (libcurl and ALSA only, as today).
- All new `src/*.cpp` go into the `calypso_core` static library.
- New tests are executables registered with `add_test` behind `CALYPSO_BUILD_TESTS`, in the style of `puck/tests/test_segment_spool.cpp`.
- **Build and test:**
  - `cmake -S puck -B /tmp/pb -DCALYPSO_BUILD_TESTS=ON && cmake --build /tmp/pb && ctest --test-dir /tmp/pb --output-on-failure`
  - It must build on macOS without ALSA. Use `#if defined(CALYPSO_HAS_ALSA)` like `capture.cpp`.
- **Secrets:** the token comes only from `config/.env` (`API_TOKEN`) and is never printed.
- **Sample format:** 16 kHz mono PCM16. The backend rejects samples without enough speech with HTTP 422 (`VOICE_MIN_SPEECH_S`, 2 s).
- **Commit style:** `feat(puck): …`, ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Don't push.
- **Branch:** `fix/puck-who-online`.

## Review Focus

1. **Clipping:** a high gain must saturate, not wrap around. `test_gain_saturates`.
2. **Mic busy:** `calypso_enroll` run while the `calypso-puck` service holds the mic must print a clear "stop the puck service first" hint, not crash.
3. **Name lookup:** a name matching zero or several people must stop before recording. `test_find_person_none_and_ambiguous`.
4. **Quiet sample:** if the RMS (after gain) is below `MIN_SPEECH_RMS`, don't upload; say "too quiet, move the mic closer".
5. **Backend 422:** print the backend's reason and continue with the next sample.

---

### Task 1: `MIC_GAIN` software gain

**Files:**
- Create: `puck/include/audio_gain.hpp`, `puck/src/audio_gain.cpp`, `puck/tests/test_audio_gain.cpp`
- Modify:
  - `puck/include/capture.hpp`, `puck/src/capture.cpp`: add `void set_gain(float gain)` and apply it in `read_chunk`.
  - `puck/include/config.hpp`, `puck/src/config.cpp`: add `float mic_gain = 1.0f;` from `MIC_GAIN`, clamped to [1, 32].
  - `puck/main.cpp`: call `capture.set_gain(cfg.mic_gain)` and log the value.
  - `puck/src/state_machine.cpp`: replace its local RMS helper with `pcm_rms` if one exists.
  - `puck/config/.env.example`: `MIC_GAIN=1.0`, with a comment.
  - `puck/INSTRUCTIONS.md`: one line on `MIC_GAIN`.
  - `puck/CMakeLists.txt`

**Interfaces (Produces):**
```cpp
namespace calypso {
// Multiplies samples by gain with saturation to [-32768, 32767]. gain <= 1 leaves pcm unchanged.
void apply_gain(std::vector<std::int16_t>& pcm, float gain);
// Root-mean-square of pcm, normalized to 0..1 (sample / 32768). Empty → 0.
float pcm_rms(const std::vector<std::int16_t>& pcm);
}
```

- [ ] **Step 1: Write the failing tests** in `test_audio_gain.cpp`:
  - `test_gain_one_is_identity`;
  - `test_gain_scales`: gain 4 turns `{100, -100}` into `{400, -400}`;
  - `test_gain_saturates`: gain 32 turns `{2000, -2000}` into `{32767, -32768}`;
  - `test_rms_known_signal`: `{16384, -16384}` gives 0.5, within 1e-4;
  - `test_rms_empty_is_zero`.
- [ ] **Step 2:** build. It fails because `audio_gain.hpp` doesn't exist.
- [ ] **Step 3:** implement, wire into `Capture`/config/main, and register the test.
- [ ] **Step 4:** run ctest. All pass, and `calypso_puck` builds.
- [ ] **Step 5:** commit `feat(puck): MIC_GAIN software gain for quiet lav mics`.

### Task 2: `calypso_enroll` puck-mic voice enrollment tool

**Files:**
- Create:
  - `puck/include/people_json.hpp`, `puck/src/people_json.cpp`, `puck/tests/test_people_json.cpp`
  - `puck/enroll_main.cpp`, which becomes executable `calypso_enroll` (links `calypso_core`, like `calypso_puck`)
- Modify:
  - `puck/CMakeLists.txt`
  - `puck/INSTRUCTIONS.md`: a section "Enroll a voice from the puck mic", with the exact commands below.

**Interfaces:**
- Consumes: `load_config`, `Capture` (with `set_gain`, Task 1), `pcm_rms`, `pcm16_to_wav`.
- Produces:
```cpp
namespace calypso {
struct PersonRef { std::string id; std::string name; bool is_patient = false; };
// Parses GET /people (a JSON array of objects; ignore other fields, incl. nested arrays and escaped strings).
bool parse_people(const std::string& json, std::vector<PersonRef>& out);
// Case-insensitive exact name match. Returns the id, or sets error to
// "no person named X" / "more than one person named X".
std::optional<std::string> find_person_id(const std::vector<PersonRef>& people,
                                          const std::string& name, std::string& error);
}
```
  Look at `src/gallery_json.cpp` for the existing hand-parser style. Reuse its helpers if they fit.

**CLI behavior:**
- Usage: `calypso_enroll --name <Name> [--samples 3] [--seconds 8] [--config config/.env]`.
- Steps:
  1. `load_config`, then `GET http://BACKEND_IP:BACKEND_PORT/people` with the Bearer token, then `find_person_id`. On error, print it and exit 2 before touching the mic.
  2. Open `Capture(cfg.mic_device, cfg.chunk_ms)` with `set_gain(cfg.mic_gain)`. On failure, print `could not open mic <device> — stop the puck first: sudo systemctl stop calypso-puck` and exit 3.
  3. For each sample:
     - print `Sample i/N: read aloud for S seconds… 3 2 1 go`;
     - record S seconds and print `rms=…`;
     - if `rms < cfg.min_speech_rms`, print `too quiet (rms=X < MIN_SPEECH_RMS=Y): clip the mic closer or raise MIC_GAIN` and don't upload;
     - otherwise POST multipart field `audio` (`sample.wav`, `audio/wav`) to `/people/{id}/voice`, then print the HTTP status plus the response body (`voice_prints`, `speech_s`) or the 422 reason.
  4. Print a summary, `uploaded K/N samples for <Name>`, and remind the user to restart the puck: `sudo systemctl start calypso-puck`.
- Exit 0 if K ≥ 1, else 1.
- Never print the token.

- [ ] **Step 1: Write the failing tests** in `test_people_json.cpp`:
  - `test_parse_people_basic`: two people with nested `facts` arrays and an escaped quote in a name; ids, names and `is_patient` come back right;
  - `test_find_person_case_insensitive`: "eric" finds "Eric";
  - `test_find_person_none_and_ambiguous`: both give nullopt plus the exact error text above;
  - `test_parse_people_invalid_json_false`.
- [ ] **Step 2:** build. It fails.
- [ ] **Step 3:** implement `people_json`, `enroll_main.cpp` (curl helpers local to that file, following `backend_link.cpp`'s curl usage), and the CMake target. Add the INSTRUCTIONS section.
- [ ] **Step 4:** run ctest. All pass, and both `calypso_puck` and `calypso_enroll` build on macOS. Smoke check: `calypso_enroll --name X --config /nonexistent` exits non-zero with a clear message.
- [ ] **Step 5:** commit `feat(puck): calypso_enroll records voice prints through the puck mic`.
