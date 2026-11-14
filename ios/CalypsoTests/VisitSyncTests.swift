import XCTest
@testable import Calypso

final class VisitSyncTests: XCTestCase {
    private let arrival = Date(timeIntervalSince1970: 1_700_000_000)

    func testVisitMapsDistantFutureToNilDeparture() {
        let open = VisitSync.makeVisit(arrival: arrival, departure: .distantFuture, lat: 32.73, lon: -97.11)
        XCTAssertNil(open.departed)
        XCTAssertEqual(open.arrived, arrival)
        XCTAssertEqual(open.lat, 32.73)
        XCTAssertNil(open.placeName)

        let departure = arrival.addingTimeInterval(3600)
        let closed = VisitSync.makeVisit(arrival: arrival, departure: departure, lat: 32.73, lon: -97.11)
        XCTAssertEqual(closed.departed, departure)
    }

    func testVisitIdIsStableAcrossArrivalAndDeparture() {
        let open = VisitSync.makeVisit(arrival: arrival, departure: .distantFuture, lat: 32.73, lon: -97.11)
        let closed = VisitSync.makeVisit(arrival: arrival, departure: arrival.addingTimeInterval(60), lat: 32.73, lon: -97.11)
        XCTAssertEqual(open.id, closed.id)
        let other = VisitSync.makeVisit(arrival: arrival, departure: .distantFuture, lat: 33.0, lon: -97.11)
        XCTAssertNotEqual(open.id, other.id)
    }
}
