import SwiftUI

/// Onboarding progress: Periwinkle Mist dots, the current one a wider Periwinkle Deep capsule,
/// then "Step N of M" in Caption, Ink Soft on Paper.
struct StepDots: View {
    let current: Int
    let total: Int

    init(current: Int, total: Int) {
        self.current = current
        self.total = total
    }

    private var caption: String { "Step \(current) of \(total)" }

    var body: some View {
        ViewThatFits(in: .horizontal) {
            HStack(spacing: 12) { dots; label }
            VStack(spacing: 8) { dots; label }
        }
        .frame(maxWidth: .infinity)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(caption)
    }

    private var dots: some View {
        HStack(spacing: 8) {
            ForEach(1...max(total, 1), id: \.self) { step in
                Capsule()
                    .fill(step == current ? Color.periwinkleDeep : Color.periwinkleMist)
                    .frame(width: step == current ? 28 : 12, height: 12)
            }
        }
    }

    private var label: some View {
        Text(caption)
            .calypsoFont(.caption)
            .foregroundStyle(Color.inkSoft)
            .fixedSize()
    }
}

#Preview {
    VStack(spacing: 24) {
        StepDots(current: 1, total: 6)
        StepDots(current: 2, total: 6)
        StepDots(current: 6, total: 6)
        StepDots(current: 3, total: 6).dynamicTypeSize(.accessibility5)
    }
    .padding(24)
    .background(Color.paper)
}
