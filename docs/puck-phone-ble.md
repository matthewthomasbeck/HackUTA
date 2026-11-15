# Puck ↔ phone BLE contract

The puck is the **peripheral**. It advertises service `C41A0001-5E7A-4C1B-9A3D-CA1F5050C0DE` with a local name
starting with `Calypso`. Every payload is one UTF-8 JSON object per write or notify.

| Name | UUID | Props | Payload |
|---|---|---|---|
| `who` | `C41A0002-5E7A-4C1B-9A3D-CA1F5050C0DE` | notify | `{"status":"identified"\|"uncertain"\|"unknown","person_id":"p_sarah","display_name":"Sarah","relationship":"daughter","score":0.72}` (mirrors puck `WhoIsTalking`; empty strings allowed) |
| `control` | `C41A0003-5E7A-4C1B-9A3D-CA1F5050C0DE` | write | `{"cmd":"enroll_start","speaker":"patient","index":0,"text":"…"}`, `{"cmd":"enroll_finish","speaker":"patient","count":5}`, `{"cmd":"enroll_cancel","speaker":"patient"}` |
| `events` | `C41A0004-5E7A-4C1B-9A3D-CA1F5050C0DE` | notify | `{"event":"enroll_recording","index":0}`, `{"event":"enroll_saved","index":0}`, `{"event":"enroll_failed","index":0,"reason":"too_quiet"}`, `{"event":"enroll_done","speaker":"patient"}` |

The puck sends `who` only when someone is speaking (roughly every `OFFLINE_SEGMENT_MS`). The phone treats the
speaker as gone after **20 s** with no `who` message. On `enroll_start` the puck records one clip, ending on silence
or after a cap, and saves it under `gallery/patient/`. The phone gives up on a clip after **15 s** without
`enroll_saved` or `enroll_failed`.

## What the phone does

The iOS app scans for the service, connects, and subscribes to `who` and `events`. It shows a "Talking with" card on
Today: a name only when `status` is `identified` with a non-empty `display_name`; `uncertain` and `unknown` both
show neutral "Getting to know someone new…" wording, even if a candidate name is present. Messages whose
`person_id` is `"patient"` (or a known patient) are dropped, since the patient is never the subject of a card.
During onboarding ("Teach your voice") it writes `enroll_start` for each of five sentences, waits for
`enroll_saved`, and sends `enroll_finish` after the last one without waiting for `enroll_done`. Unknown JSON
fields are ignored and an unrecognised `status` is treated as `unknown`; an unrecognised `event` is discarded.
