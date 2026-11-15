import XCTest
@testable import Calypso

final class DayPresentationTests: XCTestCase {
    private var cal: Calendar = {
        var c = Calendar(identifier: .gregorian)
        c.locale = Locale(identifier: "en_US")
        c.timeZone = TimeZone(identifier: "America/Chicago")!
        return c
    }()
    private let tz = TimeZone(identifier: "America/Chicago")!
    private let en = Locale(identifier: "en_US")

    private func date(_ y: Int, _ m: Int, _ d: Int, _ h: Int = 10) -> Date {
        cal.date(from: DateComponents(year: y, month: m, day: d, hour: h))!
    }

    private func event(id: String = "e", start: String, place: String = "Home", conf: Double = 0.9,
                       people: [String] = [], summary: String = "S", photos: [String] = []) throws -> DayEvent {
        let json: [String: Any] = ["id": id, "start": start, "end": start, "place": place,
                                   "place_confidence": conf, "people": people, "summary": summary,
                                   "evidence": [], "photo_ids": photos]
        let data = try JSONSerialization.data(withJSONObject: json)
        return try JSONDecoder.calypso.decode(DayEvent.self, from: data)
    }

    func testPlaceThresholdBoundary() {
        XCTAssertTrue(PlaceCertainty.isUncertain(0.42))
        XCTAssertTrue(PlaceCertainty.isUncertain(0.5999))
        XCTAssertFalse(PlaceCertainty.isUncertain(0.6))
        XCTAssertFalse(PlaceCertainty.isUncertain(0.87))
    }

    func testHeaderToday() {
        let now = date(2026, 11, 14)
        XCTAssertEqual(DayHeader.make(for: now, now: now, calendar: cal),
                       DayHeader(title: "Today", caption: "Saturday, November 14"))
    }

    func testHeaderYesterday() {
        XCTAssertEqual(DayHeader.make(for: date(2026, 11, 13), now: date(2026, 11, 14), calendar: cal),
                       DayHeader(title: "Friday", caption: "November 13 · Yesterday"))
    }

    func testHeaderThreeDaysAgo() {
        XCTAssertEqual(DayHeader.make(for: date(2026, 11, 11), now: date(2026, 11, 14), calendar: cal),
                       DayHeader(title: "Wednesday", caption: "November 11 · 3 days ago"))
    }

    func testHeaderAcrossYearBoundary() {
        XCTAssertEqual(DayHeader.make(for: date(2026, 12, 30), now: date(2027, 1, 2), calendar: cal),
                       DayHeader(title: "Wednesday", caption: "December 30 · 3 days ago"))
    }

    func testSwitcherLabels() {
        let now = date(2026, 11, 14)
        XCTAssertEqual(DaySwitcherLabels.make(for: now, now: now, calendar: cal),
                       DaySwitcherLabels(previous: "Yesterday", next: "Tomorrow", nextEnabled: false))
        XCTAssertEqual(DaySwitcherLabels.make(for: date(2026, 11, 13), now: now, calendar: cal),
                       DaySwitcherLabels(previous: "Thursday", next: "Today", nextEnabled: true))
        XCTAssertEqual(DaySwitcherLabels.make(for: date(2026, 11, 11), now: now, calendar: cal),
                       DaySwitcherLabels(previous: "Tuesday", next: "Thursday", nextEnabled: true))
    }

    func testChipNameFallsBackToSomeoneNew() {
        XCTAssertNil(DayPresentation.chipName(for: "p_unknown", names: ["p_sarah": "Sarah"]))
        XCTAssertEqual(DayPresentation.chipName(for: "p_sarah", names: ["p_sarah": "Sarah"]), "Sarah")
    }

    func testHeroCandidatesOrderedAndDeduped() throws {
        let events = [
            try event(id: "1", start: "2026-11-14T11:00:00-06:00", photos: ["b", "c"]),
            try event(id: "2", start: "2026-11-14T09:00:00-06:00", photos: ["a", "b"]),
            try event(id: "3", start: "2026-11-14T10:00:00-06:00", photos: []),
        ]
        XCTAssertEqual(DayPresentation.heroPhotoCandidates(events), ["a", "b", "c"])
        XCTAssertEqual(DayPresentation.heroPhotoCandidates([events[2]]), [])
    }

