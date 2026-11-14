import SwiftUI

struct PersonDetailView: View {
    let client: APIClient?
    @State var person: Person
    var onUpdate: (Person) -> Void = { _ in }
    @State private var memories: [String] = []
    @State private var editing = false
    @State private var draftName = ""
    @State private var error: String?

    var body: some View {
        List {
            Section {
                VStack(spacing: 8) {
                    FaceView(urlString: person.facePhotoUrl, size: 120)
                    Text(person.name ?? "Unnamed visitor").font(.title2.bold())
                    if let relationship = person.relationship {
                        Text(relationship).foregroundStyle(.secondary)
                    }
                }
                .frame(maxWidth: .infinity)
            }
            if let error { Section { Text(error).foregroundStyle(.red) } }
            Section("Recent memories") {
                if memories.isEmpty {
                    Text("Nothing yet").foregroundStyle(.secondary)
                }
                ForEach(memories, id: \.self, content: Text.init)
            }
        }
        .navigationTitle(person.name ?? "Unnamed visitor")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            Button("Edit name") {
                draftName = person.name ?? ""
                editing = true
            }
        }
        .alert("Name", isPresented: $editing) {
            TextField("Name", text: $draftName)
            Button("Save") { Task { await save() } }
            Button("Cancel", role: .cancel) {}
        }
        .task { await load() }
    }

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
            self.error = "Couldn't save the name"
        }
    }
}
