import SwiftUI

/// Today (Figma 20:489, quiet day 20:1025, couldn't load 20:1097): header, day switcher, hero photo, then the
/// day's moments on a sea-path rail. `initialDay` exists for the DEBUG `-screen` routes.
struct TodayView: View {
    let client: APIClient?
    @State private var day: Date
    @State private var content = DayContent()
    @State private var names: [String: String] = [:]
    @State private var pickingDay = false

    @Environment(\.dynamicTypeSize) private var dynamicTypeSize
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    #if DEBUG
    /// DEBUG `today-bottom` route: scroll to the end note once moments load, for screenshots.
    fileprivate var debugScrollToEnd = false
    #endif

    init(client: APIClient?, initialDay: Date = Date()) {
        self.client = client
        _day = State(initialValue: initialDay)
    }

    private var events: [DayEvent] { content.events }
    private var state: DayContent.State { content.state }
    private var isToday: Bool { Calendar.current.isDateInToday(day) }
    /// Under accessibility sizes the rail is dropped and cards fill the width.
    private var showsRail: Bool { !dynamicTypeSize.isAccessibilitySize }
    private var hasMoments: Bool { state != .failed && !events.isEmpty }
    /// One gull per screen: the walking gull on the rail wins over the header Peek. Under accessibility sizes the
    /// Peek is dropped too, so the caption and title get the full width.
    private var showsWalkingGull: Bool { hasMoments && showsRail && isToday }
    private var showsPeek: Bool {
        state == .loaded && !events.isEmpty && !showsWalkingGull && !dynamicTypeSize.isAccessibilitySize
    }

