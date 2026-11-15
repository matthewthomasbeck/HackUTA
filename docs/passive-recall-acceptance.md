# Passive recall: live acceptance checklist

> **Team heads-up:** `SegmentMeta` in `backend/calypso/models.py` (the shared contract) gained
> `time_synced: bool = True`. The agent's shared copy is already synced, and the puck sends it.
> The iOS app and dashboard don't use `SegmentMeta`, but check any fixtures that mirror it.

Run these on real hardware with real keys (`CALYPSO_STT=grok`, `CALYPSO_SUMMARIZER=claude`, `CALYPSO_DETECTOR=claude`). Fill in the blanks.

Tester: ______  Date: ______  Backend commit: ______  Puck commit: ______

## 1. Capture to FaceTime card
Wear the puck, say "Sarah and I are having coffee" near the patient, then in a FaceTime call ask "Mom, what did you do today?"
- [ ] `puck.segment` appeared on the dashboard. Time seen: ______
- [ ] A day event exists for today (`GET /days/{today}/events`) with the right place and people, within about 60 s of the first speech (`CALYPSO_REBUILD_DELAY_S`; under `CALYPSO_JOBS=rq` the worker must run with `--with-scheduler`). Result: ______
- [ ] The agent showed a "today" card listing it. Result: ______

## 2. Re-upload creates no duplicate
Re-send the same `segment_uuid` (kill the puck's uploader after the POST but before the ack, or replay with curl).
- [ ] One utterance row, one day event, response `duplicate: true`. Result: ______

## 3. Offline spool and reboot
Unplug the network, record 2 minutes of speech, reboot the Pi while still offline, reconnect.
- [ ] Spooled segments survived the reboot (spool file count before/after: ______ / ______).
- [ ] All uploaded oldest-first after reconnect. Result: ______
- [ ] Event times match the wall clock when spoken (max drift: ______ s). `time_synced` value sent after reboot: ______

## 4. Negative utterance
Say "The weather today is awful" in the call.
- [ ] No card shown. Result: ______

## 5. Empty-day and uncertain-identity cards
- [ ] On a day with no events, ask "what did you do today?": neutral card ("A quiet day at home" on a home day, otherwise "Nothing saved yet today"). Result: ______
- [ ] With an unclear speaker/face, no person is named; neutral wording only. Result: ______

## 6. Recall latency
Ask five recall questions in a live call. Copy `recall_latency_ms=` from the agent log.
| # | Question | recall_latency_ms | Card shown / dropped |
|---|---|---|---|
| 1 | | | |
| 2 | | | |
| 3 | | | |
| 4 | | | |
| 5 | | | |

Note: the latency clock (`sentence_end`) starts when the agent's STT returns the sentence, so `recall_latency_ms` and the 4 s staleness check exclude STT time. Add the STT time when comparing against the 2.5 s end-to-end target. Cards older than 4 s are discarded; that is proven by `test_stale_recall_card_dropped`, not by this checklist. Target: end of sentence to card on screen of 2.5 s or less. Median: ______ ms.
