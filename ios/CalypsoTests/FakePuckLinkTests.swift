import XCTest
@testable import Calypso

@MainActor
final class FakePuckLinkTests: XCTestCase {
    private var defaults: UserDefaults!

    override func setUp() {
        super.setUp()
        defaults = UserDefaults(suiteName: "FakePuckLinkTests")
        defaults.removePersistentDomain(forName: "FakePuckLinkTests")
    }

    private func makeLink(pinned: FakeSpeaker? = nil) -> FakePuckLink {
        FakePuckLink(timeScale: 0.01, pinnedSpeaker: pinned, arguments: [], defaults: defaults)
    }

    func testScanFoundConnectTransitions() async {
        let link = makeLink(pinned: FakeSpeaker.none)
        var states: [PuckConnectionState] = []
        let connected = expectation(description: "connected")
        link.onStateChange = { s in
            states.append(s)
            if case .connected = s { connected.fulfill() }
        }
        link.startScanning()
        try? await Task.sleep(nanoseconds: 100_000_000)
        link.connect()
        await fulfillment(of: [connected], timeout: 2)
        XCTAssertEqual(states, [.scanning, .found(name: "Calypso Puck"), .connecting, .connected(name: "Calypso Puck")])
        XCTAssertTrue(defaults.bool(forKey: "puckPaired"))
        link.disconnect()
    }

    func testReconnectRemembered() async {
        let link = makeLink(pinned: FakeSpeaker.none)
        link.reconnectRemembered()
        XCTAssertEqual(link.state, .idle)
        defaults.set(true, forKey: "puckPaired")
        link.reconnectRemembered()
        XCTAssertEqual(link.state, .connecting)
        link.disconnect()
    }

    func testEnrollmentEvents() async {
        let link = makeLink(pinned: FakeSpeaker.none)
        defaults.set(true, forKey: "puckPaired")
        link.reconnectRemembered()
        try? await Task.sleep(nanoseconds: 100_000_000)
        var events: [PuckEvent] = []
        link.onEvent = { events.append($0) }
        link.send(.enrollStart(index: 1, text: "hi"))
        XCTAssertEqual(events, [.recording(index: 1)])
        try? await Task.sleep(nanoseconds: 200_000_000)
        link.send(.enrollFinish(count: 5))
        XCTAssertEqual(events, [.recording(index: 1), .saved(index: 1), .done])
        link.disconnect()
    }

    func testPinnedSpeakerSarah() async {
        let link = makeLink(pinned: .sarah)
        var whos: [WhoIsTalking] = []
        link.onWho = { whos.append($0) }
        defaults.set(true, forKey: "puckPaired")
        link.reconnectRemembered()
        try? await Task.sleep(nanoseconds: 200_000_000)
        link.disconnect()
        XCTAssertFalse(whos.isEmpty)
        XCTAssertTrue(whos.allSatisfy { $0.displayName == "Sarah" && $0.status == .identified })
    }

    func testFakeSpeakerLaunchArgument() {
        XCTAssertEqual(FakeSpeaker.from(arguments: ["app", "-fakeSpeaker", "unknown"]), .unknown)
        XCTAssertNil(FakeSpeaker.from(arguments: ["app"]))
    }
}

@MainActor
final class PuckConnectionTests: XCTestCase {
    func testSpeakerExpiresAfterQuiet() async {
        let link = FakePuckLink(timeScale: 0.01, pinnedSpeaker: .none, arguments: [],
                                defaults: UserDefaults(suiteName: "PuckConnectionTests")!)
        let conn = PuckConnection(link: link, expiry: 0.1)
        link.onWho?(WhoIsTalking(status: .identified, personId: "p_sarah", displayName: "Sarah"))
        XCTAssertEqual(conn.speaker?.displayName, "Sarah")
        try? await Task.sleep(nanoseconds: 400_000_000)
        XCTAssertNil(conn.speaker)
    }

    func testNewWhoResetsExpiry() async {
        let link = FakePuckLink(timeScale: 0.01, pinnedSpeaker: .none, arguments: [],
                                defaults: UserDefaults(suiteName: "PuckConnectionTests")!)
        let conn = PuckConnection(link: link, expiry: 0.3)
        link.onWho?(WhoIsTalking(status: .unknown))
        try? await Task.sleep(nanoseconds: 200_000_000)
        link.onWho?(WhoIsTalking(status: .unknown))
        try? await Task.sleep(nanoseconds: 200_000_000)
        XCTAssertNotNil(conn.speaker)
        try? await Task.sleep(nanoseconds: 300_000_000)
        XCTAssertNil(conn.speaker)
    }
}
