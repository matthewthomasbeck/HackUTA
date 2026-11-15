import Foundation

/// One rule for "does this person have a name?": a missing, empty or whitespace-only name counts as unnamed, so
/// every screen shows the same "not sure" wording instead of a blank headline. Kept out of `Models.swift` (contract).
enum PersonName {
    static func display(_ name: String?) -> String? {
        guard let trimmed = name?.trimmingCharacters(in: .whitespacesAndNewlines), !trimmed.isEmpty else { return nil }
        return trimmed
    }
}

extension Person {
    /// The name to show, or nil when the person is unnamed (see `PersonName.display`).
    var displayName: String? { PersonName.display(name) }
}
