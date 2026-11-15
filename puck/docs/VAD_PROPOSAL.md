# Proposal: speech-based segments for the puck

For: Matt (puck owner) · From: Eric · Status: proposal only, not being built in `feat/imessage-and-recall`

## Why

The puck currently cuts the mic stream into fixed `SEGMENT_MS=3000` chunks, silence included, and uploads every one. Everything downstream pays for that:

- **STT quality.** Words and sentences get cut at chunk edges. Grok transcribes fragments like "…went to the caf" and "é with Sarah this…", and the day builder has to summarize from them.
- **Cost and rate limits.** About 1,200 uploads and STT calls per hour, even in a silent room.
- **Voice ID.** The backend needs at least 2 s of speech (`VOICE_MIN_SPEECH_S`) to embed a voice. A 3 s chunk that is partly silence rarely qualifies, so almost nothing is attributed to a person.
- **Offline spool.** The new durable spool holds about 4.5 h of continuous audio in 512 MB. Dropping silence would stretch that a lot.

## Proposal

Segment on speech instead of on time:

1. Add a voice activity detector to the capture path, before the upload spool.
   - Start with an energy (RMS) gate with hangover, which is cheap and has no dependencies.
   - webrtcvad (C library) is an easy step up if the energy gate proves too noisy.
2. Open a segment when speech starts. Close it after about 700 ms of silence, or at 15 s at the latest.
   - Drop segments shorter than 1 s.
   - Keep about 300 ms of pre-roll so first syllables aren't clipped.
3. Each closed segment gets its `segment_uuid` and `ts_start`/`ts_end` when it closes, exactly as the new `UploadQueue` expects. Nothing changes server-side: `POST /puck/segments` already accepts any length up to `CALYPSO_MAX_AUDIO_BYTES` (5 MB, about 2.6 min at 16 kHz mono).
4. New config, with suggested defaults: `VAD_MODE=energy|webrtc|off` (default `energy`), `VAD_SILENCE_MS=700`, `VAD_MAX_SEGMENT_MS=15000`, `VAD_MIN_SEGMENT_MS=1000`, `VAD_PREROLL_MS=300`. `VAD_MODE=off` keeps today's fixed chunks.
5. The offline voice-ID path (`OfflineBuffer`) can also take speech-only clips. That is optional.

## Interaction with the durable queue

The upload queue being added on `feat/imessage-and-recall` takes closed segments of any length (`<ts_start>_<uuid>.wav` + `.json`). VAD changes only *where segments are closed*, not how they're queued or uploaded, so the two pieces of work don't conflict.

## How to verify

- A unit test feeds synthetic speech, then silence, then speech PCM, and checks the segment count, lengths and pre-roll.
- On device: talk for 30 s, stay quiet for 60 s, talk again. Expect about 2–5 segments, not about 30.
- Watch `puck.segment` on the dashboard. Segment `seconds` should vary, and no segments should arrive during silence.
