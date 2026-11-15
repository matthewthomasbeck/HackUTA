import CoreLocation
import Photos
import SwiftUI

@MainActor
final class LocationPermission: NSObject, ObservableObject, CLLocationManagerDelegate {
    private let manager = CLLocationManager()
    private var userRequested = false

    override init() {
        super.init()
        manager.delegate = self
    }

    /// iOS grants "Always" in two steps: When-In-Use first, then the Always upgrade.
    func request() {
        userRequested = true
        if manager.authorizationStatus == .notDetermined {
            manager.requestWhenInUseAuthorization()
        } else {
            manager.requestAlwaysAuthorization()
        }
    }

    /// Also fires when the manager is created, so only upgrade after a request the user started.
    nonisolated func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        Task { @MainActor in
            if userRequested, manager.authorizationStatus == .authorizedWhenInUse {
                manager.requestAlwaysAuthorization()
            }
        }
    }
}

/// Figma "Permissions" (20:1173). The requests are unchanged; the status is only read, to show "Allowed".
struct PermissionsView: View {
    var onBack: () -> Void
    var onDone: () -> Void
    @StateObject private var location = LocationPermission()
    @State private var photosAllowed = false
    @State private var locationAllowed = false

    var body: some View {
        OnboardingScaffold(step: .permissions, onBack: onBack) {
            VStack(alignment: .leading, spacing: 8) {
                OnboardingHeading(title: "Last step",
                                  message: "Photos and places help Calypso⁻¹ tell you about your day.")
                    .overlay(alignment: .topTrailing) {
                        // Beside the back button, its feet level with the short title, as in Figma
                        // (this pose is taller, so it dips 26pt into the title line to stay below the status bar).
                        Mascot(pose: .holdingPhoto, size: .s, shadow: true)
                            .alignmentGuide(.top) { $0[.bottom] - 26 }
                    }
                PermissionCard(icon: .photo, title: "Photos", message: "Show family photos in your day.",
                               allowed: photosAllowed) {
                    PHPhotoLibrary.requestAuthorization(for: .readWrite) { _ in
                        Task { @MainActor in refreshStatus() }
                    }
                }
                PermissionCard(icon: .pin, title: "Location",
                               message: "Know where your day happened.", allowed: locationAllowed) {
                    location.request()
                }
                Spacer(minLength: 24)
                CalypsoButton("Done", action: onDone)
            }
            .padding(.horizontal, 24)
            .frame(maxHeight: .infinity)
        }
        .onAppear(perform: refreshStatus)
        // The system prompt makes the app inactive; re-read once it is answered (or on return from Settings).
        .onReceive(NotificationCenter.default.publisher(for: UIApplication.didBecomeActiveNotification)) { _ in
            refreshStatus()
        }
    }

    private func refreshStatus() {
        let photos = PHPhotoLibrary.authorizationStatus(for: .readWrite)
        photosAllowed = photos == .authorized || photos == .limited
        let place = CLLocationManager().authorizationStatus
        locationAllowed = place == .authorizedAlways || place == .authorizedWhenInUse
    }
}

/// Figma `Permission / *`: icon disc, Headline title, Callout reason, then Allow or the "Allowed" pill.
private struct PermissionCard: View {
    let icon: CalypsoGlyph
    let title: String
    let message: String
    let allowed: Bool
    let onAllow: () -> Void
    @ScaledMetric(relativeTo: .title2) private var disc: CGFloat = 64
    @Environment(\.dynamicTypeSize) private var typeSize

    var body: some View {
        // The reason wraps, so `ViewThatFits` would always stack; switch on AX sizes instead.
        let layout = typeSize.isAccessibilitySize
            ? AnyLayout(VStackLayout(alignment: .leading, spacing: 12))
            : AnyLayout(HStackLayout(spacing: 16))
        PaperCard(horizontalPadding: 16, verticalPadding: 12) {
            VStack(alignment: .leading, spacing: 10) {
                layout {
                    CalypsoIcon(icon, relativeTo: .title2)
                        .foregroundStyle(Color.ink)
                        .frame(width: disc, height: disc)
                        .background(Color.apricotCream, in: Circle())
                    VStack(alignment: .leading, spacing: 2) {
                        Text(title).calypsoFont(.headline).foregroundStyle(Color.ink)
                        Text(message).calypsoFont(.callout).foregroundStyle(Color.inkSoft)
                    }
                    .fixedSize(horizontal: false, vertical: true)
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
                .accessibilityElement(children: .combine)
                if allowed {
                    HStack(spacing: 12) {
                        CalypsoIcon("checkmark.circle.fill", size: 36)
                        Text("Allowed").calypsoFont(.bodyStrong)
                    }
                    .foregroundStyle(Color.ink)
                    .frame(maxWidth: .infinity, minHeight: 56)
                    .background(Color.periwinkleMist, in: RoundedRectangle(cornerRadius: 24))
                    .accessibilityElement(children: .combine)
                    .accessibilityLabel("\(title) allowed")
                } else {
                    CalypsoButton("Allow", kind: .secondary, action: onAllow)
                        .accessibilityLabel("Allow \(title)")
                }
            }
        }
    }
}

#Preview {
    PermissionsView(onBack: {}, onDone: {})
}

#Preview("AX5") {
    PermissionsView(onBack: {}, onDone: {}).dynamicTypeSize(.accessibility5)
}
