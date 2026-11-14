import XCTest
import Contacts
@testable import Calypso

final class ContactBuilderTests: XCTestCase {
    func testCalypsoContactHasNameAndPhone() {
        let contact = ContactBuilder.calypso(phone: "+15551234567")
        XCTAssertEqual(contact.givenName, "Calypso⁻¹")
        XCTAssertEqual(contact.phoneNumbers.first?.value.stringValue, "+15551234567")
        XCTAssertNotNil(contact.imageData)
    }
}
