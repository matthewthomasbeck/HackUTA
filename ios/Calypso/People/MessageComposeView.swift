import MessageUI
import SwiftUI

/// The system Messages compose sheet, prefilled with recipients and a body. `onFinish` gets the result; the
/// presenter dismisses the sheet.
struct MessageComposeView: UIViewControllerRepresentable {
    let recipients: [String]
    let body: String
    let onFinish: (MessageComposeResult) -> Void

    init(recipients: [String], body: String, onFinish: @escaping (MessageComposeResult) -> Void) {
        self.recipients = recipients
        self.body = body
        self.onFinish = onFinish
    }

    init(recipient: String, body: String, onFinish: @escaping (MessageComposeResult) -> Void) {
        self.init(recipients: [recipient], body: body, onFinish: onFinish)
    }

    func makeUIViewController(context: Context) -> MFMessageComposeViewController {
        let controller = MFMessageComposeViewController()
        controller.recipients = recipients
        controller.body = body
        controller.messageComposeDelegate = context.coordinator
        return controller
    }

    func updateUIViewController(_ controller: MFMessageComposeViewController, context: Context) {}

    func makeCoordinator() -> Coordinator { Coordinator(onFinish: onFinish) }

    final class Coordinator: NSObject, MFMessageComposeViewControllerDelegate {
        let onFinish: (MessageComposeResult) -> Void

        init(onFinish: @escaping (MessageComposeResult) -> Void) { self.onFinish = onFinish }

        func messageComposeViewController(_ controller: MFMessageComposeViewController,
                                          didFinishWith result: MessageComposeResult) {
            onFinish(result)
        }
    }
}
