# Calypso⁻¹ Pitch Script (3:00 pitch + 2:00 Q&A)

Slide order: **Problem → Solution → Live demo → Tech stack.**
Speakers are split by track: **Eric** (problem, solution), **Keanu** (demo), **Matt** (puck), **Vishnu** (backend, close).

Spoken pace is about 150 words a minute. Times are cumulative. Text in *[brackets]* is a stage direction, not a line. Text in `{braces}` is a value to fill in from `docs/spikes.md` or the dashboard after the dry run. Don't say a number on stage that we haven't measured.

| Section | Speaker | Time | Length |
|---|---|---|---|
| 1. Problem | Eric | 0:00–0:40 | 40 s |
| 2. Solution | Eric | 0:40–1:10 | 30 s |
| 3. Live demo | Keanu (+ cast) | 1:10–2:25 | 75 s |
| 4. Tech stack | Matt → Vishnu | 2:25–3:00 | 35 s |
| Q&A | everyone | 3:00–5:00 | 2 min |

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

*(~95 words.)*

---

## 3. Live demo (Keanu narrates, 1:10–2:25)

**Cast and screens**

| Role | Who | Device |
|---|---|---|
| Mary (patient, puck on her iPhone) | Matt | Mary's iPhone, **mirrored to the projector** (QuickTime or AirPlay) |
| Sarah (enrolled daughter) | Vishnu | Sarah's iPhone, **at the back of the room or on headphones** to avoid audio feedback |
| Newcomer (not enrolled) | Eric | Eric's iPhone |
| Narrator + dashboard | Keanu | Laptop with `https://{host}/dashboard` on the second screen |

**Before the pitch:** Matt carries his iPhone with the puck on the back that morning on a real café visit, chats with someone, and takes a photo (Task 19, Step 2). Vishnu has done the 1-minute setup call, so his face and voice are enrolled as "Sarah, daughter." Run `seed_demo.py` as the backup.

**Slide:** a "LIVE" title card, then cut to the mirrored phone and the dashboard side by side.

### Beat 1: The call starts (~10 s)
*[Vishnu texts Calypso⁻¹: "call mom with me." If `GROUP_CALL_START` is `manual_only`, or the dial is slow, Vishnu starts the group FaceTime by hand. Don't wait more than 5 s.]*

> Matt is playing Mary. The puck has been on the back of his phone all morning. Vishnu is her daughter Sarah, and he just texted Calypso⁻¹ "call Mom with me." Calypso⁻¹ starts the group FaceTime.

### Beat 2: The identity card (~20 s)
*[Sarah's face appears. The identity card shows on the Calypso⁻¹ tile: photo · "Sarah" · "Your daughter" · a recent memory.]*

> The moment Sarah appears, Calypso⁻¹'s tile shows Mary who this is: her name, "your daughter," and something they did together recently. On the dashboard you can see why: the face match scored `{face_score}`, the voice agreed, and the gap to the next-closest person cleared our safety margin.

### Beat 3: "What did you do today?" (~25 s)
*[Vishnu: "Mom, what did you do today?" The Today card appears with something like "9:10 · Blue Bean Café · coffee and a chat" and the morning's photo.]*

> Now the question that used to end in silence. Within `{latency}` seconds, Mary sees her own morning: the café she went to, who she talked with, and the photo she took. Mary can answer her daughter herself.

*[Optional if ahead of time. Vishnu: "Ugh, the weather today is awful." No card appears.]*

> And it knows when not to interrupt. "Today" in a passing sentence doesn't trigger anything.

### Beat 4: Learning someone new (~20 s; cut first if running long)
*[Eric joins. The card reads "Getting to know someone new…" Eric: "Hi Mary, I'm Eric, Sarah's friend from school." Calypso⁻¹ says once, aloud: "Nice to meet you, Eric. How do you know Mary?" Eric answers.]*

> Eric isn't enrolled, so instead of guessing, Calypso⁻¹ says "getting to know someone new." It hears his introduction and asks one question, the only time it ever speaks in a group call. Next time Eric calls, Mary will see his name.

**Demo fallbacks (from the runbook):**
- Puck offline → the Today card is built from the seeded data. Don't mention it unless asked.
- Group dial fails → start the call by hand and keep narrating.
- A card is slow → point at the dashboard's live scores and say "here's the decision being made."
- Wrong or uncertain match → it should show nothing or "uncertain." Say: "That's the safety rule working. It won't guess."

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

**2. "Privacy? It's recording a vulnerable person all day."** (Matt + Vishnu)
Only voiced segments are kept, not continuous audio. Data goes to the family's own backend, not a third-party cloud, and every API call needs a bearer token. Photos that look like IDs, cards, or screenshots are flagged by Claude Haiku and are never searchable or shown. Consent is a real issue: in a product, the family and the patient (or their legal proxy) opt in at setup, and recording would be visibly indicated. We don't claim to have solved it in 24 hours.

**3. "Why FaceTime instead of your own app?"** (Keanu)
Because the patient already knows how to answer FaceTime, and a new app is the hardest thing to ask of someone with dementia. Chert let us put an agent into a real FaceTime call, so the help shows up in the call they already have. We render on Calypso⁻¹'s own video tile, not overlays on Apple's UI, so it works on any iPhone with no install on Mary's side.

**4. "How fast is it?"** (Keanu)
Our target is ≤ 2.5 s from the end of a sentence to the card on screen, and the dashboard measures every stage. In our dry runs we hit `{measured p50 / worst}`. If the recall round trip takes over 4 s, the agent drops the card instead of showing a stale one.

**5. "How does it learn people with no data on day one?"** (Keanu)
Each relative does a 1-minute setup call with Calypso⁻¹. It asks who they are to Mary and something they share, Claude Sonnet extracts the name, relationship, and facts, and we enroll their face crops and voice. Relatives can also iMessage photos. In a call, an unknown face gets the learning flow you saw. The voices the puck has already heard but couldn't name get attached once that person is identified.

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
- [ ] Run the whole thing twice with a timer. If over 3:00, cut demo Beat 4 first, then the "weather" negative.
- [ ] Mirror Mary's phone to the projector, and open the dashboard on the second screen.
- [ ] Sarah's phone goes out of earshot or on headphones.
- [ ] Charge the puck's power bank. Run `seed_demo.py` as the backup.
- [ ] Remember the trial's 5-minute call cap: start the demo call no earlier than about 30 s before the demo.
