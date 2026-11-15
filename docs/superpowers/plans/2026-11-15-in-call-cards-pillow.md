# In-Call Cards — Pillow re-skin plan

Goal: make `agent/calypso_agent/cards.py` draw the approved paper-cut in-call designs (Figma page
`06 In-Call`, node `98:180`, file `iFIEYln3PGonIVjgQwwLp2`) instead of the dark-navy cards, for the
720×1280 portrait frames the agent sends as its FaceTime video.

Spec: the Figma page above plus `figma-layout-notes.md` in this plan's SDD workspace (the designers'
measured layouts per card and the review's "Notes for the Pillow implementer"). Product rules: `CLAUDE.md`.

## Global Constraints (bind every task)

1. **Shared branch.** Another Claude session is committing puck work on this same branch
   (`fix/puck-who-online`). Touch only the files your task names. Stage by explicit path
   (`git add <path>…`), never `git add -A`/`.`, never `git stash`, `reset`, `checkout --`, `rebase`, or
   amend. If `git commit` fails because of someone else's staged files, commit with
   `git commit -- <your paths>`. Commit messages follow `feat(agent): …` / `chore(agent): …` and end
   with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
2. **Contract is frozen.** Do not change `Card` in `agent/calypso_agent/contract.py` (it mirrors the
   backend's shared models). Card kinds stay `identity | learning | today | memory`.
3. **Palette** (RGB hex): Paper `#FBF6EE` (background), Card `#FFFFFF`, Ink `#1E2A44`, Ink Soft `#4A4759`,
   Periwinkle `#9AA6E8`, Periwinkle Deep `#3E4A9E`, Periwinkle Mist `#C9D0F5`, Apricot `#F4A97A`,
   Apricot Cream `#FAD3B5`.
4. **Type scale** (px size / line height): Display 96/108 Fraunces SemiBold · Title 72/84 Fraunces
   SemiBold · Headline 56/68 Nunito Bold · Body 48/64 Nunito Regular · Body Strong 48/64 Nunito Bold ·
   Caption 40/52 Nunito SemiBold. Nothing smaller than 40px. Margins 48, text width 624.
5. **Shell geometry** (every portrait card): header PNG 720×120 at (0,0) (logo + "Calypso⁻¹" wordmark);
   content area y 120–1216 with 48 side padding and 32 top/bottom padding; optional footer band just
   above y 1216 (status line in Caption Ink Soft, centered; "TEST MODE" pill = Apricot Cream rounded
   pill with Caption Ink text, centered, above the status line); wave strip PNG 720×64 at y 1216.
6. **Safety rules from CLAUDE.md stay true:** never show a guessed name, the unknown-person look stays
   neutral, no photo unless supplied in `images`, truncate rather than overflow.
7. **Truncation** cuts at the last whole word that fits, then adds "…" (U+2026). A single word longer than
   the line still breaks by character (existing behaviour).
8. Run `cd agent && uv run --group dev pytest -m "not live"` before committing; all must pass.

## Task 1: Assets (fonts + illustrations)

Create `agent/calypso_agent/assets/` with:
- `fonts/`: static TTFs `Fraunces-SemiBold.ttf`, `Nunito-Regular.ttf`, `Nunito-SemiBold.ttf`,
  `Nunito-Bold.ttf`, plus `OFL.txt` for each family (`Fraunces-OFL.txt`, `Nunito-OFL.txt`). Source: the
  google/fonts GitHub repo variable fonts (`ofl/fraunces/Fraunces[SOFT,WONK,opsz,wght].ttf`,
  `ofl/nunito/Nunito[wght].ttf`), instanced to static with fontTools
  (`uvx --from fonttools fonttools varLib.instancer … wght=600 opsz=72 SOFT=0 WONK=0` for Fraunces;
  `wght=400|600|700` for Nunito). Do not add fontTools as a project dependency.
  Verify each font renders "Calypso⁻¹ Getting to know someone new…" in Pillow.
- `art/`: transparent PNGs (RGBA, real alpha — verify corners are alpha 0) exported from Figma with
  `get_screenshot` (fileKey `iFIEYln3PGonIVjgQwwLp2`, sessionId
  `e9e61a1a-8595-4879-a049-0ecd204e0c6c`, `contentsOnly: true`), or for gull poses from the cleaned
  PNGs in `~/Downloads/CalypsoDesignHandoff/art/` resized with Pillow (LANCZOS). Target sizes in px:
  `header.png` 720×120 (the shell's Header frame, inside component `98:181`; Paper background is fine
  here since it sits on Paper), `wave-strip.png` 720×64 (shell `Wave Strip`), `scene-waves.png`
  720×82 (the cropped `Scene Waves` in frame `99:578`), `boat.png` 84×72 (`Odyssey / Boat` 11:46),
  `island-home.png` 264×180 (11:74), `avatar-unknown.png` 280×280 (`Unknown Avatar` in frame 99:280),
  `avatar-known.png` 280×280 (Avatar Known 160, 16:65), gulls by pose and width:
  `gull-presenting-120.png`, `gull-thinking-120.png`, `gull-thinking-200.png`,
  `gull-holding-photo-120.png`, `gull-lantern-200.png`, `gull-lantern-300.png`,
  `gull-resting-200.png`, `gull-sailing-400.png` (height by aspect ratio; include the flat shadow
  ellipse if the source has one).
- Make sure the assets ship with the package (check `agent/pyproject.toml` build config; include
  package data if needed) and that `.gitignore` does not exclude them.
- Add `agent/tests/test_card_assets.py`: every file above exists, PNGs are RGBA with the listed width,
  fonts load with `ImageFont.truetype`.
- Commit: `chore(agent): add paper-cut card fonts and art`.

## Task 2: Paper-cut portrait renderer

Rewrite the portrait path of `agent/calypso_agent/cards.py` to match the Figma cards, using Task 1's
assets. Keep the public API: `render(card, images, *, size=(1280,720))`, `render_portrait`,
`caption_cards(text)`, `idle_frame()`, `font(size)`, `wrapped`, `text_block`, `CALL_SIZE`,
`BACKGROUND`, `main()`. Add `stamp_footer(image, *, status=None, test=False)` that draws Constraint 5's
footer onto a rendered portrait frame (used by Task 3).

Card → layout mapping (content stacked and centered vertically in the content area unless noted; gap 32):
- `identity`: supplied photo (first `image_urls` entry present in `images`) in a 400×440 Apricot Cream
  mat (radius 24, padding 16, photo 368×408 radius 16, 4px white inner border) — or
  `avatar-known.png` when none; name in Display Ink (max 2 lines); `lines[0]` = relationship in
  Headline Periwinkle Deep (max 2); remaining lines in Body Ink Soft (max 3 total lines);
  gull-presenting-120 below. All text centered.
- `learning`: `avatar-unknown.png`; title in Title Ink centered (max 3 lines); `lines` in Body Ink Soft
  centered; gull-thinking-120. Never a name.
- `today`: top-aligned. If `lines` is empty → quiet-day layout (gull-resting-200, Title, Body
  "Nothing new yet today. Rest days matter too."). Otherwise title in Title Ink; each line is a moment
  row: white rounded card (radius 24, padding 24/16) with an Apricot time tag (radius 16, Caption Ink)
  when the line starts with a clock time like `9:30 AM`, then the rest in Body Strong Ink (max 2 lines);
  rows stop when the next one would cross y 1184 (drop the rest — never shrink text); boat.png on the
  last shown row's tag line, right-aligned.
- `memory`: photo variant when an image is supplied (Caption "title" Periwinkle Deep, 592×408 photo in
  the mat, Headline `lines[0]`, Body rest, gull-holding-photo-120); text-only variant otherwise (white
  panel radius 32, 4px Periwinkle Mist border, Caption title / Headline line 0 / Body rest, all
  centered; gull-lantern-200 below).
- System states (all `memory` cards with these exact titles — export them as module constants):
  `CONNECTING = "Connecting…"` → gull-sailing-400 over scene-waves, Title below;
  `LISTENING = "Listening…"` → idle scene: Apricot Cream sun ellipse 120×120, scene-waves,
  island-home, gull-lantern-300, Headline "Listening…" below;
  captions (`title` starting with `CAPTIONS = "Let’s talk"`, curly apostrophe) → top-aligned, Caption
  Periwinkle Deep heading, Body Ink lines left-aligned (max 7), page indicator "n of N" in Caption Ink
  Soft centered at the bottom of the content area when the title carries ` · n of N`.
  `caption_cards` produces titles `"Let’s talk"` (single page) or `"Let’s talk · 1 of 2"`.
  `idle_frame()` renders LISTENING.
- Truncation per Constraint 7 for every text block.
- The landscape 1280×720 path (`render` with default size, used by `demo.py`) may keep its current
  layout but must use the new palette and fonts; it must not crash.
- Update existing tests that assert the old dark background (`agent/tests/test_milestone.py`,
  `agent/tests/test_live_stage1.py::test_portrait_captions_page_without_dropping_words`) so they assert
  the new design's invariants instead (size, Paper background, no words lost across caption pages).
  Add tests: whole-word truncation; today rows never cross y 1184; identity without photo never pastes
  a photo; captions page indicator; `stamp_footer` changes only the footer band.
- `python -m calypso_agent.cards --demo` writes portrait PNGs for every card + system state to `out/`.
  Look at them (Read the PNGs) and compare with the Figma screenshots before committing.
- Commit: `feat(agent): paper-cut in-call card renderer`.

## Task 3: Live footer wiring

In `agent/calypso_agent/live_media.py` `run()`, replace the two `draw.text(...)` calls that stamp the
camera status (26px at y 1138) and "TEST MODE" (y 1200) with `stamp_footer(picture,
status=<same shortened status text or None>, test=True)`; drop now-unused imports. Change nothing else
in the file. Make sure the "Connecting…" status card in `live_media.py` uses `cards.CONNECTING`.
Run the agent tests. Commit: `feat(agent): stamp call status in the paper-cut footer`.
