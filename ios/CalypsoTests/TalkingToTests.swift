import XCTest
@testable import Calypso

final class TalkingToTests: XCTestCase {
    private let connected = PuckConnectionState.connected(name: "Calypso Puck")
    private let sarah = WhoIsTalking(status: .identified, personId: "p_sarah", displayName: "Sarah",
                                     relationship: "daughter", score: 0.81)

    func testIdentifiedMatchesStoredPersonByID() {
        let stored = Person(id: "p_sarah", name: "Sarah", relationship: "daughter",
                            facePhotoUrl: "https://example.com/sarah.jpg")
        let p = TalkingToPresentation.make(state: connected, speaker: sarah, people: [stored])
        XCTAssertEqual(p, .person(stored))
        guard case .person(let person) = p else { return XCTFail() }
        XCTAssertEqual(person.facePhotoUrl, "https://example.com/sarah.jpg")
    }

    func testIdentifiedWithoutStoredPersonBuildsOne() {
        let p = TalkingToPresentation.make(state: connected, speaker: sarah, people: [])
        XCTAssertEqual(p, .person(Person(id: "p_sarah", name: "Sarah", relationship: "daughter")))
    }

    func testIdentifiedWithoutIDUsesPuckPrefixedID() {
        let who = WhoIsTalking(status: .identified, displayName: "Tom")
        let p = TalkingToPresentation.make(state: connected, speaker: who, people: [])
        XCTAssertEqual(p, .person(Person(id: "puck_Tom", name: "Tom")))
    }

    func testStoredPersonWithoutNameTakesPuckName() {
        let stored = Person(id: "p_sarah", facePhotoUrl: "x")
        let p = TalkingToPresentation.make(state: connected, speaker: sarah, people: [stored])
        XCTAssertEqual(p, .person(Person(id: "p_sarah", name: "Sarah", facePhotoUrl: "x")))
    }

    func testIdentifiedWithoutNameIsSomeoneNew() {
        let who = WhoIsTalking(status: .identified, personId: "p_x", displayName: nil)
        XCTAssertEqual(TalkingToPresentation.make(state: connected, speaker: who, people: []), .someoneNew)
    }

    func testUncertainWithCandidateNameIsSomeoneNew() {
        let who = WhoIsTalking(status: .uncertain, personId: "p_sarah", displayName: "Sarah", score: 0.5)
        let stored = Person(id: "p_sarah", name: "Sarah")
        XCTAssertEqual(TalkingToPresentation.make(state: connected, speaker: who, people: [stored]), .someoneNew)
    }

    func testUnknownIsSomeoneNew() {
        XCTAssertEqual(TalkingToPresentation.make(state: connected, speaker: WhoIsTalking(status: .unknown),
                                                  people: []), .someoneNew)
    }

    func testNoSpeakerIsQuiet() {
        XCTAssertEqual(TalkingToPresentation.make(state: connected, speaker: nil, people: []), .quiet)
    }

    func testLiteralPatientIDIsQuiet() {
        let who = WhoIsTalking(status: .identified, personId: "patient", displayName: "Margaret")
        XCTAssertEqual(TalkingToPresentation.make(state: connected, speaker: who, people: []), .quiet)
    }

    func testStoredPatientIsQuietEvenWhenUncertain() {
        let patient = Person(id: "p_margaret", name: "Margaret", isPatient: true)
        for status in [WhoIsTalking.Status.identified, .uncertain] {
            let who = WhoIsTalking(status: status, personId: "p_margaret", displayName: "Margaret")
            XCTAssertEqual(TalkingToPresentation.make(state: connected, speaker: who, people: [patient]), .quiet)
        }
    }

    func testAnyOtherStateIsNotConnected() {
        let states: [PuckConnectionState] = [.idle, .bluetoothOff, .unauthorized, .scanning,
                                             .found(name: "Calypso Puck"), .connecting, .failed("x")]
        for state in states {
            XCTAssertEqual(TalkingToPresentation.make(state: state, speaker: sarah, people: []), .notConnected,
                           "\(state)")
        }
    }

    func testPersonWording() {
        let p = TalkingToPresentation.person(Person(id: "p_sarah", name: "Sarah", relationship: "Daughter"))
        XCTAssertEqual(p.caption, "Talking with")
        XCTAssertEqual(p.title, "Sarah")
        XCTAssertEqual(p.subtitle, "your daughter")
        XCTAssertEqual(p.accessibilityLabel, "Talking with Sarah, your daughter. Opens Sarah’s profile.")
        XCTAssertTrue(p.isLive)
    }

    func testPersonWithoutRelationship() {
        let p = TalkingToPresentation.person(Person(id: "p_tom", name: "Tom"))
        XCTAssertNil(p.subtitle)
        XCTAssertEqual(p.accessibilityLabel, "Talking with Tom. Opens Tom’s profile.")
    }

    func testNeutralWording() {
        XCTAssertEqual(TalkingToPresentation.someoneNew.caption, "Talking with")
        XCTAssertEqual(TalkingToPresentation.someoneNew.title, "Someone new")
        XCTAssertEqual(TalkingToPresentation.someoneNew.subtitle, "Getting to know them…")
        XCTAssertEqual(TalkingToPresentation.someoneNew.accessibilityLabel,
                       "Talking with someone new. Calypso⁻¹ doesn’t know this voice yet. Opens more about them.")
        XCTAssertTrue(TalkingToPresentation.someoneNew.isLive)

        XCTAssertEqual(TalkingToPresentation.quiet.caption, "Right now")
        XCTAssertEqual(TalkingToPresentation.quiet.title, "It’s quiet")
        XCTAssertEqual(TalkingToPresentation.quiet.subtitle, "I’ll show who you’re talking with.")
        XCTAssertEqual(TalkingToPresentation.quiet.accessibilityLabel,
                       "Right now it’s quiet. I’ll show who you’re talking with.")
        XCTAssertFalse(TalkingToPresentation.quiet.isLive)

        XCTAssertEqual(TalkingToPresentation.notConnected.caption, "Your puck")
        XCTAssertEqual(TalkingToPresentation.notConnected.title, "Not connected")
        XCTAssertEqual(TalkingToPresentation.notConnected.subtitle, "Keep your puck close to your phone.")
        XCTAssertEqual(TalkingToPresentation.notConnected.accessibilityLabel,
                       "Your puck is not connected. Keep your puck close to your phone. Tap to connect.")
        XCTAssertFalse(TalkingToPresentation.notConnected.isLive)
    }
}
