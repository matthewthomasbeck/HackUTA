import SwiftUI

struct TodayView: View {
    let client: APIClient?
    @State private var day = Date()
    @State private var events: [DayEvent] = []
    @State private var names: [String: String] = [:]
    @State private var error: String?

    var body: some View {
        NavigationStack {
            List {
                DatePicker("Day", selection: $day, in: ...Date(), displayedComponents: .date)
                ForEach(events) { EventRow(event: $0, names: names) }
            }
            .overlay {
                if events.isEmpty { ContentUnavailableView(error ?? "Nothing on this day", systemImage: "calendar") }
            }
            .navigationTitle("Today")
            .refreshable { await load() }
            .task(id: day) { await load() }
        }
    }

    private func load() async {
        guard let client else { error = "App isn't configured"; return }
        do {
            let key = Self.dayFormatter.string(from: day)
            async let loaded = client.events(day: key)
            if let people = try? await client.people() {
                names = Dictionary(uniqueKeysWithValues: people.compactMap { p in p.name.map { (p.id, $0) } })
            }
            events = try await loaded.sorted { $0.start < $1.start }
            error = nil
        } catch is CancellationError {
            return
        } catch let error as URLError where error.code == .cancelled {
            return
        } catch {
            events = []
            self.error = "Couldn't load this day"
        }
    }

    private static let dayFormatter: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.dateFormat = "yyyy-MM-dd"
        return f
    }()
}
