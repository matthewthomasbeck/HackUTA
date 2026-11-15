import SwiftUI

/// Previous / next day buttons (Today screen, Figma 20:489). Previous is Secondary "‹ <label>".
/// Next is Secondary "<label> ›" when enabled; when disabled it's Ink Soft text on Paper with a dashed
/// Periwinkle outline, no chevron and no opacity fade. The pair stacks when it doesn't fit (AX sizes).
struct DaySwitcher: View {
    let labels: DaySwitcherLabels
    let onPrevious: () -> Void
    let onNext: () -> Void

    init(labels: DaySwitcherLabels, onPrevious: @escaping () -> Void, onNext: @escaping () -> Void) {
        self.labels = labels
        self.onPrevious = onPrevious
        self.onNext = onNext
    }

    var body: some View {
        ViewThatFits(in: .horizontal) {
            HStack(spacing: 12) { previous; next }
            VStack(spacing: 12) { previous; next }
        }
    }

    private var previous: some View {
        Button(action: onPrevious) { Text("‹ \(labels.previous)")}
            .buttonStyle(CalypsoButtonStyle(.secondary, horizontalPadding: 12))
            .accessibilityLabel(labels.previous)
            .accessibilityHint("Previous day")
    }

    @ViewBuilder private var next: some View {
        if labels.nextEnabled {
            Button(action: onNext) { Text("\(labels.next) ›")}
                .buttonStyle(CalypsoButtonStyle(.secondary, horizontalPadding: 12))
                .accessibilityLabel(labels.next)
                .accessibilityHint("Next day")
        } else {
            Button(action: {}) { Text(labels.next)}
                .buttonStyle(DisabledDayStyle())
                .disabled(true)
                .accessibilityLabel(labels.next)
        }
    }
}

/// Disabled next-day look: Paper fill, 2pt dashed Periwinkle [8,6] outline, Ink Soft text. No fade.
private struct DisabledDayStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        let shape = RoundedRectangle(cornerRadius: 24)
        configuration.label
            .calypsoFont(.bodyStrong)
            .foregroundStyle(Color.inkSoft)
            .multilineTextAlignment(.center)
            .padding(.horizontal, 12)
            .padding(.vertical, 8)
            .frame(maxWidth: .infinity, minHeight: 72)
            .background(Color.paper, in: shape)
            .overlay(shape.strokeBorder(Color.periwinkle, style: StrokeStyle(lineWidth: 2, dash: [8, 6])))
    }
}

#Preview {
    VStack(spacing: 24) {
        DaySwitcher(labels: DaySwitcherLabels(previous: "Yesterday", next: "Tomorrow", nextEnabled: false),
                    onPrevious: {}, onNext: {})
        DaySwitcher(labels: DaySwitcherLabels(previous: "Tuesday", next: "Thursday", nextEnabled: true),
                    onPrevious: {}, onNext: {})
    }
    .padding(24)
    .background(Color.paper)
}

#Preview("AX5") {
    DaySwitcher(labels: DaySwitcherLabels(previous: "Tuesday", next: "Thursday", nextEnabled: true),
                onPrevious: {}, onNext: {})
        .padding(24)
        .background(Color.paper)
        .dynamicTypeSize(.accessibility5)
}
