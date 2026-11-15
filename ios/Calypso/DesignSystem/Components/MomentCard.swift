import SwiftUI

/// Figma `Moment Card` (18:225). Apricot time tag, Headline (`event.summary`, per the plan's ruling), Place Row,
/// one Person Chip per person, then photo thumbs (a thumb that fails to load is removed). Read by VoiceOver as one
/// element using `DayPresentation.accessibilityLabel`.
struct MomentCard: View {
    let event: DayEvent
    let names: [String: String]
    let photoURL: (String) -> URL?

    @State private var failedPhotos: Set<String> = []

    init(event: DayEvent, names: [String: String], photoURL: @escaping (String) -> URL?) {
        self.event = event
        self.names = names
        self.photoURL = photoURL
    }

    private var visiblePhotos: [String] {
        var seen = Set<String>()
        return event.photoIds.filter { !failedPhotos.contains($0) && seen.insert($0).inserted }
    }

    var body: some View {
        PaperCard {
            VStack(alignment: .leading, spacing: 16) {
                TimeTag(text: event.start.formatted(date: .omitted, time: .shortened))
                Text(event.summary)
                    .calypsoFont(.headline)
                    .foregroundStyle(Color.ink)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .fixedSize(horizontal: false, vertical: true)
                PlaceRow(place: event.place, isUncertain: PlaceCertainty.isUncertain(event.placeConfidence))
                if !event.people.isEmpty {
                    FlowLayout(spacing: 8) {
                        ForEach(Array(event.people.enumerated()), id: \.offset) { _, id in
                            PersonChip(name: DayPresentation.chipName(for: id, names: names))
                        }
                    }
                }
                if !visiblePhotos.isEmpty {
                    FlowLayout(spacing: 8) {
                        ForEach(visiblePhotos, id: \.self) { id in
                            PhotoTile(url: photoURL(id), style: .thumb) {
                                failedPhotos.insert(id)
                            }
                        }
                    }
                }
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel(DayPresentation.accessibilityLabel(for: event, names: names))
    }
}

/// Apricot paper tag with uneven corners (4 / 12), Caption in Ink.
private struct TimeTag: View {
    let text: String

    var body: some View {
        Text(text)
            .calypsoFont(.caption)
            .foregroundStyle(Color.ink)
            .padding(.horizontal, 14)
            .padding(.vertical, 6)
            .background(Color.apricot, in: UnevenRoundedRectangle(topLeadingRadius: 4, bottomLeadingRadius: 12,
                                                                 bottomTrailingRadius: 4, topTrailingRadius: 12))
    }
}

/// Left-aligned wrapping row (chips, thumbs). Children wider than the row get the full row width.
struct FlowLayout: Layout {
    var spacing: CGFloat = 8

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let rows = arrange(width: proposal.width ?? .infinity, subviews: subviews)
        let width = rows.map(\.width).max() ?? 0
        let height = rows.map(\.height).reduce(0, +) + spacing * CGFloat(max(rows.count - 1, 0))
        return CGSize(width: proposal.width.map { min($0, width) } ?? width, height: height)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var y = bounds.minY
        for row in arrange(width: bounds.width, subviews: subviews) {
            var x = bounds.minX
            for item in row.items {
                subviews[item.index].place(at: CGPoint(x: x, y: y), anchor: .topLeading,
                                           proposal: ProposedViewSize(item.size))
                x += item.size.width + spacing
            }
            y += row.height + spacing
        }
    }

    private struct Row {
        var items: [(index: Int, size: CGSize)] = []
        var width: CGFloat = 0
        var height: CGFloat = 0
    }

    private func arrange(width maxWidth: CGFloat, subviews: Subviews) -> [Row] {
        var rows: [Row] = []
        var row = Row()
        for (index, subview) in subviews.enumerated() {
            var size = subview.sizeThatFits(.unspecified)
            if size.width > maxWidth {
                size = subview.sizeThatFits(ProposedViewSize(width: maxWidth, height: nil))
                size.width = min(size.width, maxWidth)
            }
            let needed = row.items.isEmpty ? size.width : row.width + spacing + size.width
            if needed > maxWidth, !row.items.isEmpty {
                rows.append(row)
                row = Row()
            }
            row.width = row.items.isEmpty ? size.width : row.width + spacing + size.width
            row.height = max(row.height, size.height)
            row.items.append((index, size))
        }
        if !row.items.isEmpty { rows.append(row) }
        return rows
    }
}

#if DEBUG
enum ComponentSamples {
    static func event(time: String = "11:00", summary: String = "Coffee with Sarah", place: String = "Blue Bean Café",
                      confidence: Double = 0.9, people: [String] = ["p_sarah", "p_new"],
                      photos: [String] = []) -> DayEvent {
        // Local wall-clock time, so the tag reads e.g. "11:00 AM" in any simulator time zone.
        let offset = TimeZone.current.secondsFromGMT()
        let zone = String(format: "%@%02d:%02d", offset < 0 ? "-" : "+", abs(offset) / 3600, abs(offset) % 3600 / 60)
        let json = """
        {"id":"ev_\(time)","start":"2026-11-14T\(time):00\(zone)","end":"2026-11-14T\(time):30\(zone)",
         "place":"\(place)","place_confidence":\(confidence),"people":\(people),
         "summary":"\(summary)","photo_ids":\(photos)}
        """
        // swiftlint:disable:next force_try
        return try! JSONDecoder.calypso.decode(DayEvent.self, from: Data(json.utf8))
    }

    static let names = ["p_sarah": "Sarah", "p_tom": "Tom", "p_mom": "Mom"]

    /// Thumbs: "loading" ids point at a host that never answers quickly; "missing" ids get no URL (fail).
    static func photoURL(_ id: String) -> URL? {
        id.hasPrefix("missing") ? nil : URL(string: "https://example.invalid/photos/\(id).jpg")
    }
}

#Preview("Moment cards") {
    ScrollView {
        VStack(spacing: 16) {
            MomentCard(event: ComponentSamples.event(), names: ComponentSamples.names,
                       photoURL: ComponentSamples.photoURL)
            MomentCard(event: ComponentSamples.event(summary: "A walk in the garden",
                                                     place: "Somewhere with park sounds", confidence: 0.4,
                                                     people: ["p_tom"], photos: ["a", "missing_b", "c"]),
                       names: ComponentSamples.names, photoURL: ComponentSamples.photoURL)
        }
        .padding(24)
    }
    .background(Color.paper)
}

#Preview("Moment card AX5") {
    ScrollView {
        MomentCard(event: ComponentSamples.event(summary: "A walk in the garden",
                                                 place: "Somewhere with park sounds", confidence: 0.4,
                                                 people: ["p_mom", "p_new"], photos: ["a"]),
                   names: ComponentSamples.names, photoURL: ComponentSamples.photoURL)
            .padding(24)
    }
    .background(Color.paper)
    .dynamicTypeSize(.accessibility5)
}
#endif
