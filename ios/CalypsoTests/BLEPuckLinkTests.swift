import CoreBluetooth
import XCTest
@testable import Calypso

final class BLEPuckLinkTests: XCTestCase {
    func testManagerStateMapping() {
        XCTAssertEqual(BLEPuckLink.linkState(for: .poweredOff), .bluetoothOff)
        XCTAssertEqual(BLEPuckLink.linkState(for: .unauthorized), .unauthorized)
        XCTAssertNil(BLEPuckLink.linkState(for: .poweredOn))
        XCTAssertNil(BLEPuckLink.linkState(for: .unknown))
    }

    func testDecodeWhoPayload() {
        let json = #"{"status":"identified","person_id":"p_sarah","display_name":"Sarah","relationship":"daughter","score":0.72}"#
        let who = BLEPuckLink.decode(WhoIsTalking.self, from: Data(json.utf8))
        XCTAssertEqual(who?.displayName, "Sarah")
        XCTAssertEqual(who?.status, .identified)
    }

    func testDecodeEventPayload() {
        let event = BLEPuckLink.decode(PuckEvent.self, from: Data(#"{"event":"enroll_saved","index":2}"#.utf8))
        XCTAssertEqual(event, .saved(index: 2))
    }

    func testBadPayloadsDropSilently() {
        XCTAssertNil(BLEPuckLink.decode(PuckEvent.self, from: Data("nope".utf8)))
        XCTAssertNil(BLEPuckLink.decode(PuckEvent.self, from: Data(#"{"event":"mystery"}"#.utf8)))
        XCTAssertNil(BLEPuckLink.decode(WhoIsTalking.self, from: nil))
    }
}
