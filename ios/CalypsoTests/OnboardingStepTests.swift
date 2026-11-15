import XCTest
@testable import Calypso

final class OnboardingStepTests: XCTestCase {
    func testStepOrder() {
        XCTAssertEqual(OnboardingStep.allCases,
                       [.welcome, .companion, .addContact, .groupCall, .permissions, .inviteFamily, .allSet])
    }

    func testTotalIsSeven() {
        XCTAssertEqual(OnboardingStep.total, 7)
    }

    func testNumbers() {
        XCTAssertEqual(OnboardingStep.welcome.number, 1)
        XCTAssertEqual(OnboardingStep.groupCall.number, 4)
        XCTAssertEqual(OnboardingStep.permissions.number, 5)
        XCTAssertEqual(OnboardingStep.inviteFamily.number, 6)
        XCTAssertEqual(OnboardingStep.allSet.number, 7)
    }

    func testNextPrevious() {
        XCTAssertNil(OnboardingStep.welcome.previous)
        XCTAssertNil(OnboardingStep.allSet.next)
        XCTAssertEqual(OnboardingStep.addContact.next, .groupCall)
        XCTAssertEqual(OnboardingStep.addContact.previous, .companion)
        XCTAssertEqual(OnboardingStep.permissions.next, .inviteFamily)
        XCTAssertEqual(OnboardingStep.inviteFamily.previous, .permissions)
        XCTAssertEqual(OnboardingStep.inviteFamily.next, .allSet)
        XCTAssertEqual(OnboardingStep.allSet.previous, .inviteFamily)
    }
}
