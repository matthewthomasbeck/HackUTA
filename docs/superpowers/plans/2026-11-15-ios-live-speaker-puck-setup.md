# iOS: live "talking with" card + puck setup steps

**Goal.** (1) On Today, replace the "Family photo" hero with a live card showing who the patient is talking to right
now, pushed from the puck over Bluetooth LE. A recognized person opens their People profile when tapped. Someone
unrecognized opens a calm "someone new" sheet. (2) Add two onboarding steps: **Connect your puck** (BLE pairing) and
**Teach it your voice**, where the patient reads sentences that the **puck's** mic records. The phone mic is never used.

**Scope.** iOS only. Bluetooth is the only data source for the card (no backend `/stream` for now). Matt's puck side
(`puck/src/phone_link.cpp`) is still a stub, so the app ships a `FakePuckLink` and the BLE contract is written down
for Matt in `docs/puck-phone-ble.md`.

**Spec.** No separate spec. The user approved going straight to building ("just dive in"). This plan is the
authority, along with `CLAUDE.md`.

## Figma (designed first; match these)

File `iFIEYln3PGonIVjgQwwLp2`. Read a frame with the Figma MCP `get_screenshot`/`get_design_context` (nodeId below).

- Page **02 Today**:
  - Component set **Talking With** `81:425`. Variants: Person `81:387`, Someone New `81:399`, Quiet `81:410`,
    Not Connected `81:419`. Each is 345 wide, min height 180, radius 16, padding 20, gap 16, and laid out as a row:
    leading visual, a text column, then a chevron.
  - Today with the live card: `81:427`. The "Someone new" sheet: `81:502`.
- Page **01 Onboarding** (row at y=980):
  - Connect your puck, found state `81:943`; connected state `81:1008`.
  - Teach your voice, listening state `81:1152`; saved state `81:1202`. Step labels read "Step 6 of 9" / "Step 7 of 9".

The design overrides earlier wording in this plan where they differ:
- **Person card:** `apricotCream` fill, 4pt white stroke. Avatar about 104pt. A 12pt terracotta live dot + Caption
  "Talking with". Name in Title (Fraunces 34). Callout "your daughter" in inkSoft. Chevron.
- **Someone New card:** `periwinkleMist` fill. A 104pt white disc holding the 48pt sound-wave glyph. Live dot +
  "Talking with". Headline "Someone new". Callout "Getting to know them…". Chevron.
- **Quiet card:** `card` (white) fill. A 104pt `apricotCream` disc with `Mascot(.resting, .s)`. Caption "Right now",
  Headline "It's quiet", Callout "I'll show who you're talking with." No live dot, no chevron.
- **Not Connected card:** `paper` fill, a dashed 2.5pt periwinkle border (dash 8/6) like the disabled day-switcher
  button. An 88pt `periwinkleMist` disc with the sound-wave glyph at 60% opacity. Caption "Your puck", Headline "Not
  connected", Callout "Keep your puck close to your phone."
- **Someone-new sheet:** paper sheet with a grabber, `Mascot(.thinking, .m)`, Title "Someone new", the Body text from
  Task 3 and a Primary "Okay".
- **Connect your puck:**
  - Layout: the PermissionsView layout with `Mascot(.presenting, .s)` at the top right. The status card reuses the
    PermissionCard look: a 64pt apricotCream disc with the sound-wave glyph, Headline "Calypso Puck" and a Callout.
  - Found state: Callout "Found nearby", Secondary "Connect" inside the card, Quiet "Skip for now" at the bottom.
  - Connected state: Callout "Ready. It will listen for you.", the "Connected" check pill (same as "Allowed"),
    Primary "Continue".
  - Other states use the same card with a spinner or button per Task 4.
- **Teach your voice:**
  - Layout: `Mascot(.wave, .s)` top right (`.celebrating` once saved).
  - Sentence card: Caption "Sentence 2 of 5", the sentence in Title font wrapped in curly quotes, a 5-segment
    progress bar (done = periwinkleDeep, current = periwinkle, todo = periwinkleMist, 8pt tall, radius 4, gap 8),
    then the status pill. While recording, the pill shows the sound-wave glyph + "Listening…".
  - Bottom while reading: Quiet "Skip for now".
  - Saved state: the card shows the disc + "5 of 5 sentences" / "Your voice is saved on your puck." + a "Voice
    saved" check pill. The body copy becomes "Calypso⁻¹ can now tell your voice apart from family and friends."
    Primary "Continue".

## Global constraints

