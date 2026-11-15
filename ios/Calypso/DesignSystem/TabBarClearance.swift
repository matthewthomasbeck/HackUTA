import SwiftUI

/// Height of the custom tab bar above the home indicator, published by `HomeView`.
///
/// SwiftUI's `TabView` and `NavigationStack` are UIKit containers and don't pass a `safeAreaInset` applied
/// outside them down to their pages, so each scrolling screen reserves this space itself via `tabBarClearance()`.
private struct TabBarClearanceKey: EnvironmentKey {
    static let defaultValue: CGFloat = 0
}

extension EnvironmentValues {
    var tabBarClearance: CGFloat {
        get { self[TabBarClearanceKey.self] }
        set { self[TabBarClearanceKey.self] = newValue }
    }
}

extension View {
    /// Keeps the end of a scroll view clear of the tab bar. A no-op outside `HomeView`.
    func tabBarClearance() -> some View {
        modifier(TabBarClearance())
    }
}

private struct TabBarClearance: ViewModifier {
    @Environment(\.tabBarClearance) private var clearance

    func body(content: Content) -> some View {
        content.safeAreaInset(edge: .bottom, spacing: 0) {
            Color.clear.frame(height: clearance)
        }
    }
}

/// Reports the tab bar's height so `HomeView` can publish it as `tabBarClearance`.
struct TabBarHeightKey: PreferenceKey {
    static let defaultValue: CGFloat = 0
    static func reduce(value: inout CGFloat, nextValue: () -> CGFloat) { value = max(value, nextValue()) }
}
