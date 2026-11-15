# Calypso⁻¹

**A memory companion for people with dementia, inside FaceTime.** Built at HackUTA 2026 for Chert's "Best Use of FaceTime."

Mary never learns an app. Her family calls her on FaceTime, she adds Calypso⁻¹, and it shows her who she's talking to and what she did, from a memory bank built by her puck.

## Inspiration

**57 million people live with dementia today. By 2050 that number reaches 153 million**, and someone new is diagnosed about **every 3 seconds** (WHO; *The Lancet Public Health*, 2022).

Picture Mary, 78. Every Sunday her daughter Sarah FaceTimes her. Sarah asks, "What did you do today, Mom?" Mary can't remember, and some weeks she isn't sure who's calling. The call ends in silence. The WHO lists not recognizing family as a symptom as dementia progresses.

In the *Odyssey*, Calypso kept Odysseus on her island and made him forget home. We built the inverse: **Calypso⁻¹**, which brings people home to their memories.

## What it does

Calypso⁻¹ joins Mary's FaceTime calls as a quiet guest. When a relative's face appears, Mary sees a card on Calypso⁻¹'s video tile: **"Sarah, your daughter."** When someone asks "What did you do today?", she sees her own day and can answer for herself. Mary doesn't learn a new app. She just answers FaceTime.

- **The puck:** a Raspberry Pi with a lav mic that Mary wears. It records her day, works with no Wi-Fi, and uploads once it reconnects.
- **One-time setup call:** each relative FaceTimes Calypso⁻¹ once. It asks their name and how they know Mary, then saves their face and voice.
- **Identity cards in group calls:** in a FaceTime with Mary and a relative, Calypso⁻¹ matches faces and voices and shows who's there, one card at a time.
- **In-call recall:** Claude Haiku spots questions about Mary's day, and Calypso⁻¹ answers with a card built from what the puck heard.
- **iPhone app and judge dashboard:** the SwiftUI app handles onboarding, people, and Mary's Today timeline. A live dashboard shows every decision: puck audio, voice match, face score, and recall.

**It never guesses.** Below the confidence bar, the card says "Getting to know someone new…" instead of naming the wrong daughter. Places work the same way: "somewhere with café sounds," never a made-up name.

## The demo

Our demo video (under 2 minutes) is a screen recording of the phones and the dashboard, with the real call audio. Everything in it was tested live on 2026-11-15.

1. **The memory bank.** The puck listens all day. The dashboard lights up Puck → Ingest → Speech + voice → Day builder, and the app's Today timeline fills in (garden · tea with Eric · Riverside Park). Audio is deleted; only text is kept.
2. **A new relative introduces themselves.** Eric FaceTimes Calypso⁻¹. It looks for a familiar face, then asks "What's your name, and how do you know Mary?", reads his answer back, and saves him only after he says "Yes": 3 face prints and 1 voice print.
3. **A known relative is recognized.** Keanu calls, and his face score passes the threshold in about 5 seconds.
4. **The family call.** Mary is on FaceTime with Keanu and taps Add People → Calypso⁻¹. Its tile shows "Keanu · Mary's brother," and it says "Hi Mary, you're speaking with Keanu, your brother." Mary herself never gets a card.
5. **"Mary, what did you do today?"** A Today card appears, built from what really happened, and the dashboard shows the recall latency (target ≤ 2.5 s).
6. **Someone else joins.** Eric is added and introduced the same way.
7. **It never guesses.** Small talk gets no recall card, and a "Not sure yet" face gets no identity card.

**Honesty notes:** Mary is a composite character played by a teammate, not a real patient. Mary's days in the demo are seeded sample speech and phone visits, run through our real day builder; in real use, the puck and Mary's phone build them. Group FaceTime works through Chert's line and was tested with 3 iPhones.

## How we built it

**The flow:**

1. **Puck → Vultr:** the puck spools audio to disk and uploads it to our FastAPI backend on Vultr.
2. **Vultr backend:** Grok transcribes, Claude summarizes, and SQLite + Redis/RQ store and process everything.
3. **FaceTime → Chert → LiveKit:** Chert bridges the call into a LiveKit room, where our Calypso⁻¹ agent (also on Vultr) sees and hears it.
4. **Agent → FaceTime:** the agent asks the backend who's there and sends cards back as its outgoing video.
5. **iPhone app + dashboard:** the SwiftUI app syncs with the backend, and an event bus streams every decision to the judge dashboard over SSE.

Every part talks to the others only through the backend's HTTP API, with one shared pydantic contract.

