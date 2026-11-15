import XCTest
@testable import Calypso

final class ComponentsTests: XCTestCase {
    func testPlaceRowAccessibilityLabel() {
        XCTAssertEqual(PlaceRow.accessibilityLabel(place: "Blue Bean Café", isUncertain: false), "At Blue Bean Café")
        XCTAssertEqual(PlaceRow.accessibilityLabel(place: "Somewhere with park sounds", isUncertain: true),
                       "Place not certain: somewhere with park sounds")
    }

    func testHomeTabOrderAndSymbols() {
        XCTAssertEqual(HomeTab.allCases.map(\.title), ["Today", "People", "Account"])
        XCTAssertEqual(HomeTab.allCases.map(\.systemImage), ["calendar", "person.2", "person"])
    }
}
