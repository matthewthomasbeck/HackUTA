import SwiftUI

extension View {
    /// Keeps the status bar on Paper: no system scroll-edge blur on iOS 26, and a solid Paper strip
    /// over the top safe area so scrolled content never shows through.
    func paperTopEdge() -> some View {
        modifier(PaperTopEdge())
    }
}

private struct PaperTopEdge: ViewModifier {
    func body(content: Content) -> some View {
        Group {
            if #available(iOS 26.0, *) {
                content.scrollEdgeEffectHidden(true, for: .top)
            } else {
                content
            }
        }
        .overlay(alignment: .top) {
            GeometryReader { proxy in
                Color.paper
                    .frame(height: proxy.safeAreaInsets.top)
                    .ignoresSafeArea(edges: .top)
            }
            .allowsHitTesting(false)
            .accessibilityHidden(true)
        }
    }
}
