import XCTest
@testable import Calypso

final class FamilyInviteTests: XCTestCase {
    func testMessageBodyIncludesCalypsoNumberAsStored() {
        XCTAssertEqual(FamilyInvite.messageBody(calypsoPhone: "+15125550100"),
                       "Hi! I’m using Calypso⁻¹ to help me remember. Please FaceTime Calypso⁻¹ at +15125550100 to set up your profile.")
    }

    func testMessageBodyWithoutNumberStillReadsWell() {
        let expected = "Hi! I’m using Calypso⁻¹ to help me remember. Please FaceTime Calypso⁻¹ to set up your profile."
        XCTAssertEqual(FamilyInvite.messageBody(calypsoPhone: ""), expected)
        XCTAssertEqual(FamilyInvite.messageBody(calypsoPhone: "  \n"), expected)
    }

    func testInviteesUseFirstPhoneAndSkipContactsWithoutOne() {
        let picked = [
            FamilyInvite.PickedContact(givenName: "Sarah", fullName: "Sarah Lee", phones: ["+15125550142", "+15125550999"]),
            FamilyInvite.PickedContact(givenName: "Nobody", fullName: "Nobody Home", phones: []),
            FamilyInvite.PickedContact(givenName: "Tom", fullName: "Tom Lee", phones: ["  ", "+15125550143"]),
        ]
        let invitees = FamilyInvite.invitees(from: picked)
        XCTAssertEqual(invitees.map(\.name), ["Sarah", "Tom"])
        XCTAssertEqual(FamilyInvite.recipients(invitees), ["+15125550142", "+15125550143"])
    }

    func testDisplayNameFallsBackToFullNameThenPhone() {
        XCTAssertEqual(FamilyInvite.PickedContact(givenName: "Sarah", fullName: "Sarah Lee", phones: ["1"]).displayName,
                       "Sarah")
        XCTAssertEqual(FamilyInvite.PickedContact(givenName: " ", fullName: "Dr. Lee", phones: ["1"]).displayName,
                       "Dr. Lee")
        XCTAssertEqual(FamilyInvite.PickedContact(givenName: "", fullName: "", phones: ["+15125550142"]).displayName,
                       "+15125550142")
    }

    func testInviteesDropDuplicatePhones() {
        let picked = [
            FamilyInvite.PickedContact(givenName: "Sarah", fullName: "", phones: ["+15125550142"]),
            FamilyInvite.PickedContact(givenName: "Sarah (work)", fullName: "", phones: ["+15125550142"]),
        ]
        XCTAssertEqual(FamilyInvite.invitees(from: picked).map(\.name), ["Sarah"])
    }

    func testMergeAppendsWithoutDuplicates() {
        let sarah = FamilyInvite.Invitee(name: "Sarah", phone: "+15125550142")
        let tom = FamilyInvite.Invitee(name: "Tom", phone: "+15125550143")
        let ana = FamilyInvite.Invitee(name: "Ana", phone: "+15125550144")
        XCTAssertEqual(FamilyInvite.merge([sarah, tom], with: [tom, ana, sarah]), [sarah, tom, ana])
    }
}
