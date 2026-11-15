import SwiftUI
import UIKit
import XCTest
@testable import Calypso

@MainActor
final class SwipeBackTests: XCTestCase {
    /// A window in the test host's scene, so views actually appear and transitions animate.
    private func makeWindow(root: UIViewController) throws -> UIWindow {
        let scene = try XCTUnwrap(UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }.first)
        let window = UIWindow(windowScene: scene)
        window.rootViewController = root
        window.makeKeyAndVisible()
        return window
    }

    func testPopAllowedOnlyOnPushedScreensAndNeverMidTransition() {
        XCTAssertFalse(SwipeBackGate.allowsPop(stackCount: 1, isTransitioning: false))
        XCTAssertTrue(SwipeBackGate.allowsPop(stackCount: 2, isTransitioning: false))
        XCTAssertFalse(SwipeBackGate.allowsPop(stackCount: 2, isTransitioning: true))
        XCTAssertFalse(SwipeBackGate.allowsPop(stackCount: 0, isTransitioning: false))
    }

    func testGateReadsTheNavigationStack() throws {
        let nav = UINavigationController(rootViewController: UIViewController())
        let gate = SwipeBackGate(navigationController: nav)
        let pop = try XCTUnwrap(nav.interactivePopGestureRecognizer)
        XCTAssertFalse(gate.gestureRecognizerShouldBegin(pop))
        nav.pushViewController(UIViewController(), animated: false)
        XCTAssertTrue(gate.gestureRecognizerShouldBegin(pop))
        // Any other recognizer is never started by the gate.
        XCTAssertFalse(gate.gestureRecognizerShouldBegin(UIPanGestureRecognizer()))
    }

    /// Asks the gate from inside the pushed screen's `viewWillAppear`, while the push animation is in flight.
    private final class ProbeController: UIViewController {
        var onWillAppear: (() -> Void)?
        override func viewWillAppear(_ animated: Bool) {
            super.viewWillAppear(animated)
            onWillAppear?()
        }
    }

    func testGateRefusesWhileAPushIsAnimating() throws {
        let nav = UINavigationController(rootViewController: UIViewController())
        let window = try makeWindow(root: nav)
        defer { window.isHidden = true }
        let gate = SwipeBackGate(navigationController: nav)
        let pop = try XCTUnwrap(nav.interactivePopGestureRecognizer)

        let probe = ProbeController()
        let checked = expectation(description: "checked mid-push")
        probe.onWillAppear = {
            XCTAssertNotNil(nav.transitionCoordinator, "push should be animating")
            XCTAssertEqual(nav.viewControllers.count, 2)
            XCTAssertFalse(gate.gestureRecognizerShouldBegin(pop))
            checked.fulfill()
        }
        // Let the root screen appear first; UIKit doesn't animate a push into a window that hasn't shown yet.
        RunLoop.main.run(until: Date().addingTimeInterval(0.3))
        nav.pushViewController(probe, animated: true)
        wait(for: [checked], timeout: 3)

        // Once the push has finished, the same gate lets the swipe begin.
        let settled = expectation(description: "push finished")
        func poll() {
            if nav.transitionCoordinator == nil { settled.fulfill() } else {
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.05, execute: poll)
            }
        }
        poll()
        wait(for: [settled], timeout: 3)
        XCTAssertTrue(gate.gestureRecognizerShouldBegin(pop))
    }

    /// The modifier only touches the navigation controller of the screen that uses it, and puts the old delegate
    /// back once that screen is gone. Plain navigation controllers keep UIKit's own delegate.
    func testInstallerScopesTheGateToItsScreen() throws {
        let plain = UINavigationController(rootViewController: UIViewController())
        plain.loadViewIfNeeded()
        XCTAssertFalse(plain.interactivePopGestureRecognizer?.delegate is SwipeBackGate)

        let nav = UINavigationController(rootViewController: UIViewController())
        let pop = try XCTUnwrap(nav.interactivePopGestureRecognizer)
        let original = pop.delegate
        XCTAssertFalse(original is SwipeBackGate)

        let installer = SwipeBackInstallerController()
        let pushed = UIViewController()
        pushed.addChild(installer)
        installer.didMove(toParent: pushed)
        nav.pushViewController(pushed, animated: false)

        installer.install()
        XCTAssertTrue(pop.delegate is SwipeBackGate)
        XCTAssertTrue(pop.delegate?.gestureRecognizerShouldBegin?(pop) == true)

        installer.uninstall()
        XCTAssertTrue(pop.delegate === original)
    }

    /// End to end: a SwiftUI screen with `.swipeBackEnabled()` pushed in a window gets the gate on appear.
    func testModifierInstallsOnAppear() throws {
        let nav = UINavigationController(rootViewController: UIViewController())
        let window = try makeWindow(root: nav)
        defer { window.isHidden = true }
        let pop = try XCTUnwrap(nav.interactivePopGestureRecognizer)
        let original = pop.delegate

        nav.pushViewController(UIHostingController(rootView: Text("Person").swipeBackEnabled()), animated: false)
        let installed = expectation(description: "gate installed")
        func poll() {
            if pop.delegate is SwipeBackGate { installed.fulfill() } else {
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.05, execute: poll)
            }
        }
        poll()
        wait(for: [installed], timeout: 3)

        nav.popViewController(animated: false)
        let restored = expectation(description: "delegate restored")
        func pollRestored() {
            if pop.delegate === original { restored.fulfill() } else {
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.05, execute: pollRestored)
            }
        }
        pollRestored()
        wait(for: [restored], timeout: 3)
    }
}
