import SwiftUI

/// Bottom-sheet chrome shared by the Calling and details sheets (Figma 59:500, 59:550): Paper, top corners 32,
/// padding 16 top / 24 sides / 40 bottom, 20pt gap, and a drawn 48×6 Periwinkle Mist handle in place of the system
/// drag indicator. The sheet is as tall as its content (so it follows Dynamic Type) and scrolls if that's too tall.
struct PaperSheet<Content: View>: View {
    let content: Content
    @State private var contentHeight: CGFloat = 400

    init(@ViewBuilder content: () -> Content) {
        self.content = content()
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                Capsule()
                    .fill(Color.periwinkleMist)
                    .frame(width: 48, height: 6)
                    .frame(maxWidth: .infinity)
                    .accessibilityHidden(true)
                content
            }
            .padding(.horizontal, 24)
            .padding(.top, 16)
            .padding(.bottom, 40)
            .onGeometryChange(for: CGFloat.self) { $0.size.height } action: { contentHeight = $0 }
        }
        .scrollBounceBehavior(.basedOnSize)
        .background(Color.paper.ignoresSafeArea())
        .presentationDetents([.height(contentHeight)])
        .presentationDragIndicator(.hidden)
        .presentationBackground(Color.paper)
        .presentationCornerRadius(32)
    }
}
