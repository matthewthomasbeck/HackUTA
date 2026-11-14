import CoreLocation
import Photos
import SwiftUI

@MainActor
final class LocationPermission: NSObject, ObservableObject, CLLocationManagerDelegate {
    private let manager = CLLocationManager()

    override init() {
        super.init()
        manager.delegate = self
    }

    /// iOS grants "Always" in two steps: When-In-Use first, then the Always upgrade.
    func request() {
        if manager.authorizationStatus == .notDetermined {
            manager.requestWhenInUseAuthorization()
        } else {
            manager.requestAlwaysAuthorization()
        }
    }

    nonisolated func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        if manager.authorizationStatus == .authorizedWhenInUse {
            manager.requestAlwaysAuthorization()
        }
    }
}

struct PermissionsView: View {
    var onDone: () -> Void
    @StateObject private var location = LocationPermission()

    var body: some View {
        VStack(alignment: .leading, spacing: 24) {
            Text("Last step").font(.title.bold())
            Text("Photos and places help Calypso⁻¹ tell you about your day.").foregroundStyle(.secondary)
            Button("Allow Photos") {
                PHPhotoLibrary.requestAuthorization(for: .readWrite) { _ in }
            }
            .buttonStyle(.bordered)
            Button("Allow Location (Always)") { location.request() }
                .buttonStyle(.bordered)
            Spacer()
            Button("Done", action: onDone)
                .buttonStyle(.borderedProminent).controlSize(.large).frame(maxWidth: .infinity)
        }
        .padding()
    }
}