- SwiftUI, iOS 17+. Match the surrounding code: paper-cut design system (`Color.paper/ink/inkSoft/periwinkleDeep/
  periwinkleMist/apricotCream/card`, `.calypsoFont(...)`, `PaperCard`, `CalypsoButton(kind: .primary/.secondary/.quiet)`,
  `Mascot(pose:size:)`, `Avatar(urlString:isKnown:size:)`, `OnboardingScaffold`, `OnboardingHeading`). Doc comments
  should have the same density as the neighbouring files.
- **Never show the wrong person.** Only `status == identified` with a non-empty name shows a name. `uncertain` and
  `unknown` render the same neutral "Getting to know someone new…" wording, even if the puck sent a candidate name.
- The patient is never the subject of the card. Drop any message whose `person_id` matches a patient (`isPatient`)
  or equals the literal `"patient"`.
- Don't touch `Calypso/Core/Models.swift`, the shared contract. New types live in `Calypso/Puck/`.
- Swappable provider rule: `PuckLink` protocol with `BLEPuckLink` (CoreBluetooth) and `FakePuckLink`. Fake is used
  on the simulator and whenever the launch argument `-fakePuck` is present.
- After adding files, run `xcodegen` in `ios/` and commit the regenerated `ios/Calypso.xcodeproj`.
- Respect Reduce Motion (crossfade instead of movement) and Dynamic Type (AX sizes stack vertically). Give every
  interactive element an accessibility label.
- Tests: `xcodebuild test -project ios/Calypso.xcodeproj -scheme Calypso -destination 'platform=iOS Simulator,name=iPhone 17'`.
  Put pure logic (decoding, reducers, presentation) under unit tests. Views get `#Preview`s and DEBUG `-screen` routes.
- Commit on the current branch (`docs/judge-demo-pitch`). Messages look like `feat(ios): …` and end with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## BLE contract (the source of truth for Tasks 1, 2, 5; copy into `docs/puck-phone-ble.md`)

The puck is the **peripheral** and advertises service `C41A0001-5E7A-4C1B-9A3D-CA1F5050C0DE`, local name prefix
`Calypso`. Characteristics:

| Name | UUID | Props | Payload (UTF-8 JSON, one object per write/notify) |
|---|---|---|---|
| `who` | `C41A0002-5E7A-4C1B-9A3D-CA1F5050C0DE` | notify | `{"status":"identified"\|"uncertain"\|"unknown","person_id":"p_sarah","display_name":"Sarah","relationship":"daughter","score":0.72}` (mirrors puck `WhoIsTalking`; empty strings allowed) |
| `control` | `C41A0003-5E7A-4C1B-9A3D-CA1F5050C0DE` | write | `{"cmd":"enroll_start","speaker":"patient","index":0,"text":"…"}`, `{"cmd":"enroll_finish","speaker":"patient","count":5}`, `{"cmd":"enroll_cancel","speaker":"patient"}` |
| `events` | `C41A0004-5E7A-4C1B-9A3D-CA1F5050C0DE` | notify | `{"event":"enroll_recording","index":0}`, `{"event":"enroll_saved","index":0}`, `{"event":"enroll_failed","index":0,"reason":"too_quiet"}`, `{"event":"enroll_done","speaker":"patient"}` |

The puck sends `who` only when someone is speaking (roughly every `OFFLINE_SEGMENT_MS`). The phone treats the
speaker as gone after **20 s** with no `who` message. On `enroll_start` the puck records one clip, ending on silence
or after a cap, and saves it under `gallery/patient/`. The phone gives up on a clip after **15 s** without
`enroll_saved`/`enroll_failed`.

---

## Task 1: Puck core types, fake link, contract doc

**Files:** create `ios/Calypso/Puck/PuckMessages.swift`, `ios/Calypso/Puck/PuckLink.swift`,
`ios/Calypso/Puck/FakePuckLink.swift`, `ios/CalypsoTests/PuckMessagesTests.swift`, `ios/CalypsoTests/FakePuckLinkTests.swift`,
`docs/puck-phone-ble.md`.

