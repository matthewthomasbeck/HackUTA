# Calypso⁻¹: Claude controller and media transport

The active agent is Claude on the Vultr backend. Python on the laptop is the
Chert/LiveKit media transport: it captures camera/audio, transcribes speech with
xAI, forwards events, plays speech effects, and renders returned cards. It does
not choose prompts, enroll people, select identities, or decide recall actions.

See [the real-call guide](../docs/stage1-test.md) for credentials and acceptance.

## Active components

- `main.py`: explicit setup/group routing and media lifecycle.
- `gateway.py`: authenticated events/effects interface to the backend.
- `live_media.py`, `face_crop.py`: media capture, single-face crops, speech
  segmentation/playout and outgoing video. Face detection is isolated from
  LiveKit's native libraries. It is preprocessing, not identity matching.
- `grok.py`: xAI speech adapter; requires local `XAI_API_KEY`.
- `cards.py`, `scheduler.py`: rendering and reliable 6–10 second display timing.
- `backend/calypso/claude_controller.py`: Claude conversation/tool loop,
  confirmation and identity guards, recall, and backend writes.
- `backend/calypso/routes/agent_sessions.py`: authenticated session gateway.

Only the backend needs `ANTHROPIC_API_KEY`. `CALYPSO_AGENT_MODEL` selects the
Claude model (default `claude-sonnet-4-6`, verified with the server account).

The older `conversation.py`, `core.py`, `state.py`, `stage1_backend.py` and
`demo.py` are offline regression fixtures from the first prototype. They are
not imported by the live media entrypoint. Running the old demo does not test
Claude. Shared-model drift is checked against `contract.py`.

## Agreed scope

In-person puck collection stays passive. Direct relative setup and a separate
recognition call are the first milestone. Patient-requested relative calling
remains a separate workflow; on connection failure it should offer another
relative. Notification fallback and expanded missing-phone handling are deferred.
Other required flows and remaining platform constraints are in the guide's
coverage table. The current gateway does not expose a dial tool or patient mode.

## Local checks

```sh
# From agent/
uv run --group dev python -m pytest -q
# From backend/
uv run --group dev python -m pytest -q
```

The local suites use deterministic Claude tool responses. A small real Claude
setup-greeting probe was also verified on Vultr after gateway deployment; it
created no person and its backend call was ended afterward. FaceTime media and
real speech have not yet passed live acceptance.
