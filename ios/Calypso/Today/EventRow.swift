import SwiftUI

struct EventRow: View {
    let event: DayEvent
    /// Person id -> display name.
    let names: [String: String]

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("\(event.start.formatted(date: .omitted, time: .shortened)) · \(event.place) · \(event.summary)")
            if !event.people.isEmpty {
                HStack {
                    ForEach(event.people, id: \.self) { id in
                        Text(names[id] ?? "Unnamed visitor")
                            .font(.caption)
                            .padding(.horizontal, 8).padding(.vertical, 3)
                            .background(.thinMaterial, in: Capsule())
                    }
                }
            }
            // The backend has no photo-serving URL yet, so show placeholders per photo.
            if !event.photoIds.isEmpty {
                HStack {
                    ForEach(event.photoIds, id: \.self) { _ in
                        Image(systemName: "photo")
                            .frame(width: 44, height: 44)
                            .background(.quaternary, in: RoundedRectangle(cornerRadius: 6))
                    }
                }
            }
        }
        .padding(.vertical, 4)
    }
}
