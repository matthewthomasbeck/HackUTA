import SwiftUI

/// Figma `Person Chip` (16:92). nil name renders the "Someone new" chip; never a guessed name.
/// 64pt tall; grows taller (never truncates) at large Dynamic Type sizes.
struct PersonChip: View {
    let name: String?

    init(name: String?) {
        self.name = name
    }

    var body: some View {
        // Stacks the name under the avatar when the row doesn't fit (AX sizes), so names never break mid-word.
        ViewThatFits(in: .horizontal) {
            HStack(spacing: 12) { avatar; label }
                .padding(2)
                .padding(.trailing, 22)
            VStack(alignment: .leading, spacing: 4) { avatar; label }
                .padding(.horizontal, 20)
                .padding(.vertical, 12)
        }
        .frame(minHeight: 64)
        .background(background)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(name ?? "Someone new")
    }

    @ViewBuilder private var avatar: some View {
        if name != nil {
            Avatar(urlString: nil, isKnown: true, size: 60)
        } else {
            AvatarUnknownDisc(size: 60, outlined: false)
        }
    }

    private var label: some View {
        Text(name ?? "Someone new")
            .calypsoFont(.bodyStrong)
            .foregroundStyle(Color.ink)
            .fixedSize(horizontal: false, vertical: true)
    }

    @ViewBuilder private var background: some View {
        let shape = RoundedRectangle(cornerRadius: 32)
        if name != nil {
            shape.fill(Color.card).overlay(shape.strokeBorder(Color.periwinkleMist, lineWidth: 2))
        } else {
            shape.fill(Color.periwinkleMist)
                .overlay(shape.strokeBorder(Color.inkSoft, style: StrokeStyle(lineWidth: 2, dash: [7, 5])))
        }
    }
}

#Preview {
    VStack(alignment: .leading, spacing: 12) {
        PersonChip(name: "Sarah")
        PersonChip(name: nil)
    }
    .padding(24)
    .background(Color.paper)
}

#Preview("AX5") {
    VStack(alignment: .leading, spacing: 12) {
        PersonChip(name: "Grandma Rosalind")
        PersonChip(name: nil)
    }
    .padding(24)
    .background(Color.paper)
    .dynamicTypeSize(.accessibility5)
}
