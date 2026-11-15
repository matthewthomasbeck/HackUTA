import UIKit
import XCTest
@testable import Calypso

@MainActor
final class SwipeBackTests: XCTestCase {
    func testPopGestureOnlyBeginsOnPushedScreens() throws {
        let nav = UINavigationController(rootViewController: UIViewController())
        nav.loadViewIfNeeded()
        let pop = try XCTUnwrap(nav.interactivePopGestureRecognizer)
        XCTAssertTrue(pop.delegate === nav)
        XCTAssertFalse(nav.gestureRecognizerShouldBegin(pop))

        nav.pushViewController(UIViewController(), animated: false)
        XCTAssertTrue(nav.gestureRecognizerShouldBegin(pop))
    }
}
