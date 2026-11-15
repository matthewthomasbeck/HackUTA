import UIKit

/// Screens that hide the system back button (to use the paper-cut `BackButton`, since the iOS 26 one is a glass
/// circle) lose UIKit's edge swipe-back. Taking over the pop gesture's delegate brings it back for every pushed
/// screen; the root screen never starts it.
extension UINavigationController: @retroactive UIGestureRecognizerDelegate {
    override open func viewDidLoad() {
        super.viewDidLoad()
        interactivePopGestureRecognizer?.delegate = self
    }

    public func gestureRecognizerShouldBegin(_ gestureRecognizer: UIGestureRecognizer) -> Bool {
        viewControllers.count > 1
    }
}
