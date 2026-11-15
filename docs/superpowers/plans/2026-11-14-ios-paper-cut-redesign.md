# iOS Paper-cut / Odyssey Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle the SwiftUI app under `ios/` to the Figma "paper-cut / Odyssey" design, keeping all behavior, networking and sync logic unchanged.

**Architecture:** A new `ios/Calypso/DesignSystem/` module (tokens, fonts, mascot, decorations, components) is built first; screens are then restyled one area at a time on top of it. Pure presentation logic (place certainty, day headers, day-switcher labels, hero-photo candidates, onboarding steps) lives in small testable types. A DEBUG-only `-screen <route>` launch argument opens any screen directly so every task can screenshot its work in the simulator.

**Tech Stack:** SwiftUI (iOS 17+), xcodegen, XCTest, Figma MCP (`get_design_context`, `get_screenshot`, `download_assets`), bundled Fraunces + Nunito (SIL OFL).

**Spec:** `~/Downloads/CalypsoDesignHandoff/NEXT-SESSION-PROMPT.md` (binding), with `~/Downloads/CalypsoDesignHandoff/design-plan.md` (palette, type, "not sure" rules, Odyssey motifs, both addenda), `foundations-report.md` (component node IDs, contrast table), `task-7-report.md`, `task-8-report.md`, `fix-wave-report.md` (latest node IDs). Art: `~/Downloads/CalypsoDesignHandoff/art/` (use these PNGs, not Figma exports).

**Figma:** fileKey `iFIEYln3PGonIVjgQwwLp2`. Read-only: never edit the file. Before any Figma call, load the `figma:figma-design-to-code` and `figma:figma-swiftui` skills, call `create_session` once, and pass `clientLanguages: "swift"`, `clientFrameworks: "swiftui"`, `skillNames: "figma-design-to-code"` to `get_design_context`. Reference screenshots of every frame are already saved in `/private/tmp/claude-501/-Users-ericlee-Coding-Personal-HackUTA/e307faa7-fb1d-413f-acf7-3bdf50dfbb27/scratchpad/figma/` (`01-welcome.png` … `31-reset-confirm.png`, `board.png`).

| Frame | Node | SwiftUI |
|---|---|---|
| Foundations (tokens, components, mascot, logos) | `0:1` | `DesignSystem/` |
| Welcome | `20:329` | onboarding `.welcome` |
| Meet your companion | `20:455` | onboarding `.companion` (new) |
| Add to Contacts | `20:938` | `AddContactView` |
| Permissions | `20:1173` | `PermissionsView` |
| You're all set | `39:440` | onboarding `.allSet` (new) |
| Today (scroll) | `20:489` | `TodayView` + `MomentCard` |
| Today — quiet day | `20:1025` | `TodayView` empty state |
| Today — couldn't load | `20:1097` | `TodayView` error state |
| People | `20:212` | `PeopleListView` |
| Person — Sarah | `20:668` | `PersonDetailView` named |
| Person — someone new | `20:852` | `PersonDetailView` `name == nil` |
| Edit name — sheet | `20:969` | `EditNameSheet` |
| Account | `20:386` | `AccountView` |
| Reset — confirm | `20:727` | `ResetConfirmDialog` |

## Global Constraints

- Branch `feat/ios-paper-cut-redesign`. Never commit to `main`; never push or open a PR.
- `backend/calypso/models.py` and `ios/Calypso/Core/Models.swift` are the shared contract: do not change them.
- Do not change behavior of `APIClient`, `PhotoSync`, `VisitSync`, `ContactBuilder`, `Config`, `LocationPermission`, or the permission requests. Keep `@AppStorage("onboarded")`, pull-to-refresh, `.task(id: day)` loading, `updatePerson` + `onUpdate` propagation, and Reset clearing the `UserDefaults` persistent domain.
- After adding/removing files run `cd ios && xcodegen` and commit the regenerated `ios/Calypso.xcodeproj`.
- Commits: `feat(ios): …` / `test(ios): …` / `chore(ios): …`, each ending with the line `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Test command: `xcodebuild test -project ios/Calypso.xcodeproj -scheme Calypso -destination 'platform=iOS Simulator,name=iPhone 17'`. Existing tests must keep passing.
- Colors (exact): Paper `#FBF6EE`, Card `#FFFFFF`, Ink `#1E2A44`, Ink Soft `#4A4759`, Periwinkle `#9AA6E8`, Periwinkle Deep `#3E4A9E`, Periwinkle Mist `#C9D0F5`, Apricot `#F4A97A`, Apricot Cream `#FAD3B5`, Olive `#A99A4C` (decorative only), Terracotta `#C2603F` (decorative only).
- Light-only: `.preferredColorScheme(.light)` at the root. No dark mode.
- Contrast: body text pairs ≥ 7:1. Never body text on Periwinkle; never Ink Soft on Apricot Cream or Periwinkle Mist; never Periwinkle Deep on Periwinkle Mist. Primary buttons: Periwinkle Deep fill, white text. **Nothing is ever red** (errors and reset included).
- Type (all via `Font.custom(_:size:relativeTo:)`): Display Fraunces SemiBold 44/52 `.largeTitle`; Title Fraunces SemiBold 34/42 `.title`; Headline Nunito Bold 28/36 `.title2`; Body Nunito Regular 24/32 `.body`; Body Strong Nunito Bold 24/32 `.body`; Callout Nunito Regular 22/30 `.callout`; Caption Nunito SemiBold 20/26 `.footnote`. Nothing below 20pt at default size.
- Dynamic Type: layouts work at AX1–AX5; horizontal rows stack vertically (`ViewThatFits` or `dynamicTypeSize.isAccessibilitySize`); names never truncate.
- Touch targets ≥ 64pt. Buttons 72pt tall, full width, radius 24, with a press state.
- No gradients, no `.material`/glass, no stacked drop shadows. Texture/wobble only inside illustrations; text, photos, controls stay crisp.
- Mascot: decorative (`accessibilityHidden(true)`) unless meaningful; ≤ 96pt on Today/People/Account and never over photos or names; at most one gull per screen; never animated.
- Motion: subtle springs for card appear and sheet presentation (critically damped, `.spring(response: 0.35, dampingFraction: 1)`); under `accessibilityReduceMotion` use a plain opacity fade.
- "Not sure" copy is exact: unknown person row "Getting to know someone new…" / "Tap to add their name"; chip "Someone new"; detail "Calypso⁻¹ has seen this person but doesn't know their name yet." + "Add their name". Never "Unnamed visitor", never a guessed name. Uncertain place: `placeConfidence < 0.6`, never a pin. Quiet day: "A quiet day" / "Nothing new was recorded. That's okay. Rest days matter." / "Look at another day". Error: "We couldn't load this day right now." / "Try again". People empty: "No people yet. People appear after your first FaceTime with Calypso⁻¹." Use curly apostrophes (’) in visible copy.
- Sensitive photos are never requested or shown (they 404; a failed photo is hidden, never shown as a broken placeholder).
- User-facing name exactly `Calypso⁻¹`.