- **Hardware / edge:** Raspberry Pi, Saramonic lav mic, C++ capture pipeline, sherpa-onnx with NVIDIA NeMo TitaNet for on-device voice ID, Bluetooth LE to the phone, 3D-printed mount
- **Backend:** Python, FastAPI, SQLite, Redis + RQ job queue, server-sent events
- **AI/ML:** Claude Sonnet (setup calls, daily summaries), Claude Haiku (detecting recall questions), xAI Grok (speech-to-text and text-to-speech), OpenCV YuNet + SFace (faces), TitaNet (voices)
- **Calls:** Chert, LiveKit Agents, Pillow (renders cards into the agent's video)
- **Frontend:** SwiftUI (iOS 17+), plain HTML/JS dashboard
- **Infrastructure:** Vultr, systemd

Every provider (STT, TTS, face model, voice model, call topology) sits behind one interface with a fake version, so swapping one is one env var and the tests never need live keys.

Open-source parts we used: YuNet/SFace (faces), NeMo TitaNet via sherpa-onnx (voice), YAMNet (sounds), LiveKit, Chert. Built by us: puck firmware, backend, agent, iOS app, dashboard.

### How we used Vultr

Vultr runs everything in the call path. One Vultr server hosts three systemd services that start at boot and restart on failure:

- **`calypso-backend`:** the FastAPI API, SQLite database, Redis + RQ workers, face and voice models, and all Claude decisions
- **`calypso-media`:** the LiveKit media worker that sees and hears the call and sends cards back as video
- **`calypso-chert`:** the Chert FaceTime connector

No laptop sits in the call path. The puck and the iPhone upload straight to Vultr, the agent calls the backend over loopback, and secrets stay in root-only env files on the server.

### How we used hardware

The puck is Mary's memory. It's a Raspberry Pi with a Google Coral Edge TPU, a Saramonic lav mic, a power bank, and a 3D-printed top plate.

- **Offline first:** every audio segment is written to an on-disk spool before anything else. When the network returns, it uploads oldest first. Each segment gets a UUID at capture, so retries never create duplicates on the server.
- **Clock-safe:** if the Pi boots without network time, segments are held and their timestamps are corrected once the clock syncs, so Mary's day stays in the right order.
- **On-device voice ID on a Coral TPU:** in offline mode, every model runs on a Google Coral Edge TPU attached to the Pi, not the Pi's CPU. TitaNet works out "who is talking" with no internet, using voiceprints the puck syncs from the backend.
- **Bluetooth LE to the iPhone:** the puck streams "who is talking" to the app over a custom BLE service, which also handles teaching the puck Mary's voice during onboarding.

### How we used Chert

Chert is what makes FaceTime possible. It bridges a real FaceTime call into a LiveKit room, so our Python agent can see and hear the call like any participant.

- **Setup calls:** a relative FaceTimes the Calypso⁻¹ contact. The agent talks with them (Grok voice, Claude for the conversation), and the backend saves their name, relationship, face prints, and voice prints, tied to their verified caller number.
- **Cards as video:** we render each card with Pillow and publish it as the agent's outgoing video, so the cards show up on Calypso⁻¹'s FaceTime tile. Nothing gets installed on Mary's phone.
- **Automatic routing:** each incoming call is routed to setup or group mode by who is calling.
- **Silent in group calls:** the agent speaks only to confirm a new person. Otherwise it shows one card at a time, for 6 to 10 seconds.

### How we used SpaceX AI (xAI Grok)

Grok is Calypso⁻¹'s ears and voice.

- **Speech-to-text:** Grok transcribes the puck's audio on the backend. Those transcripts feed Claude Sonnet, which builds Mary's day.
- **Live call speech:** in setup calls, Grok transcribes the relative and speaks Calypso⁻¹'s replies through the LiveKit media worker.

Both sit behind our STT and TTS interfaces (`CALYPSO_STT`, `CALYPSO_TTS`).

## Challenges we ran into

- **Getting into a FaceTime call at all.** Chert's LiveKit keys weren't provisioned at first (`livekit_not_provisioned`), so we brought our own LiveKit project. We also hit worker sessions stuck "cleaning up" and calls missing from call records, and had to tell provider problems apart from our own bugs.
- **Group calls.** Automatic group dialing and native hangup weren't available through the CLI, so the agent asks the caller to hang up and the group call is started from FaceTime.
- **Not showing the wrong person.** Reviewing our deployed build, we found that a demo test setting could override a real face match. We made it opt-in and off by default. We also found that two relatives sharing one phone number could merge into one profile, which is still on our list.
- **Audio that survives bad Wi-Fi.** Fixed 3-second chunks cut words in half and wasted uploads. Making the queue durable, idempotent, and clock-safe on a Pi took more care than recording did.
- **Four parallel tracks in 24 hours.** Puck, backend, agent, and iOS were built by four people at once. A single shared data contract and fake versions of every provider let each of us build before the others were done.

## Accomplishments that we're proud of

- **Real FaceTime enrollment works end to end.** A relative calls Calypso⁻¹, has a short conversation, and their name, relationship, face, and voice are saved on our Vultr backend.
- **Mary doesn't install anything.** The cards are Calypso⁻¹'s own video in an ordinary FaceTime call, the only interface many people with dementia already know.
- **Safety is built in, not added on.** Face matches need a minimum score *and* a clear lead over the next-closest person, or the card stays neutral. Photos flagged as sensitive are never shown.
- **A puck that keeps working offline.** It records to disk, uploads later without duplicates, and identifies voices on the device.

## What we learned

- How to bridge a consumer app like FaceTime into a programmable media pipeline with Chert and LiveKit, and how to draw on an agent's outgoing video.
- How to design for a user who can't tell you the system is wrong: confidence thresholds, margins between candidates, and neutral fallback wording.
- How to make edge uploads reliable: write to disk first, fix IDs at capture, retry with backoff, and correct clocks later.
- How to split work between AI models: Haiku for fast decisions, Sonnet for writing, Grok for speech.
- How to let four people build in parallel against one API contract with fake providers.

## What's next for Calypso⁻¹

- **Automatic group calls.** Have Calypso⁻¹ dial Mary and a relative together, and let Mary say "call my daughter."
- **iMessage intake.** Let relatives text photos and memory notes that feed Mary's recall.
- **Tune on real families.** Pilot with memory-care families and tune face and voice thresholds on real lighting, cameras, and voices.
- **A caregiver view, and consent.** Build a caregiver view and a clear consent flow for the people Mary's puck hears. Calypso⁻¹ is a communication aid, not a medical device, and we won't make medical claims without evidence.

---

## For developers

### Team

| Track | Owner | Folder | Tasks |
|---|---|---|---|
| Backend + judge dashboard | Vishnu | `backend/`, `dashboard/` | [`docs/tasks/vishnu-backend.md`](docs/tasks/vishnu-backend.md) |
| Puck (Raspberry Pi) | Matt | `puck/`, `3d_parts/` | [`docs/tasks/matt-puck.md`](docs/tasks/matt-puck.md) |
| Chert FaceTime agent | Keanu | `agent/` | [`docs/tasks/keanu-agent.md`](docs/tasks/keanu-agent.md) |
| iOS app | Eric | `ios/` | [`docs/tasks/eric-ios.md`](docs/tasks/eric-ios.md) |
| Demo | everyone | | [`docs/tasks/all-demo.md`](docs/tasks/all-demo.md) |

### Layout
```
backend/    FastAPI on Vultr. calypso/models.py is the shared contract for every component
puck/       C++ capture → on-disk spool → uploader, plus on-device voice ID and BLE to the phone
agent/      Chert LiveKit agent: recognition, cards as video, setup calls, recall
ios/        SwiftUI app (Xcode project generated by xcodegen from ios/project.yml)
dashboard/  Judge dashboard (static, served by the backend at /dashboard)
3d_parts/   STL files for the puck's case
docs/       Spec, plans, per-person tasks, spike results, runbooks
```

### Running
Python parts use [uv](https://docs.astral.sh/uv/). Copy `.env.example` to `.env` first.
```bash
cd backend && uv run --group dev pytest
cd backend && uv run uvicorn calypso.app:app --host 0.0.0.0 --port 8000
cd agent   && uv run --group dev pytest

# Puck (Pi: sudo apt install cmake g++ libasound2-dev libcurl4-openssl-dev)
cd puck && cmake -S . -B build && cmake --build build && ./build/calypso_puck

# iOS
cd ios && xcodegen
xcodebuild test -project ios/Calypso.xcodeproj -scheme Calypso -destination 'platform=iOS Simulator,name=iPhone 17'
```
See [`puck/INSTRUCTIONS.md`](puck/INSTRUCTIONS.md) for puck configuration and voice enrollment, and [`docs/vultr-call-services.md`](docs/vultr-call-services.md) for the server's systemd services.

### Docs
- Design spec: [`docs/superpowers/specs/2026-11-14-calypso-inv-design.md`](docs/superpowers/specs/2026-11-14-calypso-inv-design.md)
- Implementation plan: [`docs/superpowers/plans/2026-11-14-calypso-inv.md`](docs/superpowers/plans/2026-11-14-calypso-inv.md)
- API: [`docs/api.md`](docs/api.md)
- Hour-1 spike results: [`docs/spikes.md`](docs/spikes.md)

### Rules for everyone
- Never show the wrong person or a made-up place. When unsure, use neutral wording.
- Every provider or hardware choice (STT, TTS, accelerator, call mode) sits behind an interface with a `Fake*` version, and swapping it is one env var.
- Don't change `backend/calypso/models.py` without telling the team.
