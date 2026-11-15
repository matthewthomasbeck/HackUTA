import SwiftUI

/// The Figma `Icon / *` glyphs (15:60–15:88), exported as template vector PDFs (32×32 frame, 2.5pt round strokes).
/// Their color comes from `foregroundStyle`.
enum CalypsoGlyph: String {
    case today = "IconToday"
    case people = "IconPeople"
    case account = "IconAccount"
    case chevronLeft = "IconChevronLeft"
    /// `Icon / Chevron Left` mirrored; Figma has no separate right chevron.
    case chevronRight
    case pin = "IconPin"
    case soundWave = "IconSoundWave"
    case feather = "IconFeather"
    case photo = "IconPhoto"
    /// `Icon / Video` (58:323): FaceTime, on the person page's Call button.
    case video = "IconVideo"

    var image: Image {
        switch self {
        case .chevronRight: Image(CalypsoGlyph.chevronLeft.rawValue).renderingMode(.template)
        default: Image(rawValue).renderingMode(.template)
        }
    }

    var isMirrored: Bool { self == .chevronRight }
}

/// A square icon box (32pt default) that scales with Dynamic Type relative to `textStyle`. Draws a Figma glyph,
/// or an SF Symbol for the few glyphs Figma doesn't define (permission and checkmark icons in onboarding).
struct CalypsoIcon: View {
    private enum Source { case glyph(CalypsoGlyph), symbol(String) }

    private let source: Source
    @ScaledMetric private var box: CGFloat

    init(_ glyph: CalypsoGlyph, size: CGFloat = 32, relativeTo textStyle: Font.TextStyle = .body) {
        source = .glyph(glyph)
        _box = ScaledMetric(wrappedValue: size, relativeTo: textStyle)
    }

    init(_ systemName: String, size: CGFloat = 32, relativeTo textStyle: Font.TextStyle = .body) {
        source = .symbol(systemName)
        _box = ScaledMetric(wrappedValue: size, relativeTo: textStyle)
    }

    var body: some View {
        Group {
            switch source {
            case .glyph(let glyph):
                glyph.image
                    .resizable()
                    .scaledToFit()
                    .scaleEffect(x: glyph.isMirrored ? -1 : 1, y: 1)
            case .symbol(let name):
                Image(systemName: name)
                    .font(.system(size: box * 0.72, weight: .medium))
            }
        }
        .frame(width: box, height: box)
        .accessibilityHidden(true)
    }
}

#Preview {
    HStack(spacing: 12) {
        ForEach([CalypsoGlyph.today, .people, .account, .chevronLeft, .chevronRight, .pin, .soundWave, .feather,
                 .photo, .video], id: \.self) { glyph in
            CalypsoIcon(glyph)
        }
    }
    .foregroundStyle(Color.ink)
    .padding(24)
    .background(Color.paper)
}
