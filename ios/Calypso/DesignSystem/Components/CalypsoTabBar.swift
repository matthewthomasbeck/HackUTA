import SwiftUI

enum HomeTab: Int, CaseIterable {
    case today, people, account

    var title: String {
        switch self {
        case .today: "Today"
        case .people: "People"
        case .account: "Account"
        }
    }

    var systemImage: String {
        switch self {
        case .today: "calendar"
        case .people: "person.2"
        case .account: "person"
        }
    }
}

/// Figma `Tab Bar` (17:147): Card background, Periwinkle Mist top hairline, Mist pill behind the selected icon
/// only. The selected label is Periwinkle Deep on Card; unselected items are Ink. The system tab bar is
/// replaced because the iOS 26 one is glass (plan ruling); VoiceOver semantics are kept by hand.
struct CalypsoTabBar: View {
    @Binding var selection: HomeTab

    init(selection: Binding<HomeTab>) {
        _selection = selection
    }

    var body: some View {
        HStack(spacing: 0) {
            ForEach(HomeTab.allCases, id: \.self) { tab in
                item(tab)
            }
        }
        .padding(.horizontal, 8)
        .background(alignment: .top) {
            Color.card
                .overlay(alignment: .top) { Color.periwinkleMist.frame(height: 1) }
                .ignoresSafeArea(edges: .bottom)
        }
        // Tab labels are capped like the system bar; the Large Content Viewer covers bigger sizes.
        .dynamicTypeSize(...DynamicTypeSize.xxxLarge)
    }

    private func item(_ tab: HomeTab) -> some View {
        let selected = tab == selection
        return Button {
            selection = tab
        } label: {
            VStack(spacing: 2) {
                CalypsoIcon(tab.systemImage, size: 28, relativeTo: .footnote)
                    .foregroundStyle(selected ? Color.periwinkleDeep : Color.ink)
                    .frame(width: 64, height: 32)
                    .background(selected ? Color.periwinkleMist : Color.clear, in: Capsule())
                Text(tab.title)
                    .calypsoFont(.caption)
                    .foregroundStyle(selected ? Color.periwinkleDeep : Color.ink)
                    .lineLimit(1)
                    .minimumScaleFactor(0.8)
            }
            .padding(.top, 4)
            .frame(maxWidth: .infinity, minHeight: 64, alignment: .top)
            .contentShape(Rectangle())
        }
        .buttonStyle(PressableStyle())
        .accessibilityLabel(tab.title)
        .accessibilityHint("Tab, \(tab.rawValue + 1) of \(HomeTab.allCases.count)")
        .accessibilityAddTraits(selected ? [.isSelected] : [])
        .accessibilityShowsLargeContentViewer {
            Label(tab.title, systemImage: tab.systemImage)
        }
    }
}

#Preview {
    struct Demo: View {
        @State var tab: HomeTab = .today
        var body: some View {
            VStack(spacing: 0) {
                Color.paper
                CalypsoTabBar(selection: $tab)
            }
        }
    }
    return Demo()
}
