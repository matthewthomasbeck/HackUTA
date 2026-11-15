import Contacts
import MessageUI
import SwiftUI

/// Figma "Invite your family" (62:232) and "Invite your family · sent" (62:283). "Choose family" opens the
/// system contact picker, then the Messages compose sheet with every picked number; once the text is sent the
/// step shows who it went to.
struct InviteFamilyView: View {
    var onBack: () -> Void
    var onNext: () -> Void
    /// Everyone texted so far. Non-empty shows the "sent" state.
    @State private var invited: [FamilyInvite.Invitee]
    @State private var picking = false
    /// The invitees in the open compose sheet.
    @State private var composing: Compose?
    @State private var note: String?

    private struct Compose: Identifiable {
        let id = UUID()
        let invitees: [FamilyInvite.Invitee]
    }

    init(onBack: @escaping () -> Void, onNext: @escaping () -> Void, invited: [FamilyInvite.Invitee] = []) {
        self.onBack = onBack
        self.onNext = onNext
        _invited = State(initialValue: invited)
    }

    var body: some View {
        OnboardingScaffold(step: .inviteFamily, onBack: onBack) {
            Group {
                if invited.isEmpty { inviteContent } else { sentContent }
            }
            .padding(.horizontal, 24)
            .frame(maxHeight: .infinity)
        }
        .contactPicker(isPresented: $picking, onSelect: picked)
        .sheet(item: $composing) { compose in
            MessageComposeView(recipients: FamilyInvite.recipients(compose.invitees),
                               body: FamilyInvite.messageBody(calypsoPhone: Config.chertPhone)) { result in
                // .cancelled / .failed: stay where we are.
                if result == .sent { invited = FamilyInvite.merge(invited, with: compose.invitees) }
                composing = nil
            }
            .ignoresSafeArea()
        }
    }

    // MARK: Invite

    private var inviteContent: some View {
        VStack(alignment: .leading, spacing: 12) {
            Mascot(pose: .presenting, size: .m, shadow: true)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 8)
            OnboardingHeading(title: "Invite your family",
                              message: "Send them a text so they can FaceTime Calypso⁻¹ and set up their profile.")
            messagePreview
            Spacer(minLength: 24)
            calmNote
            Button(action: choose) {
                HStack(spacing: 12) {
                    CalypsoIcon(.people)
                    Text("Choose family")
                }
            }
            .buttonStyle(CalypsoButtonStyle(.primary))
            CalypsoButton("Skip for now", kind: .quiet, action: onNext)
        }
    }

    /// What the family will receive (Figma `Message Preview`).
    private var messagePreview: some View {
        PaperCard {
            VStack(alignment: .leading, spacing: 4) {
                Text("They’ll get a text")
                    .font(.custom("Nunito-Bold", size: 22, relativeTo: .callout))
                    .foregroundStyle(Color.ink)
                Text("“Hi! I’m using Calypso⁻¹ to help me remember. Please FaceTime Calypso⁻¹ to set up your profile.”")
                    .font(.custom("Nunito-Regular", size: 20, relativeTo: .footnote))
                    .foregroundStyle(Color.inkSoft)
            }
            .fixedSize(horizontal: false, vertical: true)
        }
        .accessibilityElement(children: .combine)
    }

    // MARK: Sent

    private var sentContent: some View {
        VStack(alignment: .leading, spacing: 12) {
            Mascot(pose: .celebrating, size: .s, shadow: true)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 8)
            OnboardingHeading(title: "Invites sent",
                              message: "When they FaceTime Calypso⁻¹, they’ll show up in People.")
            PaperCard {
                VStack(alignment: .leading, spacing: 12) {
                    Text("Texts sent to")
                        .calypsoFont(.headline)
                        .foregroundStyle(Color.ink)
                        .accessibilityAddTraits(.isHeader)
                    ForEach(invited, id: \.phone) { PersonChip(name: $0.name) }
                }
            }
            Spacer(minLength: 24)
            calmNote
            CalypsoButton("Continue", action: onNext)
            CalypsoButton("Invite more family", kind: .quiet, action: choose)
        }
    }

    // MARK: Flow

    @ViewBuilder private var calmNote: some View {
        if let note {
            Text(note)
                .calypsoFont(.caption)
                .foregroundStyle(Color.inkSoft)
                .multilineTextAlignment(.center)
                .frame(maxWidth: .infinity)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    private func choose() {
        note = nil
        picking = true
    }

    private func picked(_ contacts: [CNContact]) {
        guard !contacts.isEmpty else { return }
        let invitees = FamilyInvite.invitees(from: contacts.map(FamilyInvite.PickedContact.init))
        guard !invitees.isEmpty else { note = FamilyInvite.noPhoneNote; return }
        guard MFMessageComposeViewController.canSendText() else { note = FamilyInvite.noMessagesNote; return }
        composing = Compose(invitees: invitees)
    }
}

#Preview {
    InviteFamilyView(onBack: {}, onNext: {})
}

#Preview("Sent") {
    InviteFamilyView(onBack: {}, onNext: {}, invited: [.init(name: "Sarah", phone: "1"), .init(name: "Tom", phone: "2")])
}
