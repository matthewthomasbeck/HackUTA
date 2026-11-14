import SwiftUI

struct GroupCallHowToView: View {
    var onNext: () -> Void

    private let steps: [(icon: String, text: String)] = [
        ("video.fill", "Open FaceTime and tap New FaceTime"),
        ("person.2.fill", "Add Mom and Calypso⁻¹"),
        ("video.circle.fill", "Tap Video"),
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: 24) {
            Text("How to start a group FaceTime").font(.title.bold())
            ForEach(Array(steps.enumerated()), id: \.offset) { index, step in
                HStack(spacing: 16) {
                    Image(systemName: step.icon).font(.largeTitle).frame(width: 56).foregroundStyle(.tint)
                    VStack(alignment: .leading) {
                        Text("Step \(index + 1)").font(.caption).foregroundStyle(.secondary)
                        Text(step.text).font(.headline)
                    }
                }
            }
            Text("Or text Calypso⁻¹: *call Mom with me*").foregroundStyle(.secondary)
            Spacer()
            Button("Next", action: onNext)
                .buttonStyle(.borderedProminent).controlSize(.large).frame(maxWidth: .infinity)
        }
        .padding()
    }
}
