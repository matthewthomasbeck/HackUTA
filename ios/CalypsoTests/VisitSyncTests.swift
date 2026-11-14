import XCTest
@testable import Calypso

final class VisitSyncTests: XCTestCase {
    private let arrival = Date(timeIntervalSince1970: 1_700_000_000)

    func testVisitMapsDistantFutureToNilDeparture() throws {
        let open = try XCTUnwrap(VisitSync.makeVisit(arrival: arrival, departure: .distantFuture, lat: 32.73, lon: -97.11))
        XCTAssertNil(open.departed)
        XCTAssertEqual(open.arrived, arrival)
        XCTAssertEqual(open.lat, 32.73)
        XCTAssertNil(open.placeName)

        let departure = arrival.addingTimeInterval(3600)
        let closed = try XCTUnwrap(VisitSync.makeVisit(arrival: arrival, departure: departure, lat: 32.73, lon: -97.11))
        XCTAssertEqual(closed.departed, departure)
    }

    func testDistantPastArrivalClampsToStartOfDepartureDay() throws {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(identifier: "America/Chicago")!
        let departure = arrival.addingTimeInterval(3600)
        let visit = try XCTUnwrap(VisitSync.makeVisit(arrival: .distantPast, departure: departure,
                                                      lat: 32.73, lon: -97.11, calendar: calendar))
        XCTAssertEqual(visit.arrived, calendar.startOfDay(for: departure))
        XCTAssertEqual(visit.departed, departure)
    }

    func testUnknownArrivalAndDepartureDropsVisit() {
        XCTAssertNil(VisitSync.makeVisit(arrival: .distantPast, departure: .distantFuture, lat: 1, lon: 2))
    }

    func testVisitIdDependsOnArrivalTimeOnly() throws {
        let open = try XCTUnwrap(VisitSync.makeVisit(arrival: arrival, departure: .distantFuture, lat: 32.73, lon: -97.11))
        let closed = try XCTUnwrap(VisitSync.makeVisit(arrival: arrival, departure: arrival.addingTimeInterval(60), lat: 32.7301, lon: -97.1102))
        XCTAssertEqual(open.id, closed.id)
        let later = try XCTUnwrap(VisitSync.makeVisit(arrival: arrival.addingTimeInterval(5), departure: .distantFuture, lat: 32.73, lon: -97.11))
        XCTAssertNotEqual(open.id, later.id)
    }

    func testQueueRoundTripAndDedupe() throws {
        let open = try XCTUnwrap(VisitSync.makeVisit(arrival: arrival, departure: .distantFuture, lat: 32.73, lon: -97.11))
        let closed = try XCTUnwrap(VisitSync.makeVisit(arrival: arrival, departure: arrival.addingTimeInterval(60), lat: 32.73, lon: -97.11))
        var queue = VisitSync.enqueue(open, into: [])
        queue = VisitSync.enqueue(closed, into: queue)
        XCTAssertEqual(queue, [closed])

        let data = try XCTUnwrap(VisitSync.encodeQueue(queue))
        XCTAssertEqual(VisitSync.decodeQueue(data), queue)
    }
}
