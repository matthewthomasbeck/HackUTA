import SwiftUI

/// Figma "You’re all set" (39:440): the gull celebrates on the shore.
struct AllSetView: View {
    var onDone: () -> Void

    var body: some View {
        OnboardingScaffold(step: .allSet, onBack: nil, bleedsTop: true) {
            OnboardingScene(height: 430) { s in
                DecorationImage(.seascapeShore)
                    .onCanvas(x: 0, y: 70, width: 393, height: 340, scale: s)
                Mascot(pose: .celebrating, size: .custom(MascotSize.xl.width * s), shadow: true)
                    // Figma's 285pt box overlaps the shadow onto the feet; ours stacks it, so lift the gull to match.
                    .offset(x: 40 * s, y: 111 * s)
            }
            VStack(alignment: .leading, spacing: 12) {
                OnboardingHeading(title: "You’re all set",
                                  message: "Calypso⁻¹ will gently help you remember your day and the people you love.",
                                  display: true)
                Spacer(minLength: 24)
                CalypsoButton("Open Today", action: onDone)
            }
            .padding(.horizontal, 24)
            .padding(.top, 8)
            .frame(maxHeight: .infinity)
        }
    }
}

#Preview {
    AllSetView {}
}
