import XCTest
@testable import Calypso

final class VoiceEnrollmentTests: XCTestCase {
    private let text = VoiceEnrollment.sentences

    func testFiveSentences() {
        XCTAssertEqual(text.count, 5)
        XCTAssertEqual(VoiceEnrollment().phase, .ready)
        XCTAssertEqual(VoiceEnrollment().index, 0)
    }

    func testHappyPathReadsAllFiveThenFinishes() {
        var e = VoiceEnrollment()
        for i in 0..<5 {
            XCTAssertEqual(e.index, i)
            XCTAssertEqual(e.start(), .enrollStart(index: i, text: text[i]))
            XCTAssertEqual(e.phase, .recording)
            e.apply(.recording(index: i))
            XCTAssertEqual(e.phase, .recording)
            e.apply(.saved(index: i))
            XCTAssertEqual(e.phase, .saved)
            if i < 4 {
                XCTAssertNil(e.next())
                XCTAssertEqual(e.phase, .ready)
            }
        }
        XCTAssertEqual(e.next(), .enrollFinish(count: 5))
        XCTAssertEqual(e.phase, .finished)
    }

    func testFinishIsFireAndForgetAndLateDoneIsIgnored() {
        var e = VoiceEnrollment(index: 4, phase: .saved)
        XCTAssertEqual(e.next(), .enrollFinish(count: 5))
        XCTAssertEqual(e.phase, .finished)
        e.apply(.done)
        XCTAssertEqual(e.phase, .finished)
    }

    func testTooQuietReason() {
        var e = VoiceEnrollment()
        _ = e.start()
        e.apply(.failed(index: 0, reason: "too_quiet"))
        XCTAssertEqual(e.phase, .failed("That was a little quiet. Let's try once more."))
    }

    func testOtherReasonsUseGenericMessage() {
        for reason in [nil, "", "mic_error"] as [String?] {
            var e = VoiceEnrollment()
            _ = e.start()
            e.apply(.failed(index: 0, reason: reason))
            XCTAssertEqual(e.phase, .failed(VoiceEnrollment.genericFailure))
        }
        XCTAssertEqual(VoiceEnrollment.genericFailure, "We didn't hear that. Let's try again.")
    }

    func testRetryRestartsSameSentence() {
        var e = VoiceEnrollment(index: 2, phase: .failed("x"))
        XCTAssertEqual(e.retry(), .enrollStart(index: 2, text: text[2]))
        XCTAssertEqual(e.phase, .recording)
        XCTAssertEqual(e.index, 2)
    }

    func testTimeoutFailsARecordingOnly() {
        var e = VoiceEnrollment()
        _ = e.start()
        e.timeout()
        XCTAssertEqual(e.phase, .failed("We didn't hear that. Let's try again."))
        var saved = VoiceEnrollment(index: 0, phase: .saved)
        saved.timeout()
        XCTAssertEqual(saved.phase, .saved)
    }

    func testStaleIndexEventsAreIgnored() {
        var e = VoiceEnrollment(index: 1, phase: .ready)
        _ = e.start()
        e.apply(.saved(index: 0))
        XCTAssertEqual(e.phase, .recording)
        e.apply(.failed(index: 0, reason: "too_quiet"))
        XCTAssertEqual(e.phase, .recording)
        e.apply(.saved(index: 1))
        XCTAssertEqual(e.phase, .saved)
    }

    func testEventsOutsideRecordingAreIgnored() {
        var e = VoiceEnrollment()
        e.apply(.saved(index: 0))
        XCTAssertEqual(e.phase, .ready)
        XCTAssertNil(e.next())
    }

    func testPuckLostResetsRecordingAndFailed() {
        var recording = VoiceEnrollment()
        _ = recording.start()
        recording.puckLost()
        XCTAssertEqual(recording.phase, .ready)
        var failed = VoiceEnrollment(index: 2, phase: .failed("x"))
        failed.puckLost()
        XCTAssertEqual(failed.phase, .ready)
        XCTAssertEqual(failed.index, 2)
        var saved = VoiceEnrollment(index: 1, phase: .saved)
        saved.puckLost()
        XCTAssertEqual(saved.phase, .saved)
    }

    func testLateEventFromTimedOutAttemptIsNotCreditedToRetry() {
        var e = VoiceEnrollment()
        _ = e.start()
        e.timeout()
        _ = e.retry()
        e.apply(.saved(index: 0))
        XCTAssertEqual(e.phase, .recording)
        e.apply(.recording(index: 0))
        e.apply(.saved(index: 0))
        XCTAssertEqual(e.phase, .saved)
    }
}