## Rulings (controller decisions where spec and data disagree)

- **Moment title:** `DayEvent` has no title field; the card's Headline is `event.summary`, and there is no separate Callout summary line. — The contract can't change. — Cost if wrong: cards read slightly differently from Figma.
- **Quiet day in the fake backend:** `seeded_events` returns `[]` for days more than 2 days back (the real `/days/{date}/events` returns an empty list; "A quiet day at home" is the agent's Card wording). — Needed to demo the quiet state. — Cost: none to production.
- **Tab bar:** custom `CalypsoTabBar` over a `TabView` whose system bar is hidden, because the iOS 26+ system tab bar is glass and can't carry the Mist pill. It keeps VoiceOver tab semantics (`.isSelected`, "Tab, N of 3" hint). — Cost: re-test if Apple changes tab-bar APIs.
- **Hero photo caption** and **person-detail family photo** have no data source: show the hero without a caption; omit the person photo. Listed as deferred.
- **Onboarding steps:** 6 steps, every step shows dots and "Step N of 6".
- **Back navigation in People:** keep the system back button (tinted Periwinkle Deep) so swipe-back keeps working; onboarding uses the custom `BackButton`.
- **Hero candidates:** the client can't know which photo is sensitive; it tries `photoIds` in order and shows the first that loads, hiding the hero if none do.

## Review Focus

- A person id in `event.people` that isn't in the people list (or has `name == nil`) must render "Someone new", never an id or blank. — Task 2 test `testChipNameFallsBackToSomeoneNew`.
- `placeConfidence` exactly `0.6` is certain; `0.5999` is uncertain. — Task 2 test `testPlaceThresholdBoundary`.
- Day headers across a month/year boundary and for "yesterday" (1 day ago) must not say "Today". — Task 2 tests `testHeaderYesterday`, `testHeaderAcrossYearBoundary`.
- Every photo of the day failing (sensitive/404) hides the hero; there's no empty frame. — Task 2 test `testHeroCandidatesOrderedAndDeduped` plus Task 4's `HeroPhoto` advancing on failure (verified in simulator with `ph_sensitive`).
- AX5 Dynamic Type on Moment cards and People rows: no truncated names, rows stack. — Verified per screen task with previews at `.accessibility5` and in Task 8 simulator pass.

---

### Task 1: Design system foundations (tokens, fonts, assets, mascot, debug routes)

**Files:**
- Create: `ios/Calypso/DesignSystem/Palette.swift`, `ios/Calypso/DesignSystem/Typography.swift`, `ios/Calypso/DesignSystem/Mascot.swift`, `ios/Calypso/DesignSystem/Decoration.swift`
- Create: `ios/Calypso/Resources/Fonts/` (`Fraunces-SemiBold.ttf`, `Nunito-Regular.ttf`, `Nunito-SemiBold.ttf`, `Nunito-Bold.ttf`, plus `OFL-Fraunces.txt`, `OFL-Nunito.txt`)
- Create: `ios/Calypso/Assets.xcassets/Gull{Wave,Presenting,Peek,Thinking,HoldingPhoto,Resting,Walking,Sailing,Lantern,Celebrating}.imageset`, decoration imagesets (see Step 5)
- Replace: `ios/Calypso/Assets.xcassets/Logo.imageset` (from `art/Calypso Circle Logo.png`), `AppIcon.appiconset` (single 1024 universal from `art/Calypso App Icon.png`; resize to exactly 1024×1024 with `sips` if needed)
- Create: `ios/Calypso/Debug/ScreenRoute.swift`
- Modify: `ios/project.yml` (`UIAppFonts` under `info.properties`), `ios/Calypso/CalypsoApp.swift` (light scheme, debug route hook)
- Test: `ios/CalypsoTests/DesignSystemTests.swift`

**Interfaces:**
- Produces:
  - `extension Color { static let paper, card, ink, inkSoft, periwinkle, periwinkleDeep, periwinkleMist, apricot, apricotCream, olive, terracotta }` (exact hex from Global Constraints).
  - `enum CalypsoTextStyle: CaseIterable { case display, title, headline, body, bodyStrong, callout, caption }` with `var font: Font`, `var size: CGFloat`, `var leading: CGFloat`; `extension View { func calypsoFont(_ style: CalypsoTextStyle) -> some View }` (applies font + line spacing for the leading).
  - `enum MascotPose: String, CaseIterable { case wave, presenting, peek, thinking, holdingPhoto, resting, walking, sailing, lantern, celebrating }` with `var assetName: String` ("GullWave", "GullHoldingPhoto", …); `enum MascotSize { case xl, l, m, s, custom(CGFloat) }` with `var width: CGFloat` (280/200/120/72); `struct Mascot: View { init(pose: MascotPose, size: MascotSize, shadow: Bool = false) }`: aspect-fit, `accessibilityHidden(true)`, optional flat Ink-free ellipse shadow `#D9DAEC` under the feet.
  - `enum Decoration: String { case oliveBranch = "OliveBranch", meander = "MeanderBorder", islandHome = "IslandHome", lighthouse = "Lighthouse", wavesCalm = "WavesCalm", wavesLively = "WavesLively", seascape = "Seascape" }`; `struct DecorationImage: View { init(_ decoration: Decoration) }`, which is resizable, aspect-fit, and `accessibilityHidden(true)`.
  - `enum ScreenRoute { static var current: String? }`: reads `-screen <value>` from `ProcessInfo.processInfo.arguments` in `#if DEBUG` only (nil in Release). `CalypsoApp` consults it: when non-nil it shows `ScreenRoute.view(for:)` instead of the normal root. Later tasks add cases to the `switch` inside `static func view(for route: String) -> AnyView`. This task registers `"design-system"`, which shows a scrolling specimen of colors, the 7 text styles, and all 10 mascot poses.

- [ ] **Step 1: Write failing tests** in `DesignSystemTests.swift`:
  - `testTextStyleSpecs`: assert `(size, leading)` per style equals display (44,52), title (34,42), headline (28,36), body (24,32), bodyStrong (24,32), callout (22,30), caption (20,26), and `CalypsoTextStyle.allCases.allSatisfy { $0.size >= 20 }`.
  - `testFontsRegistered`: `UIFont(name: "Fraunces-SemiBold", size: 20)`, `"Nunito-Regular"`, `"Nunito-SemiBold"`, `"Nunito-Bold"` are all non-nil (use the PostScript names the TTFs actually report; adjust the test strings to match the instanced files).
  - `testMascotAssetsExist`: for every `MascotPose.allCases`, `UIImage(named: pose.assetName, in: Bundle(for: <a class in the app target>) ?? .main, with: nil)` is non-nil; same for every `Decoration` raw value and `"Logo"`.
  - `testMascotSizes`: xl 280, l 200, m 120, s 72, custom(96) 96.
- [ ] **Step 2: Run tests and confirm they fail to compile/fail.**
- [ ] **Step 3: Fonts.** Download the variable TTFs from the google/fonts GitHub repo (`ofl/fraunces/Fraunces[SOFT,WONK,opsz,wght].ttf`, `ofl/nunito/Nunito[wght].ttf`, plus each `OFL.txt`) into a scratch dir, then make static instances with fontTools: `uvx --from fonttools fonttools varLib.instancer <in> wght=600 opsz=72 SOFT=0 WONK=0 -o Fraunces-SemiBold.ttf`, and Nunito at `wght=400/600/700`. Set each instance's name table (family + PostScript name) so `UIFont(name:)` resolves the names in the test. Add `UIAppFonts` (the four file names) to `project.yml` `info.properties`, then `xcodegen` (regenerates Info.plist).
- [ ] **Step 4: Mascot + logo + app icon assets.** Copy each `art/Calypso Gull - <Pose>.png` into `Gull<Pose>.imageset` as a single universal image (Contents.json `"idiom":"universal"`). If a source exceeds ~1200px on its long side, downscale with `sips -Z 1200` to keep the bundle small. Replace Logo and AppIcon as listed. `ContactBuilder` keeps using `UIImage(named: "Logo")`; don't touch it.
- [ ] **Step 5: Decorations from Figma.** Use `download_assets` with `defaultFormat: "pdf"` (fall back to `"svg"`) on Foundations nodes: Olive Branch `13:6`, Meander Border `12:60`, Island Home `11:74`, Lighthouse `11:105`, Waves Calm `12:33`, Waves Lively `12:45`; and for the Welcome seascape, use the detached seascape frame inside Welcome `20:329` (find its id with `get_metadata`; task-8 report names it `37:1730`). Hide nothing; export as-is, but the Welcome gull itself comes from the `GullSailing` PNG, so if the seascape export contains the gull, export the seascape's background children only, or accept it and don't overlay a second gull. Put each in an imageset named as in `Decoration`, with `"preserves-vector-representation": true`.
- [ ] **Step 6: Implement** `Palette.swift`, `Typography.swift`, `Mascot.swift`, `Decoration.swift`, `ScreenRoute.swift` per Interfaces. Add `.preferredColorScheme(.light)` to the `WindowGroup` root and the debug route hook in `CalypsoApp`.
- [ ] **Step 7: Run tests and confirm they pass.** Then build, install, and launch with `xcrun simctl launch booted com.calypso.app -screen design-system` and `xcrun simctl io booted screenshot <scratch>/t1-design-system.png`; check that fonts render as Fraunces/Nunito, not the system font.
- [ ] **Step 8: Commit** `feat(ios): add paper-cut design tokens, fonts, mascot and decoration assets`.

### Task 2: Presentation logic + fake backend quiet day

**Files:**
- Create: `ios/Calypso/Today/DayPresentation.swift`
- Modify: `ios/scripts/fake_backend.py` (`seeded_events`: return `[]` for `day < today - timedelta(days=2)`; update the `p_unknown` comment to say the app shows "Getting to know someone new…")
- Test: `ios/CalypsoTests/DayPresentationTests.swift`

**Interfaces:**
- Produces:
  - `enum PlaceCertainty { static let minimumConfidence = 0.6 /* mirrors PLACE_CONF_MIN in backend/calypso/config.py */; static func isUncertain(_ confidence: Double) -> Bool }`.
  - `struct DayHeader: Equatable { let title: String; let caption: String; static func make(for day: Date, now: Date = Date(), calendar: Calendar = .current) -> DayHeader }`. Same day as `now` gives `("Today", "Saturday, November 14")`. 1 day ago gives `("Friday", "November 13 · Yesterday")`. N ≥ 2 days ago gives `("Wednesday", "November 11 · 3 days ago")`. Use `calendar.locale` for formatting; the weekday is `EEEE`, the dates are templates `EEEEMMMMd` / `MMMMd`.
  - `struct DaySwitcherLabels: Equatable { let previous: String; let next: String; let nextEnabled: Bool; static func make(for day: Date, now: Date = Date(), calendar: Calendar = .current) -> DaySwitcherLabels }`. When the day is today: `("Yesterday", "Tomorrow", false)`. When the day is yesterday: `(<weekday of day−1>, "Today", true)`. Otherwise: `(<weekday of day−1>, <weekday of day+1>, true)`.
  - `enum DayPresentation`:
    - `static func chipName(for personId: String, names: [String: String]) -> String?` returns nil when the person is unknown or unnamed, so `PersonChip` shows "Someone new".
    - `static func heroPhotoCandidates(_ events: [DayEvent]) -> [String]` returns all `photoIds` in event-start order, deduped, keeping first occurrence.
    - `static func accessibilityLabel(for event: DayEvent, names: [String: String], timeZone: TimeZone = .current) -> String` returns `"<h:mm a>, <summary>, at <place>, with <names joined ", ">"`. When uncertain, the place clause is `"place not certain: <place>"`. The "with …" clause is omitted when there are no people, and unknown people read "someone new".
- [ ] **Step 1: Write failing tests** (calendar: `Calendar(identifier: .gregorian)` with `locale = Locale(identifier: "en_US")`, `timeZone = TimeZone(identifier: "America/Chicago")!`; build `DayEvent`s by decoding JSON with `JSONDecoder.calypso`):
  - `testPlaceThresholdBoundary`: `isUncertain(0.42) == true`, `isUncertain(0.5999) == true`, `isUncertain(0.6) == false`, `isUncertain(0.87) == false`.
  - `testHeaderToday`: day = now = 2026-11-14 10:00 → `DayHeader(title: "Today", caption: "Saturday, November 14")`.
  - `testHeaderYesterday`: day 2026-11-13 → `("Friday", "November 13 · Yesterday")`.
  - `testHeaderThreeDaysAgo`: day 2026-11-11 → `("Wednesday", "November 11 · 3 days ago")`.
  - `testHeaderAcrossYearBoundary`: now 2027-01-02, day 2026-12-30 → `("Wednesday", "December 30 · 3 days ago")`.
  - `testSwitcherLabels`: today gives `("Yesterday","Tomorrow",false)`, yesterday (2026-11-13) gives `("Thursday","Today",true)`, and 2026-11-11 gives `("Tuesday","Thursday",true)`.
  - `testChipNameFallsBackToSomeoneNew`: `chipName(for: "p_unknown", names: ["p_sarah":"Sarah"]) == nil`, `chipName(for: "p_sarah", …) == "Sarah"`.
  - `testHeroCandidatesOrderedAndDeduped`: events given out of order (start 11:00 with `["b","c"]`, start 9:00 with `["a","b"]`, one with `[]`) → `["a","b","c"]`; all-empty → `[]`.
  - `testAccessibilityLabelKnownPlace`: 9:30 AM, summary "Grocery shopping with Mom", place "Kroger", conf 0.87, people `["p_mom"]`, names `["p_mom":"Mom"]` → `"9:30 AM, Grocery shopping with Mom, at Kroger, with Mom"`.
  - `testAccessibilityLabelUncertainPlace`: place "Somewhere with park sounds", conf 0.42, people `["p_tom","p_x"]`, names `["p_tom":"Tom"]` → `"3:00 PM, A walk, place not certain: Somewhere with park sounds, with Tom, someone new"`.
- [ ] **Step 2: Run and confirm failure.**
- [ ] **Step 3: Implement** `DayPresentation.swift` per Interfaces. Note that the time formatter must use a fixed `en_US` locale only in tests via parameters; the app uses current.
- [ ] **Step 4: Edit `fake_backend.py`** as listed; run `uv run ios/scripts/fake_backend.py --port 8765 &` then `curl -s -H 'Authorization: Bearer dev-token' localhost:8765/days/<today−5 in yyyy-MM-dd>/events` prints `[]`; then kill it.
- [ ] **Step 5: `xcodegen`, run tests, and confirm they pass.**
- [ ] **Step 6: Commit** `feat(ios): add day presentation logic and quiet-day fake backend`.

### Task 3: Design-system components

**Files:**
- Create in `ios/Calypso/DesignSystem/Components/`: `CalypsoButton.swift`, `BackButton.swift`, `NavHeader.swift`, `DaySwitcher.swift`, `Avatar.swift`, `PersonChip.swift`, `PlaceRow.swift`, `PhotoTile.swift`, `MomentCard.swift`, `CalmMessage.swift`, `CalypsoTabBar.swift`, `Logo.swift`, `PaperCard.swift`, `StepDots.swift`
- Modify: `ios/Calypso/Debug/ScreenRoute.swift` (register `"components"`, which shows every component in each state in a scroll view)

Pull each component's design with `get_design_context` on its Foundations node (`foundations-report.md` lists them: Button `15:95`, Back Button `15:96`, Tab Bar `17:147`, Nav Header `17:148`, Avatar `16:78`, Person Chip `16:92`, Place Row `16:104`, Photo `15:112`, Moment Card `18:225`, Logo `39:384`, Calm Message `18:226`, Icons `15:60`–`15:88`). Map icons to SF Symbols: Today `calendar`, People `person.2`, Account `person`, Chevron `chevron.left`, Pin `mappin.and.ellipse`, Sound wave `waveform`, Feather `leaf`, Photo `photo`. If `get_design_context` returns SF Symbol names, prefer those.

**Interfaces:**
- Consumes: Task 1 tokens, `calypsoFont`, `Mascot`, `DecorationImage`; Task 2 `DaySwitcherLabels`, `PlaceCertainty`, `DayPresentation`.
- Produces:
  - `enum CalypsoButtonKind { case primary, secondary, quiet }`; `struct CalypsoButtonStyle: ButtonStyle { init(_ kind: CalypsoButtonKind) }`. Primary is Periwinkle Deep fill with white Body Strong text. Secondary is a Card fill with a 2pt Ink border and Ink text. Quiet is Periwinkle Deep underlined text, 64pt tall. Primary and Secondary are 72pt tall, full width, radius 24. Pressed state is scale 0.97 plus a slightly darker fill, with no animation under Reduce Motion. Also `struct CalypsoButton: View { init(_ title: String, kind: CalypsoButtonKind = .primary, systemImage: String? = nil, action: @escaping () -> Void) }`.
  - `struct BackButton: View { init(_ label: String = "Back", action: @escaping () -> Void) }`: chevron plus label in Periwinkle Deep, 64pt tall.
  - `struct NavHeader<Accessory: View>: View { init(caption: String, title: String, @ViewBuilder accessory: () -> Accessory) }` plus `NavHeader where Accessory == EmptyView` `init(caption:title:)`. Caption style, then Display title (`.isHeader` trait), with the accessory trailing.
  - `struct DaySwitcher: View { init(labels: DaySwitcherLabels, onPrevious: @escaping () -> Void, onNext: @escaping () -> Void) }` (`DaySwitcherLabels` comes from Task 2). Previous is Secondary with "‹ <label>". When `nextEnabled == false`, Next shows Ink Soft text on Paper with a 2pt dashed Periwinkle `[8,6]` outline, no chevron and no opacity fade, `.disabled(true)`. When enabled, it's Secondary "<label> ›". Use `ViewThatFits` to stack the two at AX sizes.
  - `struct Avatar: View { init(urlString: String?, isKnown: Bool, size: CGFloat) }` for sizes 64 and 160. Known shows the face photo, or an Apricot Cream disc with an Ink Soft silhouette and a white ring. Unknown shows a Periwinkle Mist disc with a dashed Ink Soft outline and the `leaf` glyph.
  - `struct PersonChip: View { init(name: String?) }`: nil shows the "Someone new" dashed Mist chip with the leaf glyph; otherwise an avatar-dot plus name. Height 64.
  - `struct PlaceRow: View { init(place: String, isUncertain: Bool) }`. Known shows a pin plus the place in Body. Uncertain shows a `waveform` glyph and the place text in a dashed Apricot Cream chip, Ink text, wrapping. Accessibility label is "Place not certain: <place lowercased first letter>" when uncertain and "At <place>" otherwise.
  - `enum PhotoTileStyle { case hero, thumb }`; `struct PhotoTile: View { init(url: URL?, style: PhotoTileStyle, onFailure: @escaping () -> Void = {}) }`. Apricot Cream mat, 4pt white border, radius 16. Hero is full width and 220 tall; thumb is 96×96. While loading it shows the Apricot Cream mat with the photo glyph. On failure it calls `onFailure()` and renders `EmptyView`, so there's never a broken placeholder.
  - `struct MomentCard: View { init(event: DayEvent, names: [String: String], photoURL: @escaping (String) -> URL?) }`. Layout: Apricot time tag (Caption, Ink), then Headline `event.summary`, then `PlaceRow(place:isUncertain: PlaceCertainty.isUncertain(event.placeConfidence))`, then one `PersonChip(name: DayPresentation.chipName(for:names:))` per person, then thumbs (`PhotoTile .thumb`; a failed thumb is removed). Container is `PaperCard`. Accessibility: `.accessibilityElement(children: .combine)` with label `DayPresentation.accessibilityLabel(for:names:)` (Task 2).
  - `struct CalmMessage: View { init(pose: MascotPose, title: String, message: String, buttonTitle: String? = nil, action: (() -> Void)? = nil) }`: illustration panel (Mascot M on `wavesCalm`, radius 24, clipped), Title, Body, optional Secondary button.
  - `enum HomeTab: Int, CaseIterable { case today, people, account }` with `title` and `systemImage`; `struct CalypsoTabBar: View { init(selection: Binding<HomeTab>) }`. Card background, 1pt Periwinkle Mist top hairline, Periwinkle Mist pill behind the selected icon only, labels in Caption (20pt). Selected label is Periwinkle Deep on Card; unselected is Ink. Each item is a `Button` with `.accessibilityAddTraits(selected ? [.isSelected] : [])`, label = title, hint "Tab, N of 3". Height ≥ 64.
  - `struct Logo: View { init(size: CGFloat = 112) }`: the circle `Logo` image, decorative unless given a label.
  - `struct PaperCard<Content: View>: View`: padding 20, Card fill, 2pt Periwinkle Mist border, radius 24. Also `extension View { func paperCard() -> some View }`.
  - `struct StepDots: View { init(current: Int, total: Int) }`. Dots are Periwinkle Mist, and the current one is a wider Periwinkle Deep capsule. Caption "Step N of M" is in Ink Soft on Paper. Accessibility label "Step N of M".
- [ ] **Step 1:** Add `#Preview`s for each component, including `.dynamicTypeSize(.accessibility5)` previews for MomentCard, PersonChip, PlaceRow, DaySwitcher.
- [ ] **Step 2:** Implement per Interfaces, matching each Foundations node's design context.
- [ ] **Step 3:** `xcodegen`, run the full test suite (must pass), then launch `-screen components` and take a screenshot. Compare it against the Foundations components (`get_screenshot` on section `19:391`) and fix visible drift.
- [ ] **Step 4: Commit** `feat(ios): add paper-cut UI components`.

### Task 4: Today screen

**Files:**
- Modify: `ios/Calypso/Today/TodayView.swift`
- Delete: `ios/Calypso/Today/EventRow.swift` (replaced by `MomentCard`), and `ios/Calypso/Today/.gitkeep`
- Create: `ios/Calypso/Today/HeroPhoto.swift`, `ios/Calypso/Today/SeaPathRail.swift`
- Modify: `ios/Calypso/Debug/ScreenRoute.swift` (register `"today"`, `"today-quiet"` (day = now − 5 days), `"today-error"` (a client pointed at an unreachable URL `http://127.0.0.1:9`))

Design: `get_design_context` on `20:489`, `20:1025`, `20:1097` (screenshots `10-today.png`, `11-today-quiet.png`, `12-today-error.png`).

**Interfaces:**
- Consumes: `DayHeader`, `DaySwitcherLabels`, `DayPresentation`, `PlaceCertainty` (Task 2); `NavHeader`, `DaySwitcher`, `MomentCard`, `PhotoTile`, `CalmMessage`, `CalypsoButton`, `Mascot`, `DecorationImage` (Tasks 1 and 3).
- Produces: `TodayView(client: APIClient?, initialDay: Date = Date())` (the `initialDay` param exists for debug routes).
- [ ] **Step 1: Restructure state.** Replace `error: String?` with `enum LoadState { case loading, loaded, failed }`. Keep the `load()` body's networking, names building, sorting, and cancellation handling exactly; only the assignments change (`.failed` instead of the error string). `client == nil` maps to `.failed`.
- [ ] **Step 2: Layout.** Use a `ScrollView` on `Color.paper` (ignores safe area), with `.refreshable` and `.task(id: day)` kept. From the top:
  - `NavHeader(caption: header.caption, title: header.title)` with the `Mascot(.peek, .s)` accessory, only on the loaded non-empty state.
  - `DaySwitcher`. Previous goes to `day − 1`. Next goes to `day + 1`, capped at today.
  - A Quiet "Pick a day" button that opens a `.sheet` with a graphical `DatePicker(in: ...Date())` and a Primary "Done".
  - `HeroPhoto`.
  - "Your day" in Headline.
  - The moments, as `SeaPathRail` + `MomentCard` rows.
  - The end note "That’s your day so far." in Callout, Ink Soft.
- [ ] **Step 3: `HeroPhoto(candidates: [String], photoURL: (String) -> URL?)`.** Holds `@State index`. Renders `PhotoTile(.hero)` for `candidates[index]`, and `onFailure` advances the index. When `candidates` is empty or exhausted it renders nothing. Reset the index when `candidates` changes.
- [ ] **Step 4: `SeaPathRail`.** A decorative leading column (48pt wide) with a dotted Periwinkle line, an Apricot dot aligned with each card's time tag, and small wave marks. `Mascot(.walking, .custom(52))` sits at the last moment only when the day is today; otherwise no gull. It's `accessibilityHidden(true)`. Under AX sizes, drop the rail and let cards fill the width. Only one gull per screen: when the walking gull is shown, hide the header Peek.
- [ ] **Step 5: States.**
  - loading: the existing content, or a calm `ProgressView` tinted Periwinkle Deep.
  - loaded + empty: header (no mascot), switcher, then `CalmMessage(pose: .resting, title: "A quiet day", message: "Nothing new was recorded. That’s okay. Rest days matter.", buttonTitle: "Look at another day") { day = day − 1 }`.
  - failed: header, switcher, `CalmMessage(pose: .thinking, title: "We couldn’t load this day right now.", message: "", buttonTitle: "Try again") { Task { await load() } }`, plus a Quiet "Look at another day". Hide the body text when the message is empty.
  - Cards appear with the spring from Global Constraints, or opacity only under Reduce Motion.
- [ ] **Step 6:** Delete `EventRow.swift`, run `xcodegen`, run tests (pass). Run the fake backend (`uv run ios/scripts/fake_backend.py`), set `ios/Secrets.xcconfig` to `API_BASE_URL = http:/$()/127.0.0.1:8000` and `API_TOKEN = dev-token` (this file is git-ignored; back up the existing one first and restore it at the end), then build. Screenshot `-screen today` (scroll with multiple captures if needed), `today-quiet`, and `today-error`, and compare each with the Figma PNGs. Also check that `ph_sensitive` never appears and the "Somewhere with park sounds" card has no pin. Fix drift.
- [ ] **Step 7: Commit** `feat(ios): restyle Today with moment cards and calm states`.

### Task 5: People list, person detail, edit-name sheet

**Files:**
- Modify: `ios/Calypso/People/PeopleListView.swift`, `ios/Calypso/People/PersonDetailView.swift`
- Create: `ios/Calypso/People/EditNameSheet.swift`
- Delete: `ios/Calypso/People/.gitkeep`; remove `FaceView` (replaced by `Avatar`), after confirming with grep that nothing else uses it
- Modify: `ios/Calypso/Debug/ScreenRoute.swift` (register `"people"`, `"person-p_sarah"`, `"person-p_unknown"`, `"edit-name-p_unknown"`)

Design: `20:212`, `20:668`, `20:852`, `20:969` (screenshots `20-people.png` … `23-edit-name-sheet.png`).

**Interfaces:**
- Consumes: `NavHeader`, `Avatar`, `PaperCard`, `CalypsoButton`, `CalmMessage`, `Mascot`, `DecorationImage(.oliveBranch/.meander)`.
- Produces: `struct EditNameSheet: View { init(initialName: String, onSave: @escaping (String) -> Void, onCancel: @escaping () -> Void) }`; `PersonDetailView(client:person:onUpdate:startEditing: Bool = false)` (the `startEditing` param serves the debug route).
- [ ] **Step 1: People list.** Use a `ScrollView` + `LazyVStack` inside the existing `NavigationStack` (nav bar hidden at root). It contains:
  - `NavHeader(caption: "The people who love you.", title: "People")` with the olive-branch accessory, then the meander trim.
  - Rows as `NavigationLink`s, Card, ≥ 104pt tall. Each row has `Avatar` 64, then a Headline name and a Callout relationship (capitalize the first letter only: "Mother"), then a chevron.
  - The unknown row (`name == nil`) shows the Unknown avatar, "Getting to know someone new…" in Headline and "Tap to add their name" in Callout.
  - Filter out `isPatient` people.
  - Empty state: `CalmMessage(pose: .peek, title: "No people yet", message: "People appear after your first FaceTime with Calypso⁻¹.")`.
  - Load error: `CalmMessage(pose: .thinking, title: "We couldn’t load people right now.", message: "", buttonTitle: "Try again")`.
  - At AX sizes the row stacks the avatar above the text.
  - Keep `load()`, `.refreshable`, `.task`, and the `onUpdate` index replacement exactly.
- [ ] **Step 2: Person detail (named).** Use a `ScrollView` on Paper, keeping the system back button tinted `.periwinkleDeep` (`.tint` on the stack). From the top:
  - `Avatar` 160, then the name in Display and the relationship in Callout, Ink Soft.
  - A "Things to remember" `PaperCard` with Apricot bullet dots, using `person.facts`; hide it when there are none.
  - "Recent moments" in Headline, with each memory string in its own `PaperCard` (Body); when there are none, a Callout "No moments yet. They’ll appear after your next visit together."
  - A Secondary "Edit name" button.
  - Errors show calm Ink Soft text, never red.
- [ ] **Step 3: Person detail (unknown, `name == nil`).**
  - Unknown `Avatar` 160, then Title "Getting to know someone new…", then Body "Calypso⁻¹ has seen this person but doesn’t know their name yet.", then Primary "Add their name".
  - When there are no memories, a small calm block with `Mascot(.thinking, .s)` and "No moments yet. They’ll appear after your next visit together."
  - The nav title is never "Unnamed visitor"; use an empty inline title.
- [ ] **Step 4: Edit name sheet.** Replace the `.alert` with `.sheet(isPresented: $editing)` presenting `EditNameSheet` (`.presentationDetents([.medium, .large])`, Paper background).
  - Contents: Title "What’s their name?", a 72pt-tall `TextField` (Body, Card fill, 2pt Periwinkle Mist border, radius 24, auto-focused), Primary "Save" (disabled while the name is blank), Quiet "Cancel".
  - Save calls the existing `save()` path (`updatePerson` + `onUpdate`) with the trimmed name, then dismisses.
- [ ] **Step 5:** `xcodegen`, tests pass, then run against the fake backend and screenshot the four routes. Compare with Figma and fix drift.
- [ ] **Step 6: Commit** `feat(ios): restyle People, person detail and edit-name sheet`.

### Task 6: Home tab bar + Account + reset confirm

**Files:**
- Modify: `ios/Calypso/CalypsoApp.swift` (`HomeView` uses `CalypsoTabBar`), `ios/Calypso/Account/AccountView.swift`
- Create: `ios/Calypso/Account/ResetConfirmDialog.swift`
- Modify: `ios/Calypso/Debug/ScreenRoute.swift` (register `"home"`, `"account"`, `"reset"`)

Design: `20:386`, `20:727`, Tab Bar `17:147` (screenshots `30-account.png`, `31-reset-confirm.png`).

**Interfaces:**
- Consumes: `CalypsoTabBar`, `HomeTab`, `NavHeader`, `PaperCard`, `CalypsoButton`, `Logo`, `Mascot(.lantern)`, `DecorationImage(.lighthouse)`.
- Produces: `struct ResetConfirmDialog: View { init(onKeep: @escaping () -> Void, onReset: @escaping () -> Void) }`; `AccountView(confirmingReset: Bool = false)` (the debug route opens with the dialog shown).
- [ ] **Step 1: HomeView.** `@State var tab: HomeTab = .today`; a `TabView(selection:)` holding the three tabs with `.toolbar(.hidden, for: .tabBar)`, plus `.safeAreaInset(edge: .bottom) { CalypsoTabBar(selection: $tab) }`. Keep the `scenePhase` `PhotoSync` hook exactly.
- [ ] **Step 2: Account.** A `ScrollView` on Paper containing, from the top:
  - `NavHeader(caption: "Calypso⁻¹", title: "Account")`.
  - A hero panel (Periwinkle Mist, radius 24) with `Logo(size: 76)`, `Mascot(.lantern, .custom(96))` and the lighthouse.
  - A Connection `PaperCard`: Headline "Connection"; Callout "Server" over the Body Strong value (`Config.apiBaseURL?.host() ?? "Not set"`); Callout "Calypso⁻¹ phone" over the Body Strong value (`Config.chertPhone`, or "Not set").
  - Secondary "Run setup again" (sets `onboarded = false`).
  - Secondary "Reset this phone" with an Apricot `exclamationmark.triangle.fill` glyph.
  - Callout footer "This clears this phone’s sync history and pending visits, then starts setup again. Nothing on the server is deleted."
- [ ] **Step 3: Reset confirm.** Replace `.confirmationDialog` with an overlay: an Ink 50% scrim plus a centered `PaperCard` containing:
  - Title "Reset this phone?"
  - Body "This clears this phone’s sync history and pending visits, then starts setup again. Nothing on the server is deleted."
  - Primary "Keep everything" (on top) and Secondary "Reset this phone" (below).

  The dialog has `.accessibilityAddTraits(.isModal)`, and a tap on the scrim keeps everything. "Reset this phone" calls the existing `reset()` unchanged. Present it with the spring and a scale-from-0.96 transition, or opacity only under Reduce Motion.
- [ ] **Step 4:** `xcodegen`, tests pass, then screenshot `account`, `reset`, `home` and compare. In the Accessibility Inspector or simulator VoiceOver, check that the tab items announce selected and "Tab, N of 3".
- [ ] **Step 5: Commit** `feat(ios): restyle Account, reset dialog and tab bar`.

### Task 7: Onboarding flow

**Files:**
- Modify: `ios/Calypso/Onboarding/OnboardingView.swift`, `AddContactView.swift`, `GroupCallHowToView.swift`, `PermissionsView.swift` (view only; `LocationPermission` unchanged)
- Create: `ios/Calypso/Onboarding/OnboardingStep.swift`, `WelcomeView.swift`, `MeetCompanionView.swift`, `AllSetView.swift`, `OnboardingScaffold.swift`
- Modify: `ios/Calypso/Debug/ScreenRoute.swift` (register `"onboarding-<rawValue>"` for each step)
- Test: `ios/CalypsoTests/OnboardingStepTests.swift`

Design: `20:329`, `20:455`, `20:938`, `20:1173`, `39:440` (screenshots `01-welcome.png` … `05-all-set.png`). Group FaceTime has no frame: style it like Permissions.

**Interfaces:**
- Produces: `enum OnboardingStep: Int, CaseIterable { case welcome, companion, addContact, groupCall, permissions, allSet }` with `static var total: Int` (= `allCases.count`), `var number: Int` (rawValue + 1), `var next: OnboardingStep?`, `var previous: OnboardingStep?`. `OnboardingScaffold<Content>(step: OnboardingStep, onBack: (() -> Void)?, @ViewBuilder content:)` places the optional `BackButton` at the top and `StepDots(current: step.number, total: OnboardingStep.total)` at the bottom.
- [ ] **Step 1: Write failing tests:** `testStepOrder` (allCases == [.welcome, .companion, .addContact, .groupCall, .permissions, .allSet]), `testTotalIsSix`, `testNumbers` (welcome 1, groupCall 4, permissions 5, allSet 6), `testNextPrevious` (welcome.previous nil, allSet.next nil, addContact.next == .groupCall).
- [ ] **Step 2: Run, confirm failure; implement `OnboardingStep`; tests pass.**
- [ ] **Step 3: Screens** (copy from Figma; all text in the design system styles):
  - **Welcome:** the `seascape` decoration across the top ~45% with `Mascot(.sailing, .l)` and `Logo(size: 112)` at the top right. Display "Welcome to Calypso⁻¹", Body "Every journey leads home. Let’s bring you home to your memories.", Primary "Get started".
  - **Meet your companion:** Back. `Mascot(.presenting, .l, shadow: true)` on a rock by the calm waves, with the olive branch. Title "Hi, I’m your Calypso⁻¹ gull", Body "I’ll help you remember your day and the people you love. You can FaceTime me anytime.", Primary "Next".
  - **Add to Contacts:** Back. Small `Mascot(.wave, .m)`. Title "Add Calypso⁻¹ to your contacts", Body "Then you can FaceTime Calypso⁻¹ just like family.", Primary "Add to Contacts" (keep the existing `NewContactSheet` flow and the disabled-when-`CHERT_PHONE`-empty rule with its Caption hint), Quiet "Skip for now" (the old "Continue").
  - **Group FaceTime:** Back. `Mascot(.presenting, .s)`. Title "Start a group FaceTime". Three numbered step cards (`PaperCard`: Apricot Cream number disc with Ink numeral, then a Headline step text) using the existing three steps' text and SF Symbols. Callout "Or text Calypso⁻¹: “call Mom with me”". Primary "Next".
  - **Permissions:** Back, `Mascot(.holdingPhoto, .s)`, Title "Last step", Body "Photos and places help Calypso⁻¹ tell you about your day."
    - Two `PaperCard`s:
      - Photos: icon disc, Headline, Callout "Show family photos in your day."
      - Location: icon disc, Headline, Callout "Know where your day happened."
    - Each card has a Secondary "Allow" that runs the existing request.
    - After the request returns granted, the card shows a Periwinkle Mist pill with a `checkmark.circle.fill` and "Allowed" in Ink. Read `PHPhotoLibrary.authorizationStatus(for: .readWrite)` and `CLLocationManager().authorizationStatus` on appear and after each request; the authorization calls themselves don't change.
    - Primary "Done" advances to All set.
  - **You’re all set:** `seascape` with `Mascot(.celebrating, .xl)`. Title "You’re all set", Body (pull it from `get_design_context` on `39:440`), Primary "Open Today" sets `onboarded = true`.
  - Step transitions: push-style move+opacity spring, opacity only under Reduce Motion.
- [ ] **Step 4:** `xcodegen`, tests pass, then screenshot each `onboarding-*` route and compare. Fix drift.
- [ ] **Step 5: Commit** `feat(ios): restyle onboarding with companion, group FaceTime and all-set steps`.

### Task 8: Accessibility + simulator verification pass, deferred notes

**Files:**
- Modify: any view needing fixes found here
- Modify: `docs/tasks/eric-ios.md` (append a "Paper-cut redesign — deferred" section)
- Output: screenshots in `/private/tmp/claude-501/-Users-ericlee-Coding-Personal-HackUTA/e307faa7-fb1d-413f-acf7-3bdf50dfbb27/scratchpad/sim/`

- [ ] **Step 1:** Full test suite passes.
- [ ] **Step 2:** With the fake backend running, screenshot every route at default size: all onboarding steps, `home`, `today` (top + scrolled), `today-quiet`, `today-error`, `people`, `person-p_sarah`, `person-p_unknown`, `edit-name-p_unknown`, `account`, `reset`. Name them `<route>.png`. Then take Dynamic Type screenshots of `today`, `people` and `person-p_sarah` at `xxxLarge` and `accessibility-extra-extra-extra-large` (`xcrun simctl ui booted content_size <size>`), named `<route>-<size>.png`. Reset to `large` afterwards.
- [ ] **Step 3:** Compare each one against its Figma PNG in the scratchpad `figma/` folder. Fix visible drift and any truncation or overlap at AX sizes, then re-screenshot what changed.
- [ ] **Step 4:** Audit contrast pairs and touch targets by code read: grep for `.red`, `Color.red`, `role: .destructive`, `.material`, `LinearGradient`, `.shadow(`, `"Unnamed visitor"`, and font sizes below 20. All must be absent, except `.shadow` used only for the mascot ellipse.
- [ ] **Step 5:** Append deferred items to `docs/tasks/eric-ios.md`:
  - The hero caption and the person-detail family photo have no data source.
  - The app icon text reads "^-1"; a corrected icon is coming.
  - Any drift that can't be matched, with the reason.
  - Dark mode is not designed.
- [ ] **Step 6:** Restore the original `ios/Secrets.xcconfig` from its backup. Commit `chore(ios): accessibility pass and deferred redesign notes`.
