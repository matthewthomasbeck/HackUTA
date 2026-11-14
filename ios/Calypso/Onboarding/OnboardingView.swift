import SwiftUI

struct OnboardingView: View {
    private enum Step { case welcome, addContact, groupCall, permissions }

    @AppStorage("onboarded") private var onboarded = false
    @State private var step = Step.welcome

    var body: some View {
        switch step {
        case .welcome:
            VStack(spacing: 24) {
                Spacer()
                Image("Logo").resizable().scaledToFit().frame(width: 140).clipShape(Circle())
                Text("Welcome to Calypso⁻¹").font(.largeTitle.bold()).multilineTextAlignment(.center)
                Text("A gentle memory companion for the people you love.")
                    .multilineTextAlignment(.center).foregroundStyle(.secondary)
                Spacer()
                Button("Get Started") { step = .addContact }.buttonStyle(.borderedProminent).controlSize(.large)
            }
            .padding()
        case .addContact:
            AddContactView { step = .groupCall }
        case .groupCall:
            GroupCallHowToView { step = .permissions }
        case .permissions:
            PermissionsView { onboarded = true }
        }
    }
}
