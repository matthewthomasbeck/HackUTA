# Hour-1 spike results

Fill these in during Task 0. Later tasks read these values. Copy the env ones into `.env`.

| Key | Owner | Value | Notes |
|---|---|---|---|
| `AGENT_TRACK_MODE` (`per_participant` \| `composite`) | Keanu | | participants/tracks seen in a group call |
| `GROUP_CALL_START` (`agent_dials_both` \| `agent_dials_relative_then_add` \| `manual_only`) | Keanu | | |
| 5-minute call cap hit? | Keanu | | |
| Grok STT mode (`streaming` \| `batch_only`) + latency | Vishnu | | |
| Grok TTS (`ok` \| `fallback:<name>`) + latency | Vishnu | | |
| `PUCK_MIC` device name (`arecord -l`) | Matt | | Saramonic lav via USB-A adapter |
| `PUCK_SOUND_BACKEND` / accelerator (`coral` \| `hailo` \| `none`) | Matt | | |
| Sound tag ms/segment (cpu / accelerator) | Matt | | |
| Battery life with accelerator | Matt | | |

## Keanu: preparation and live procedure

The track logger is implemented at `agent/spikes/log_tracks.py`. Local tests pass;
no live call has been observed yet. The agent track mode, group dialing strategy,
and call cap above remain undecided. Values in `.env.example` are defaults, not evidence.

### Account diagnostics (2026-11-14)

- CLI login verified; selected project is `calypso`, role `owner`.
- `chert doctor` confirms the session, service connectivity, and clock are valid.
- Line assignment now verified: the line is available, its Mac is online, no
  session holds it, and the trial has 50 minutes remaining at diagnostic time.
- **Blocked: `chert livekit` returns `livekit_not_provisioned`**, including a
  second attempt after preparing the Python worker. Chert needs to provision the
  project's LiveKit keys, or the owner can supply their own LiveKit project.
- The starter's missing OpenAI key is not a requirement for the metadata logger
  or a reason to change the project's planned speech providers.
- Stage 1 update: Keanu has a separate LiveKit account/project and will configure
  its URL/API key/secret locally. The deployed backend is reachable and accepts the
  supplied token; Mary was created and verified as the sole demo patient. xAI and
  LiveKit credentials were still pending at the end of implementation. The
  [real-call test guide](stage1-test.md) tracks remaining live acceptance.

### Python dispatch entrypoint

`agent/spikes/chert_agent.py` registers `calypso-track-spike` using the LiveKit
Agents runtime and logs each dispatched room. No model provider key is needed.
Once `chert livekit` succeeds in `agent/`, use two terminals there:

```sh
# Terminal 1
uv run --env-file .env.local python spikes/chert_agent.py dev
```

```sh
# Terminal 2
npx --yes @trychert/facetime@0.1.0-beta.21 dev --agent calypso-track-spike
```

The private `.env.local` is ignored by Git. The dispatch entrypoint is verified
to import and expose its CLI; connection and dispatch remain untested until keys
are available. It is a silent observer: the managed bridge's audio-readiness
requirement below still needs resolution for sustained live calls.

### Prerequisites

- Chert account and FaceTime project/line (account already confirmed by Keanu).
- Official managed CLI verified locally: `@trychert/facetime@0.1.0-beta.21`.
  Run `npx --yes @trychert/facetime@0.1.0-beta.21 login` to sign in.
  `chert new <dir> --video` generates the Node video starter; there is no
  separate hackathon starter link in this repo. Generate it outside `agent/`
  to avoid replacing the Python package. The CLI's `guide agent` also documents
  registering a Python LiveKit agent by name.
- Room URL and a short-lived observer token for the **same LiveKit room** as the
  call, using a unique identity so the observer does not displace the agent.
  Set `LIVEKIT_URL` and `LIVEKIT_TOKEN` in the local, ignored `.env`.
  The Shared-plan starter can instead receive a call token from `chert dev`;
  integrating this observer with that handoff is still pending account setup.
- Two teammates available to join FaceTime; record which phones are present and
  when they join/leave, without committing their phone numbers.

### Spike A: group tracks

From `agent/`:

```sh
uv sync --group dev
mkdir -p out
uv run --env-file ../.env python spikes/log_tracks.py --duration 360 > out/group-tracks.jsonl
```

The logger emits identities, audio/video publication SIDs, advertised video
dimensions, mute flags, elapsed time, and connection events every two seconds.
It does not publish media or store audio/video. Output is ignored by Git.

1. Start the Chert agent using its verified starter instructions. Join the call
   with both teammates; confirm the observer is in that call's room.
2. Check identities and track SIDs as each teammate joins and leaves.
3. Separate tracks attributable to each caller support `per_participant`.
   A single bridge participant alone does **not** prove `composite`: inspect
   the incoming video with the starter and confirm both people appear in a grid.
4. Stay connected past five minutes. Record call start time separately from the
   observer's connection time; its `elapsed_s` measures observation, not call age.
5. Record observations and the chosen mode in the table, then update the local env.

### Spike B: group dialing

Use the authenticated Chert API explorer or verified starter client; endpoint
payloads and authentication must come from the managed service documentation.
Do not infer them from the separate open-source browser connector.

1. Place a call to teammate 1 with `POST /calls`; wait for connection.
2. Try a second `POST /calls` to teammate 2. Record whether all three remain in
   **one** call, or whether the first call is replaced/rejected.
3. If needed, test teammate 1 using FaceTime's Add People.
4. Record `agent_dials_both`, `agent_dials_relative_then_add`, or `manual_only`
   based on the observed outcome. Record failures as well as successes.
5. After both live spikes, check off Task 0 Steps 2–3 in `tasks/keanu-agent.md`.
   Do not mark the shared speech/puck spikes complete on their owners' behalf.

References: [Chert SDK/setup](https://github.com/cherthq/sdk),
[managed CLI](https://www.npmjs.com/package/@trychert/facetime),
[LiveKit room API](https://docs.livekit.io/reference/python/livekit/rtc/room.html),
[track publication metadata](https://docs.livekit.io/reference/python/livekit/rtc/track_publication.html).

### Platform behavior to verify before the silent group agent

The installed CLI's `guide agent` says the managed bridge expects one unmuted
agent audio publication and a greeting within 10 seconds of `bridge_ready`;
otherwise it can end the call with `remote_audio_timeout`. Check this against
the project's requirement to stay silent in group calls. The logger is a
metadata observer and is not a replacement for that media agent.
