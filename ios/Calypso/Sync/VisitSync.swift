import CoreLocation

/// Watches CLVisit events and uploads them on arrival and departure.
final class VisitSync: NSObject, CLLocationManagerDelegate {
    private static let pendingKey = "visitSync.pending"
    private let manager = CLLocationManager()
    private let client: APIClient

    init(client: APIClient) {
        self.client = client
        super.init()
        manager.delegate = self
    }

    func start() {
        manager.startMonitoringVisits()
        Task { await flush() }
    }

    /// CLVisit reports `.distantFuture` as the departure while the person is still there.
    /// The id derives from arrival + coordinates so the departure upload upserts the arrival one.
    static func makeVisit(arrival: Date, departure: Date, lat: Double, lon: Double) -> Visit {
        Visit(
            id: String(format: "visit-%d-%.5f-%.5f", Int(arrival.timeIntervalSince1970), lat, lon),
            arrived: arrival,
            departed: departure == .distantFuture ? nil : departure,
            lat: lat, lon: lon, placeName: nil
        )
    }

    func locationManager(_ manager: CLLocationManager, didVisit visit: CLVisit) {
        let mapped = Self.makeVisit(arrival: visit.arrivalDate, departure: visit.departureDate,
                                    lat: visit.coordinate.latitude, lon: visit.coordinate.longitude)
        var pending = Self.pending
        pending[mapped.id] = mapped // a departure replaces the queued arrival
        Self.pending = pending
        Task { await flush() }
    }

    /// Uploads everything queued, including visits that failed earlier.
    private func flush() async {
        let queued = Self.pending
        guard !queued.isEmpty else { return }
        do {
            try await client.uploadVisits(Array(queued.values))
            // Drop only what was sent; a newer version of the same visit may have been queued meanwhile.
            Self.pending = Self.pending.filter { queued[$0.key] != $0.value }
        } catch {
            // Stays queued; retried on the next visit event or launch.
        }
    }

    private static var pending: [String: Visit] {
        get {
            guard let data = UserDefaults.standard.data(forKey: pendingKey) else { return [:] }
            return (try? JSONDecoder.calypso.decode([String: Visit].self, from: data)) ?? [:]
        }
        set {
            UserDefaults.standard.set(try? JSONEncoder.calypso.encode(newValue), forKey: pendingKey)
        }
    }
}
