import SwiftUI

struct OnboardingView: View {
    @AppStorage("onboarded") private var onboarded = false
    @State private var step: OnboardingStep
    /// Whether the last move went forward, so the push slides the right way.
    @State private var forward = true
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    init(initialStep: OnboardingStep = .welcome) {
        _step = State(initialValue: initialStep)
    }

    var body: some View {
        ZStack {
            Color.paper.ignoresSafeArea()
            screen(for: step)
                .id(step)
                .transition(transition)
        }
    }

    @ViewBuilder private func screen(for step: OnboardingStep) -> some View {
        switch step {
        case .welcome:
            WelcomeView(onNext: goNext)
        case .companion:
            MeetCompanionView(onBack: goBack, onNext: goNext)
        case .addContact:
            AddContactView(onBack: goBack, onNext: goNext)
        case .groupCall:
            GroupCallHowToView(onBack: goBack, onNext: goNext)
        case .permissions:
            PermissionsView(onBack: goBack, onDone: goNext)
        case .allSet:
            // Only the final step finishes onboarding.
            AllSetView { onboarded = true }
        }
    }

    private var transition: AnyTransition {
        if reduceMotion { return .opacity }
        return .asymmetric(insertion: .move(edge: forward ? .trailing : .leading).combined(with: .opacity),
                           removal: .move(edge: forward ? .leading : .trailing).combined(with: .opacity))
    }

    private func goNext() { move(to: step.next, forward: true) }

    private func goBack() { move(to: step.previous, forward: false) }

    private func move(to target: OnboardingStep?, forward: Bool) {
        guard let target else { return }
        let animate = {
            withAnimation(reduceMotion ? .easeInOut(duration: 0.2) : .spring(response: 0.35, dampingFraction: 1)) {
                step = target
            }
        }
        guard self.forward != forward else { return animate() }
        // Let the outgoing screen pick up the new direction before it is removed.
        self.forward = forward
        DispatchQueue.main.async(execute: animate)
    }
}

#Preview {
    OnboardingView()
}
