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

struct HomeView: View {
    @Environment(\.scenePhase) private var scenePhase
    @State private var visitSync = APIClient.configured.map(VisitSync.init)
    private let client = APIClient.configured

    var body: some View {
        TabView {
            TodayView(client: client).tabItem { Label("Today", systemImage: "clock") }
            PeopleListView(client: client).tabItem { Label("People", systemImage: "person.2") }
        }
        .task { visitSync?.start() }
        .onChange(of: scenePhase) { _, phase in
            if phase == .active, let client { Task { await PhotoSync.syncNew(using: client) } }
        }
    }
}
