import Foundation

/// The onboarding steps, in order. Every step shows "Step N of 7".
enum OnboardingStep: Int, CaseIterable {
    case welcome, companion, addContact, groupCall, permissions, inviteFamily, allSet

    static var total: Int { allCases.count }

    /// 1-based position shown to the user.
    var number: Int { rawValue + 1 }

    var next: OnboardingStep? { OnboardingStep(rawValue: rawValue + 1) }

    var previous: OnboardingStep? { OnboardingStep(rawValue: rawValue - 1) }
}
