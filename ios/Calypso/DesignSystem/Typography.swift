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

    private var fontName: String {
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
