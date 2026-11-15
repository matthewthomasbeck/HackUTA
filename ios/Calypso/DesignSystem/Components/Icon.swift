import SwiftUI

/// SF Symbol standing in for a Figma `Icon / *` (15:60–15:88): a square box (32pt default) with a
/// round, medium-weight glyph. The box scales with Dynamic Type relative to `textStyle`.
struct CalypsoIcon: View {
    let systemName: String
    @ScaledMetric private var box: CGFloat

    init(_ systemName: String, size: CGFloat = 32, relativeTo textStyle: Font.TextStyle = .body) {
        self.systemName = systemName
        _box = ScaledMetric(wrappedValue: size, relativeTo: textStyle)
    }

    var body: some View {
        Image(systemName: systemName)
            .font(.system(size: box * 0.72, weight: .medium))
            .frame(width: box, height: box)
            .accessibilityHidden(true)
    }
}
