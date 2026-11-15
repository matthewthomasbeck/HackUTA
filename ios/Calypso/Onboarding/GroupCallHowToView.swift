import SwiftUI

/// "Start a group FaceTime". No Figma frame; styled like Permissions (20:1173): numbered step cards.
struct GroupCallHowToView: View {
    var onBack: () -> Void
    var onNext: () -> Void

    private let steps = [
        "Open FaceTime and tap New FaceTime",
        "Add Mom and Calypso⁻¹",
        "Tap Video",
    ]

    var body: some View {
        OnboardingScaffold(step: .groupCall, onBack: onBack) {
            VStack(alignment: .leading, spacing: 8) {
                OnboardingHeading(title: "Start a group FaceTime", message: nil)
                    .padding(.top, 20) // clears the Back button and the gull
                    .overlay(alignment: .topTrailing) {
                        // Stands on the title line, beside the back button, like the Permissions gull.
                        Mascot(pose: .presenting, size: .s, shadow: true)
                            .alignmentGuide(.top) { $0[.bottom] }
                    }
                    .padding(.bottom, 4)
                ForEach(Array(steps.enumerated()), id: \.offset) { index, step in
                    StepCard(number: index + 1, text: step)
                }
                Text("Or text Calypso⁻¹: “call Mom with me”")
                    .calypsoFont(.callout)
                    .foregroundStyle(Color.inkSoft)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.top, 4)
                Spacer(minLength: 24)
                CalypsoButton("Next", action: onNext)
            }
            .padding(.horizontal, 24)
            .frame(maxHeight: .infinity)
        }
    }
}

/// Apricot Cream number disc with an Ink numeral, then the Headline step text.
private struct StepCard: View {
    let number: Int
    let text: String
    @ScaledMetric(relativeTo: .title2) private var disc: CGFloat = 64
    @Environment(\.dynamicTypeSize) private var typeSize

    var body: some View {
        // The text wraps, so `ViewThatFits` would always pick the stack; switch on AX sizes instead.
        let layout = typeSize.isAccessibilitySize
            ? AnyLayout(VStackLayout(alignment: .leading, spacing: 12))
            : AnyLayout(HStackLayout(spacing: 16))
        PaperCard(horizontalPadding: 16, verticalPadding: 12) {
            layout { numberDisc; label }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Step \(number): \(text)")
    }

    private var numberDisc: some View {
        Text("\(number)")
            .calypsoFont(.headline)
            .foregroundStyle(Color.ink)
            .frame(width: disc, height: disc)
            .background(Color.apricotCream, in: Circle())
    }

    private var label: some View {
        Text(text)
            .calypsoFont(.headline)
            .foregroundStyle(Color.ink)
            .fixedSize(horizontal: false, vertical: true)
            .frame(maxWidth: .infinity, alignment: .leading)
    }
}

#Preview {
    GroupCallHowToView(onBack: {}, onNext: {})
}

#Preview("AX5") {
    GroupCallHowToView(onBack: {}, onNext: {}).dynamicTypeSize(.accessibility5)
}
