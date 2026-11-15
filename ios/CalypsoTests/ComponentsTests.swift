import XCTest
import UIKit
@testable import Calypso

final class ComponentsTests: XCTestCase {
    func testPlaceRowAccessibilityLabel() {
        XCTAssertEqual(PlaceRow.accessibilityLabel(place: "Blue Bean Café", isUncertain: false), "At Blue Bean Café")
        XCTAssertEqual(PlaceRow.accessibilityLabel(place: "Somewhere with park sounds", isUncertain: true),
                       "Place not certain: somewhere with park sounds")
    }

    func testHomeTabOrderAndGlyphs() {
        XCTAssertEqual(HomeTab.allCases.map(\.title), ["Today", "People", "Account"])
        XCTAssertEqual(HomeTab.allCases.map(\.glyph), [.today, .people, .account])
    }

    func testFigmaGlyphAssetsExist() {
        for glyph in [CalypsoGlyph.today, .people, .account, .chevronLeft, .pin, .soundWave, .feather, .photo] {
            XCTAssertNotNil(UIImage(named: glyph.rawValue),
                            glyph.rawValue)
        }
    }
}
