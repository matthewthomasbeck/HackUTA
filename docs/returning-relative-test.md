# Returning-relative recognition

Set `CALYPSO_CALL_MODE=recognize` for an explicitly selected, single-relative recognition call. `setup` continues to enroll callers. Automatic setup-versus-recognition routing is not implemented; switching modes applies to all calls handled by that worker.

`CALYPSO_CONTROLLED_RECOGNITION=false` is the default. The gateway no longer forces controlled results. `CALYPSO_STAGE1` does not enable fake recognition; tests that need fixtures must explicitly set `CALYPSO_CONTROLLED_RECOGNITION=true`. Only then is the saved enrollment ID read as a fixture. Card events report the actual controlled flag and fixture identity cards retain the “Test profile” label.

## Behavior

- Starts with a neutral waiting card and one brief greeting to satisfy Chert's audio timeout; it does not start an enrollment interview.
- Sends clear face crops to backend `/recognize`, excluding the patient.
- On caller utterances, sends the WAV and, when available, a recent face crop for existing face/voice fusion. Without a face, voice-only results can be used.
- Claude can display only the backend-identified person, with stored name, relationship to the patient, and memories/facts. Patient profiles are rejected.
- Uncertainty produces neutral wording; unknown faces debounce into the learning card. After the opening greeting, recognition mode cannot speak newcomer questions or enroll anyone.

Voice attribution is valid only under the explicit single-relative assumption. Do not use this mode for group calls. Multi-person tracking and group speaker attribution remain separate work. Existing model thresholds and ambiguity/conflict rules are unchanged.

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
- Ambiguous/conflicting evidence: neutral wording. Cover the camera and provide sufficient speech to test voice-only matching.
- Mary: no patient identity card.
- Hang up and call again: session cleanup and no identity carried between calls.

Watch `recognize`, `card.queued`, and `card.shown` events. Adapter tests do not establish real biometric accuracy; record phone results and lighting/threshold limitations. Chert must accept the call before recognition can be evaluated; prolonged “cleaning up” and missing incoming-call records are provider readiness blockers.

Chert has previously advertised a ten-second greeting requirement after bridge readiness. This mode now emits one brief greeting immediately on session start. Verify on a real call that synthesized audio arrives within the deadline. Group-call silence must be evaluated independently.

Identity cards replace displayed/pending neutral placeholders immediately. Other real cards keep their minimum reading time. Missing face crops do not generate uncertainty cards or clear the last match; actual uncertain results clear it and emit neutral wording once per uncertainty transition.
