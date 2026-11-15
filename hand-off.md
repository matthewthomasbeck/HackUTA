# Handoff: calling, iMessage, and passive-memory recall

These three workflows are being handed off from Keanu's agent work. Owners are to be assigned by the team. This document describes the agreed behavior and the integration work; it does not claim the workflows are complete.

## Shared architecture and boundaries

- Claude on Vultr owns conversation decisions and tool selection: `backend/calypso/claude_controller.py` and `backend/calypso/routes/agent_sessions.py`.
- Python handles LiveKit audio/video transport and executes gateway responses: `agent/calypso_agent/main.py`, `live_media.py`, and `gateway.py`. Keep business decisions in the backend.
- Relative enrollment has succeeded in real FaceTime calls, including backend persistence. Preserve that workflow, the portrait cards, and verified caller-number association.
- Current call modes are explicitly `setup` and `group`; patient-requested calling needs a new supported route/mode. Do not treat every caller as Mary or infer patient identity from participant count.
- The existing gateway has no dialing tool. Backend `POST /calls` records calls; it does **not** place a FaceTime call. Provider dialing must be a separate Chert adapter.
- Read `docs/api.md`, `docs/tasks/keanu-agent.md`, `agent/README.md`, and `docs/stage1-test.md`. Some progress tables describe earlier milestones; verify the current source and deployment before relying on them.
- Use fake Chert/model/backend responses for development, then run the live acceptance scenarios below. Record what was actually tested and what remains blocked.

## 1. Mary requests a call to a relative

**Outcome:** Mary calls Calypso and says, for example, “Call my daughter Sarah.” The agent resolves the stored relative, confirms the intended person, attempts connection, and offers another relative if connection fails.

### Work to implement

- Add explicit patient-call routing and a reliable way to establish that this is the patient workflow. Keep unknown-relative enrollment separate.
- Look up relatives from the backend using their stored names, relationships, and callable phone numbers. Never invent a number or use a spoken claim as verified caller identity.
- Resolve ambiguity with a short question. Confirm the selected person before dialing; cancel without dialing if Mary declines.
- Add a Claude tool backed by a Chert calling adapter. Verify the available Chert API and credential permissions before choosing a connection strategy.
- Test whether Chert can form the required patient–relative–agent call. If only manual group formation is supported, provide truthful instructions and document that limitation rather than claiming a connection succeeded.
- Handle busy, declined, unanswered, and provider-error outcomes with bounded timeouts. Offer another stored relative; obtain confirmation before a second attempt.
- Prevent duplicate dialing on retried requests. End/cancel attempts and clean up session resources without losing saved enrollment data.
- A stored person may have no phone. For the hackathon, give a brief explanation and offer another person. A missing-number collection workflow and notification/message fallback are deferred.

### Acceptance criteria

- A unique requested relative is resolved and dialed only after confirmation.
- Ambiguous names prompt clarification; declining or canceling makes no provider call.
- Busy/unanswered/error results offer another relative without inventing success.
- A person without a number does not trigger a malformed call.
- Retrying the same action does not dial twice.
- A live test demonstrates the actual connection topology and cleanup; record any provider limitation.

**Starting points:** `backend/calypso/claude_controller.py`, `routes/agent_sessions.py`, `routes/people.py`, `routes/calls.py`, `agent/calypso_agent/gateway.py`, and the group-dial spike in `docs/spikes.md`.

## 2. iMessage intake and call requests

**Outcome:** A known relative can send a photo or memory note, or ask “call Mom with me.” The system stores the appropriate information and either starts the supported call flow or supplies manual group-call instructions.

### Work to implement

- Build a Chert messaging adapter using the currently supported API. The original plan mentions `GET/POST /shared-messages` and polling every three seconds; verify those assumptions against the account's current API before implementation.
- Associate senders with enrolled relatives using provider-verified sender information and stored phone numbers. Unknown senders must not modify another person's profile or trigger calls.
- Deduplicate incoming provider message IDs so polling/retries do not repeat writes, replies, or calls. Persist the processing cursor/state across service restarts.
- Classify requests into photo enrollment, memory note, call request, or a brief supported/help response. Claude decides intent; backend code validates and executes tools.
- Send suitable identity photos to `POST /people/{id}/faces`. Handle invalid/no-face images without reporting success. Do not assume every photo is an identity photo; clarify ambiguous intent.
- Store memory notes through a defined backend contract with the correct person association and source. Coordinate any new endpoint/model change with the backend owner.
- Reuse the calling adapter from workflow 1. For “call Mom with me,” resolve the sender and patient, then apply the verified group-call strategy.
- If automatic group dialing is unavailable, reply with clear manual FaceTime/Add People instructions. Avoid simultaneous automatic and manual attempts.
- Verify messaging eligibility and trial restrictions. The original plan assumes recipients must previously have joined a call; do not assume arbitrary outbound messaging is permitted.

### Acceptance criteria

