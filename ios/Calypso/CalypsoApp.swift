import SwiftUI
import UIKit

/// Visit monitoring must start at launch: iOS relaunches a terminated app in the background for visits.
final class AppDelegate: NSObject, UIApplicationDelegate {
    private var visitSync: VisitSync?

    func application(_ application: UIApplication,
                     didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {
        if UserDefaults.standard.bool(forKey: "onboarded") { startVisitSync() }
        return true
    }

    func startVisitSync() {
        guard visitSync == nil, let client = APIClient.configured else { return }
        let sync = VisitSync(client: client)
        visitSync = sync
        sync.start()
    }
}

@main
struct CalypsoApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) private var delegate
    @AppStorage("onboarded") private var onboarded = false

    var body: some Scene {
        WindowGroup {
            Group {
                if let route = ScreenRoute.current {
                    ScreenRoute.view(for: route)
                } else if onboarded {
                    HomeView()
                } else {
                    OnboardingView()
                }
            }
            .preferredColorScheme(.light)
        }
        .onChange(of: onboarded) { _, done in
            if done { delegate.startVisitSync() }
        }
    }
}

struct HomeView: View {
    @Environment(\.scenePhase) private var scenePhase
    private let client = APIClient.configured

    var body: some View {
        TabView {
            TodayView(client: client).tabItem { Label("Today", systemImage: "clock") }
            PeopleListView(client: client).tabItem { Label("People", systemImage: "person.2") }
            AccountView().tabItem { Label("Account", systemImage: "person.crop.circle") }
        }
        .onChange(of: scenePhase, initial: true) { _, phase in
            if phase == .active, let client { Task { await PhotoSync.syncNew(using: client) } }
        }
    }
}