    func testAccessibilityLabelKnownPlace() throws {
        let e = try event(start: "2026-11-14T09:30:00-06:00", place: "Kroger", conf: 0.87,
                          people: ["p_mom"], summary: "Grocery shopping with Mom")
        XCTAssertEqual(DayPresentation.accessibilityLabel(for: e, names: ["p_mom": "Mom"], timeZone: tz, locale: en),
                       "9:30 AM, Grocery shopping with Mom, at Kroger, with Mom")
    }

    func testAccessibilityLabelUncertainPlace() throws {
        let e = try event(start: "2026-11-14T15:00:00-06:00", place: "Somewhere with park sounds", conf: 0.42,
                          people: ["p_tom", "p_x"], summary: "A walk")
        XCTAssertEqual(DayPresentation.accessibilityLabel(for: e, names: ["p_tom": "Tom"], timeZone: tz, locale: en),
                       "3:00 PM, A walk, place not certain: somewhere with park sounds, with Tom, someone new")
    }

    func testDayChangeClearsPreviousDaysMoments() throws {
        var content = DayContent()
        content.events = [try event(id: "yesterday_lunch", start: "2026-11-13T12:00:00Z")]
        content.state = .loaded
        content.dayChanged()
        XCTAssertEqual(content.events, [])
        XCTAssertEqual(content.state, .loading)
    }

    func testDayChangeAfterFailureGoesBackToLoading() {
        var content = DayContent(events: [], state: .failed)
        content.dayChanged()
        XCTAssertEqual(content.state, .loading)
    }

    func testAccessibilityTimeFollows24HourLocale() throws {
        let e = try event(start: "2026-11-14T14:30:00-06:00", summary: "Lunch")
        let label = DayPresentation.accessibilityLabel(for: e, names: [:], timeZone: tz,
                                                       locale: Locale(identifier: "en_GB"))
        XCTAssertTrue(label.hasPrefix("14:30, Lunch"), label)
    }

    func testChipNameTreatsBlankAsSomeoneNew() {
        XCTAssertNil(DayPresentation.chipName(for: "p_a", names: ["p_a": ""]))
        XCTAssertNil(DayPresentation.chipName(for: "p_a", names: ["p_a": "   "]))
        XCTAssertEqual(DayPresentation.chipName(for: "p_a", names: ["p_a": " Sarah "]), "Sarah")
    }

    // MARK: Stale loads (a load never writes under a day that's no longer selected)

    func testApplyWritesWhenTheDayIsStillSelected() throws {
        var content = DayContent()
        let e = try event(id: "sat", start: "2026-11-14T12:00:00Z")
        XCTAssertTrue(content.apply(.loaded([e]), for: "2026-11-14", selectedKey: "2026-11-14"))
        XCTAssertEqual(content, DayContent(events: [e], state: .loaded))
    }

    func testRefreshThatLandsAfterADayChangeIsDropped() throws {
        // Saturday refresh still running; the user moves to Friday and Friday's load finishes first.
        var content = DayContent()
        let friday = try event(id: "fri", start: "2026-11-13T12:00:00Z")
        content.dayChanged()
        content.apply(.loaded([friday]), for: "2026-11-13", selectedKey: "2026-11-13")
        let saturday = try event(id: "sat", start: "2026-11-14T12:00:00Z")
        XCTAssertFalse(content.apply(.loaded([saturday]), for: "2026-11-14", selectedKey: "2026-11-13"))
        XCTAssertFalse(content.apply(.failed, for: "2026-11-14", selectedKey: "2026-11-13"))
        XCTAssertEqual(content, DayContent(events: [friday], state: .loaded))
    }

    func testCancelledLoadIsDropped() throws {
        var content = DayContent()
        let e = try event(id: "sat", start: "2026-11-14T12:00:00Z")
        XCTAssertFalse(content.apply(.loaded([e]), for: "2026-11-14", selectedKey: "2026-11-14", cancelled: true))
        XCTAssertEqual(content, DayContent())
    }

    func testFailureForTheSelectedDayClearsMoments() throws {
        var content = DayContent(events: [try event(start: "2026-11-14T12:00:00Z")], state: .loaded)
        content.apply(.failed, for: "2026-11-14", selectedKey: "2026-11-14")
        XCTAssertEqual(content, DayContent(events: [], state: .failed))
    }
}
