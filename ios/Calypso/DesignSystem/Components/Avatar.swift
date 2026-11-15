import SwiftUI

/// Figma `Avatar` (16:78), sizes 64 and 160.
/// Known: the face photo (or an Apricot Cream disc with a silhouette) inside a white ring.
/// Unknown: Periwinkle Mist disc, dashed Ink Soft outline, leaf glyph. Never a guessed face.
struct Avatar: View {
    let urlString: String?
    let isKnown: Bool
    let size: CGFloat

    init(urlString: String?, isKnown: Bool, size: CGFloat) {
        self.urlString = urlString
        self.isKnown = isKnown
        self.size = size
    }

    private var ring: CGFloat { max(3, size / 32) }

    var body: some View {
        Group {
            if isKnown {
                known
            } else {
                AvatarUnknownDisc(size: size)
            }
        }
        .frame(width: size, height: size)
        .accessibilityHidden(true)
    }

    private var known: some View {
        ZStack {
            AvatarSilhouette()
            if let urlString, let url = URL(string: urlString) {
                AsyncImage(url: url) { phase in
                    if case .success(let image) = phase {
                        image.resizable().scaledToFill()
                    }
                }
            }
        }
        .frame(width: size, height: size)
        .clipShape(Circle())
        .overlay(Circle().strokeBorder(Color.white, lineWidth: ring))
    }
}

/// Apricot Cream disc with a head-and-shoulders silhouette (Helper/Photo Glyph tint).
struct AvatarSilhouette: View {
    var body: some View {
        GeometryReader { geo in
            let s = geo.size.width
            ZStack {
                Color.apricotCream
                Circle()
                    .fill(Color.photoGlyph)
                    .frame(width: s * 0.34, height: s * 0.34)
                    .position(x: s / 2, y: s * 0.38)
                Ellipse()
                    .fill(Color.photoGlyph)
                    .frame(width: s * 0.74, height: s * 0.5)
                    .position(x: s / 2, y: s * 0.92)
            }
        }
        .aspectRatio(1, contentMode: .fit)
    }
}

/// Unknown-person disc: Periwinkle Mist, dashed Ink Soft outline, leaf glyph in Periwinkle Deep.
struct AvatarUnknownDisc: View {
    let size: CGFloat
    var outlined: Bool = true

    var body: some View {
        ZStack {
            Circle().fill(Color.periwinkleMist)
            if outlined {
                Circle().strokeBorder(Color.inkSoft, style: StrokeStyle(lineWidth: size >= 100 ? 2.5 : 2, dash: [7, 5]))
            }
            Image(systemName: "leaf")
                .font(.system(size: size * (outlined ? 0.36 : 0.4), weight: .semibold))
                .foregroundStyle(Color.periwinkleDeep)
        }
        .frame(width: size, height: size)
    }
}

#Preview {
    HStack(spacing: 24) {
        Avatar(urlString: nil, isKnown: true, size: 64)
        Avatar(urlString: nil, isKnown: true, size: 160)
        Avatar(urlString: nil, isKnown: false, size: 64)
        Avatar(urlString: nil, isKnown: false, size: 160)
    }
    .padding(24)
    .background(Color.paper)
}
