import XCTest
@testable import Calypso

final class PuckMessagesTests: XCTestCase {
    private func who(_ json: String) throws -> WhoIsTalking {
        try JSONDecoder().decode(WhoIsTalking.self, from: Data(json.utf8))
    }

    private func event(_ json: String) throws -> PuckEvent {
        try JSONDecoder().decode(PuckEvent.self, from: Data(json.utf8))
    }

    private func json(_ command: PuckCommand) throws -> [String: AnyHashable] {
        let data = try JSONEncoder().encode(command)
        return try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: AnyHashable])
    }

    func testDecodesIdentified() throws {
        let w = try who(#"{"status":"identified","person_id":"p_sarah","display_name":"Sarah","relationship":"daughter","score":0.72}"#)
        XCTAssertEqual(w, WhoIsTalking(status: .identified, personId: "p_sarah", displayName: "Sarah",
                                       relationship: "daughter", score: 0.72))
    }

    func testDecodesUncertain() throws {
        let w = try who(#"{"status":"uncertain","person_id":"p_sarah","display_name":"Sarah","score":0.5}"#)
        XCTAssertEqual(w.status, .uncertain)
        XCTAssertNil(w.relationship)
    }

    func testEmptyStringsBecomeNil() throws {
        let w = try who(#"{"status":"unknown","person_id":"","display_name":"  ","relationship":"","score":0}"#)
        XCTAssertNil(w.personId)
        XCTAssertNil(w.displayName)
        XCTAssertNil(w.relationship)
        XCTAssertEqual(w.score, 0)
    }

    func testUnknownStatusStringDecodesAsUnknown() throws {
        XCTAssertEqual(try who(#"{"status":"banana"}"#).status, .unknown)
    }

    func testCommandEncoding() throws {
        XCTAssertEqual(try json(.enrollStart(index: 2, text: "Hello there")),
                       ["cmd": "enroll_start", "speaker": "patient", "index": 2, "text": "Hello there"])
        XCTAssertEqual(try json(.enrollFinish(count: 5)),
                       ["cmd": "enroll_finish", "speaker": "patient", "count": 5])
        XCTAssertEqual(try json(.enrollCancel), ["cmd": "enroll_cancel", "speaker": "patient"])
    }

    func testEventDecoding() throws {
        XCTAssertEqual(try event(#"{"event":"enroll_recording","index":0}"#), .recording(index: 0))
        XCTAssertEqual(try event(#"{"event":"enroll_saved","index":3}"#), .saved(index: 3))
        XCTAssertEqual(try event(#"{"event":"enroll_failed","index":1,"reason":"too_quiet"}"#),
                       .failed(index: 1, reason: "too_quiet"))
        XCTAssertEqual(try event(#"{"event":"enroll_failed","index":1}"#), .failed(index: 1, reason: nil))
        XCTAssertEqual(try event(#"{"event":"enroll_done","speaker":"patient"}"#), .done)
    }

    func testUnrecognizedEventThrows() {
        XCTAssertThrowsError(try event(#"{"event":"enroll_exploded","index":0}"#))
    }
}
