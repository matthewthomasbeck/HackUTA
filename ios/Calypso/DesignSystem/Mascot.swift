import SwiftUI

enum MascotPose: String, CaseIterable {
    case wave, presenting, peek, thinking, holdingPhoto, resting, walking, sailing, lantern, celebrating

    var assetName: String { "Gull" + rawValue.prefix(1).uppercased() + rawValue.dropFirst() }
}

enum MascotSize {
    case xl, l, m, s, custom(CGFloat)

    var width: CGFloat {
        switch self {
        case .xl: 280
        case .l: 200
        case .m: 120
        case .s: 72
        case .custom(let w): w
        }
    }
}

/// Decorative gull. Never animated; hidden from VoiceOver.
struct Mascot: View {
    let pose: MascotPose
    let size: MascotSize
    var shadow: Bool = false

    init(pose: MascotPose, size: MascotSize, shadow: Bool = false) {
        self.pose = pose
        self.size = size
        self.shadow = shadow
    }

    var body: some View {
        VStack(spacing: -size.width * 0.04) {
            Image(pose.assetName)
                .resizable()
                .aspectRatio(contentMode: .fit)
                .frame(width: size.width)
            if shadow {
                Ellipse()
                    .fill(Color(hex: 0xD9DAEC))
                    .frame(width: size.width * 0.6, height: size.width * 0.07)
            }
        }
        .accessibilityHidden(true)
    }
}
