import SwiftUI

/// Card container from Figma `Moment Card` (18:225): padding 20, Card fill, 2pt Periwinkle Mist border, radius 24.
/// Dialog cards (Figma 20:727) pass `cornerRadius: 32, bordered: false`.
struct PaperCard<Content: View>: View {
    let content: Content
    let horizontalPadding: CGFloat
    let verticalPadding: CGFloat
    let cornerRadius: CGFloat
    let bordered: Bool

    /// Figma `Permission / *` cards use 16 × 12 padding; everything else uses the default 20.
    init(horizontalPadding: CGFloat = 20, verticalPadding: CGFloat = 20, cornerRadius: CGFloat = 24,
         bordered: Bool = true, @ViewBuilder content: () -> Content) {
        self.horizontalPadding = horizontalPadding
        self.verticalPadding = verticalPadding
        self.cornerRadius = cornerRadius
        self.bordered = bordered
        self.content = content()
    }

    var body: some View {
        content
            .padding(.horizontal, horizontalPadding)
            .padding(.vertical, verticalPadding)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color.card, in: RoundedRectangle(cornerRadius: cornerRadius))
            .overlay {
                if bordered {
                    RoundedRectangle(cornerRadius: cornerRadius).strokeBorder(Color.periwinkleMist, lineWidth: 2)
                }
            }
    }
}

extension View {
    func paperCard() -> some View {
        PaperCard { self }
    }
}

#Preview {
    VStack(spacing: 16) {
        PaperCard {
            Text("A paper card").calypsoFont(.headline).foregroundStyle(Color.ink)
        }
        Text("Via modifier").calypsoFont(.body).foregroundStyle(Color.ink).paperCard()
    }
    .padding(24)
    .background(Color.paper)
}
