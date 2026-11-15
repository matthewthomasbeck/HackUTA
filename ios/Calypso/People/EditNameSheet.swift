import SwiftUI

/// Edit name sheet (Figma 20:969): Title, a 72pt name field (auto-focused), Primary "Save" (disabled while the name
/// is blank) and Quiet "Cancel". `onSave` receives the trimmed name.
struct EditNameSheet: View {
    let onSave: (String) -> Void
    let onCancel: () -> Void
    @State private var name: String
    @FocusState private var fieldFocused: Bool

    init(initialName: String, onSave: @escaping (String) -> Void, onCancel: @escaping () -> Void) {
        self.onSave = onSave
        self.onCancel = onCancel
        _name = State(initialValue: initialName)
    }

    private var trimmedName: String { name.trimmingCharacters(in: .whitespacesAndNewlines) }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                Text("What’s their name?")
                    .calypsoFont(.title)
                    .foregroundStyle(Color.ink)
                    .accessibilityAddTraits(.isHeader)
                TextField("Name", text: $name,
                          prompt: Text("Type their name").foregroundStyle(Color.inkSoft))
                    .calypsoFont(.body)
                    .foregroundStyle(Color.ink)
                    .tint(Color.periwinkleDeep)
                    .textContentType(.name)
                    .textInputAutocapitalization(.words)
                    .autocorrectionDisabled()
                    .submitLabel(.done)
                    .onSubmit(save)
                    .focused($fieldFocused)
                    .padding(.horizontal, 20)
                    .padding(.vertical, 8)
                    .frame(minHeight: 72)
                    .background(Color.card, in: RoundedRectangle(cornerRadius: 24))
                    .overlay(RoundedRectangle(cornerRadius: 24).strokeBorder(Color.ink, lineWidth: 2)) // Figma 20:969
                    .contentShape(RoundedRectangle(cornerRadius: 24))
                    .onTapGesture { fieldFocused = true }
                CalypsoButton("Save", action: save)
                    .disabled(trimmedName.isEmpty)
                CalypsoButton("Cancel", kind: .quiet, action: onCancel)
            }
            .padding(.horizontal, 24)
            .padding(.top, 32)
            .padding(.bottom, 40)
        }
        .scrollBounceBehavior(.basedOnSize)
        .background(Color.paper.ignoresSafeArea())
        .presentationDetents([.medium, .large])
        .presentationDragIndicator(.visible)
        .presentationBackground(Color.paper)
        .presentationCornerRadius(32)
        .task {
            // Focusing during the sheet's entrance is unreliable; wait for it to settle.
            try? await Task.sleep(for: .milliseconds(400))
            fieldFocused = true
        }
    }

    private func save() {
        guard !trimmedName.isEmpty else { return }
        onSave(trimmedName)
    }
}

#Preview {
    Color.paper
        .sheet(isPresented: .constant(true)) {
            EditNameSheet(initialName: "", onSave: { _ in }, onCancel: {})
        }
}
