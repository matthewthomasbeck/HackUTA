import XCTest
@testable import Calypso

final class ModelsDecodingTests: XCTestCase {
    private func fixture(_ name: String) throws -> Data {
        let url = try XCTUnwrap(Bundle(for: Self.self).url(forResource: name, withExtension: "json"))
        return try Data(contentsOf: url)
    }

    func testDecodePerson() throws {
        let person = try JSONDecoder.calypso.decode(Person.self, from: fixture("person"))
        XCTAssertEqual(person.id, "p_mom")
        XCTAssertEqual(person.name, "Mom")
        XCTAssertEqual(person.relationship, "mother")
        XCTAssertFalse(person.isPatient)
        XCTAssertEqual(person.facePhotoUrl, "https://example.com/faces/p_mom.jpg")
        XCTAssertEqual(person.facts.count, 2)
    }

    func testPersonDefaultsWhenOptionalFieldsAbsent() throws {
        let json = Data(#"{"id":"p_x"}"#.utf8)
        let person = try JSONDecoder.calypso.decode(Person.self, from: json)
        XCTAssertNil(person.name)
        XCTAssertFalse(person.isPatient)
        XCTAssertEqual(person.facts, [])
    }

    func testDecodeDayEvent() throws {
        let events = try JSONDecoder.calypso.decode([DayEvent].self, from: fixture("day_events"))
        XCTAssertEqual(events.count, 2)
        let first = events[0]
        XCTAssertEqual(first.place, "Kroger")
        XCTAssertEqual(first.placeConfidence, 0.87, accuracy: 0.0001)
        XCTAssertEqual(first.people, ["p_mom"])
        XCTAssertEqual(first.photoIds, ["ph1"])
        // No fractional seconds, no timezone -> UTC.
        XCTAssertEqual(first.start, Date(timeIntervalSince1970: 1_794_648_600))
        XCTAssertEqual(first.end.timeIntervalSince(first.start), 45 * 60)
        // Fractional seconds with Z, and explicit offset without fraction.
        XCTAssertEqual(events[1].start.timeIntervalSince1970, 1_794_657_600.25, accuracy: 0.001)
        XCTAssertEqual(events[1].end.timeIntervalSince1970, 1_794_661_200, accuracy: 0.001)
    }

    func testDateVariants() throws {
        let cases = [
            "2026-11-14T09:30:00Z", "2026-11-14T09:30:00.123456Z",
            "2026-11-14T09:30:00", "2026-11-14T09:30:00.123456", "2026-11-14T04:30:00-05:00",
        ]
        for text in cases {
            let json = Data(#"{"id":"v","arrived":"\#(text)","lat":1,"lon":2}"#.utf8)
            let visit = try JSONDecoder.calypso.decode(Visit.self, from: json)
            XCTAssertEqual(visit.arrived.timeIntervalSince1970, 1_794_648_600, accuracy: 0.5, text)
            XCTAssertNil(visit.departed)
        }
    }

    func testDecodeCard() throws {
        let card = try JSONDecoder.calypso.decode(Card.self, from: fixture("card"))
        XCTAssertEqual(card.kind, .identity)
        XCTAssertEqual(card.lines.count, 2)
        XCTAssertEqual(card.imageUrls.count, 1)
    }

    func testVisitEncodesSnakeCaseKeys() throws {
        let visit = Visit(id: "v1", arrived: Date(timeIntervalSince1970: 0), departed: nil,
                          lat: 1, lon: 2, placeName: "Cafe")
        let object = try JSONSerialization.jsonObject(with: JSONEncoder.calypso.encode(visit)) as? [String: Any]
        XCTAssertEqual(object?["place_name"] as? String, "Cafe")
        XCTAssertNotNil(object?["arrived"] as? String)
    }
}
