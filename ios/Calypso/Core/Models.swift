import Foundation

// Mirrors backend/calypso/models.py (pydantic). Keep field-for-field in sync.

struct Person: Codable, Equatable, Identifiable {
    var id: String
    var name: String?
    var relationship: String?
    var isPatient: Bool
    var facePhotoUrl: String?
    var facts: [String]
    var phone: String?

    init(id: String, name: String? = nil, relationship: String? = nil, isPatient: Bool = false,
         facePhotoUrl: String? = nil, facts: [String] = [], phone: String? = nil) {
        self.id = id; self.name = name; self.relationship = relationship
        self.isPatient = isPatient; self.facePhotoUrl = facePhotoUrl; self.facts = facts
        self.phone = phone
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(String.self, forKey: .id)
        name = try c.decodeIfPresent(String.self, forKey: .name)
        relationship = try c.decodeIfPresent(String.self, forKey: .relationship)
        isPatient = try c.decodeIfPresent(Bool.self, forKey: .isPatient) ?? false
        facePhotoUrl = try c.decodeIfPresent(String.self, forKey: .facePhotoUrl)
        facts = try c.decodeIfPresent([String].self, forKey: .facts) ?? []
        phone = try c.decodeIfPresent(String.self, forKey: .phone)
    }
}

struct Visit: Codable, Equatable, Identifiable {
    var id: String
    var arrived: Date
    var departed: Date?
    var lat: Double
    var lon: Double
    var placeName: String?
}

struct Photo: Codable, Equatable, Identifiable {
    var id: String
    var takenAt: Date
    var lat: Double?
    var lon: Double?
    var path: String
    var sensitive: Bool = false
    var caption: String?
    var eventId: String?
}

/// The `meta` JSON field sent with `POST /app/photos`.
struct PhotoMeta: Codable, Equatable {
    var id: String
    var takenAt: Date
    var lat: Double?
    var lon: Double?
}

struct DayEvent: Codable, Equatable, Identifiable {
    var id: String
    var start: Date
    var end: Date
    var place: String
    var placeConfidence: Double
    var people: [String] = []
    var summary: String
    var evidence: [String] = []
    var photoIds: [String] = []

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(String.self, forKey: .id)
        start = try c.decode(Date.self, forKey: .start)
        end = try c.decode(Date.self, forKey: .end)
        place = try c.decode(String.self, forKey: .place)
        placeConfidence = try c.decode(Double.self, forKey: .placeConfidence)
        people = try c.decodeIfPresent([String].self, forKey: .people) ?? []
        summary = try c.decode(String.self, forKey: .summary)
        evidence = try c.decodeIfPresent([String].self, forKey: .evidence) ?? []
        photoIds = try c.decodeIfPresent([String].self, forKey: .photoIds) ?? []
    }
}

struct Card: Codable, Equatable {
    enum Kind: String, Codable { case identity, learning, today, memory }
    var kind: Kind
    var title: String
    var lines: [String]
    var imageUrls: [String] = []

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        kind = try c.decode(Kind.self, forKey: .kind)
        title = try c.decode(String.self, forKey: .title)
        lines = try c.decode([String].self, forKey: .lines)
        imageUrls = try c.decodeIfPresent([String].self, forKey: .imageUrls) ?? []
    }
}

// MARK: - JSON coding

private enum DateParsing {
    private static func formatter(fractional: Bool) -> ISO8601DateFormatter {
        let f = ISO8601DateFormatter()
        f.formatOptions = fractional
            ? [.withInternetDateTime, .withFractionalSeconds]
            : [.withInternetDateTime]
        return f
    }

    private static let hasZone = try! NSRegularExpression(pattern: #"(Z|[+-]\d{2}:?\d{2})$"#)

    /// Pydantic emits ISO-8601 with or without fractional seconds and with or without a zone.
    /// A missing zone means UTC.
    static func parse(_ text: String) -> Date? {
        let range = NSRange(text.startIndex..., in: text)
        let zoned = hasZone.firstMatch(in: text, range: range) == nil ? text + "Z" : text
        return formatter(fractional: true).date(from: zoned) ?? formatter(fractional: false).date(from: zoned)
    }

    static func format(_ date: Date) -> String {
        formatter(fractional: true).string(from: date)
    }
}

extension JSONDecoder {
    static let calypso: JSONDecoder = {
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        d.dateDecodingStrategy = .custom { decoder in
            let text = try decoder.singleValueContainer().decode(String.self)
            guard let date = DateParsing.parse(text) else {
                throw DecodingError.dataCorrupted(.init(codingPath: decoder.codingPath,
                                                        debugDescription: "Bad ISO-8601 date: \(text)"))
            }
            return date
        }
        return d
    }()
}

extension JSONEncoder {
    static let calypso: JSONEncoder = {
        let e = JSONEncoder()
        e.keyEncodingStrategy = .convertToSnakeCase
        e.dateEncodingStrategy = .custom { date, encoder in
            var c = encoder.singleValueContainer()
            try c.encode(DateParsing.format(date))
        }
        return e
    }()
}
