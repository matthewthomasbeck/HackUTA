import XCTest
@testable import Calypso

final class PeoplePresentationTests: XCTestCase {
    func testRelationshipCapitalizesFirstLetterOnly() {
        XCTAssertEqual(PeoplePresentation.relationshipLabel("mother"), "Mother")
        XCTAssertEqual(PeoplePresentation.relationshipLabel("next-door neighbor"), "Next-door neighbor")
        XCTAssertEqual(PeoplePresentation.relationshipLabel("  daughter "), "Daughter")
    }

    func testRowRelationshipIsYourPlusLowercase() {
        XCTAssertEqual(PeoplePresentation.rowRelationship("Mother"), "Your mother")
        XCTAssertEqual(PeoplePresentation.rowRelationship(" daughter "), "Your daughter")
        XCTAssertNil(PeoplePresentation.rowRelationship("  "))
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

    func testBlankNameIsUnnamedEverywhere() {
        XCTAssertNil(Person(id: "p_a").displayName)
        XCTAssertNil(Person(id: "p_a", name: "").displayName)
        XCTAssertNil(Person(id: "p_a", name: " \n\t ").displayName)
        XCTAssertEqual(Person(id: "p_a", name: "  Sarah ").displayName, "Sarah")
        XCTAssertEqual(PeoplePresentation.rowAccessibilityLabel(Person(id: "p_a", name: "  ")),
                       PeoplePresentation.rowAccessibilityLabel(Person(id: "p_a")))
    }
}
