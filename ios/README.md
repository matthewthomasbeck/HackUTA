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
