import Contacts
import ContactsUI
import SwiftUI

extension View {
    /// Presents the system contact picker with multiple selection while `isPresented` is true. It needs no
    /// Contacts permission. `onSelect` runs once the picker has finished dismissing, so the caller can present
    /// another sheet right away.
    func contactPicker(isPresented: Binding<Bool>, onSelect: @escaping ([CNContact]) -> Void) -> some View {
        background(ContactPickerHost(isPresented: isPresented, onSelect: onSelect).frame(width: 0, height: 0))
    }
}

/// An invisible view controller that presents `CNContactPickerViewController` modally. Wrapping the picker
/// itself in a SwiftUI `.sheet` misbehaves: it dismisses itself and leaves an empty sheet behind.
private struct ContactPickerHost: UIViewControllerRepresentable {
    @Binding var isPresented: Bool
    let onSelect: ([CNContact]) -> Void

    func makeUIViewController(context: Context) -> UIViewController { UIViewController() }

    func updateUIViewController(_ host: UIViewController, context: Context) {
        context.coordinator.parent = self
        guard isPresented, host.presentedViewController == nil else { return }
        let picker = CNContactPickerViewController()
        picker.delegate = context.coordinator
        picker.displayedPropertyKeys = [CNContactPhoneNumbersKey]
        DispatchQueue.main.async { host.present(picker, animated: true) }
    }

    func makeCoordinator() -> Coordinator { Coordinator(parent: self) }

    final class Coordinator: NSObject, CNContactPickerDelegate {
        var parent: ContactPickerHost

        init(parent: ContactPickerHost) { self.parent = parent }

        func contactPicker(_ picker: CNContactPickerViewController, didSelect contacts: [CNContact]) {
            let parent = parent
            afterDismissal(of: picker) {
                parent.isPresented = false
                parent.onSelect(contacts)
            }
        }

        func contactPickerDidCancel(_ picker: CNContactPickerViewController) {
            let parent = parent
            afterDismissal(of: picker) { parent.isPresented = false }
        }

        /// The picker dismisses itself before calling its delegate; wait for that animation to end.
        private func afterDismissal(of picker: UIViewController, _ work: @escaping () -> Void) {
            if let transition = picker.transitionCoordinator {
                transition.animate(alongsideTransition: nil) { _ in work() }
            } else {
                DispatchQueue.main.async(execute: work)
            }
        }
    }
}

extension FamilyInvite.PickedContact {
    init(_ contact: CNContact) {
        let given = contact.isKeyAvailable(CNContactGivenNameKey) ? contact.givenName : ""
        let family = contact.isKeyAvailable(CNContactFamilyNameKey) ? contact.familyName : ""
        let phones = contact.isKeyAvailable(CNContactPhoneNumbersKey)
            ? contact.phoneNumbers.map(\.value.stringValue) : []
        self.init(givenName: given,
                  fullName: [given, family].filter { !$0.isEmpty }.joined(separator: " "),
                  phones: phones)
    }
}
