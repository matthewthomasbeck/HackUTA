import SwiftUI

struct EventRow: View {
    let event: DayEvent
    /// Person id -> display name.
    let names: [String: String]
    let photoURL: (String) -> URL?

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
            if !event.photoIds.isEmpty {
                HStack {
                    ForEach(event.photoIds, id: \.self) { id in
                        AsyncImage(url: photoURL(id)) { image in
                            image.resizable().scaledToFill()
                        } placeholder: {
                            Image(systemName: "photo")
                        }
                        .frame(width: 44, height: 44)
                        .background(.quaternary)
                        .clipShape(RoundedRectangle(cornerRadius: 6))
                    }
                }
            }
        }
        .padding(.vertical, 4)
    }
}
