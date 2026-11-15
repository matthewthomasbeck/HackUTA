import SwiftUI

/// Calling sheet (Figma 59:500), shown once the "call <name> with me" iMessage is sent: Calypso⁻¹'s agent is now
/// ringing both phones.
struct CallingSheet: View {
    let name: String
    let onCancel: () -> Void

    var body: some View {
        PaperSheet {
            Text("Calling \(name)…")
                .calypsoFont(.title)
                .foregroundStyle(Color.ink)
                .frame(maxWidth: .infinity, alignment: .leading)
                .accessibilityAddTraits(.isHeader)
            HStack(spacing: 16) {
                Mascot(pose: .sailing, size: .m)
                Text("Your phone will ring in a moment. Calypso⁻¹ will be on the call too.")
                    .calypsoFont(.body)
                    .foregroundStyle(Color.inkSoft)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .fixedSize(horizontal: false, vertical: true)
            }
            // The app can't stop the agent's dial once the iMessage is sent; "Cancel call" only closes this sheet.
            CalypsoButton("Cancel call", kind: .quiet, action: onCancel)
        }
    }
}

#Preview {
    Color.paper
        .sheet(isPresented: .constant(true)) {
            CallingSheet(name: "Sarah", onCancel: {})
        }
}
