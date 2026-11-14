# Calypso⁻¹

**A memory companion for people with dementia, built for HackUTA × Chert "Best Use of FaceTime."**

In the *Odyssey*, Calypso held Odysseus on her island and kept him from going home. Calypso⁻¹ is the inverse: it brings people home to their memories.

- **The puck:** a Raspberry Pi with a lavalier mic, worn by the patient. It listens through the day, tags background sounds, and works offline. Combined with the phone's location, this builds a timeline of the day: where they were, who they talked to, and what about.
- **The agent:** a Chert FaceTime agent that joins a group FaceTime with the patient and a relative. It recognizes the relative by face and voice and shows cards on its own video tile, such as "Sarah, your daughter" or, when asked "what did you do today?", the patient's day.
- **The app:** a SwiftUI iPhone app with onboarding (including adding Calypso⁻¹ as a contact), people, the Today timeline, and photo and location sync.
- **The dashboard:** a live view for judges of the timeline, recognition scores, and pipeline latency.

## Docs
- Design spec: [`docs/superpowers/specs/2026-11-14-calypso-inv-design.md`](docs/superpowers/specs/2026-11-14-calypso-inv-design.md)
- Implementation plan: [`docs/superpowers/plans/2026-11-14-calypso-inv.md`](docs/superpowers/plans/2026-11-14-calypso-inv.md)
- Hour-1 spike results: [`docs/spikes.md`](docs/spikes.md)

## Who owns what

| Track | Owner | Folder | Tasks |
|---|---|---|---|
| Backend + judge dashboard | Vishnu | `backend/`, `dashboard/` | [`docs/tasks/vishnu-backend.md`](docs/tasks/vishnu-backend.md) |
| Puck (Raspberry Pi) | Matt | `puck/` | [`docs/tasks/matt-puck.md`](docs/tasks/matt-puck.md) |
| Chert FaceTime agent | Keanu | `agent/` | [`docs/tasks/keanu-agent.md`](docs/tasks/keanu-agent.md) |
| iOS app | Eric | `ios/` | [`docs/tasks/eric-ios.md`](docs/tasks/eric-ios.md) |
| Demo | everyone | `scripts/` | [`docs/tasks/all-demo.md`](docs/tasks/all-demo.md) |

**Start here:** everyone runs their hour-1 spike (Task 0 in your task file) and writes the result in `docs/spikes.md` before building on assumptions.

## Layout
```
backend/    FastAPI on Vultr. calypso/models.py is the shared contract for every component
puck/       Pi capture → VAD → sound tags → offline queue → uploader
agent/      Chert LiveKit agent: recognition loop, cards as video, setup calls, recall
ios/        SwiftUI app (see ios/README.md to create the Xcode project)
dashboard/  Judge dashboard (static, served by the backend at /dashboard)
scripts/    Demo seed script
docs/       Spec, plan, per-person tasks, spike results
```

## Running
Python parts use [uv](https://docs.astral.sh/uv/). Copy `.env.example` to `.env` first.
```bash
cd backend && uv run --group dev pytest      # tests
cd backend && uv run uvicorn calypso.app:app --host 0.0.0.0 --port 8000   # after Task 1
cd puck    && uv run --group dev pytest
cd agent   && uv run --group dev pytest
```

## Rules for everyone
- Never show the wrong person or a made-up place. When unsure, use neutral wording.
- Every provider or hardware choice still open (STT, TTS, accelerator, call mode) sits behind an interface with a `Fake*` version, and swapping it is one env var.
- Don't change `backend/calypso/models.py` without telling the team.
