# Calypso⁻¹ iOS app (Eric)

SwiftUI, iOS 17+. Tasks: [`docs/tasks/eric-ios.md`](../docs/tasks/eric-ios.md).

## Setup
The Xcode project is generated from `project.yml` with [xcodegen](https://github.com/yonaskolb/XcodeGen) (`brew install xcodegen`):

```
cd ios && xcodegen
```

`project.yml` already configures (so you don't set these by hand in Xcode):
- iOS 17, SwiftUI app target `Calypso`, unit-test target `CalypsoTests` (Fixtures bundled as resources). Code signing is off, so no team ID is committed; set your own team in Xcode to run on a device.
- **Background Modes → Location updates** (`UIBackgroundModes: [location]`, for Visits).
- Info.plist usage strings:
  - `NSContactsUsageDescription`: "Calypso⁻¹ adds itself to your contacts so you can FaceTime it."
  - `NSPhotoLibraryUsageDescription`: "Calypso⁻¹ places your photos on your day's timeline."
  - `NSLocationAlwaysAndWhenInUseUsageDescription`, `NSLocationWhenInUseUsageDescription`: "Calypso⁻¹ remembers places you visited so it can tell you about your day."
- Folder layout: `Calypso/Onboarding`, `Calypso/Core`, `Calypso/People`, `Calypso/Today`, `Calypso/Sync`, plus `CalypsoTests/Fixtures`.

## Config
`Config.swift` reads `API_BASE_URL`, `API_TOKEN`, and `CHERT_PHONE` from Info.plist, which gets them from build settings. Copy `Secrets.xcconfig.example` to `Secrets.xcconfig` (git-ignored) and fill it in; the build works without it (values are empty). In xcconfig `//` starts a comment, so write URLs as `https:/$()/host`.

Re-run `xcodegen` after editing `project.yml` or adding source files, and commit the regenerated `Calypso.xcodeproj`.

Run tests:
```
xcodebuild test -project ios/Calypso.xcodeproj -scheme Calypso -destination 'platform=iOS Simulator,name=iPhone 17'
```

## Fake backend
Until the real backend is deployed, `scripts/fake_backend.py` serves every endpoint `APIClient` calls: seeded people (including the patient and an unnamed visitor), a day of events anchored on whatever date you pick, a quiet day for dates more than 2 days back, and a sensitive photo that 404s. Uploaded photos and visits are kept in memory and show up in Today on the next refresh.

```
uv run ios/scripts/fake_backend.py          # prints the API_BASE_URL lines for simulator and device
```
Set `API_BASE_URL` (the Mac's LAN IP on a device) and `API_TOKEN = dev-token` in `Secrets.xcconfig`, then rebuild.

## Smoke test against the real backend
`scripts/smoke_test.sh` compiles the app's real `Core/{Models,APIClient,Config}.swift` with `scripts/smoke/main.swift` into a macOS CLI and calls every `APIClient` endpoint: auth, people, person detail, rename, day events, photo upload and retry, photo and face media, and visit open then depart. It doesn't touch the Xcode project or DerivedData.

```
ios/scripts/smoke_test.sh               # runs backend/ on :8765 with a throwaway DB, seeds it, tests
ios/scripts/smoke_test.sh URL TOKEN     # a deployed backend; leaves "Smoke …" people and smoke-* photos/visits behind
```
Against a deployed backend there's no day-event seeding, so the events check only checks decoding.
