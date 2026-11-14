import SwiftUI

@main
struct CalypsoApp: App {
    @AppStorage("onboarded") private var onboarded = false

    var body: some Scene {
        WindowGroup {
            if onboarded {
                HomeView()
            } else {
                OnboardingView()
            }
        }
    }
}

/// Placeholder until the People / Today / Sync screens land.
struct HomeView: View {
    var body: some View {
        VStack(spacing: 16) {
            Image("Logo").resizable().scaledToFit().frame(width: 96).clipShape(Circle())
            Text("Calypso⁻¹").font(.largeTitle.bold())
        }
    }
}
