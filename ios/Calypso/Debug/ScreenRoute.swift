import SwiftUI

/// DEBUG-only `-screen <route>` launch argument, so any screen can be opened directly in the simulator.
enum ScreenRoute {
    static var current: String? {
        #if DEBUG
        let args = ProcessInfo.processInfo.arguments
        guard let i = args.firstIndex(of: "-screen"), i + 1 < args.count else { return nil }
        return args[i + 1]
        #else
        return nil
        #endif
    }

    /// Later tasks add a case per route here.
    static func view(for route: String) -> AnyView {
        #if DEBUG
        // "onboarding-<rawValue>" or "onboarding-<name>", e.g. "onboarding-3" / "onboarding-groupCall".
        if let step = OnboardingStep.allCases.first(where: {
            route == "onboarding-\($0.rawValue)" || route == "onboarding-\($0)"
        }) {
            return AnyView(OnboardingView(initialStep: step))
        }
        #endif
        switch route {
        #if DEBUG
        case "design-system":
            return AnyView(DesignSystemSpecimen())
        case "components":
            return AnyView(ComponentsSpecimen(page: 1))
        case "components-2":
            return AnyView(ComponentsSpecimen(page: 2))
        case "components-3":
            return AnyView(ComponentsSpecimen(page: 3))
        case "components-4":
            return AnyView(ComponentsSpecimen(page: 4))
        case "components-ax":
            return AnyView(ComponentsSpecimen(page: 5).dynamicTypeSize(.accessibility5))
        case "today":
            return AnyView(TodayView(client: APIClient.configured))
        case "today-bottom":
            return AnyView(TodayView(client: APIClient.configured).debugScrolledToEnd())
        case "today-ax":
            return AnyView(TodayView(client: APIClient.configured).dynamicTypeSize(.accessibility5))
        case "today-quiet":
            let fiveDaysAgo = Calendar.current.date(byAdding: .day, value: -5, to: Date()) ?? Date()
            return AnyView(TodayView(client: APIClient.configured, initialDay: fiveDaysAgo).debugWithTabBar())
        case "today-error":
            // Nothing listens on port 9, so every request fails fast.
            let unreachable = APIClient(baseURL: URL(string: "http://127.0.0.1:9")!, token: "dev-token")
            return AnyView(TodayView(client: unreachable).debugWithTabBar())
        case "people":
            return AnyView(PeopleListView(client: APIClient.configured))
        case "people-ax":
            return AnyView(PeopleListView(client: APIClient.configured).dynamicTypeSize(.accessibility5))
        case "person-p_sarah":
            return AnyView(DebugPersonStack(seed: Person(id: "p_sarah", name: "Sarah", relationship: "daughter")))
        case "person-p_unknown":
            return AnyView(DebugPersonStack(seed: Person(id: "p_unknown")))
        case "edit-name-p_unknown":
            return AnyView(DebugPersonStack(seed: Person(id: "p_unknown"), startEditing: true))
        case "home":
            return AnyView(HomeView())
        case "account":
            return AnyView(HomeView(initialTab: .account))
        case "account-bottom":
            return AnyView(AccountView().defaultScrollAnchor(.bottom)
                .safeAreaInset(edge: .bottom, spacing: 0) { CalypsoTabBar(selection: .constant(.account)) })
        case "reset":
            // Account with the dialog open, over the same tab bar the app shows.
            return AnyView(AccountView(confirmingReset: true)
                .safeAreaInset(edge: .bottom, spacing: 0) { CalypsoTabBar(selection: .constant(.account)) })
        #endif
        default:
            return AnyView(Text("Unknown route").calypsoFont(.body).padding())
        }
    }
}

#if DEBUG
/// Opens a person screen already pushed on a People stack, so the back button and swipe-back work as in the app.
private struct DebugPersonStack: View {
    let seed: Person
    var startEditing = false
    @State private var path: [String]

    init(seed: Person, startEditing: Bool = false) {
        self.seed = seed
        self.startEditing = startEditing
        _path = State(initialValue: [seed.id])
    }

    var body: some View {
        NavigationStack(path: $path) {
            Color.paper
                .ignoresSafeArea()
                .navigationTitle("People")
                .toolbar(.hidden, for: .navigationBar)
                .navigationDestination(for: String.self) { _ in
                    PersonDetailView(client: APIClient.configured, person: seed, startEditing: startEditing)
                }
        }
        .tint(Color.periwinkleDeep)
    }
}
#endif

#if DEBUG
struct DesignSystemSpecimen: View {
    private let colors: [(String, Color)] = [
        ("paper", .paper), ("card", .card), ("ink", .ink), ("inkSoft", .inkSoft),
        ("periwinkle", .periwinkle), ("periwinkleDeep", .periwinkleDeep), ("periwinkleMist", .periwinkleMist),
        ("apricot", .apricot), ("apricotCream", .apricotCream), ("olive", .olive), ("terracotta", .terracotta),
    ]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                Text("Colors").calypsoFont(.title)
                LazyVGrid(columns: [GridItem(.adaptive(minimum: 110), spacing: 8)], spacing: 8) {
                    ForEach(colors, id: \.0) { name, color in
                        VStack(spacing: 4) {
                            RoundedRectangle(cornerRadius: 12).fill(color).frame(height: 48)
                                .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color.ink.opacity(0.2)))
                            Text(name).font(.system(size: 12)).foregroundStyle(Color.ink)
                        }
                    }
                }
                Text("Type").calypsoFont(.title)
                ForEach(CalypsoTextStyle.allCases, id: \.self) { style in
                    Text("\(String(describing: style)) \(Int(style.size))/\(Int(style.leading))")
                        .calypsoFont(style).foregroundStyle(Color.ink)
                }
                Text("Mascot").calypsoFont(.title)
                LazyVGrid(columns: [GridItem(.adaptive(minimum: 120), spacing: 12)], spacing: 12) {
                    ForEach(MascotPose.allCases, id: \.self) { pose in
                        VStack {
                            Mascot(pose: pose, size: .m, shadow: true)
                            Text(pose.rawValue).calypsoFont(.caption).foregroundStyle(Color.inkSoft)
                        }
                    }
                }
                Text("Decorations").calypsoFont(.title)
                ForEach(Decoration.allCases, id: \.self) {
                    DecorationImage($0).frame(height: 100)
                }
            }
            .padding(24)
        }
        .background(Color.paper)
    }
}
#endif

#if DEBUG
private extension View {
    /// Pins the real tab bar under a state route, so screenshots show what fits above it.
    func debugWithTabBar() -> some View {
        safeAreaInset(edge: .bottom, spacing: 0) { CalypsoTabBar(selection: .constant(.today)) }
    }
}
#endif
