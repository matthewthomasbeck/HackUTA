# Calypso⁻¹ Design Spec

> Approved 2026-11-14. Implementation plan: `docs/superpowers/plans/2026-11-14-calypso-inv.md`.

**Name:** Calypso⁻¹. In the Odyssey, Calypso held Odysseus and made him forget home; the inverse brings people home to memory.

**Why:** People with dementia often can't recognize relatives or recall their own day, which makes family calls painful ("What did you do today, Mom?" → blank). Primary goal: win Chert's "Best Use of FaceTime" (fresh use of video ×2, wow, usefulness; live judging by Gary Gao on a real FaceTime). Also HackUTA (robustness, Odyssey theme, creativity). The Chert rep confirmed the group-call concept.

**Goals**
1. **Recognize the relative.** In a group FaceTime (patient + relative + Calypso⁻¹), the agent identifies the relative (face first, voice second). It shows an identity card on its own video: photo, name, relationship, recent memories.
2. **Cold start:**
   - Each relative does a 1-minute setup call with the agent. Relatives can also iMessage photos and facts.
   - Learn-in-call: an unknown face gets "Getting to know someone new…". The agent hears the intro, asks one confirmation question aloud, and creates a profile; otherwise it saves an unnamed visitor.
   - The puck's unnamed voice clusters are attached to a person once identified.
   - Name, face, and relationship are useful on day one.
3. **"My day" timeline.** Events with time, place, people, and a summary, built from speech cues, background sounds (YAMNet), and **phone location (iOS Visits)**. Location gives the *where*, audio gives the *what*. Places below the confidence threshold get neutral wording. In calls, "what did you do today?" → Today card.
4. **Photos placed on the timeline** by time and place, not by narration.
5. **iOS app** (SwiftUI): onboarding that adds Calypso⁻¹ as a contact and explains group FaceTime; People; Today timeline; photo and visit sync.
6. **Judge dashboard:** day timeline with evidence, live call scores and decisions, pipeline latency and health.
7. **Agent-started group call:** "call Mom with me" by iMessage. In scope; the method depends on the spike, with manual start as the fallback.

**Non-goals:** medical claims, reminders, medication; overlays inside Apple's FaceTime UI; multiple patients.

**Anti-goals:** a wrong person or an invented place; random popups; talking over family in group calls.

**Constraints**
- 4 people, about 24 hours.
- Hardware: Pi 4/5, a tensor accelerator (Coral or Hailo, undecided), Saramonic USB-C lavalier (clipped to the collar, plugged into the Pi's USB-A port via adapter), power bank, MagSafe.
- AI: Claude (reasoning), Grok/xAI (STT and TTS), self-hosted models on Vultr.
- Chert: LiveKit + `chert dev`, 5-minute call cap on the trial, one call per line, the agent can only text phones that have joined a call.
- The venue Wi-Fi isolates clients, so the public Vultr backend works around it, with Tailscale for SSH.

**Left to builders:** exact thresholds (starting values in Task 1), card visual design, prompt wording, Swift styling, event window size.
