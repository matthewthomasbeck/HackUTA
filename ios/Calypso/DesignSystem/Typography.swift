import SwiftUI
import UIKit

enum CalypsoTextStyle: CaseIterable {
    case display, title, headline, body, bodyStrong, callout, caption

    var size: CGFloat {
        switch self {
        case .display: 44
        case .title: 34
        case .headline: 28
        case .body, .bodyStrong: 24
        case .callout: 22
        case .caption: 20
        }
    }

    var leading: CGFloat {
        switch self {
        case .display: 52
        case .title: 42
        case .headline: 36
        case .body, .bodyStrong: 32
        case .callout: 30
        case .caption: 26
        }
    }

    /// Extra space between lines so the line pitch matches the Figma leading. Nunito and Fraunces already
    /// have a natural line height at or above the Figma leading, so this is usually 0.
    var extraLeading: CGFloat {
        let natural = UIFont(name: fontName, size: size)?.lineHeight ?? size
        return max(0, leading - natural)
    }

    var fontName: String {
        switch self {
        case .display, .title: "Fraunces-SemiBold"
        case .headline, .bodyStrong: "Nunito-Bold"
        case .body, .callout: "Nunito-Regular"
        case .caption: "Nunito-SemiBold"
        }
    }

    var relativeTo: Font.TextStyle {
        switch self {
        case .display: .largeTitle
        case .title: .title
        case .headline: .title2
        case .body, .bodyStrong: .body
        case .callout: .callout
        case .caption: .footnote
        }
    }

    var font: Font { .custom(fontName, size: size, relativeTo: relativeTo) }
}

private struct CalypsoFontModifier: ViewModifier {
    let style: CalypsoTextStyle
    // Scales the extra leading with Dynamic Type, same as the font itself.
    @ScaledMetric private var extra: CGFloat

    init(style: CalypsoTextStyle) {
        self.style = style
        _extra = ScaledMetric(wrappedValue: style.extraLeading, relativeTo: style.relativeTo)
    }

    func body(content: Content) -> some View {
        content.font(style.font).lineSpacing(extra)
    }
}

extension View {
    func calypsoFont(_ style: CalypsoTextStyle) -> some View {
        modifier(CalypsoFontModifier(style: style))
    }
}

extension CalypsoTextStyle {
    var uiTextStyle: UIFont.TextStyle {
        switch relativeTo {
        case .largeTitle: .largeTitle
        case .title: .title1
        case .title2: .title2
        case .callout: .callout
        case .footnote: .footnote
        default: .body
        }
    }

    /// The Dynamic Type–scaled UIFont for this style, for measuring text.
    func scaledUIFont(for dynamicTypeSize: DynamicTypeSize) -> UIFont {
        let base = UIFont(name: fontName, size: size) ?? .systemFont(ofSize: size)
        let traits = UITraitCollection(preferredContentSizeCategory: UIContentSizeCategory(dynamicTypeSize))
        return UIFontMetrics(forTextStyle: uiTextStyle).scaledFont(for: base, compatibleWith: traits)
    }
}

/// Text that wraps only between words. If its longest word is wider than the space it gets (huge Dynamic Type on
/// a narrow column, e.g. "Yesterday" or "November" at AX5), the whole text shrinks just enough for that word to
/// fit on one line, instead of breaking it mid-word. At normal sizes it renders exactly like `calypsoFont(style)`.
/// Join words that must stay together (a chevron and its label) with a non-breaking space.
struct WordSafeText: View {
    let text: String
    let style: CalypsoTextStyle
    let alignment: Alignment

    @Environment(\.dynamicTypeSize) private var dynamicTypeSize
    @State private var width: CGFloat = 0

    init(_ text: String, style: CalypsoTextStyle, alignment: Alignment = .leading) {
        self.text = text
        self.style = style
        self.alignment = alignment
    }

    static func scale(text: String, font: UIFont, availableWidth: CGFloat) -> CGFloat {
        guard availableWidth > 0 else { return 1 }
        let widest = text.split(whereSeparator: { $0 == " " || $0 == "\n" })
            .map { (String($0) as NSString).size(withAttributes: [.font: font]).width }
            .max() ?? 0
        guard widest > availableWidth else { return 1 }
        return max(0.4, (availableWidth - 2) / widest)
    }

    private var scale: CGFloat {
        Self.scale(text: text, font: style.scaledUIFont(for: dynamicTypeSize), availableWidth: width)
    }

    var body: some View {
        Text(text)
            .font(.custom(style.fontName, size: style.size * scale, relativeTo: style.relativeTo))
            .calypsoFont(style)
            .frame(maxWidth: .infinity, alignment: alignment)
            .onGeometryChange(for: CGFloat.self, of: { $0.size.width }, action: { width = $0 })
    }
}
