import Contacts
import ContactsUI
import SwiftUI

/// Figma "Add to Contacts" (20:938).
struct AddContactView: View {
    var onBack: () -> Void
    var onNext: () -> Void
    @State private var showEditor = false

    var body: some View {
        OnboardingScaffold(step: .addContact, onBack: onBack) {
            VStack(alignment: .leading, spacing: 12) {
                Mascot(pose: .wave, size: .m, shadow: true)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 8)
                OnboardingHeading(title: "Add Calypso⁻¹ to your contacts",
                                  message: "Then you can FaceTime Calypso⁻¹ just like family.")
                contactPreview
                Spacer(minLength: 24)
                if Config.chertPhone.isEmpty {
                    Text("Set CHERT_PHONE in Secrets.xcconfig to add the contact.")
                        .calypsoFont(.caption)
                        .foregroundStyle(Color.inkSoft)
                        .frame(maxWidth: .infinity)
                        .multilineTextAlignment(.center)
                }
                CalypsoButton("Add to Contacts") { showEditor = true }
                    .disabled(Config.chertPhone.isEmpty)
                    .opacity(Config.chertPhone.isEmpty ? 0.5 : 1)
                CalypsoButton("Skip for now", kind: .quiet, action: onNext)
            }
            .padding(.horizontal, 24)
            .frame(maxHeight: .infinity)
        }
        .sheet(isPresented: $showEditor) {
            NewContactSheet(contact: ContactBuilder.calypso(phone: Config.chertPhone)) {
                showEditor = false
                onNext()
            }
            .ignoresSafeArea()
        }
    }

    /// What the new contact will look like. It uses the logo, the contact's real photo, so this screen
    /// keeps a single gull.
    private var contactPreview: some View {
        PaperCard {
            ViewThatFits(in: .horizontal) {
                HStack(spacing: 16) { Logo(size: 80); contactText }
                VStack(alignment: .leading, spacing: 12) { Logo(size: 80); contactText }
            }
        }
        .accessibilityElement(children: .combine)
    }

    private var contactText: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("Calypso⁻¹").calypsoFont(.headline).foregroundStyle(Color.ink)
            Text("FaceTime · Message").calypsoFont(.caption).foregroundStyle(Color.inkSoft)
        }
        .fixedSize(horizontal: false, vertical: true)
    }
}

#Preview {
    AddContactView(onBack: {}, onNext: {})
}

private struct NewContactSheet: UIViewControllerRepresentable {
    let contact: CNMutableContact
    let onDone: () -> Void

    func makeUIViewController(context: Context) -> UINavigationController {
        let controller = CNContactViewController(forNewContact: contact)
        controller.delegate = context.coordinator
        return UINavigationController(rootViewController: controller)
    }

    func updateUIViewController(_ uiViewController: UINavigationController, context: Context) {}

    func makeCoordinator() -> Coordinator { Coordinator(onDone: onDone) }

    final class Coordinator: NSObject, CNContactViewControllerDelegate {
        let onDone: () -> Void
        init(onDone: @escaping () -> Void) { self.onDone = onDone }

        func contactViewController(_ viewController: CNContactViewController, didCompleteWith contact: CNContact?) {
            onDone()
        }
    }
}
