import CoreBluetooth
import Foundation

/// The puck's BLE service and characteristic UUIDs. The contract lives in `docs/puck-phone-ble.md`.
enum PuckUUID {
    static let service = CBUUID(string: "C41A0001-5E7A-4C1B-9A3D-CA1F5050C0DE")
    /// Notify: who is speaking now (`WhoIsTalking` JSON).
    static let who = CBUUID(string: "C41A0002-5E7A-4C1B-9A3D-CA1F5050C0DE")
    /// Write: enrollment commands (`PuckCommand` JSON).
    static let control = CBUUID(string: "C41A0003-5E7A-4C1B-9A3D-CA1F5050C0DE")
    /// Notify: enrollment progress (`PuckEvent` JSON).
    static let events = CBUUID(string: "C41A0004-5E7A-4C1B-9A3D-CA1F5050C0DE")
}

/// One `who` notification. Mirrors the puck's `WhoIsTalking` (`puck/include/types.hpp`); empty strings from the
/// puck decode to nil, and an unrecognised status decodes as `.unknown` so we never guess a person.
struct WhoIsTalking: Decodable, Equatable {
    enum Status: String, Decodable { case identified, uncertain, unknown }

    var status: Status
    var personId: String?
    var displayName: String?
    var relationship: String?
    var score: Double?

    init(status: Status, personId: String? = nil, displayName: String? = nil,
         relationship: String? = nil, score: Double? = nil) {
        self.status = status
        self.personId = personId
        self.displayName = displayName
        self.relationship = relationship
        self.score = score
    }

    private enum CodingKeys: String, CodingKey {
        case status, score, relationship
        case personId = "person_id"
        case displayName = "display_name"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        let raw = try c.decodeIfPresent(String.self, forKey: .status)
        status = raw.flatMap(Status.init(rawValue:)) ?? .unknown
        personId = Self.nonEmpty(try c.decodeIfPresent(String.self, forKey: .personId))
        displayName = PersonName.display(try c.decodeIfPresent(String.self, forKey: .displayName))
        relationship = Self.nonEmpty(try c.decodeIfPresent(String.self, forKey: .relationship))
        score = try c.decodeIfPresent(Double.self, forKey: .score)
    }

    private static func nonEmpty(_ s: String?) -> String? { PersonName.display(s) }
}

/// A write to the puck's `control` characteristic. Enrollment is always for the patient.
enum PuckCommand: Encodable, Equatable {
    case enrollStart(index: Int, text: String)
    case enrollFinish(count: Int)
    case enrollCancel

    private enum CodingKeys: String, CodingKey { case cmd, speaker, index, text, count }

    func encode(to encoder: Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encode("patient", forKey: .speaker)
        switch self {
        case .enrollStart(let index, let text):
            try c.encode("enroll_start", forKey: .cmd)
            try c.encode(index, forKey: .index)
            try c.encode(text, forKey: .text)
        case .enrollFinish(let count):
            try c.encode("enroll_finish", forKey: .cmd)
            try c.encode(count, forKey: .count)
        case .enrollCancel:
            try c.encode("enroll_cancel", forKey: .cmd)
        }
    }
}

/// A notification on the puck's `events` characteristic.
enum PuckEvent: Decodable, Equatable {
    case recording(index: Int)
    case saved(index: Int)
    case failed(index: Int, reason: String?)
    case done

    private enum CodingKeys: String, CodingKey { case event, index, reason }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        let name = try c.decode(String.self, forKey: .event)
        switch name {
        case "enroll_recording": self = .recording(index: try c.decode(Int.self, forKey: .index))
        case "enroll_saved": self = .saved(index: try c.decode(Int.self, forKey: .index))
        case "enroll_failed":
            self = .failed(index: try c.decode(Int.self, forKey: .index),
                           reason: try c.decodeIfPresent(String.self, forKey: .reason))
        case "enroll_done": self = .done
        default:
            throw DecodingError.dataCorruptedError(forKey: .event, in: c,
                                                   debugDescription: "Unknown puck event \(name)")
        }
    }
}
