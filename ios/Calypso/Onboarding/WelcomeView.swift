import SwiftUI

/// Figma "Welcome" (20:329): the gull sails home across the seascape.
struct WelcomeView: View {
    var onNext: () -> Void

    var body: some View {
        OnboardingScaffold(step: .welcome, onBack: nil, bleedsTop: true) {
            // Canvas starts at the top of the screen; the seascape art sits 24pt down, as in Figma.
            OnboardingScene(height: 364) { s in
                // The boat sails behind the waves, so the gull is drawn first.
                Mascot(pose: .sailing, size: .custom(MascotSize.l.width * s))
                    .offset(x: 100 * s, y: 124 * s)
                DecorationImage(.seascape)
                    .onCanvas(x: 0, y: 24, width: 393, height: 340, scale: s)
                Logo(size: 112 * s)
                    .offset(x: 265 * s, y: 56 * s)
            }
            VStack(alignment: .leading, spacing: 12) {
                OnboardingHeading(title: "Welcome to Calypso⁻¹",
                                  message: "Every journey leads home. Let’s bring you home to your memories.",
                                  display: true)
                Spacer(minLength: 24)
                CalypsoButton("Get started", action: onNext)
            }
            .padding(.horizontal, 24)
            .padding(.top, 12)
            .frame(maxHeight: .infinity)
        }
    }
}

#Preview {
    WelcomeView {}
}

#Preview("AX5") {
    WelcomeView {}.dynamicTypeSize(.accessibility5)
}
