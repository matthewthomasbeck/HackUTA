import SwiftUI

/// Figma `Back Button` (15:96): chevron + label in Periwinkle Deep, 64pt tall, hugs width.
struct BackButton: View {
    let label: String
    let action: () -> Void

    init(_ label: String = "Back", action: @escaping () -> Void) {
        self.label = label
        self.action = action
    }

    var body: some View {
        Button(action: action) {
            HStack(spacing: 4) {
                CalypsoIcon("chevron.left")
                Text(label).calypsoFont(.bodyStrong)
            }
            .foregroundStyle(Color.periwinkleDeep)
            .padding(.trailing, 12)
            .frame(minHeight: 64)
            .contentShape(Rectangle())
        }
        .buttonStyle(PressableStyle())
        .accessibilityLabel(label)
    }
}

#Preview {
    VStack(alignment: .leading) {
        BackButton {}
        BackButton("People") {}
    }
    .padding(24)
    .frame(maxWidth: .infinity, alignment: .leading)
    .background(Color.paper)
}
