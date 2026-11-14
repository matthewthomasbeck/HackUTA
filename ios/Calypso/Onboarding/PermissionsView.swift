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
