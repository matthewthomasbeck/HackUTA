import SwiftUI

enum CalypsoButtonKind {
    case primary, secondary, quiet
}

/// Figma `Button` (15:95). Primary/Secondary 72pt, Quiet 64pt; full width, radius 24.
/// Pressed: scale 0.97 plus a slightly darker fill, applied on touch-down. No animation under Reduce Motion.
struct CalypsoButtonStyle: ButtonStyle {
    let kind: CalypsoButtonKind
    let horizontalPadding: CGFloat

    init(_ kind: CalypsoButtonKind, horizontalPadding: CGFloat = 24) {
        self.kind = kind
        self.horizontalPadding = horizontalPadding
    }

    func makeBody(configuration: Configuration) -> some View {
        CalypsoButtonBody(kind: kind, horizontalPadding: horizontalPadding,
                          label: configuration.label, isPressed: configuration.isPressed)
    }
}

private struct CalypsoButtonBody<Label: View>: View {
    let kind: CalypsoButtonKind
    let horizontalPadding: CGFloat
    let label: Label
    let isPressed: Bool
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    private static var deepPressed: Color { Color(hex: 0x323C85) }
    private static var cardPressed: Color { Color(hex: 0xEEF0FB) }

    var body: some View {
        label
            .calypsoFont(.bodyStrong)
            .underline(kind == .quiet)
            .multilineTextAlignment(.center)
            .foregroundStyle(foreground)
            .padding(.horizontal, horizontalPadding)
            .padding(.vertical, 8)
            .frame(maxWidth: .infinity, minHeight: kind == .quiet ? 64 : 72)
            .background(background)
            .contentShape(RoundedRectangle(cornerRadius: 24))
            .scaleEffect(isPressed ? 0.97 : 1)
            .animation(reduceMotion ? nil : .spring(response: 0.25, dampingFraction: 1), value: isPressed)
    }

    private var foreground: Color {
        switch kind {
        case .primary: .white
        case .secondary: .ink
        case .quiet: isPressed ? Self.deepPressed : .periwinkleDeep
        }
    }

    @ViewBuilder private var background: some View {
        switch kind {
        case .primary:
            RoundedRectangle(cornerRadius: 24).fill(isPressed ? Self.deepPressed : .periwinkleDeep)
        case .secondary:
            RoundedRectangle(cornerRadius: 24)
                .fill(isPressed ? Self.cardPressed : .card)
                .overlay(RoundedRectangle(cornerRadius: 24).strokeBorder(Color.ink, lineWidth: 2))
        case .quiet:
            Color.clear
        }
    }
}

struct CalypsoButton: View {
    let title: String
    let kind: CalypsoButtonKind
    let systemImage: String?
    let action: () -> Void

    init(_ title: String, kind: CalypsoButtonKind = .primary, systemImage: String? = nil,
         action: @escaping () -> Void) {
        self.title = title
        self.kind = kind
        self.systemImage = systemImage
        self.action = action
    }

    var body: some View {
        Button(action: action) {
            if let systemImage {
                Label(title, systemImage: systemImage)
            } else {
                Text(title)
            }
        }
        .buttonStyle(CalypsoButtonStyle(kind))
    }
}

/// Touch-down feedback for small text controls (Back, tabs): scale 0.97, no animation under Reduce Motion.
struct PressableStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        PressableBody(label: configuration.label, isPressed: configuration.isPressed)
    }
}

private struct PressableBody<Label: View>: View {
    let label: Label
    let isPressed: Bool
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        label
            .opacity(isPressed ? 0.75 : 1)
            .scaleEffect(isPressed ? 0.97 : 1)
            .animation(reduceMotion ? nil : .spring(response: 0.25, dampingFraction: 1), value: isPressed)
    }
}

#Preview("Buttons") {
    VStack(spacing: 16) {
        CalypsoButton("Continue") {}
        CalypsoButton("Continue", kind: .secondary) {}
        CalypsoButton("Continue", kind: .quiet) {}
        CalypsoButton("Add to Contacts", systemImage: "person.crop.circle.badge.plus") {}
    }
    .padding(24)
    .background(Color.paper)
}

#Preview("Buttons AX5") {
    VStack(spacing: 16) {
        CalypsoButton("Look at another day", kind: .secondary) {}
        CalypsoButton("Continue") {}
    }
    .padding(24)
    .background(Color.paper)
    .dynamicTypeSize(.accessibility5)
}
