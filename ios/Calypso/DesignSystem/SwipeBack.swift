import SwiftUI
import UIKit

/// Screens that hide the system back button (to use the paper-cut `BackButton`, since the iOS 26 one is a glass
/// circle) lose UIKit's edge swipe-back. `.swipeBackEnabled()` brings it back for that one screen only: while the
/// screen is on screen, its navigation controller's pop gesture gets a `SwipeBackGate` delegate, and the previous
/// delegate is put back when the screen goes away. No other navigation controller is touched.
extension View {
    func swipeBackEnabled() -> some View {
        background(SwipeBackInstaller().frame(width: 0, height: 0).accessibilityHidden(true))
    }
}

/// The pop gesture's delegate: it only begins on a pushed screen (never the root) and never mid-transition, so a
/// swipe during a push animation can't wedge the stack.
final class SwipeBackGate: NSObject, UIGestureRecognizerDelegate {
    private weak var navigationController: UINavigationController?

    init(navigationController: UINavigationController) {
        self.navigationController = navigationController
    }

    static func allowsPop(stackCount: Int, isTransitioning: Bool) -> Bool {
        stackCount > 1 && !isTransitioning
    }

    func gestureRecognizerShouldBegin(_ gestureRecognizer: UIGestureRecognizer) -> Bool {
        guard let nav = navigationController, gestureRecognizer === nav.interactivePopGestureRecognizer else {
            return false
        }
        return Self.allowsPop(stackCount: nav.viewControllers.count, isTransitioning: nav.transitionCoordinator != nil)
    }
}

/// Installs the gate on appear and restores the previous delegate on disappear. If an interactive pop is cancelled,
/// the screen appears again and the gate goes back on.
final class SwipeBackInstallerController: UIViewController {
    private var gate: SwipeBackGate?
    private weak var installedOn: UINavigationController?
    private weak var previousDelegate: UIGestureRecognizerDelegate?

    override func viewWillAppear(_ animated: Bool) {
        super.viewWillAppear(animated)
        install()
    }

    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        install()
    }

    override func viewDidDisappear(_ animated: Bool) {
        super.viewDidDisappear(animated)
        uninstall()
    }

    func install() {
        guard installedOn == nil, let nav = navigationController, let pop = nav.interactivePopGestureRecognizer
        else { return }
        let gate = SwipeBackGate(navigationController: nav)
        previousDelegate = pop.delegate
        pop.delegate = gate
        self.gate = gate
        installedOn = nav
    }

    func uninstall() {
        if let pop = installedOn?.interactivePopGestureRecognizer, pop.delegate === gate {
            pop.delegate = previousDelegate
        }
        gate = nil
        installedOn = nil
        previousDelegate = nil
    }
}

private struct SwipeBackInstaller: UIViewControllerRepresentable {
    func makeUIViewController(context: Context) -> SwipeBackInstallerController { SwipeBackInstallerController() }
    func updateUIViewController(_ controller: SwipeBackInstallerController, context: Context) {}
}
