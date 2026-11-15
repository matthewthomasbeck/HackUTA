import SwiftUI

/// Figma "Meet your companion" (20:455): the gull presents itself on a rock by the calm waves.
struct MeetCompanionView: View {
    var onBack: () -> Void
    var onNext: () -> Void

    var body: some View {
        OnboardingScaffold(step: .companion, onBack: onBack, bleedsTop: true) {
            OnboardingScene(height: 400) { s in
                DecorationImage(.wavesCalm)
                    .onCanvas(x: 0, y: 290, width: 393, height: 110, scale: s)
                Image(Decoration.shoreRock.rawValue)
                    .resizable()
                    .onCanvas(x: 46, y: 282, width: 300, height: 110, scale: s)
                Mascot(pose: .presenting, size: .custom(MascotSize.l.width * s), shadow: true)
                    .offset(x: 96 * s, y: 136 * s)
                DecorationImage(.oliveBranch)
                    .onCanvas(x: 245, y: 30, width: 126, height: 63, scale: s)
            }
            VStack(alignment: .leading, spacing: 12) {
                OnboardingHeading(title: "Hi, I’m your Calypso⁻¹ gull",
                                  message: "I’ll help you remember your day and the people you love. You can FaceTime me anytime.")
                Spacer(minLength: 24)
                CalypsoButton("Next", action: onNext)
            }
            .padding(.horizontal, 24)
            .padding(.top, 8)
            .frame(maxHeight: .infinity)
        }
    }
}

#Preview {
    MeetCompanionView(onBack: {}, onNext: {})
}
