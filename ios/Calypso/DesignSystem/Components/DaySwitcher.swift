import SwiftUI

/// Previous / next day buttons (Today screen, Figma 20:489). Previous is Secondary "‹ <label>".
/// Next is Secondary "<label> ›" when enabled; when disabled it's Ink Soft text on Paper with a dashed
/// Periwinkle outline, no chevron and no opacity fade. The pair stacks when it doesn't fit (AX sizes); a label
/// too wide for its button shrinks rather than breaking mid-word (`WordSafeText`).
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
        Button(action: onPrevious) { WordSafeText("‹\u{00A0}\(labels.previous)", style: .bodyStrong, alignment: .center) }
            .buttonStyle(CalypsoButtonStyle(.secondary, horizontalPadding: 12))
            .accessibilityLabel(labels.previous)
            .accessibilityHint("Previous day")
    }

    @ViewBuilder private var next: some View {
        if labels.nextEnabled {
            Button(action: onNext) { WordSafeText("\(labels.next)\u{00A0}›", style: .bodyStrong, alignment: .center) }
                .buttonStyle(CalypsoButtonStyle(.secondary, horizontalPadding: 12))
                .accessibilityLabel(labels.next)
                .accessibilityHint("Next day")
        } else {
            Button(action: {}) { WordSafeText(labels.next, style: .bodyStrong, alignment: .center) }
                .buttonStyle(CalypsoButtonStyle(.secondary, horizontalPadding: 12))
                .disabled(true)
                .accessibilityLabel(labels.next)
        }
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