1. `PuckMessages.swift`:
   - `enum PuckUUID` holding the four `CBUUID` constants from the contract (`import CoreBluetooth`).
   - `struct WhoIsTalking: Decodable, Equatable` with `enum Status: String, Decodable { case identified, uncertain, unknown }`,
     `status`, `personId: String?`, `displayName: String?`, `relationship: String?`, `score: Double?`. Decode
     snake_case keys. Empty strings become nil (reuse `PersonName.display` for the name). An unknown status string
     decodes as `.unknown`.
   - `enum PuckCommand: Encodable, Equatable { case enrollStart(index: Int, text: String), enrollFinish(count: Int), enrollCancel }`,
     encoding exactly the contract JSON with `"speaker":"patient"`.
   - `enum PuckEvent: Decodable, Equatable { case recording(index: Int), saved(index: Int), failed(index: Int, reason: String?), done }`.
     Decoding an unrecognized event throws.
2. `PuckLink.swift`:
   - `enum PuckConnectionState: Equatable { case idle, bluetoothOff, unauthorized, scanning, found(name: String), connecting, connected(name: String), failed(String) }`.
   - `@MainActor protocol PuckLink: AnyObject` with `var state: PuckConnectionState { get }`,
     `var onStateChange: ((PuckConnectionState) -> Void)? { get set }`, `var onWho: ((WhoIsTalking) -> Void)? { get set }`,
     `var onEvent: ((PuckEvent) -> Void)? { get set }`, `func startScanning()`, `func connect()` (connects to the
     found puck), `func reconnectRemembered()`, `func send(_ command: PuckCommand)`, `func disconnect()`.
   - `@MainActor final class PuckConnection: ObservableObject` wraps one `PuckLink`. It exposes `@Published state`,
     `@Published speaker: WhoIsTalking?` (cleared 20 s after the last `who`, timer injectable for tests),
     `@Published lastEvent: PuckEvent?` and `var isConnected: Bool`, and forwards `startScanning/connect/reconnectRemembered/send`.
     It also has `static func make(arguments: [String] = ProcessInfo.processInfo.arguments) -> PuckConnection`, which
     picks Fake on `targetEnvironment(simulator)` or `-fakePuck` and `BLEPuckLink` otherwise. Until Task 2 lands,
     make it return Fake with a `// Task 2:` comment.
3. `FakePuckLink.swift`: scripted, timer-driven (injectable delay scale so tests run fast). `startScanning` goes
   scanning → `found("Calypso Puck")` after ~1.5 s. `connect` goes connecting → `connected("Calypso Puck")` after
   ~1 s. `reconnectRemembered` connects directly if `UserDefaults` `puckPaired` is true (set it on connect).
   `send(.enrollStart(i, _))` emits `.recording(i)` at once and `.saved(i)` after ~3 s. `enrollFinish` emits `.done`.
   Once connected, it runs a speaker loop: Sarah identified (`p_sarah`, "Sarah", "daughter", 0.81) every 4 s for
   16 s, then silence for 25 s, then `unknown` every 4 s for 12 s, then repeats. Launch argument `-fakeSpeaker
   sarah|unknown|none` pins the loop to one state for screenshots.
4. Tests:
   - Decoding: identified, uncertain, empty strings → nil, unknown status string.
   - Command encoding JSON equality, compared as dictionaries.
   - Event decoding, including failed with and without reason, and the unrecognized-event error.
   - `PuckConnection` speaker expiry with an injected clock/timer.
   - Fake scan→found→connect transitions with a tiny delay scale.
5. `docs/puck-phone-ble.md`: the contract section above, plus a short "what the phone does" paragraph for Matt.
6. `xcodegen`, run tests, commit `feat(ios): puck link types, fake puck, BLE contract`.

## Task 2: CoreBluetooth link and app wiring

**Files:** create `ios/Calypso/Puck/BLEPuckLink.swift`. Modify `ios/project.yml` (add
`NSBluetoothAlwaysUsageDescription: "Calypso⁻¹ connects to your puck to show who you're talking with."`),
`ios/Calypso/Puck/PuckLink.swift` (`make` now returns BLE on device) and `ios/Calypso/CalypsoApp.swift`.

