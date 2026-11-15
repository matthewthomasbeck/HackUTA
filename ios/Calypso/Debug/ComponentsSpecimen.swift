#if DEBUG
import SwiftUI

/// `-screen components` (and `components-2`, `components-3`, `components-4`, `components-ax`): every design-system component in
/// each state, split into pages so each fits a screenshot. Page 5 is shown at AX5.
struct ComponentsSpecimen: View {
    let page: Int
    @State private var tab: HomeTab = .today

    var body: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    switch page {
                    case 1: pageOne
                    case 2: pageTwo
                    case 3: pageThree
                    case 4: pageFour
                    default: pageAX
                    }
                }
                .padding(24)
            }
            if page == 1 { CalypsoTabBar(selection: $tab) }
        }
        .background(Color.paper)
    }

    @ViewBuilder private var pageOne: some View {
        NavHeader(caption: "Saturday, November 14", title: "Today") { Mascot(pose: .wave, size: .s) }
        DaySwitcher(labels: .init(previous: "Yesterday", next: "Tomorrow", nextEnabled: false),
                    onPrevious: {}, onNext: {})
        DaySwitcher(labels: .init(previous: "Tuesday", next: "Thursday", nextEnabled: true),
                    onPrevious: {}, onNext: {})
        CalypsoButton("Continue") {}
        CalypsoButton("Continue", kind: .secondary) {}
        CalypsoButton("Continue", kind: .quiet) {}
        HStack {
            BackButton {}
            Spacer()
            Logo(size: 72)
        }
        StepDots(current: 2, total: 6)
    }

    @ViewBuilder private var pageTwo: some View {
        HStack(spacing: 16) {
            Avatar(urlString: nil, isKnown: true, size: 64)
            Avatar(urlString: nil, isKnown: true, size: 160)
        }
        HStack(spacing: 16) {
            Avatar(urlString: nil, isKnown: false, size: 64)
            Avatar(urlString: nil, isKnown: false, size: 160)
        }
        FlowLayout(spacing: 12) {
            PersonChip(name: "Sarah")
            PersonChip(name: nil)
        }
        PlaceRow(place: "Blue Bean Café", isUncertain: false)
        PlaceRow(place: "Somewhere with park sounds", isUncertain: true)
    }

    @ViewBuilder private var pageThree: some View {
        PhotoTile(url: URL(string: "https://example.invalid/hero.jpg"), style: .hero)
        HStack(spacing: 8) {
            PhotoTile(url: URL(string: "https://example.invalid/t.jpg"), style: .thumb)
            PhotoTile(url: nil, style: .thumb)
        }
        Text("Paper card").calypsoFont(.body).foregroundStyle(Color.ink).paperCard()
        CalmMessage(pose: .resting, title: "A quiet day",
                    message: "Nothing new was recorded. That’s okay. Rest days matter.",
                    buttonTitle: "Look at another day") {}
    }

    @ViewBuilder private var pageFour: some View {
        MomentCard(event: ComponentSamples.event(), names: ComponentSamples.names,
                   photoURL: ComponentSamples.photoURL)
        MomentCard(event: ComponentSamples.event(time: "15:00", summary: "A walk in the garden",
                                                 place: "Somewhere with park sounds", confidence: 0.4,
                                                 people: ["p_tom"], photos: ["a", "missing_b", "c"]),
                   names: ComponentSamples.names, photoURL: ComponentSamples.photoURL)
    }

    @ViewBuilder private var pageAX: some View {
        DaySwitcher(labels: .init(previous: "Tuesday", next: "Thursday", nextEnabled: true),
                    onPrevious: {}, onNext: {})
        PersonChip(name: "Grandma Rosalind")
        PersonChip(name: nil)
        PlaceRow(place: "Somewhere with park sounds", isUncertain: true)
        MomentCard(event: ComponentSamples.event(summary: "Coffee with Sarah", people: ["p_sarah", "p_new"]),
                   names: ComponentSamples.names, photoURL: ComponentSamples.photoURL)
        StepDots(current: 3, total: 6)
    }
}
#endif
