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

    /// CLVisit reports `.distantFuture` as the departure while the person is still there, and
    /// `.distantPast` as the arrival when it wasn't observed. An unknown arrival is clamped to the
    /// start of the departure's local day; with neither known the visit is dropped.
    /// The id derives from the arrival time only (whole seconds), so the departure upserts the arrival.
    static func makeVisit(arrival: Date, departure: Date, lat: Double, lon: Double,
                          calendar: Calendar = .current) -> Visit? {
        var arrived = arrival
        if arrival == .distantPast {
            guard departure != .distantFuture, departure != .distantPast else { return nil }
            arrived = calendar.startOfDay(for: departure)
        }
        return Visit(
            id: "visit-\(Int(arrived.timeIntervalSince1970))",
            arrived: arrived,
            departed: departure == .distantFuture ? nil : departure,
            lat: lat, lon: lon, placeName: nil
        )
    }

    func locationManager(_ manager: CLLocationManager, didVisit visit: CLVisit) {
        guard let mapped = Self.makeVisit(arrival: visit.arrivalDate, departure: visit.departureDate,
                                          lat: visit.coordinate.latitude, lon: visit.coordinate.longitude) else { return }
        Self.pending = Self.enqueue(mapped, into: Self.pending)
        Task { await flush() }
    }

    /// Uploads everything queued, including visits that failed earlier.
    private func flush() async {
        let queued = Self.pending
        guard !queued.isEmpty else { return }
        do {
            try await client.uploadVisits(queued)
            // Drop only what was sent; a newer version of the same visit may have been queued meanwhile.
            Self.pending = Self.pending.filter { !queued.contains($0) }
        } catch {
            // Stays queued; retried on the next visit event or launch.
        }
    }

    /// A departure replaces the queued arrival with the same id.
    static func enqueue(_ visit: Visit, into queue: [Visit]) -> [Visit] {
        queue.filter { $0.id != visit.id } + [visit]
    }

    static func encodeQueue(_ queue: [Visit]) -> Data? { try? JSONEncoder.calypso.encode(queue) }

    static func decodeQueue(_ data: Data) -> [Visit] {
        (try? JSONDecoder.calypso.decode([Visit].self, from: data)) ?? []
    }

    private static var pending: [Visit] {
        get { UserDefaults.standard.data(forKey: pendingKey).map(decodeQueue) ?? [] }
        set { UserDefaults.standard.set(encodeQueue(newValue), forKey: pendingKey) }
    }
}
