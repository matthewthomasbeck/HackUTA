# Calypso⁻¹ iOS app (Eric)

SwiftUI, iOS 17+. Tasks: [`docs/tasks/eric-ios.md`](../docs/tasks/eric-ios.md).

## Create the Xcode project
1. Xcode → File → New → Project → iOS App. Product Name `Calypso`, Interface SwiftUI, Language Swift, check **Include Tests**. Save into this `ios/` folder.
2. Signing & Capabilities: add **Background Modes → Location updates** (for Visits).
3. Info.plist usage strings:
   - `NSContactsUsageDescription`: "Calypso⁻¹ adds itself to your contacts so you can FaceTime it."
   - `NSPhotoLibraryUsageDescription`: "Calypso⁻¹ places your photos on your day's timeline."
   - `NSLocationAlwaysAndWhenInUseUsageDescription`, `NSLocationWhenInUseUsageDescription`: "Calypso⁻¹ remembers places you visited so it can tell you about your day."
4. Folder layout (from the plan): `Calypso/Onboarding`, `Calypso/Core`, `Calypso/People`, `Calypso/Today`, `Calypso/Sync`, plus `CalypsoTests/Fixtures`.
5. `Config.swift` reads `API_BASE_URL`, `API_TOKEN`, and `CHERT_PHONE` from an xcconfig that isn't committed.

Run tests: `xcodebuild test -scheme Calypso -destination 'platform=iOS Simulator,name=iPhone 16'`
