import SwiftUI

/// Card container from Figma `Moment Card` (18:225): padding 20, Card fill, 2pt Periwinkle Mist border, radius 24.
struct PaperCard<Content: View>: View {
    let content: Content

    init(@ViewBuilder content: () -> Content) {
        self.content = content()
    }

    var body: some View {
        content
            .padding(20)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color.card, in: RoundedRectangle(cornerRadius: 24))
            .overlay(RoundedRectangle(cornerRadius: 24).strokeBorder(Color.periwinkleMist, lineWidth: 2))
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