1. `BLEPuckLink: NSObject, PuckLink, CBCentralManagerDelegate, CBPeripheralDelegate`:
   - Create the `CBCentralManager` lazily on first `startScanning`/`reconnectRemembered`, so the Bluetooth prompt
     only appears on the Connect step.
   - Map manager state to `.bluetoothOff` / `.unauthorized`.
   - Scan for the service UUID. The first discovery → `.found(name)`. `connect()` → `.connecting`, then discover the
     three characteristics, subscribe to `who` and `events`, and go `.connected(name)`.
   - Save `peripheral.identifier.uuidString` in `UserDefaults` key `puckPeripheralID`. `reconnectRemembered`
     retrieves the saved peripheral with `retrievePeripherals(withIdentifiers:)` and connects.
   - On unexpected disconnect, go `.idle` and call `connect` again (CoreBluetooth pending connects don't time out).
   - Decode notifications with `JSONDecoder` into `WhoIsTalking`/`PuckEvent` and drop bad payloads silently.
     `send` writes JSON to `control` `.withResponse`.
   - Hop delegate callbacks onto the main actor.
2. `CalypsoApp`: own one `@StateObject var puck = PuckConnection.make()`, inject it with `.environmentObject(puck)`
   into onboarding, home and DEBUG routes, and call `puck.reconnectRemembered()` when the app is onboarded and the
   scene becomes active.
3. Build for the simulator, run the tests, `xcodegen`, commit `feat(ios): CoreBluetooth puck link`.

## Task 3: Today "talking with" card

**Files:** create `ios/Calypso/Today/TalkingTo.swift` (presentation + view) and `ios/CalypsoTests/TalkingToTests.swift`.
Modify `ios/Calypso/Today/TodayView.swift` and `ios/Calypso/Debug/ScreenRoute.swift`. Delete
`FamilyPhotoPlaceholder` (`HeroPhoto.swift`) if nothing else uses it.

1. `enum TalkingToPresentation: Equatable` built by
   `static func make(state: PuckConnectionState, speaker: WhoIsTalking?, people: [Person]) -> TalkingToPresentation`:
   - `.person(Person)`: identified and the name is non-empty, and the person is not the patient. Use the matching
     `Person` from `people` by id when there is one (so the photo shows). Otherwise use
     `Person(id: personId ?? "puck_<name>", name:, relationship:)`.
   - `.someoneNew`: uncertain, unknown, or identified without a name.
   - `.quiet`: connected and no speaker, or the speaker was the patient.
   - `.notConnected`: any other state.
   - Each case has a `caption` / `title` / `subtitle` / `accessibilityLabel`:
     - person: caption "Talking with", title the name, subtitle "your <relationship>" when there is one. Label
       "Talking with Sarah, your daughter. Opens Sarah's profile."
     - someoneNew: "Talking with" / "Getting to know someone new…" / "Calypso⁻¹ doesn't know this voice yet."
     - quiet: "Right now" / "It's quiet" / "Calypso⁻¹ will show who you're talking with."
     - notConnected: "Your puck" / "Not connected" / "Keep your puck close to your phone."
2. `TalkingToCard` takes over the hero slot: same 16-radius white-stroked card, min height 180, so the layout
   doesn't jump.
   - person: large `Avatar` (photo or initials) on the left, then caption, name in `.title` and subtitle. The card
     background is `apricotCream` and there is a chevron affordance.
   - someoneNew: a neutral glyph (`CalypsoGlyph.soundWave`) instead of an avatar, `periwinkleMist` background.
   - quiet: `Mascot(pose: .resting, size: .s)`.
   - notConnected: muted card, no chevron, tap calls `puck.reconnectRemembered()`.
   - Crossfade on change (`.animation(..., value:)`, opacity only under Reduce Motion). AX sizes stack vertically.
   - Add a small "live" dot beside the caption when a speaker is present. It pulses unless Reduce Motion is on.
3. `TodayView`:
   - Read `@EnvironmentObject var puck: PuckConnection`.
   - Keep the full `[Person]` it already fetches (alongside `names`).
   - Wrap the body in a `NavigationStack` with a hidden nav bar, like `PeopleListView`. Tapping `.person` pushes
     `PersonDetailView(client:person:)`. Tapping `.someoneNew` opens a `.sheet` (`PaperSheet` style) titled
     "Someone new" with the text "Calypso⁻¹ doesn't know this voice yet. You can ask their name. Family can add them
     in People later." and an "Okay" primary button.
   - Show the card on **today only**. Past days keep no hero (remove the placeholder there).
   - Show the card in the loading/quiet/failed states too: put it under the header, above `stateContent`, whenever
     `isToday`.
4. DEBUG routes `today-talking-sarah`, `today-talking-unknown`, `today-talking-quiet`. Each uses a
   `PuckConnection` over a `FakePuckLink` pinned with the matching speaker. Make sure every existing `today*`/`home`
   route gets an environment object so nothing crashes.
5. Tests for every `make` branch: patient filtered, uncertain-with-name → someoneNew, id match picks the stored
   person's photo URL, notConnected, and accessibility labels.
6. `xcodegen`, tests, commit `feat(ios): live talking-with card on Today`.

## Task 4: Onboarding step order + Connect your puck

**Files:** modify `ios/Calypso/Onboarding/OnboardingStep.swift`, `OnboardingView.swift`,
`ios/CalypsoTests/OnboardingStepTests.swift`. Create `ios/Calypso/Onboarding/ConnectPuckView.swift` and
`ios/CalypsoTests/ConnectPuckPresentationTests.swift`.

1. The new order is `welcome, companion, addContact, groupCall, permissions, connectPuck, voiceSetup, inviteFamily,
   allSet`, so the total is 9. Update the doc comment ("Step N of 9") and every test expectation. Until Task 5,
   `voiceSetup` shows a temporary placeholder that just calls `onNext`.
2. `ConnectPuckView(onBack:onNext:)` uses `@EnvironmentObject puck`:
   - Mascot `.presenting` size `.m`. Heading "Connect your puck". Message "Turn on your Calypso⁻¹ puck and keep it
     close to your phone."
   - A status `PaperCard` driven by a pure `ConnectPuckPresentation.make(state:)` (title, message, primary button
     title or nil, shows spinner):
     - idle: "Ready to look", button "Find my puck" → `startScanning`.
     - scanning: spinner "Looking for your puck…".
     - found(name): "Found <name>", button "Connect" → `connect`.
     - connecting: spinner "Connecting…".
     - connected: the "Connected" check pill styled like PermissionsView's "Allowed" pill, plus a primary
       "Continue" → `onNext`.
     - bluetoothOff: "Bluetooth is off" / "Turn on Bluetooth in Control Center.", button "Try again".
     - unauthorized: "Bluetooth isn't allowed" / "Allow Bluetooth for Calypso⁻¹ in Settings.", button "Open
       Settings" (`UIApplication.openSettingsURLString`).
     - failed: "We couldn't connect" + reason, button "Try again".
   - Always a quiet "Skip for now" → `onNext`.
3. Tests: the step tests plus every `ConnectPuckPresentation` state.
4. `xcodegen`, tests, commit `feat(ios): connect-your-puck onboarding step`.

## Task 5: Teach it your voice

**Files:** create `ios/Calypso/Onboarding/VoiceSetupView.swift`, `ios/Calypso/Onboarding/VoiceEnrollment.swift` and
`ios/CalypsoTests/VoiceEnrollmentTests.swift`. Modify `OnboardingView.swift` (replace the placeholder).

1. `struct VoiceEnrollment: Equatable`, a pure state machine:
   - `static let sentences = ["My name is easy to remember, and so is my family.", "This morning I had a cup of tea by the window.", "I love hearing stories about the people I care about.", "The sea is calm today, and the sky is bright.", "Thank you for helping me remember my day."]`.
   - `enum Phase: Equatable { case ready, recording, saved, failed(String), finished }`, plus `index`.
   - Mutating `start() -> PuckCommand?`, `apply(_ event: PuckEvent)` (ignores events for other indices), `timeout()`
     (→ failed "We didn't hear that. Let's try again."), `next() -> PuckCommand?` (advances; after the last sentence
     returns `.enrollFinish(count: 5)` and goes `finished` once `.done` arrives, or immediately if the caller treats
     the finish as fire-and-forget; choose one and test it), and `retry()`.
   - Reason mapping: `too_quiet` → "That was a little quiet. Let's try once more." Anything else → the generic
     message.
2. `VoiceSetupView(onBack:onNext:)`:
   - Heading "Teach Calypso⁻¹ your voice". Message "Wear your puck and read each sentence out loud. Your puck
     listens, not your phone."
   - "Sentence 2 of 5" caption, then the sentence in a large `PaperCard` (`.title` font, ink) and a five-dot
     progress row.
   - Buttons by phase: ready → "Start reading". recording → a pulsing sound-wave indicator, "Listening…" and a
     disabled state. saved → "Next sentence" (or "Finish" on the last). failed → message + "Try again". finished →
     the "Voice saved" pill + "Continue".
   - A 15 s timeout task restarts on each `start`.
   - When the puck isn't connected: a calm message "Connect your puck first", a "Go back" secondary button and
     "Skip for now".
   - Quiet "Skip for now" in every phase. `puck.send(.enrollCancel)` when skipping or going back mid-recording.
   - Never request microphone permission.
3. Tests cover the full happy path, the failed reason mapping, retry, timeout, ignoring stale-index events, and the
   finish command.
4. `xcodegen`, tests, commit `feat(ios): teach-your-voice onboarding step`.
