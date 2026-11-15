import SwiftUI

/// Person (Figma 20:668 named, 20:852 someone new). The navigation bar is hidden (the iOS 26 system back button
/// is a glass circle) and the paper-cut "‹ People" button sits at the top of the content, as in Figma; swipe-back
/// still works through `.swipeBackEnabled()` (`SwipeBack.swift`). An unknown person is never titled "Unnamed visitor".
/// `startEditing` opens the edit-name sheet on appear (DEBUG `-screen edit-name-…` route).
struct PersonDetailView: View {
    let client: APIClient?
    @State var person: Person
    var onUpdate: (Person) -> Void = { _ in }
    @State private var memories: [String] = []
    @State private var editing = false
    @State private var draftName = ""
    @State private var error: String?

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.dismiss) private var dismiss

    init(client: APIClient?, person: Person, onUpdate: @escaping (Person) -> Void = { _ in },
         startEditing: Bool = false) {
        self.client = client
        _person = State(initialValue: person)
        self.onUpdate = onUpdate
        _editing = State(initialValue: startEditing)
        _draftName = State(initialValue: person.displayName ?? "")
    }

    private var isKnown: Bool { person.displayName != nil }

    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                BackButton("People") { dismiss() }
                    .frame(maxWidth: .infinity, alignment: .leading)
                if let name = person.displayName {
                    namedIdentity(name)
                    facts
                    recentMoments
                    if let error { errorText(error) }
                    CalypsoButton("Edit name", kind: .secondary, action: startEditing)
                } else {
                    unknownIdentity
                    if let error { errorText(error) }
                    CalypsoButton("Add their name", action: startEditing)
                    if memories.isEmpty {
                        noMomentsBlock
                    } else {
                        recentMoments
                    }
                }
            }
            .padding(.horizontal, 24)
            .padding(.top, 8)
            .padding(.bottom, 32)
            .animation(reduceMotion ? nil : .spring(response: 0.35, dampingFraction: 1), value: memories)
        }
        .background(Color.paper.ignoresSafeArea())
        .paperTopEdge()
        .navigationBarBackButtonHidden(true)
        .toolbar(.hidden, for: .navigationBar)
        .swipeBackEnabled()
        .sheet(isPresented: $editing) {
            EditNameSheet(initialName: draftName, onSave: { name in
                draftName = name
                editing = false
                Task { await save() }
            }, onCancel: { editing = false })
        }
        .task { await load() }
    }

    private func startEditing() {
        draftName = person.displayName ?? ""
        editing = true
    }

    // MARK: Named

    private func namedIdentity(_ name: String) -> some View {
        VStack(spacing: 8) {
            Avatar(urlString: person.facePhotoUrl, isKnown: true, size: 160)
            Text(name)
                .calypsoFont(.display)
                .foregroundStyle(Color.ink)
                .multilineTextAlignment(.center)
                .accessibilityAddTraits(.isHeader)
            if let relationship = PeoplePresentation.relationshipLabel(person.relationship) {
                Text(relationship)
                    .calypsoFont(.callout)
                    .foregroundStyle(Color.inkSoft)
                    .multilineTextAlignment(.center)
            }
        }
        .frame(maxWidth: .infinity)
    }

    @ViewBuilder private var facts: some View {
        if !person.facts.isEmpty {
            PaperCard {
                VStack(alignment: .leading, spacing: 12) {
                    Text("Things to remember")
                        .calypsoFont(.headline)
                        .foregroundStyle(Color.ink)
                        .accessibilityAddTraits(.isHeader)
                    ForEach(Array(person.facts.enumerated()), id: \.offset) { _, fact in
                        HStack(alignment: .firstTextBaseline, spacing: 12) {
                            Circle()
                                .fill(Color.apricot)
                                .frame(width: 14, height: 14)
                                .alignmentGuide(.firstTextBaseline) { $0[VerticalAlignment.center] + 6 }
                                .accessibilityHidden(true)
                            Text(fact)
                                .calypsoFont(.body)
                                .foregroundStyle(Color.ink)
                                .frame(maxWidth: .infinity, alignment: .leading)
                        }
                    }
                }
            }
        }
    }

    // MARK: Unknown

    private var unknownIdentity: some View {
        VStack(spacing: 12) {
            Avatar(urlString: nil, isKnown: false, size: 160)
            Text(PeoplePresentation.unknownName)
                .calypsoFont(.title)
                .foregroundStyle(Color.ink)
                .accessibilityAddTraits(.isHeader)
            Text("Calypso⁻¹ has seen this person but doesn’t know their name yet.")
                .calypsoFont(.body)
                .foregroundStyle(Color.inkSoft)
        }
        .multilineTextAlignment(.center)
        .frame(maxWidth: .infinity)
    }

    private var noMomentsBlock: some View {
        HStack(spacing: 12) {
            Mascot(pose: .thinking, size: .s, shadow: true)
            Text(Self.noMoments)
                .calypsoFont(.callout)
                .foregroundStyle(Color.ink)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 12)
        .background(Color.apricotCream, in: RoundedRectangle(cornerRadius: 24))
    }

    // MARK: Shared

    private static let noMoments = "No moments yet. They’ll appear after your next visit together."

    private var recentMoments: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Recent moments")
                .calypsoFont(.headline)
                .foregroundStyle(Color.ink)
                .accessibilityAddTraits(.isHeader)
            if memories.isEmpty {
                Text(Self.noMoments)
                    .calypsoFont(.callout)
                    .foregroundStyle(Color.inkSoft)
            }
            ForEach(Array(memories.enumerated()), id: \.offset) { _, memory in
                PaperCard {
                    Text(memory)
                        .calypsoFont(.body)
                        .foregroundStyle(Color.ink)
                }
                .transition(.opacity)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func errorText(_ message: String) -> some View {
        Text(message)
            .calypsoFont(.callout)
            .foregroundStyle(Color.inkSoft)
            .multilineTextAlignment(.center)
            .frame(maxWidth: .infinity)
    }

    // MARK: Loading

    private func load() async {
        guard let client, let detail = try? await client.person(id: person.id) else { return }
        person = detail.person
        onUpdate(person)
        memories = detail.memories
    }

    private func save() async {
        let name = draftName.trimmingCharacters(in: .whitespaces)
        guard let client, !name.isEmpty else { return }
        do {
            person = try await client.updatePerson(id: person.id, name: name)
            onUpdate(person)
            error = nil
        } catch {
            self.error = "Couldn’t save the name"
        }
    }
}

#Preview("Named") {
    NavigationStack {
        PersonDetailView(client: nil, person: Person(id: "p_sarah", name: "Sarah", relationship: "daughter",
                                                     facts: ["Lives in Austin", "Has a dog named Biscuit"]))
    }
    .tint(Color.periwinkleDeep)
}

#Preview("Someone new") {
    NavigationStack {
        PersonDetailView(client: nil, person: Person(id: "p_unknown"))
    }
    .tint(Color.periwinkleDeep)
}
