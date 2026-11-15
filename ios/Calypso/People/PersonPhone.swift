import Foundation

extension Person {
    /// The number Calypso⁻¹ can FaceTime, or nil when the phone is missing, empty or whitespace-only.
    /// Kept out of `Models.swift` (contract), next to `displayName`.
    var callablePhone: String? {
        guard let trimmed = phone?.trimmingCharacters(in: .whitespacesAndNewlines), !trimmed.isEmpty else {
            return nil
        }
        return trimmed
    }
}
