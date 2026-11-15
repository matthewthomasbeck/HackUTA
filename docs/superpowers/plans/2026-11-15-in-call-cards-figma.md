# In-Call Cards — Figma design plan

Goal: design the screens Calypso⁻¹ shows **as its own video feed during a FaceTime call**, in the
approved paper-cut "Periwinkle & Apricot" Odyssey style, so `agent/calypso_agent/cards.py` can later be
re-skinned to match.

Spec: the approved design language is `~/Downloads/CalypsoDesignHandoff/design-plan.md` (read Global
Constraints 1–9 and the ADDENDUM 10–12; the Ink color is `#1E2A44`). Product rules: `CLAUDE.md`.

Figma file key: `iFIEYln3PGonIVjgQwwLp2` · Figma sessionId: `e9e61a1a-8595-4879-a049-0ecd204e0c6c`
(pass it on every Figma file-tool call). New page: **`06 In-Call`**. Existing components live on
page `00 Foundations` (Mascot set `10:15`, Illustrations `19:390`, UI Components `19:391`). Look at
`01 Onboarding` (`20:210`) for the finished style.

What the code renders today (content source): `agent/calypso_agent/cards.py`,
`agent/calypso_agent/live_media.py` (`run()`), `agent/calypso_agent/state.py`, `Card` in
`agent/calypso_agent/contract.py` (`kind`: identity | learning | today | memory; `title`; `lines`;
`image_urls`).

## Global Constraints (bind every task)

1. **Canvas:** every card frame is **720×1280** (portrait, `CALL_SIZE`). It is shown as a FaceTime video
   tile on an older adult's phone (≈ 0.55× scale) and goes through H.264 compression at 5 fps.
2. **Video type scale** (≈ 2× the app scale; nothing below 40px; no Light/thin weights):
   `Call Display` 96/108 Fraunces Semi Bold · `Call Title` 72/84 Fraunces Semi Bold ·
   `Call Headline` 56/68 Nunito Bold · `Call Body` 48/64 Nunito Regular ·
   `Call Body Strong` 48/64 Nunito Bold · `Call Caption` 40/52 Nunito Semi Bold.
   Margins 48px. Text max width 624px.
3. **Palette** = Foundations variables (Paper `#FBF6EE` background, Card `#FFFFFF`, Ink `#1E2A44`,
   Ink Soft `#4A4759`, Periwinkle `#9AA6E8`, Periwinkle Deep `#3E4A9E`, Periwinkle Mist `#C9D0F5`,
   Apricot `#F4A97A`, Apricot Cream `#FAD3B5`, Olive/Terracotta decorative only). Text pairs ≥ 7:1.
   No red, no gradients, no glass/blur, no drop-shadow stacks.
4. **Pillow-reproducible:** the agent draws each frame with Python Pillow. Use only: flat fills,
   rounded rectangles, ellipses, simple polygons/paths, text, and illustrations that can be exported as
   PNG and pasted (mascot poses, waves, island, boat, olive branch). Every illustration must be its own
   named layer/instance so it can be exported. No effects that Pillow cannot draw.
5. **One card on screen, one idea per card.** Large, calm, uncluttered. The seagull is a small companion
   on content cards (≤ 200px), larger only on idle/system cards. It never covers a face photo or text.
6. **Never show the wrong person or a made-up place.** Unknown/uncertain → neutral wording
   ("Getting to know someone new…", "somewhere with café sounds"); never a guessed name. The patient
   (Mary) is never the subject of an identity card. Sensitive photos never appear.
7. **Product name exactly `Calypso⁻¹`.** Sample content: patient Mary; Mom (mother), Sarah (daughter,
   lives in Austin, dog Biscuit, "You bake together on Sundays."), Tom (neighbor). Saturday,
   November 14: 9:30 AM Grocery shopping with Mom · 11:00 AM Coffee with Sarah (Blue Bean Café) ·
   12:30 PM Lunch at home · 3:00 PM A walk in the garden (somewhere with park sounds).
8. **Shared shell:** every card frame is built from the `Call Card / Shell` component made in Task 1
   (instance it, fill its content slot). Do not redraw the header/footer.
9. **Ownership:** each task creates frames only inside its own Section on page `06 In-Call` (made by
   Task 1). Never move, edit or delete another task's nodes, the shell component, or any other page.
   Do not create new Figma files. Name layers meaningfully; use auto-layout.
