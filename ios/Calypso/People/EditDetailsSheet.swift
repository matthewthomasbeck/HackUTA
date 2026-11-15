import SwiftUI

/// "<name>’s details" sheet (Figma 59:550) for a named person: name and phone fields, Primary "Save" (disabled while
/// the name is blank) and Quiet "Cancel". `onSave` receives the trimmed name and the trimmed phone, or nil when the
/// phone is blank (which clears it).
struct EditDetailsSheet: View {
    let title: String
    let hint: String
    let onSave: (String, String?) -> Void
    let onCancel: () -> Void
    @State private var name: String
    @State private var phone: String

    init(name: String, phone: String?, onSave: @escaping (String, String?) -> Void, onCancel: @escaping () -> Void) {
        title = "\(name)’s details"
        hint = "Used to FaceTime \(name) with Calypso⁻¹"
        self.onSave = onSave
        self.onCancel = onCancel
        _name = State(initialValue: name)
        _phone = State(initialValue: phone ?? "")
    }

    private var trimmedName: String { name.trimmingCharacters(in: .whitespacesAndNewlines) }
    private var trimmedPhone: String? {
        let trimmed = phone.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? nil : trimmed
    }

    var body: some View {
        PaperSheet {
            Text(title)
                .calypsoFont(.title)
                .foregroundStyle(Color.ink)
                .frame(maxWidth: .infinity, alignment: .leading)
                .accessibilityAddTraits(.isHeader)
            VStack(alignment: .leading, spacing: 8) {
                fieldLabel("Name")
                DetailsField(label: "Name", prompt: "Type their name", text: $name)
                    .textContentType(.name)
                    .textInputAutocapitalization(.words)
                    .autocorrectionDisabled()
                    .submitLabel(.done)
            }
            VStack(alignment: .leading, spacing: 8) {
                fieldLabel("Phone number")
                DetailsField(label: "Phone number", prompt: "Add a number", text: $phone)
                    .keyboardType(.phonePad)
                    .textContentType(.telephoneNumber)
                // Figma has 18pt here; the app never goes below 20pt, so this is Caption 20.
                Text(hint)
                    .calypsoFont(.caption)
                    .foregroundStyle(Color.inkSoft)
            }
            CalypsoButton("Save") {
                guard !trimmedName.isEmpty else { return }
                onSave(trimmedName, trimmedPhone)
            }
            .disabled(trimmedName.isEmpty)
            CalypsoButton("Cancel", kind: .quiet, action: onCancel)
        }
    }

    private func fieldLabel(_ text: String) -> some View {
        Text(text)
            .calypsoFont(.caption)
            .foregroundStyle(Color.inkSoft)
            .accessibilityHidden(true) // the field carries the same label
    }
}

/// The 72pt paper-cut text field (Card fill, 2pt Ink border, radius 24, padding 20, Body Ink), as in `EditNameSheet`.
private struct DetailsField: View {
    let label: String
    let prompt: String
    @Binding var text: String
    @FocusState private var focused: Bool

    var body: some View {
        TextField(label, text: $text, prompt: Text(prompt).foregroundStyle(Color.inkSoft))
            .calypsoFont(.body)
            .foregroundStyle(Color.ink)
            .tint(Color.periwinkleDeep)
            .focused($focused)
            .padding(.horizontal, 20)
            .padding(.vertical, 8)
            .frame(minHeight: 72)
            .background(Color.card, in: RoundedRectangle(cornerRadius: 24))
            .overlay(RoundedRectangle(cornerRadius: 24).strokeBorder(Color.ink, lineWidth: 2))
            .contentShape(RoundedRectangle(cornerRadius: 24))
            .onTapGesture { focused = true }
    }
}

#Preview {
    Color.paper
        .sheet(isPresented: .constant(true)) {
            EditDetailsSheet(name: "Sarah", phone: "(512) 555-0142", onSave: { _, _ in }, onCancel: {})
        }
}
