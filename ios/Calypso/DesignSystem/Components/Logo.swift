import SwiftUI

/// Figma `Logo` Shape=Circle (39:384). Decorative unless given a label.
struct Logo: View {
    let size: CGFloat
    let label: String?

    init(size: CGFloat = 112, label: String? = nil) {
        self.size = size
        self.label = label
    }

    var body: some View {
        let image = Image("Logo")
            .resizable()
            .aspectRatio(contentMode: .fit)
            .frame(width: size, height: size)
        if let label {
            image.accessibilityLabel(label)
        } else {
            image.accessibilityHidden(true)
        }
    }
}

#Preview {
    HStack(spacing: 24) {
        Logo()
        Logo(size: 64, label: "Calypso⁻¹")
    }
    .padding(24)
    .background(Color.paper)
}
