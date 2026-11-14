import Contacts
import ContactsUI
import SwiftUI

struct AddContactView: View {
    var onNext: () -> Void
    @State private var showEditor = false

    var body: some View {
        VStack(spacing: 24) {
            Spacer()
            Image("Logo").resizable().scaledToFit().frame(width: 120).clipShape(Circle())
            Text("Add Calypso⁻¹ to Contacts").font(.title.bold())
            Text("So you can start a FaceTime call with Calypso⁻¹ like with anyone else.")
                .multilineTextAlignment(.center).foregroundStyle(.secondary)
            Spacer()
            Button("Add Calypso⁻¹ to Contacts") { showEditor = true }
                .buttonStyle(.borderedProminent).controlSize(.large)
            Button("Continue", action: onNext)
        }
        .padding()
        .sheet(isPresented: $showEditor) {
            NewContactSheet(contact: ContactBuilder.calypso(phone: Config.chertPhone)) {
                showEditor = false
                onNext()
            }
            .ignoresSafeArea()
        }
    }
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