    var body: some View {
        ScrollViewReader { proxy in
            ScrollView {
                VStack(alignment: .leading, spacing: 0) {
                    header
                    stateContent
                }
                .padding(.bottom, 24)
            }
            .background(Color.paper.ignoresSafeArea())
            .refreshable { await load() }
            .task(id: day) { await load() }
            .onChange(of: day) { content.dayChanged() }
            .sheet(isPresented: $pickingDay) {
                DayPickerSheet(day: $day)
            }
            #if DEBUG
            .onChange(of: events.map(\.id)) { _, ids in
                guard debugScrollToEnd, !ids.isEmpty else { return }
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.8) {
                    proxy.scrollTo(Self.endNoteID, anchor: .bottom)
                }
            }
            #endif
        }
    }

    private static let endNoteID = "today.endNote"

    // MARK: Header

    private var header: some View {
        let title = DayHeader.make(for: day)
        return VStack(alignment: .leading, spacing: 12) {
            NavHeader(caption: title.caption, title: title.title) {
                if showsPeek {
                    // Peeks over the top edge of the day switcher, as in Figma.
                    Mascot(pose: .peek, size: .s)
                        .offset(y: 16)
                }
            }
            .zIndex(1)
            DaySwitcher(labels: DaySwitcherLabels.make(for: day), onPrevious: previousDay, onNext: nextDay)
            CalypsoButton("Pick a day", kind: .quiet) { pickingDay = true }
        }
        .padding(.horizontal, 24)
        .padding(.top, 16)
        .padding(.bottom, 8)
    }

    private func previousDay() {
        day = Calendar.current.date(byAdding: .day, value: -1, to: day) ?? day
    }

    private func nextDay() {
        let next = Calendar.current.date(byAdding: .day, value: 1, to: day) ?? day
        day = min(next, Date())
    }

    // MARK: States

    @ViewBuilder private var stateContent: some View {
        switch state {
        case .failed:
            VStack(spacing: 8) {
                CalmMessage(pose: .thinking, title: "We couldn’t load this day right now.", message: "",
                            buttonTitle: "Try again", scene: false) {
                    Task { await load() }
                }
                CalypsoButton("Look at another day", kind: .quiet, action: previousDay)
            }
            .padding(.horizontal, 24)
            .padding(.top, 32)
        case .loaded where events.isEmpty:
            CalmMessage(pose: .resting, title: "A quiet day",
                        message: "Nothing new was recorded. That’s okay. Rest days matter.",
                        buttonTitle: "Look at another day", action: previousDay)
                .padding(.horizontal, 24)
                .padding(.top, 32)
        case .loading where events.isEmpty:
            ProgressView()
                .controlSize(.large)
                .tint(Color.periwinkleDeep)
                .frame(maxWidth: .infinity)
                .padding(.top, 80)
                .accessibilityLabel("Loading your day")
        default:
            moments
        }
    }

    // MARK: Moments

    private var moments: some View {
        VStack(alignment: .leading, spacing: 16) {
            HeroPhoto(candidates: DayPresentation.heroPhotoCandidates(events),
                      photoURL: { client?.photoURL(id: $0) })
            Text("Your day")
                .calypsoFont(.headline)
                .foregroundStyle(Color.ink)
                .accessibilityAddTraits(.isHeader)
                .padding(.top, 8)
            timeline
                .padding(.leading, showsRail ? -12 : 0)
            Text("That’s your day so far.")
                .calypsoFont(.callout)
                .foregroundStyle(Color.inkSoft)
                .multilineTextAlignment(.center)
                .frame(maxWidth: .infinity)
                .id(Self.endNoteID)
        }
        .padding(.horizontal, 24)
        .padding(.top, 8)
    }

    private var timeline: some View {
        VStack(spacing: 0) {
            ForEach(Array(events.enumerated()), id: \.element.id) { i, event in
                let isLast = i == events.count - 1
                MomentCard(event: event, names: names, photoURL: { client?.photoURL(id: $0) })
                    .padding(.bottom, isLast ? 0 : 28)
                    .padding(.leading, showsRail ? SeaPathRail.width + 4 : 0)
                    .background(alignment: .topLeading) {
                        if showsRail {
                            SeaPathRail(isFirst: i == 0, isLast: isLast,
                                        showsGull: isLast && showsWalkingGull, index: i,
                                        isHome: event.place == "Home"
                                            && !PlaceCertainty.isUncertain(event.placeConfidence))
                        }
                    }
                    .transition(reduceMotion ? .opacity : .opacity.combined(with: .offset(y: 24)))
            }
        }
        .animation(reduceMotion ? .easeInOut(duration: 0.25) : .spring(response: 0.35, dampingFraction: 1),
                   value: events.map(\.id))
    }

    // MARK: Loading

    private func load() async {
        guard let client else { content.state = .failed; return }
        do {
            let key = Self.dayFormatter.string(from: day)
            async let loaded = client.events(day: key)
            if let people = try? await client.people() {
                names = Dictionary(uniqueKeysWithValues: people.compactMap { p in p.name.map { (p.id, $0) } })
            }
            content.events = try await loaded.sorted { $0.start < $1.start }
            content.state = .loaded
        } catch is CancellationError {
            return
        } catch let error as URLError where error.code == .cancelled {
            return
        } catch {
            content.events = []
            content.state = .failed
        }
    }

    private static let dayFormatter: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.dateFormat = "yyyy-MM-dd"
        return f
    }()
}

#if DEBUG
extension TodayView {
    func debugScrolledToEnd() -> TodayView {
        var copy = self
        copy.debugScrollToEnd = true
        return copy
    }
}
#endif

/// "Pick a day" sheet: a graphical date picker limited to today and earlier, and a Primary "Done".
private struct DayPickerSheet: View {
    @Binding var day: Date
    @State private var draft: Date
    @Environment(\.dismiss) private var dismiss

    init(day: Binding<Date>) {
        _day = day
        _draft = State(initialValue: day.wrappedValue)
    }

    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                Text("Pick a day")
                    .calypsoFont(.title)
                    .foregroundStyle(Color.ink)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .accessibilityAddTraits(.isHeader)
                DatePicker("Day", selection: $draft, in: ...Date(), displayedComponents: .date)
                    .datePickerStyle(.graphical)
                    .tint(Color.periwinkleDeep)
                    .padding(12)
                    .background(Color.card, in: RoundedRectangle(cornerRadius: 24))
                    .overlay(RoundedRectangle(cornerRadius: 24).strokeBorder(Color.periwinkleMist, lineWidth: 2))
                CalypsoButton("Done") {
                    day = draft
                    dismiss()
                }
            }
            .padding(24)
        }
        .background(Color.paper.ignoresSafeArea())
        .presentationDetents([.large])
    }
}

#Preview("Today (no client)") {
    TodayView(client: nil)
}
