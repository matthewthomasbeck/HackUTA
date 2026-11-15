# Vultr identity integration review

Reviewed deployed commit `9cff9c5` (PR #12, face/voice prints) on November 14, 2026.
The server working tree was clean. No server source was changed during this review.

1. **P1 — Group calls still override genuine recognition with controlled results.**
   `agent/calypso_agent/gateway.py:23` sends `controlled: true` for every session.
   `backend/calypso/claude_controller.py:192` then replaces `/recognize` results with
   the configured outcome/person. Consequently a correct match from the real
   model can be ignored, or an operator-selected test profile can be displayed.
   Make controlled mode explicit/configurable and disable it for real recognition
   acceptance. Keep test labels when controlled mode is enabled.

2. **P1 — Shared-phone enrollment can attach one person's prints to another.**
   `backend/calypso/identity/enroll.py:67` returns the first person with the supplied
   phone before evaluating face or voice evidence. `routes/people.py:132` stores
   the new caller's prints under that returned person. Reproduced with a synthetic
   in-memory database: a phone belonging to A overrode an exact face match to B.
   When phones are shared, this can cause subsequent recognition to identify B
   as A. Conflicting biometric evidence should prevent automatic phone-based
   merging; do not silently choose the earliest profile.

3. **P2 — Voice matching is not wired into group-call recognition.**
   `backend/calypso/claude_controller.py:184` sends only a face JPEG to `/recognize`.
   `keep_voice` at line 255 ignores group-mode audio, and the frame handler ignores
   `voice_only` results. The new endpoint supports face/voice fusion, but the call
   controller cannot use it yet. Add a bounded participant-attributed voice window,
   forward it, and handle voice-only results without assigning mixed group audio
   to a guessed person.

The source references above refer to the deployed commit, not the older local
branch. A credential-free source snapshot was retained at
`/tmp/calypso-vultr-review` for inspection.

Operational findings and actions:

- Vultr backend is active and `/health` succeeds. All three model files have valid
  pinned SHA-256 hashes. OpenCV face models and the Sherpa voice extractor loaded
  successfully (192-dimensional voice embeddings).
- Backend non-live suite: **91 passed, 2 live tests deselected**. This is not a
  measurement of real-person biometric accuracy.
- The active database contained **1 patient, 0 relatives, 0 face embeddings and
  0 voiceprints**. Fresh enrollment is required; pulling code does not generate
  prints from the earlier setup calls automatically.
- Chert's earlier connector exited while its line was offline. At review time the
  line and Mac worker were available, but no connector session held the line.
  The server's model update was not the reason a call could not reach the agent.
- The laptop was still running the older media code without caller WAV forwarding.
  Its two media files were updated to the reviewed upstream voice-capture behavior;
  regression checks passed (**43 media tests**). The media worker was restarted.
- Chert was reconnected and confirmed an agent waiting room. This session has no
  20-minute automatic cutoff. The laptop and connector must remain running and
  connected. No outgoing phone call was placed during the review.

Next live check: repeat setup with several seconds of natural speech and a clear
camera, then verify `face_prints_added`, `voice_prints_added`, and enrollment notes.
Resolve findings 1 and 3 before calling a group test real face-and-voice recognition.
