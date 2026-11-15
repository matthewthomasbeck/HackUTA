import Foundation

/// The "Invite your family" text: who gets it and what it says. Pure, so it's unit-tested; the view maps
/// `CNContact`s into `PickedContact`s.
enum FamilyInvite {
    /// A contact from the system picker, reduced to what the invite needs.
    struct PickedContact: Equatable {
        var givenName: String
        var fullName: String
        var phones: [String]

        /// Given name, else the full name, else the phone number.
        var displayName: String {
            for candidate in [givenName, fullName] {
                let trimmed = candidate.trimmingCharacters(in: .whitespacesAndNewlines)
                if !trimmed.isEmpty { return trimmed }
            }
            return firstPhone ?? ""
        }

        /// The first non-blank phone number, as stored.
        var firstPhone: String? {
            phones.lazy
                .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
                .first { !$0.isEmpty }
        }
    }

    /// Someone who gets the text: the name shown on the chip and the number it goes to.
    struct Invitee: Equatable, Hashable {
        var name: String
        var phone: String
    }

    static func messageBody(calypsoPhone: String) -> String {
        let phone = calypsoPhone.trimmingCharacters(in: .whitespacesAndNewlines)
        let at = phone.isEmpty ? "" : " at \(phone)"
        return "Hi! I’m using Calypso⁻¹ to help me remember. Please FaceTime Calypso⁻¹\(at) to set up your profile."
    }

    /// One invitee per picked contact that has a phone (its first one), skipping repeated numbers.
    static func invitees(from contacts: [PickedContact]) -> [Invitee] {
        merge([], with: contacts.compactMap { contact in
            contact.firstPhone.map { Invitee(name: contact.displayName, phone: $0) }
        })
    }

    static func recipients(_ invitees: [Invitee]) -> [String] {
        invitees.map(\.phone)
    }

    /// `existing` followed by the new invitees whose numbers aren't already there.
    static func merge(_ existing: [Invitee], with new: [Invitee]) -> [Invitee] {
        var seen = Set(existing.map(\.phone))
        return existing + new.filter { seen.insert($0.phone).inserted }
    }

    static let noPhoneNote = "None of those contacts has a phone number."
    static let noMessagesNote = "Messages isn’t available on this phone."
}
