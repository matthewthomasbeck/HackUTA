import SwiftUI

struct PeopleListView: View {
    let client: APIClient?
    @State private var people: [Person] = []
    @State private var error: String?

    var body: some View {
        NavigationStack {
            List(people) { person in
                NavigationLink {
                    PersonDetailView(client: client, person: person)
                } label: {
                    HStack(spacing: 12) {
                        FaceView(urlString: person.facePhotoUrl, size: 44)
                        VStack(alignment: .leading) {
                            Text(person.name ?? "Unnamed visitor").font(.headline)
                            if let relationship = person.relationship {
                                Text(relationship).font(.subheadline).foregroundStyle(.secondary)
                            }
                        }
                    }
                }
            }
            .overlay {
                if people.isEmpty { ContentUnavailableView(error ?? "No people yet", systemImage: "person.2") }
            }
            .navigationTitle("People")
            .refreshable { await load() }
            .task { await load() }
        }
    }

    private func load() async {
        guard let client else { error = "App isn't configured"; return }
        do {
            people = try await client.people()
            error = nil
        } catch {
            self.error = "Couldn't load people"
        }
    }
}

struct FaceView: View {
    let urlString: String?
    let size: CGFloat

    var body: some View {
        AsyncImage(url: urlString.flatMap(URL.init(string:))) { image in
            image.resizable().scaledToFill()
        } placeholder: {
            Image(systemName: "person.crop.circle.fill").resizable().foregroundStyle(.secondary)
        }
        .frame(width: size, height: size)
        .clipShape(Circle())
    }
}
