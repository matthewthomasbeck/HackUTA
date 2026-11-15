import SwiftUI

/// The person page's Call block (Figma 59:368 / no number 59:377): a full-width button with `Icon / Video` and an
/// 8pt-gap hint under it. With a number it's Primary "FaceTime <name>"; without one it's a Card button with a 2pt
/// dashed Ink Soft outline, "Add <name>’s number". `note` (a calm Ink Soft line, never red) replaces the hint when
/// Messages can't be used on this phone.
struct CallBlock: View {
    let name: String
    let hasNumber: Bool
    var note: String?
    let onCall: () -> Void
    let onAddNumber: () -> Void

    var body: some View {
        VStack(spacing: 8) {
            if hasNumber {
                Button(action: onCall) { label("FaceTime \(name)") }
                    .buttonStyle(CalypsoButtonStyle(.primary))
            } else {
                Button(action: onAddNumber) { label("Add \(name)’s number") }
                    .buttonStyle(DashedCardButtonStyle())
            }
            Text(note ?? hint)
                .calypsoFont(.callout)
                .foregroundStyle(Color.inkSoft)
                .multilineTextAlignment(.center)
                .frame(maxWidth: .infinity)
        }
    }

    private var hint: String {
        hasNumber ? "Calypso⁻¹ joins the call to help" : "Add a number to FaceTime \(name)"
    }

    private func label(_ title: String) -> some View {
        HStack(spacing: 12) {
            CalypsoIcon(.video)
            Text(title)
        }
    }
}

/// The no-number Call button: Card fill, 2pt dashed Ink Soft outline, Ink Body Strong, 72pt, radius 24. Touch-down
/// feedback matches `CalypsoButtonStyle` (scale 0.97, no animation under Reduce Motion).
private struct DashedCardButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        DashedCardButtonBody(label: configuration.label, isPressed: configuration.isPressed)
    }
}

private struct DashedCardButtonBody<Label: View>: View {
    let label: Label
    let isPressed: Bool
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        let shape = RoundedRectangle(cornerRadius: 24)
        label
            .calypsoFont(.bodyStrong)
            .multilineTextAlignment(.center)
            .foregroundStyle(Color.ink)
            .padding(.horizontal, 24)
            .padding(.vertical, 8)
            .frame(maxWidth: .infinity, minHeight: 72)
            .background(shape.fill(isPressed ? Color(hex: 0xEEF0FB) : .card))
            .overlay(shape.strokeBorder(Color.inkSoft, style: StrokeStyle(lineWidth: 2, dash: [8, 6])))
            .contentShape(shape)
            .scaleEffect(isPressed ? 0.97 : 1)
            .animation(reduceMotion ? nil : .spring(response: 0.25, dampingFraction: 1), value: isPressed)
    }
}

#Preview {
    VStack(spacing: 24) {
        CallBlock(name: "Sarah", hasNumber: true, onCall: {}, onAddNumber: {})
        CallBlock(name: "Sarah", hasNumber: false, onCall: {}, onAddNumber: {})
        CallBlock(name: "Sarah", hasNumber: true, note: "Messages isn’t available on this phone.",
                  onCall: {}, onAddNumber: {})
    }
    .padding(24)
    .background(Color.paper)
}
