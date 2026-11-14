import SwiftUI

struct AccountView: View {
    @AppStorage("onboarded") private var onboarded = true
    @State private var confirmingReset = false

    var body: some View {
        NavigationStack {
            List {
                Section("Connection") {
                    LabeledContent("Backend", value: Config.apiBaseURL?.absoluteString ?? "Not set")
                    LabeledContent("Calypso⁻¹ phone", value: Config.chertPhone.isEmpty ? "Not set" : Config.chertPhone)
                }
                Section {
                    Button("Run setup again") { onboarded = false }
                    Button("Reset account", role: .destructive) { confirmingReset = true }
                } footer: {
                    Text("Reset clears this phone's sync history and pending visits, then starts setup again. Nothing on the server is deleted.")
                }
            }
            .navigationTitle("Account")
            .confirmationDialog("Reset this phone's Calypso⁻¹ data?", isPresented: $confirmingReset, titleVisibility: .visible) {
                Button("Reset account", role: .destructive, action: reset)
            }
        }
    }

    private func reset() {
        if let domain = Bundle.main.bundleIdentifier {
            UserDefaults.standard.removePersistentDomain(forName: domain)
        }
        onboarded = false
    }
}
