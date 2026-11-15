import Foundation

/// How the app asks Calypso⁻¹ to start a FaceTime: it iMessages the agent "call <name> with me", and the agent
/// rings both phones and joins the call.
enum CallRequest {
    static func messageBody(for name: String) -> String {
        "call \(name.trimmingCharacters(in: .whitespacesAndNewlines)) with me"
    }

    /// A calm note when the message can't be composed, or nil when it can. Checked in this order: no Messages on
    /// this phone (e.g. the simulator), then no agent number configured.
    static func unavailableNote(canSendText: Bool, agentPhone: String) -> String? {
        if !canSendText { return "Messages isn’t available on this phone." }
        if agentPhone.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            return "Calypso⁻¹’s number isn’t set up yet."
        }
        return nil
    }
}
