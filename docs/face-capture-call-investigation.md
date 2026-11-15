# Setup call investigation — November 14, 2026

All times below are America/Chicago.

## Observed evidence

- The setup backend call ran from 9:57:32 PM to 9:59:24 PM. Six caller transcript
  lines reached the backend, including the final permission-to-capture response
  at 9:58:53 PM. Its Claude/event request returned HTTP 200 at 9:58:55 PM.
- No `/people/from_intro` request was logged for this call. No relative profile
  was created. Backend health and other ingestion requests continued succeeding.
- At 9:59:24 PM, the local active LiveKit room reported a connection reset;
  reconnection attempts reported DNS resolution failures. The waiting room also
  reported connectivity failures at that time.
- Chert's call record is `failed`, duration 136 seconds, with terminal detail
  `bridge_failed`. The worker reported failure/cleanup around 9:59:40 PM with
  reason `unknown` / `worker_failed`. This is not a normal completed-call record.

The logs establish a media/bridge failure. They do not establish whether the
initial fault was local networking, a LiveKit interruption, or Chert's bridge.
The original logs did not record face sample counts or tool rejection reasons,
so the precise capture blockage cannot be reconstructed from them.

## Changes made

- Show camera sample progress on the outgoing video without replacing the current
  conversational caption.
- Report subscribed media source/kind and sample-count changes locally.
- Log gateway event kinds, crop counts, tool outcomes and output counts on Vultr;
  do not log image data, API keys or conversation text in these diagnostics.
- Preserve an explicit introduction confirmation while waiting for missing camera
  samples. A subsequent `camera_ready` event can complete enrollment once three
  fresh samples are available. Camera permission alone is never confirmation of
  the introduction. Corrections invalidate the previous confirmation.
- Show a reconnect message on recoverable local errors rather than immediately
  dropping all output. A lost media path itself cannot display that message until
  connectivity returns.
- Retain temporary worker/Chert logs for the next supervised test at
  `/tmp/calypso-media-diagnostic.log` and `/tmp/calypso-chert-diagnostic.log`.

39 media tests and 63 backend tests pass. The backend change is deployed, with
rollback files under `/root/calypso-capture-backup.dgFjli`. The infrastructure
failure is not proven fixed; the next real call must verify camera progress,
successful confirmed enrollment and uninterrupted media.
