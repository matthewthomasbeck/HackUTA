import XCTest
@testable import Calypso

final class PeoplePresentationTests: XCTestCase {
    func testRelationshipCapitalizesFirstLetterOnly() {
        XCTAssertEqual(PeoplePresentation.relationshipLabel("mother"), "Mother")
        XCTAssertEqual(PeoplePresentation.relationshipLabel("next-door neighbor"), "Next-door neighbor")
        XCTAssertEqual(PeoplePresentation.relationshipLabel("  daughter "), "Daughter")
    }

    func testBlankRelationshipIsHidden() {
        XCTAssertNil(PeoplePresentation.relationshipLabel(nil))
        XCTAssertNil(PeoplePresentation.relationshipLabel("   "))
    }

    func testUnknownPersonNeverGetsAGuessedName() {
        let label = PeoplePresentation.rowAccessibilityLabel(Person(id: "p_unknown"))
        XCTAssertTrue(label.hasPrefix("Getting to know someone new…"))
        XCTAssertFalse(label.contains("Unnamed"))
        XCTAssertFalse(label.contains("p_unknown"))
    }

    func testNamedRowLabel() {
        let sarah = Person(id: "p_sarah", name: "Sarah", relationship: "daughter")
        XCTAssertEqual(PeoplePresentation.rowAccessibilityLabel(sarah), "Sarah, Daughter")
    }
}