10. Every task finishes by taking a screenshot of each of its frames, checking it against these
    constraints, and writing its report with every frame's node ID.

## Task 1: Page + shared shell (runs first, alone)

On a new page `06 In-Call`:
- Create text styles for the video type scale (Constraint 2), prefixed `Call /`.
- Component set `Call Card / Shell` (720×1280, Paper background) with variant property
  `Footer = None | Status | Test`:
  - Header (top, 48px margins): the Logo instance (`Logo` Shape=Circle, ~72px) + wordmark
    "Calypso⁻¹" in Call Caption Periwinkle Deep. Quiet, never louder than the card content.
  - `Content` slot: an auto-layout frame filling the middle; empty in the component.
  - Footer: `Status` shows a Call Caption line in Ink Soft (sample "Learning faces · 3 samples");
    `Test` adds a small "TEST MODE" pill (Apricot Cream fill, Ink text) — the agent stamps this on test
    calls today. A thin paper-cut wave strip along the very bottom is allowed as decoration.
- Six Sections laid out left-to-right with 160px gaps, each 1600 wide × 1500 tall, titled exactly:
  `Identity`, `Learning`, `Today`, `Memory`, `System`, and put the shell component in its own
  Section `Shell` first. Add a short page-title text above the sections:
  "In-call cards — what Calypso⁻¹ shows as its FaceTime video".
- Report: page ID, shell component-set ID and variant IDs, Content slot node name, each Section ID,
  text style IDs.

## Task 2: Identity cards (parallel)
Section `Identity`, three frames:
1. `Identity — Sarah, photo` — large family photo (Photo component look, ~400×440, Apricot Cream mat,
   white border), name "Sarah" in Call Display, relationship "Your daughter" in Call Headline
   Periwinkle Deep, one memory line "You bake together on Sundays." in Call Body. Small gull (Presenting).
2. `Identity — Tom, no photo` — Avatar Known placeholder instead of a photo; "Tom" / "Your neighbor" /
   "He waves hello from next door."
3. `Identity — long text` — stress case: name "Margaret-Anne" and three long lines; show how text
   wraps and truncates with "…" (title max 2 lines, lines max 3).

## Task 3: Learning cards (parallel)
Section `Learning`, two frames:
1. `Learning — someone new` — Unknown avatar look (Periwinkle Mist, wobbly dashed outline, feather),
   Call Title "Getting to know someone new…", no name ever. Gull Thinking, small.
2. `Learning — asking their name` — the one confirmation question the agent may ask in a group call:
   Call Title "Who's joining us?", Call Body "Say their name and I'll remember them." Same unknown
   avatar. Calm, not a form — no buttons (it's a video feed, nobody can tap it).

## Task 4: Today card (parallel)
Section `Today`, two frames:
1. `Today — Saturday` — Call Caption "Saturday, November 14", Call Title "Your day so far", the four
   moments from Constraint 7 as large rows (time in an Apricot paper tag + title); the garden walk
   uses the uncertain-place wording "somewhere with park sounds". Small boat at the latest moment as in
   the app's sea-path timeline (optional, only if it fits).
2. `Today — quiet day` — gull Resting, Call Title "A quiet day", Call Body "Nothing new yet today.
   Rest days matter too."

## Task 5: Memory / recall cards (parallel)
Section `Memory`, three frames:
1. `Memory — with photo` — Call Caption "A shared memory", photo (gull Holding Photo nearby, small),
   Call Headline "Baking with Sarah", Call Body "Sundays in your kitchen — cinnamon rolls."
2. `Memory — text only` — same without a photo, gull Lantern small.
3. `Memory — not found` — calm miss below the recall threshold: Call Title "I'm not sure about that
   one", Call Body "Let's ask Sarah together." No made-up details.

## Task 6: System / idle cards (parallel)
Section `System`, three frames:
1. `System — Connecting` — Call Title "Connecting…", gull Sailing on paper-cut waves (larger is fine).
2. `System — Listening (idle)` — the card shown most of the call when nothing is happening: calm
   seascape with island home, gull Resting or Lantern, Call Headline "Listening…". It must be restful
   to look at for minutes, not busy.
3. `System — Captions` — the "Let's talk" captions page: Call Caption "Let's talk", up to 7 lines of
   spoken text in Call Body (sample: "Good morning, Mary! Sarah is here with you today. She drove in
   from Austin and brought Biscuit along. Would you like to hear about your morning?"), a page
   indicator "1 of 2" in Call Caption.
