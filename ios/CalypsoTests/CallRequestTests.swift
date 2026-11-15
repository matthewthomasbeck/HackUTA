import XCTest
@testable import Calypso

final class CallRequestTests: XCTestCase {
    func testMessageBodyAsksTheAgentToCall() {
        XCTAssertEqual(CallRequest.messageBody(for: "Sarah"), "call Sarah with me")
    }

    func testMessageBodyTrimsWhitespace() {
        XCTAssertEqual(CallRequest.messageBody(for: "  Sarah \n"), "call Sarah with me")
    }

    func testUnavailableNotes() {
        XCTAssertEqual(CallRequest.unavailableNote(canSendText: false, agentPhone: "+15125550100"),
                       "Messages isn’t available on this phone.")
        XCTAssertEqual(CallRequest.unavailableNote(canSendText: true, agentPhone: "  "),
                       "Calypso⁻¹’s number isn’t set up yet.")
        XCTAssertNil(CallRequest.unavailableNote(canSendText: true, agentPhone: "+15125550100"))
    }

    func testCallablePhone() {
        XCTAssertEqual(Person(id: "p", name: "Sarah", phone: " +15125550142 ").callablePhone, "+15125550142")
        XCTAssertNil(Person(id: "p", name: "Sarah").callablePhone)
        XCTAssertNil(Person(id: "p", name: "Sarah", phone: "").callablePhone)
        XCTAssertNil(Person(id: "p", name: "Sarah", phone: " \n ").callablePhone)
    }

    func testDetailsBodySendsNameAndPhone() throws {
        let data = try APIClient.personDetailsBody(name: "Sarah", phone: "+15125550142")
        let json = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
        XCTAssertEqual(json["name"] as? String, "Sarah")
        XCTAssertEqual(json["phone"] as? String, "+15125550142")
    }

    func testDetailsBodySendsNullToClearThePhone() throws {
        let data = try APIClient.personDetailsBody(name: "Sarah", phone: nil)
        let json = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
        XCTAssertEqual(json.keys.sorted(), ["name", "phone"])
        XCTAssertTrue(json["phone"] is NSNull)
    }
}
