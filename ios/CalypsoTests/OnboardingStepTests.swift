import XCTest
@testable import Calypso

final class OnboardingStepTests: XCTestCase {
    func testStepOrder() {
        XCTAssertEqual(OnboardingStep.allCases, [.welcome, .companion, .addContact, .groupCall, .permissions, .allSet])
    }

    func testTotalIsSix() {
        XCTAssertEqual(OnboardingStep.total, 6)
    }

    func testNumbers() {
        XCTAssertEqual(OnboardingStep.welcome.number, 1)
        XCTAssertEqual(OnboardingStep.groupCall.number, 4)
        XCTAssertEqual(OnboardingStep.permissions.number, 5)
        XCTAssertEqual(OnboardingStep.allSet.number, 6)
    }

    func testNextPrevious() {
        XCTAssertNil(OnboardingStep.welcome.previous)
        XCTAssertNil(OnboardingStep.allSet.next)
        XCTAssertEqual(OnboardingStep.addContact.next, .groupCall)
        XCTAssertEqual(OnboardingStep.addContact.previous, .companion)
    }
}
