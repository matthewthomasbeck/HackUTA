import SwiftUI

/// People (Figma 20:212): header with the olive branch, meander trim, then one card row per person.
/// The patient is never listed. An unknown person (`name == nil`) reads "Getting to know someone new…".
struct PeopleListView: View {
    let client: APIClient?
    @State private var people: [Person] = []
    @State private var error: String?
    @State private var hasLoaded = false

    @Environment(\.dynamicTypeSize) private var dynamicTypeSize

    private var listed: [Person] { people.filter { !$0.isPatient } }

    var body: some View {
        NavigationStack {
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 12) {
                    header
                    content
                }
                .padding(.horizontal, 24)
                .padding(.top, 16)
                .padding(.bottom, 24)
            }
            .background(Color.paper.ignoresSafeArea())
            // Hidden here and on the detail screen, which draws its own "‹ People" button.
            .navigationTitle("People")
            .toolbar(.hidden, for: .navigationBar)
            .refreshable { await load() }
            .task { await load() }
        }
        .tint(Color.periwinkleDeep)
    }

    // MARK: Header

    private var header: some View {
        VStack(spacing: 12) {
            // The branch overlays the title row's trailing edge (as in Figma) instead of taking a column, so the
            // caption keeps the full width.
            NavHeader(caption: "The people who love you.", title: "People")
                .overlay(alignment: .bottomTrailing) {
                    if !dynamicTypeSize.isAccessibilitySize {
                        DecorationImage(.oliveBranch)
                            .frame(width: 112)
                    }
                }
            // The 393pt art is pinned left and clipped to the column, as in Figma.
            DecorationImage(.meander)
                .frame(width: 393, height: 28)
                .frame(maxWidth: 336, alignment: .leading)
                .clipped()
                .frame(maxWidth: .infinity)
        }
    }

    // MARK: States

    @ViewBuilder private var content: some View {
        if !listed.isEmpty {
            ForEach(listed) { person in
                NavigationLink {
                    PersonDetailView(client: client, person: person) { updated in
                        if let i = people.firstIndex(where: { $0.id == updated.id }) { people[i] = updated }
                    }
                } label: {
                    PersonRow(person: person)
                }
                .buttonStyle(PressableStyle())
            }
        } else if error != nil {
            CalmMessage(pose: .thinking, title: "We couldn’t load people right now.", message: "",
                        buttonTitle: "Try again", scene: false) {
                Task { await load() }
            }
            .padding(.top, 32)
        } else if hasLoaded {
            CalmMessage(pose: .peek, title: "No people yet",
                        message: "People appear after your first FaceTime with Calypso⁻¹.")
                .padding(.top, 32)
        } else {
            ProgressView()
                .controlSize(.large)
                .tint(Color.periwinkleDeep)
                .frame(maxWidth: .infinity)
                .padding(.top, 80)
                .accessibilityLabel("Loading people")
        }
    }

    private func load() async {
        defer { hasLoaded = true }
        guard let client else { error = "App isn't configured"; return }
        do {
            people = try await client.people()
            error = nil
        } catch {
            self.error = "Couldn't load people"
        }
    }
}

/// Wording for People rows and the person screen. Never guesses a name.
enum PeoplePresentation {
    static let unknownName = "Getting to know someone new…"

    /// "mother" → "Mother": first letter capitalized only, the rest left as written. Blank → nil.
    static func relationshipLabel(_ relationship: String?) -> String? {
        guard let trimmed = relationship?.trimmingCharacters(in: .whitespacesAndNewlines),
              let first = trimmed.first else { return nil }
        return first.uppercased() + trimmed.dropFirst()
    }

    static func rowAccessibilityLabel(_ person: Person) -> String {
        guard let name = person.name else { return "\(unknownName) Tap to add their name." }
        return [name, relationshipLabel(person.relationship)].compactMap { $0 }.joined(separator: ", ")
    }
}

/// Card row (≥ 104pt): Avatar 64, Headline name, Callout relationship, chevron.
/// At accessibility sizes the avatar sits above the text so names never truncate.
private struct PersonRow: View {
    let person: Person
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize

    var body: some View {
        Group {
            if dynamicTypeSize.isAccessibilitySize {
                VStack(alignment: .leading, spacing: 12) {
                    HStack {
                        avatar
                        Spacer(minLength: 12)
                        chevron
                    }
                    text
                }
            } else {
                HStack(spacing: 12) {
                    avatar
                    text
                    chevron
                }
            }
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 16)
        .frame(maxWidth: .infinity, minHeight: 104, alignment: .leading)
        .background(Color.card, in: RoundedRectangle(cornerRadius: 24))
        .overlay(RoundedRectangle(cornerRadius: 24).strokeBorder(Color.periwinkleMist, lineWidth: 2))
        .contentShape(RoundedRectangle(cornerRadius: 24))
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(PeoplePresentation.rowAccessibilityLabel(person))
    }

    private var avatar: some View {
        Avatar(urlString: person.facePhotoUrl, isKnown: person.name != nil, size: 64)
    }

    private var text: some View {
        VStack(alignment: .leading, spacing: 4) {
            // Figma 20:264 sets the long unknown wording in Body Strong so it fits on two lines.
            Text(person.name ?? PeoplePresentation.unknownName)
                .calypsoFont(person.name == nil ? .bodyStrong : .headline)
                .foregroundStyle(Color.ink)
            if person.name == nil {
                Text("Tap to add their name")
                    .calypsoFont(.callout)
                    .foregroundStyle(Color.inkSoft)
            } else if let relationship = PeoplePresentation.relationshipLabel(person.relationship) {
                Text(relationship)
                    .calypsoFont(.callout)
                    .foregroundStyle(Color.ink)
            }
        }
        .multilineTextAlignment(.leading)
        .frame(maxWidth: .infinity, alignment: .leading)
        .fixedSize(horizontal: false, vertical: true)
    }

    private var chevron: some View {
        CalypsoIcon("chevron.right", size: 32, relativeTo: .headline)
            .foregroundStyle(Color.ink)
    }
}

#Preview("People (no client)") {
    PeopleListView(client: nil)
}

#Preview("Rows") {
    VStack(spacing: 12) {
        PersonRow(person: Person(id: "a", name: "Sarah", relationship: "daughter"))
        PersonRow(person: Person(id: "b"))
    }
    .padding(24)
    .background(Color.paper)
}

#Preview("Rows AX5") {
    VStack(spacing: 12) {
        PersonRow(person: Person(id: "a", name: "Sarah", relationship: "daughter"))
        PersonRow(person: Person(id: "b"))
    }
    .padding(24)
    .background(Color.paper)
    .dynamicTypeSize(.accessibility5)
}
