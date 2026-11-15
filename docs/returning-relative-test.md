# Returning-relative recognition

Set `CALYPSO_CALL_MODE=recognize` for an explicitly selected, single-relative recognition call. `setup` continues to enroll callers. Automatic setup-versus-recognition routing is not implemented; switching modes applies to all calls handled by that worker.

`CALYPSO_CONTROLLED_RECOGNITION=false` is the default. The gateway no longer forces controlled results. `CALYPSO_STAGE1` does not enable fake recognition; tests that need fixtures must explicitly set `CALYPSO_CONTROLLED_RECOGNITION=true`. Only then is the saved enrollment ID read as a fixture. Card events report the actual controlled flag and fixture identity cards retain the “Test profile” label.

## Behavior

- Starts with a neutral waiting card and one brief greeting to satisfy Chert's audio timeout; it does not start an enrollment interview.
- Sends clear face crops to backend `/recognize`, excluding the patient.
- Opening recognition is face-only. Caller utterances cannot identify anyone; voice samples are not sent for matching and voice-only results are ignored. Without a usable face, keep neutral wording.
- Claude can display only the backend-identified person, with stored name, relationship to the patient, and memories/facts. Patient profiles are rejected.
- Uncertainty produces neutral wording; unknown faces debounce into the learning card. After the opening greeting, recognition mode cannot speak newcomer questions or enroll anyone.
- Caller lines go to grounded recall (`POST /recall`, text only, no voice): asking "what did you do today?" can show a Today/memory card built from saved data. Recall never identifies the caller.

This mode performs face-only identification throughout the opening-recognition workflow; it does not switch to voice after a timer. Voiceprint enrollment in setup and the general backend face/voice API remain unchanged. Do not use this mode for group calls. Multi-person tracking and group speaker attribution remain separate work. Existing model thresholds and ambiguity/conflict rules are unchanged.

Calls use the existing `group` call-log kind to preserve the shared model schema; the agent session retains `mode=recognize`.

## Live acceptance after deployment

Follow `AGENTS.md`: commit/push, explicitly pull on Vultr after checking its working tree, and restart affected services between calls. This implementation does not deploy or modify server configuration.

For a deployed test, set these in `/etc/calypso/media.env`, preserving credentials:

```dotenv
CALYPSO_CALL_MODE=recognize
CALYPSO_CONTROLLED_RECOGNITION=false
```

Use enrolled relatives with usable prints and saved facts. Check:

- Returning relative: correct name, relationship and memory; no setup interview or “Test profile” label.
- Different enrolled relative: their own profile, independent of the last enrollment fixture.
- Unknown caller: neutral wording, no invented identity or enrollment write.
- Ambiguous/conflicting evidence: neutral wording. Cover the camera and speak: voice must not identify the caller.
- Mary: no patient identity card.
- Hang up and call again: session cleanup and no identity carried between calls.

Watch `recognize`, `card.queued`, and `card.shown` events. Adapter tests do not establish real biometric accuracy; record phone results and lighting/threshold limitations. Chert must accept the call before recognition can be evaluated; prolonged “cleaning up” and missing incoming-call records are provider readiness blockers.

Chert has previously advertised a ten-second greeting requirement after bridge readiness. This mode now emits one brief greeting immediately on session start. Verify on a real call that synthesized audio arrives within the deadline. Group-call silence must be evaluated independently.

Identity cards replace displayed/pending neutral placeholders immediately. Other real cards keep their minimum reading time. Missing face crops do not generate uncertainty cards or clear the last match; actual uncertain results clear it and emit neutral wording once per uncertainty transition.

The media gate races the normal `chert_bridge_ready` room flag against authenticated polling of `GET /api/v1/calls/<call UUID>`. The UUID comes only from the selected `chert-bridge-<UUID>` participant. API readiness requires the matching call/project, `status=active`, and a `facetime_call_events` entry with `event_type=bridge_ready` and `source=worker`, matching the installed Chert connector's own checks. Video arrival alone is never readiness.

Polling starts immediately after the caller participant is known: in slow connections that participant can arrive after Chert's own 30-second polling window, so waiting another 25 seconds would miss the audio deadline. Requests have a three-second timeout and retry at one-second intervals within the media gate's overall 60-second deadline. Metadata or API confirmation starts the workflow once; the other waiter is canceled. Hangup cancels both. Terminal call status aborts the wait; API/auth failures cannot count as readiness. Logs distinguish `source=room_metadata` from `source=chert_call_api` without logging credentials or caller details.

After Git deployment, repeat the slow-connection test and confirm one gateway session, one greeting, correct identity display, and clean hangup. This fallback is locally tested, not yet accepted in a live phone call.

## Automatic recognition then enrollment

Set `CALYPSO_CALL_MODE=auto` to run the requested combined workflow. After bridge readiness, it gives the brief opening greeting and checks faces for a five-second window. A confident identified relative gets a pinned “You are <name>” card with their relationship to Mary and stored memories, followed by “Please hang up now.” The flow ends without enrollment. The call itself stays open until the caller hangs up because native hangup remains unavailable with the current CLI credentials.

If no confident match is established within five seconds, the same backend session switches to setup, asks the caller's name/relationship and shared memory, confirms the introduction, and saves using the existing enrollment workflow. Opening speech cannot identify the caller or serve as enrollment confirmation. The verified caller phone is resolved for auto calls just as for setup calls. Group mode is unaffected. The deadline counts from the backend start event after bridge readiness, not from ringing. Scheduling/network/model latency can extend when the enrollment prompt is heard.

For live acceptance, test (1) enrolled face → correct identity and hang-up instruction, (2) unknown/no face → enrollment prompt after the window, (3) uncertain face → enrollment without a guessed profile, (4) confirmation/camera capture/save after fallback, and (5) hangup during the opening window without a later prompt. Deploy/configure only through the agreed Git workflow.
