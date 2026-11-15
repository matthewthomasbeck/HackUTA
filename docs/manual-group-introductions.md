# Manual group FaceTime introductions

## Scope

Mary is the fixed demo patient, loaded from the existing sole backend patient profile (name must be `Mary`). No patient enrollment UI or agent-initiated dialing is added. Mary's physical presence is assumed because the family manually forms the call; the agent does not claim to have verified that she is present.

`CALYPSO_CALL_MODE=group_intro` is a separate workflow from the existing `auto`, `setup`, `recognize`, and legacy `group` flows. Real recognition is required (`CALYPSO_CONTROLLED_RECOGNITION=false`). Group introduction calls use the existing `group` call-log kind.

## Behavior

- After confirmed bridge readiness, play one brief generic greeting to satisfy Chert's initial audio deadline. Then speak only to introduce recognized relatives.
- Send each available remote video track as a bounded full-frame JPEG, preserving all faces in a composite grid. Agent participants and screen sharing are excluded. The existing one-face setup cropper is bypassed.
- Match against all profiles, including Mary, so patient matches can be positively excluded. Also reject patient profiles before showing a card or speaking.
- Require the same relative to be confidently identified in two consecutive sampled frames on the same source, no more than three seconds apart. Multiple detections in one frame cannot count as multiple confirmations. Separate sources maintain separate confidence histories.
- Say “Hi Mary, you're speaking with Keanu, your brother.” Relationships and memories come only from the stored backend profile. If a relationship is absent, announce only the stored name.
- Show the identity card and saved facts. Announce each relative at most once during the call, even if they disappear and reappear or move to another track. A new backend session resets this history.
- Unknown, ambiguous, missing-face and patient-only results do not produce identity announcements. Keep the neutral idle/initial card. No newcomer interview, enrollment, voice matching, hang-up instruction, or automatic call termination is added in this milestone.
- Recall (from 5 s after the call starts; the opening is left to face recognition): the agent transcribes only the Chert bridge's single mixed audio track and sends each sentence as text to grounded `/recall` (no voice, no face crops, no silence events). A question like "what did you do today?" shows a silent Today/memory card built from saved data; recall never speaks and never identifies anyone. Introductions stay face-only.
- The session runs until the Chert bridge/call disconnects. A separate relative leaving does not end the remaining group session.

Matching histories follow backend person IDs per video source; this is not spatial face-box tracking or active-speaker attribution. We do not label a particular grid tile or infer which person spoke. Existing model thresholds/margins remain unchanged. Threshold failures can still occur; repeated evidence reduces transient errors but does not guarantee biometric accuracy.

## Manual test and topology checkpoint

Use an agreed test slot. Follow `AGENTS.md`: commit/push the reviewed code, merge/pull through Git, inspect the server working tree, configure `group_intro`, and restart affected services between calls. Do not run a second laptop connector. Switching this worker to `group_intro` makes every incoming call use group introductions until the mode is changed back to `auto`.

1. Start a group FaceTime manually with Mary, one enrolled relative and Calypso. If Add People or calling Calypso as a third participant is refused, record that provider limitation; no agent code can establish the missing call topology.
2. Verify the initial greeting is audible and the call stays connected past the Chert audio deadline.
3. Inspect `group_topology` and `video_source` server log entries. These log participant/track counts and publication dimensions, never images/audio. One bridge/video track does not alone prove a composite grid: confirm visually that both callers are represented. Chert may send only the active speaker, which cannot establish simultaneous recognition.
4. Keep Mary's face and the relative's face visible. Expect only the relative's introduction/card, once. Verify the relationship and memory are correct.
5. Introduce another enrolled relative: expect one separate introduction. Show an unknown person: expect no guessed name or enrollment question.
6. Hide/reveal a known relative or have them rejoin: no repeated introduction in the same call. A fresh call may introduce them again.
7. Test poor light/ambiguous matches, Mary alone, and no usable video. The agent must remain neutral and keep the call running.
8. End the group call and verify backend session cleanup and the next-call waiting room.

Record the actual phones, track/participant layout, visible content of a single bridge track, card/audio behavior, final Chert outcome and any unsupported step in `docs/spikes.md`. Unit tests with fake recognition results are not proof of Chert group support or real model accuracy.

## Current validation

Local tests cover composite multi-face results, patient exclusion, unknown/uncertain faces, per-source confirmation, duplicate detections, announcement deduplication across reappearance, full-frame encoding and regression suites. Live group topology and phone acceptance are pending; do not present this as a verified working three-party integration until the checkpoint above passes.
