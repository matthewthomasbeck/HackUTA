import XCTest
@testable import Calypso

final class OnboardingStepTests: XCTestCase {
    func testStepOrder() {
        XCTAssertEqual(OnboardingStep.allCases,
                       [.welcome, .companion, .addContact, .groupCall, .permissions, .connectPuck, .voiceSetup,
                        .inviteFamily, .allSet])
    }

    func testTotalIsNine() {
        XCTAssertEqual(OnboardingStep.total, 9)
    }

    func testNumbers() {
        XCTAssertEqual(OnboardingStep.welcome.number, 1)
        XCTAssertEqual(OnboardingStep.groupCall.number, 4)
        XCTAssertEqual(OnboardingStep.permissions.number, 5)
        XCTAssertEqual(OnboardingStep.connectPuck.number, 6)
        XCTAssertEqual(OnboardingStep.voiceSetup.number, 7)
        XCTAssertEqual(OnboardingStep.inviteFamily.number, 8)
        XCTAssertEqual(OnboardingStep.allSet.number, 9)
    }

    func testNextPrevious() {
        XCTAssertNil(OnboardingStep.welcome.previous)
        XCTAssertNil(OnboardingStep.allSet.next)
        XCTAssertEqual(OnboardingStep.addContact.next, .groupCall)
        XCTAssertEqual(OnboardingStep.addContact.previous, .companion)
        XCTAssertEqual(OnboardingStep.permissions.next, .connectPuck)
        XCTAssertEqual(OnboardingStep.connectPuck.next, .voiceSetup)
        XCTAssertEqual(OnboardingStep.voiceSetup.next, .inviteFamily)
        XCTAssertEqual(OnboardingStep.inviteFamily.previous, .voiceSetup)
        XCTAssertEqual(OnboardingStep.inviteFamily.next, .allSet)
        XCTAssertEqual(OnboardingStep.allSet.previous, .inviteFamily)
    }
}
