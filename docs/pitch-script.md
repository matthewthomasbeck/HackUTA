# Calypso⁻¹ Pitch Script (3:00 pitch + 2:00 Q&A)

Slide order: **Problem → Solution → Live demo (judge's setup call → group call → dashboard) → Tech stack.**
Speakers are split by track: **Eric** (problem, solution), **Keanu** (demo), **Matt** (puck), **Vishnu** (backend, close).

**The idea:** a judge becomes the person Mary is meeting. Matt wears Mary's puck through the whole pitch, so when the judge FaceTimes Calypso⁻¹, it already knows a little about them from what it heard. Then the judge joins a group FaceTime with Mary, and Calypso⁻¹ shows Mary who they are and what she did today.

Spoken pace is about 150 words a minute. Times are cumulative. Text in *[brackets]* is a stage direction, not a line. Text in `{braces}` is a value to fill in from `docs/spikes.md` or the dashboard after the dry run. Don't say a number on stage that we haven't measured.

| Section | Speaker | Time | Length |
|---|---|---|---|
| 1. Problem | Eric | 0:00–0:40 | 40 s |
| 2. Solution | Eric | 0:40–1:10 | 30 s |
| 3a. Judge's setup call | Keanu (+ judge) | 1:10–1:40 | 30 s |
| 3b. Group call | Keanu (+ judge, Matt) | 1:40–2:15 | 35 s |
| 3c. Dashboard | Keanu | 2:15–2:25 | 10 s |
| 4. Tech stack | Matt → Vishnu | 2:25–3:00 | 35 s |
| Q&A | everyone | 3:00–5:00 | 2 min |

---

## 0. Before the timer (Eric, ~15 s, not counted)

*[Matt is already wearing the puck. Eric picks one judge, usually whoever is closest or most engaged.]*

> Before we start, could you tell us your name and what you work on?

*[Let the judge answer in full. This is the puck's sample of their voice and the facts Calypso⁻¹ will repeat back. If the judges introduce themselves on their own, skip the question. If the answer is one word, ask a follow-up: "What brought you to HackUTA?"]*

---

## 1. Problem (Eric, 0:00–0:40)

**Slide:** a huge **57,000,000** on black. Below it, three small stat lines appear one at a time: *~10M new cases a year · 153M by 2050*. At "Meet Mary," the slide changes to a phone mockup of a FaceTime call with the caption *"What did you do today, Mom?"*

> Fifty-seven million.
>
> That's how many people are living with dementia right now, according to the World Health Organization. Nearly ten million more are diagnosed every year. That's one new case about every three seconds. By 2050, it's projected to be a hundred and fifty-three million.
>
> *[slide change]* Meet Mary. She's seventy-eight. Every Sunday her daughter Sarah FaceTimes her and asks, "What did you do today, Mom?" And Mary goes blank. Some Sundays, she isn't sure who Sarah is. The call that's meant to connect them has become the hardest part of their week.

*(~90 words. Mary and Sarah are an illustrative persona, not a real patient. If a judge asks, say so plainly: "Mary is a composite. The experience is what caregivers describe, and the WHO lists not recognizing family as a symptom of progressing dementia.")*

---

## 2. Solution (Eric, 0:40–1:10)

**Slide:** the Calypso⁻¹ wordmark, with the line *"Calypso made Odysseus forget home. We built the inverse."* Below it are three icons in a row: **Puck** (MagSafe on the back of an iPhone), **App** (an iPhone), and **Calypso⁻¹** (a FaceTime tile).

> This is Calypso⁻¹. In the Odyssey, Calypso held Odysseus and made him forget home. We built the inverse.
>
> It has three pieces. A small **puck** that snaps onto the back of Mary's iPhone with MagSafe quietly turns her day into a timeline: who she talked to, where she went, and what it sounded like. An **iPhone app** syncs her photos and the places her phone visited. And **Calypso⁻¹ itself is a contact** you add to a group FaceTime. It watches the call, and on its own video tile it shows Mary who she's talking to and what she did today.
>
> Mary doesn't learn a new app. She just answers FaceTime.
>
> *[gesture at Matt]* Matt has been wearing Mary's puck this whole time. As far as the puck knows, this room *is* Mary's day. So let's have you meet her.

*(~120 words. Say the last line warmly, not as a gotcha. The point is that the puck is Mary's memory and it's working, not that we recorded the judge.)*

---

## 3. Live demo (Keanu narrates, 1:10–2:25)

**Cast and screens**

| Role | Who | Device |
|---|---|---|
| The judge (the newcomer Mary meets) | One judge | **Team phone** (Eric's iPhone): Calypso⁻¹ app onboarded, `Calypso⁻¹` and `Mary` in Contacts. **Mirrored to the projector** the whole demo. |
| Mary (patient, puck on her iPhone) | Matt | Mary's iPhone, **muted mic speaker or headphones** so it doesn't feed back with the team phone in the same room |
| Narrator + dashboard | Keanu | Laptop with `https://{host}/dashboard` on the second screen |
| Hands the phone over, runs fallbacks | Eric | |

Mirror only the team phone. The cards are Calypso⁻¹'s outgoing video, so the room sees them on the judge's screen in both calls.

**Before the pitch:** Matt wears the puck that morning on a real café visit, chats with someone, and takes a photo (Task 19, Step 2), so Mary's Today card has real content. Rehearse a group FaceTime from the team phone to Mary + Calypso⁻¹ so it sits at the top of FaceTime's recents for a one-tap redial. Run `seed_demo.py` as the backup. Delete any rehearsal person who shares the judge's role, so the judge is the only new person.

**Judge's cue card** (hand it over with the phone):
> 1. Tap **Calypso⁻¹** and answer its question.
> 2. Hang up, then tap **Mary + Calypso⁻¹**.
> 3. Ask: **"Mary, what did you do today?"**

**Slide:** a "LIVE" title card, then cut to the mirrored team phone and the dashboard side by side.

### Beat 1: The judge calls Calypso⁻¹ (1:10–1:40, ~30 s)
*[Eric hands the judge the team phone and cue card. The judge FaceTimes Calypso⁻¹ 1:1. This is a setup call, so the agent speaks freely. It matches the judge's voice to the cluster the puck heard before the timer, and opens with it.]*

Calypso⁻¹, roughly:
> Hi, I'm Calypso⁻¹. I think I heard you a little earlier. You're {name}, and you work on {X}? How do you know Mary?

*[The judge answers. Calypso⁻¹ thanks them and says goodbye. The judge hangs up.]*

> Every relative does this once: a short FaceTime with Calypso⁻¹. But it didn't start from zero. The puck heard you introduce yourself, so it recognized your voice and already had your name. In that call it also learned your face.

*[If the voice lookup misses, the agent asks the normal setup question ("Hi, I'm Calypso⁻¹. What's your name, and how do you know Mary?"). Don't mention the miss. Say: "Every relative does this once, a 30-second FaceTime."]*

### Beat 2: The group call (1:40–2:15, ~35 s)
*[The judge taps the Mary + Calypso⁻¹ group call in recents. Matt answers as Mary. The identity card appears on the Calypso⁻¹ tile: the judge's face · "{name}" · "{how they know Mary}".]*

> Now the judge FaceTimes Mary, with Calypso⁻¹ in the call. The moment their face appears, Mary sees who this is, from a person she met one minute ago.

*[The judge reads cue 3: "Mary, what did you do today?" The Today card appears with something like "9:10 · Blue Bean Café · coffee and a chat" and the morning's photo.]*

> And the question that used to end in silence. Within `{latency}` seconds, Mary sees her own morning: the café, who she talked with, the photo she took. She can answer for herself. And the agent stays silent the whole time. It's a guest in the call, not the host.

### Beat 3: The dashboard (2:15–2:25, ~10 s)
*[Keanu points at the second screen.]*

> Here's every decision you just saw, live. The puck segments from this room, the voice match, face score `{face_score}` and the margin over the next person, and "is this sentence about Mary's day." That's the hand-off to Matt and Vishnu.

**Demo fallbacks (from the runbook):**
- Puck didn't upload the judge's intro in time → the setup call opens with the normal question (see Beat 1). The rest of the demo is unchanged.
- Puck offline all morning → the Today card is built from the seeded data. Don't mention it unless asked.
- The 1:1 call to Calypso⁻¹ doesn't connect within 5 s → skip to Beat 2 with a pre-enrolled teammate on the team phone instead of the judge ("here's someone Mary already knows"), and keep narrating.
- The group-call redial isn't in recents → FaceTime → New FaceTime → Mary + Calypso⁻¹ → Video. Eric does it, not the judge.
- A card is slow → point at the dashboard's live scores and say "here's the decision being made."
- Wrong or uncertain match → it should show nothing or "Getting to know someone new…". Say: "That's the safety rule working. It won't guess."
- The judge goes off script in the 1:1 call → let the agent finish its turn, then Eric says "let's call Mary" and points at cue 2.

**What this needs that the plan doesn't cover yet** (raise with Vishnu and Keanu now):
- **Voice lookup at the start of a 1:1 call (Vishnu).** Match the caller's voice against the puck's *unnamed* voice clusters and return that cluster's recent utterances. Today `POST /people/from_intro` only links the cluster *after* the intro (Task 5).
- **A context-aware greeting (Keanu, Task 13).** If the lookup returns utterances, Claude writes the opening line from them: name plus one fact, nothing invented. With no match, use the normal setup greeting.
- **Puck → transcript → cluster in under ~60 s,** so the pre-timer intro is clustered by 1:10. Measure it in the dry run.
- **The identity card's relationship line for a non-relative** (for example, "Met you at HackUTA"). Check that Task 5's extraction handles "I'm a judge here."
- Still blocking everything: LiveKit keys for the agent (Keanu), and the day builder and recall (Vishnu, Tasks 7–8).

---

## 4. Tech stack (Matt 2:25–2:40, Vishnu 2:40–3:00)

**Slide:** an architecture diagram. Puck → (HTTPS, offline queue) → Backend on Vultr ← iOS app; Backend ↔ Chert agent ↔ FaceTime; Backend → SSE → Dashboard. Model names go under each box.

**Matt (puck):**
> The puck is a Raspberry Pi with a mic that snaps onto the back of an iPhone with MagSafe. WebRTC voice activity detection cuts speech into segments, and YAMNet, a model trained on 521 audio classes, tags the background, like espresso machines or traffic, on `{accelerator}`. Every segment lands in an on-disk SQLite queue first, so it keeps recording through a dead hotspot. The server dedupes on a segment UUID, so retries never double-count.

**Vishnu (backend + close):**
> The backend is FastAPI on Vultr. Faces are ArcFace embeddings from InsightFace, and voices are SpeechBrain ECAPA clusters. We fuse them with a strict rule: if the top two faces score within 0.08 of each other, the answer is "uncertain." We'd rather show nothing than the wrong daughter. Grok transcribes, Claude Sonnet writes the day's events from speech, sound, and iOS location visits, and Claude Haiku decides in real time whether the last sentence is actually asking about Mary's day. The Chert agent renders each card with Pillow as its own outgoing video.
>
> Calypso⁻¹: bringing people home to memory. Thank you.

*(~150 words between the two.)*

---

## Q&A prep (2:00)

Keep each answer to **20–30 s**. The owner answers; anyone can add one sentence. If you don't know, say what we'd measure and how.

**1. "What if it shows the wrong person?"** (Vishnu)
That's our number-one anti-goal. A match needs a face score ≥ 0.45, a margin of ≥ 0.08 over the second-best person, and no disagreement from the voice model. Otherwise it's "uncertain" or "getting to know someone new," never a guess. There's a test for exactly the two-similar-relatives case (`test_recognize_ambiguous_top2_is_uncertain`). Places work the same way: below 0.6 confidence we say "somewhere with café sounds" instead of inventing a name.

**2. "Privacy? It's recording a vulnerable person all day. And it recorded me."** (Matt + Vishnu)
It did, and that's worth saying plainly: we asked you to introduce yourself while the puck was on, and it used that. In a product, people who talk with Mary would be told she wears one, the same way you'd tell a guest about a hearing aid that records. Only voiced segments are kept, not continuous audio. Data goes to the family's own backend, not a third-party cloud, and every API call needs a bearer token. Photos that look like IDs, cards, or screenshots are flagged by Claude Haiku and are never searchable or shown. Consent is a real issue: in a product, the family and the patient (or their legal proxy) opt in at setup, and recording would be visibly indicated. We don't claim to have solved it in 24 hours.

**3. "Why FaceTime instead of your own app?"** (Keanu)
Because the patient already knows how to answer FaceTime, and a new app is the hardest thing to ask of someone with dementia. Chert let us put an agent into a real FaceTime call, so the help shows up in the call they already have. We render on Calypso⁻¹'s own video tile, not overlays on Apple's UI, so it works on any iPhone with no install on Mary's side.

**4. "How fast is it?"** (Keanu)
Our target is ≤ 2.5 s from the end of a sentence to the card on screen, and the dashboard measures every stage. In our dry runs we hit `{measured p50 / worst}`. If the recall round trip takes over 4 s, the agent drops the card instead of showing a stale one.

**5. "How does it learn people with no data on day one?"** (Keanu)
You just saw it. Each relative does a short setup call with Calypso⁻¹. It asks who they are to Mary and something they share, Claude Sonnet extracts the name, relationship, and facts, and we enroll their face crops and voice. Relatives can also iMessage photos. In a group call, an unknown face gets "Getting to know someone new…" and one confirmation question. The voices the puck has already heard but couldn't name get attached once that person is identified, which is how it knew you before you called.

**6. "Group calls: how do you tell who's who?"** (Keanu)
`{AGENT_TRACK_MODE}`. If Chert gives us one track per participant, each face maps to its participant. If it's a composite grid, InsightFace returns every face with its bounding box, so we identify each tile separately. Both are behind one interface, selected by one env var.

**7. "What happens with bad Wi-Fi or no connection?"** (Matt)
The puck never depends on the network. It records, tags sounds, and can transcribe locally with whisper.cpp, all into a durable queue. When it reconnects, it drains oldest-first, and the server dedupes, so hours offline cost nothing.

**8. "Is this a medical device? Does it slow dementia?"** (Eric)
No, and we're careful not to claim that. It's a communication aid: it helps families have a better call. There are no reminders, no medication, and no diagnosis. Measuring whether it reduces call distress would be the obvious next study.

**9. "Why Claude and Grok, and what does it cost?"** (Vishnu)
Haiku for fast, cheap classification: intent detection runs in about 100 output tokens per line. Sonnet for the quality writing, the daily summaries. Grok for speech-to-text and text-to-speech. Every provider sits behind an interface with a fake for tests, so swapping one is one adapter file and one env var. Face, voice, and sound models are open-source and self-hosted.

**10. "What's next?"** (Eric)
A real pilot with a memory-care family, tuning the thresholds on real faces and lighting, multi-patient support, and a caregiver view that flags changes in routine. We're keeping medical claims out until there's evidence.

**11. "Why the name?"** (Eric)
In the Odyssey, Calypso kept Odysseus on her island for seven years and made him forget home. Calypso⁻¹ is the inverse function: it brings people back home to the people they love.

---

## Sources (for the problem slide; put them on a small footer line or an appendix slide)

- **57 million people with dementia worldwide (2021); nearly 10 million new cases a year; may not recognize family members or friends:** WHO, *Dementia* fact sheet. https://www.who.int/news-room/fact-sheets/detail/dementia
- **"One every ~3 seconds"** is our own math from the WHO figure: 10M ÷ 31.5M seconds in a year ≈ 1 per 3.2 s.
- **153 million by 2050:** GBD 2019 Dementia Forecasting Collaborators, *The Lancet Public Health* (2022), reused by the 2024 Lancet Commission. IHME summary: https://healthdata.org/news-events/newsroom/news-releases/lancet-public-health-global-dementia-cases-set-triple-2050
Note on the numbers: 57M is a 2021 figure. Say "living with dementia right now," not "as of this year."

## Pre-pitch checklist

- [ ] Fill every `{brace}` from `docs/spikes.md` and the dry-run dashboard. Delete any line whose number we didn't measure.
- [ ] Run the whole thing twice with a timer, with a teammate playing the judge who *hasn't* done a setup call. If over 3:00, shorten the dashboard beat first, then the narration after the 1:1 call.
- [ ] Time puck → transcript → voice cluster for the pre-timer intro. If it's over 60 s, move the intro question earlier or accept the fallback greeting.
- [ ] Team phone: onboarded, `Calypso⁻¹` and `Mary` in Contacts, a Mary + Calypso⁻¹ group call in FaceTime recents, Do Not Disturb on, mirrored to the projector. Print the judge's cue card.
- [ ] Mary's phone (Matt) on headphones or with its speaker muted, so it doesn't feed back with the team phone.
- [ ] Open the dashboard on the second screen.
- [ ] Between pitches, delete the previous judge's `Person` (and their voice cluster) so the next judge starts as a stranger.
- [ ] Charge the puck's power bank. Run `seed_demo.py` as the backup.
- [ ] Remember the trial's 5-minute call cap. Both demo calls start live during the pitch, so this only matters if a rehearsal call is left running.
- [ ] The pre-timer intro may not be allowed if judges are strict about time. If so, ask the question during the problem slide instead ("Before I go on, what's your name?").
