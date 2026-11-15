import SwiftUI

/// Figma `Calm Message` (18:226): illustration panel (Mascot on calm waves over a sand shore, radius 24, clipped),
/// Title, Body (Ink Soft, hidden when empty), optional Secondary button. Used for quiet days and errors; never red.
/// `scene: false` drops the shore panel and shows the mascot alone at size S with its shadow (Figma 20:1097).
struct CalmMessage: View {
    let pose: MascotPose
    let title: String
    let message: String
    let buttonTitle: String?
    let scene: Bool
    let action: (() -> Void)?

    init(pose: MascotPose, title: String, message: String, buttonTitle: String? = nil, scene: Bool = true,
         action: (() -> Void)? = nil) {
        self.pose = pose
        self.title = title
        self.message = message
        self.buttonTitle = buttonTitle
        self.scene = scene
        self.action = action
    }

    var body: some View {
        VStack(spacing: 16) {
            if scene {
                illustration
            } else {
                Mascot(pose: pose, size: .s, shadow: true)
            }
            Text(title)
                .calypsoFont(.title)
                .foregroundStyle(Color.ink)
                .multilineTextAlignment(.center)
                .accessibilityAddTraits(.isHeader)
            if !message.isEmpty {
                Text(message)
                    .calypsoFont(.body)
                    .foregroundStyle(Color.inkSoft)
                    .multilineTextAlignment(.center)
            }
            if let buttonTitle, let action {
                CalypsoButton(buttonTitle, kind: .secondary, action: action)
            }
        }
        .frame(maxWidth: .infinity)
    }

    /// Quiet Shore (14:42), 240pt tall: calm waves from 150pt down, a sand shore, the mascot resting on it.
    private var illustration: some View {
        // Layers are overlays so the oversized shore and wave art never widen the layout.
        Color.clear
            .frame(maxWidth: .infinity)
            .frame(height: 240)
            .overlay(alignment: .bottomLeading) {
                DecorationImage(.wavesCalm)
                    .scaledToFill()
                    .frame(height: 110)
                    .offset(y: 20)
            }
            .overlay(alignment: .bottom) {
                GeometryReader { geo in
                    Ellipse()
                        .fill(Color.apricotCream)
                        .frame(width: geo.size.width * 1.3, height: 120)
                        .position(x: geo.size.width / 2, y: geo.size.height - 46 + 60)
                }
            }
            .overlay(alignment: .bottom) {
                Mascot(pose: pose, size: .l)
                    .padding(.bottom, 8)
            }
            .clipShape(RoundedRectangle(cornerRadius: 24))
            .accessibilityHidden(true)
    }
}

#Preview("Quiet day") {
    CalmMessage(pose: .resting, title: "A quiet day",
                message: "Nothing new was recorded. That’s okay. Rest days matter.",
                buttonTitle: "Look at another day") {}
        .padding(24)
        .background(Color.paper)
}

#Preview("Error") {
    CalmMessage(pose: .thinking, title: "We couldn’t load this day right now.",
                message: "Check your connection, then try again.",
                buttonTitle: "Try again") {}
        .padding(24)
        .background(Color.paper)
}