- A known relative's valid photo adds prints to the intended person; invalid media receives an accurate response.
- A memory note is persisted and retrievable for that relative.
- Request variants such as “call Mom with me” and “can you get Grandma on FaceTime?” select the intended call action or supported fallback.
- Unknown senders cannot edit existing profiles or initiate calls.
- Repeated delivery and service restarts do not duplicate side effects.
- One live message-to-backend test and one live call-request/fallback test pass.

**Starting points:** Task 15 in `docs/tasks/keanu-agent.md`, `backend/calypso/routes/people.py`, `backend/calypso/models.py`, and the shared calling adapter. The proposed `imessage.py`/`dialer.py` names in the original plan are planned components, not proof that live implementations exist.

## 3. Passive puck collection feeds in-call recall

**Outcome:** A conversation during an in-person visit is collected passively. Later, a FaceTime question such as “What did you do today?” shows a card grounded in Mary's saved events or memories.

### Work to implement together

- **Puck owner:** capture/upload segments with stable IDs and timestamps; establish durable offline buffering, ordered retries, and recovery. Verify these properties rather than assuming the current emergency offline voice-ID path implements a durable upload queue.
- **Backend owner:** process uploaded speech/context, associate people only when evidence supports it, persist source-linked memories/events, and expose them to recall. Prevent duplicate ingestion by segment ID.
- **Backend/agent owner:** replace the current local `POST /recall` stub with grounded intent detection and retrieval. Connect the Claude gateway to the completed recall contract; preserve the card response model.
- **Agent owner:** supply a bounded conversation window and enqueue returned cards on the existing scheduler. Normal group behavior remains silent. No live Chert interaction is required during the original in-person visit.
- Use the patient's local calendar day consistently (`CALYPSO_TZ`; default Central time). Handle late uploads by capture time rather than treating them as events that happened at upload time.
- Show “A quiet day at home” or another evidence-appropriate empty state when no usable events exist; never invent visits, people, places, or memories.
- Protect sensitive photos from retrieval/display. Keep uncertain speaker attribution neutral, especially with mixed audio.
- Preserve one card at a time, normally 6–10 seconds, without preempting a readable card. Target sentence-end-to-card latency of 2.5 seconds or less; discard recall responses arriving after four seconds.

### Acceptance criteria

- A captured in-person segment becomes a backend memory/event and appears in a later relevant recall card.
- Re-uploading the same segment creates no duplicate event.
- Offline capture followed by reconnect preserves data and timestamps; prove recovery with a device restart if durable queuing is claimed.
- “What did you do today?” returns grounded day content; an unrelated phrase such as “the weather today is awful” produces no Today card.
- Empty-day and uncertain-identity cases produce neutral, accurate cards.
- A response delayed beyond four seconds is discarded, and actual recall latency is measured in a live call.

**Starting points:** `puck/INSTRUCTIONS.md`, `puck/src/backend_link.cpp`, `puck/src/offline_buffer.cpp`, `backend/calypso/routes/puck.py`, `jobs.py`, `routes/days.py`, `routes/recall.py`, `claude_controller.py`, and `agent/calypso_agent/scheduler.py`.

## Platform blockers and integration risks

- Chert has shown prolonged “cleaning up,” busy/occupied-worker states with no current call, and incoming attempts missing from call records. Resolve provider readiness before judging a failed live test as an application bug.
- Calls from additional phones have not been reliably established. Verify caller eligibility/allowlists with Chert; the exact cause is not confirmed. Do not assume LiveKit credentials filter callers by their phone number.
- Automatic native FaceTime hangup and group dialing are not established under the current CLI credentials. Verify capabilities independently; do not promise them based on local call-log endpoints.
- `docs/vultr-identity-review.md` records earlier recognition/identity risks. Check whether those findings still apply before building on phone-based identity merging or claiming real group face/voice recognition.
- Keep real enrollment acceptance separate from controlled recognition fixtures. Passing fake tests does not prove real identification or group-call behavior.

## Collaboration and deployment

- Suggested split: one owner for calling, one for iMessage, and coordinated puck/backend owners for collection-to-recall. Calling and messaging should share one provider adapter and failure model.
- Agree on request/response contracts before changing shared models. Document new settings and APIs; keep provider credentials in server configuration, never in this file or Git.
- Work locally. Follow `AGENTS.md`: commit and push a branch, then explicitly pull it on Vultr after inspecting server changes. No direct source uploads, remote source edits, or automatic synchronization.
- Vultr checkout: `/root/HackUTA`. Services: `calypso-backend`, `calypso-media`, and `calypso-chert`. See `docs/vultr-call-services.md`. Restart affected services only as part of an authorized deployment, between calls.
- Return a short completion note for each workflow: changed files/contracts, tests run, live results, remaining limitations, and the commit/branch to integrate.

## Getting this handoff

After Keanu commits and pushes this file to `keanu-branch`, teammates can fetch it without switching their working branch:

```sh
git fetch origin
git show origin/keanu-branch:hand-off.md
```

To bring only this document into a teammate's working branch, first ensure there is no local `hand-off.md` work to overwrite, then run:

```sh
git restore --source=origin/keanu-branch -- hand-off.md
```

Pulling/merging the whole branch is also possible, but includes its other changes; coordinate that separately.
