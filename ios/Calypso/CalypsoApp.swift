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

/// The system tab bar is hidden (the iOS 26 one is glass) and `CalypsoTabBar` sits in the bottom safe area
/// instead, so every tab's content scrolls clear of it.
struct HomeView: View {
    @Environment(\.scenePhase) private var scenePhase
    @State private var tab: HomeTab
    private let client = APIClient.configured

    init(initialTab: HomeTab = .today) {
        _tab = State(initialValue: initialTab)
    }

    var body: some View {
        TabView(selection: $tab) {
            TodayView(client: client)
                .tag(HomeTab.today)
                .toolbar(.hidden, for: .tabBar)
            PeopleListView(client: client)
                .tag(HomeTab.people)
                .toolbar(.hidden, for: .tabBar)
            AccountView()
                .tag(HomeTab.account)
                .toolbar(.hidden, for: .tabBar)
        }
        .safeAreaInset(edge: .bottom, spacing: 0) {
            CalypsoTabBar(selection: $tab)
        }
        .onChange(of: scenePhase, initial: true) { _, phase in
            if phase == .active, let client { Task { await PhotoSync.syncNew(using: client) } }
        }
    }
}
