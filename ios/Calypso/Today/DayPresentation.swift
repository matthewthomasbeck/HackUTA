import Foundation

enum PlaceCertainty {
    // Mirrors PLACE_CONF_MIN in backend/calypso/config.py.
    static let minimumConfidence = 0.6

    static func isUncertain(_ confidence: Double) -> Bool {
        confidence < minimumConfidence
    }
}

private func formatted(_ date: Date, template: String, calendar: Calendar) -> String {
    let f = DateFormatter()
    f.calendar = calendar
    f.locale = calendar.locale ?? .current
    f.timeZone = calendar.timeZone
    f.setLocalizedDateFormatFromTemplate(template)
    return f.string(from: date)
}

private func daysAgo(_ day: Date, now: Date, calendar: Calendar) -> Int {
    calendar.dateComponents([.day], from: calendar.startOfDay(for: day), to: calendar.startOfDay(for: now)).day ?? 0
}

struct DayHeader: Equatable {
    let title: String
    let caption: String

    static func make(for day: Date, now: Date = Date(), calendar: Calendar = .current) -> DayHeader {
        let n = daysAgo(day, now: now, calendar: calendar)
        if n == 0 {
            return DayHeader(title: "Today", caption: formatted(day, template: "EEEEMMMMd", calendar: calendar))
        }
        let date = formatted(day, template: "MMMMd", calendar: calendar)
        let relative = n == 1 ? "Yesterday" : "\(n) days ago"
        return DayHeader(title: formatted(day, template: "EEEE", calendar: calendar),
                         caption: "\(date) · \(relative)")
    }
}

struct DaySwitcherLabels: Equatable {
    let previous: String
    let next: String
    let nextEnabled: Bool

    static func make(for day: Date, now: Date = Date(), calendar: Calendar = .current) -> DaySwitcherLabels {
        let n = daysAgo(day, now: now, calendar: calendar)
        if n <= 0 {
            return DaySwitcherLabels(previous: "Yesterday", next: "Tomorrow", nextEnabled: false)
        }
        func weekday(offset: Int) -> String {
            let d = calendar.date(byAdding: .day, value: offset, to: day) ?? day
            return formatted(d, template: "EEEE", calendar: calendar)
        }
        return DaySwitcherLabels(previous: weekday(offset: -1),
                                 next: n == 1 ? "Today" : weekday(offset: 1),
                                 nextEnabled: true)
    }
}

enum DayPresentation {
    /// nil when the person is unknown or unnamed, so the chip reads "Someone new".
    static func chipName(for personId: String, names: [String: String]) -> String? {
        guard let name = names[personId], !name.isEmpty else { return nil }
        return name
    }

    /// All photo ids in event-start order, deduped, first occurrence kept.
    static func heroPhotoCandidates(_ events: [DayEvent]) -> [String] {
        var seen = Set<String>()
        return events.sorted { $0.start < $1.start }
            .flatMap(\.photoIds)
            .filter { seen.insert($0).inserted }
    }

    static func accessibilityLabel(for event: DayEvent, names: [String: String],
                                   timeZone: TimeZone = .current, locale: Locale = .current) -> String {
        let f = DateFormatter()
        f.locale = locale
        f.timeZone = timeZone
        f.dateFormat = "h:mm a"
        let place = PlaceCertainty.isUncertain(event.placeConfidence)
            ? "place not certain: \(event.place)" : "at \(event.place)"
        var parts = [f.string(from: event.start), event.summary, place]
        if !event.people.isEmpty {
            let who = event.people.map { chipName(for: $0, names: names) ?? "someone new" }
            parts.append("with " + who.joined(separator: ", "))
        }
        return parts.joined(separator: ", ")
    }
}

/// What the Today screen shows for the selected day. When the day changes, the previous day's moments are cleared
/// and the screen goes back to loading, so a new day's header never sits over the old day's moments. A
/// pull-to-refresh on the same day doesn't call `dayChanged()`, so it keeps its content while reloading.
struct DayContent: Equatable {
    enum State: Equatable { case loading, loaded, failed }

    var events: [DayEvent] = []
    var state: State = .loading

    mutating func dayChanged() {
        events = []
        state = .loading
    }
}
