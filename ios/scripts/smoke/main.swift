import Foundation

// Drives the app's real APIClient + Models (compiled for macOS by smoke_test.sh)
// against a running backend that smoke_test.sh has seeded.
// Args: <base_url> <token> <jpeg_path> <photo_id> <day> <expect_event: 1|0>
let args = CommandLine.arguments
let base = URL(string: args[1])!
let api = APIClient(baseURL: base, token: args[2])
let bad = APIClient(baseURL: base, token: "wrong-\(args[2])")
let jpeg = try! Data(contentsOf: URL(fileURLWithPath: args[3]))
let photoID = args[4]
let day = args[5]
let expectEvent = args[6] == "1"

struct SmokeError: Error, CustomStringConvertible {
    let description: String
    init(_ d: String) { description = d }
}

var failures = 0

@MainActor func check(_ name: String, _ body: () async throws -> String) async {
    do { print("PASS \(name): \(try await body())") }
    catch { failures += 1; print("FAIL \(name): \(error)") }
}

func status(_ url: URL) async throws -> (Int, Data) {
    let (d, r) = try await URLSession.shared.data(from: url)
    return ((r as! HTTPURLResponse).statusCode, d)
}

await check("bad token rejected") {
    do { _ = try await bad.people(); throw SmokeError("expected 401, got 200") }
    catch APIError.badStatus(let s) where s == 401 { return "401" }
}

var sarah: Person?
var unnamed: Person?
await check("GET /people") {
    let people = try await api.people()
    sarah = people.last { $0.name == "Smoke Sarah" }
    unnamed = people.last { $0.name == nil }
    guard sarah != nil else { throw SmokeError("seeded 'Smoke Sarah' missing") }
    guard unnamed != nil else { throw SmokeError("no unnamed person") }
    return "\(people.count) people, patient present: \(people.contains(where: \.isPatient))"
}

await check("face_photo_url loads") {
    guard let s = sarah?.facePhotoUrl, let url = URL(string: s) else { throw SmokeError("no face_photo_url") }
    let (code, _) = try await status(url)
    guard code == 200 else { throw APIError.badStatus(code) }
    return "\(s) → 200"
}

await check("GET /people/{id}") {
    guard let sarah else { throw SmokeError("no person") }
    let d = try await api.person(id: sarah.id)
    guard d.person.relationship == "daughter", d.person.phone != nil else { throw SmokeError("fields lost: \(d.person)") }
    return "relationship=\(d.person.relationship!), facts=\(d.person.facts), memories=\(d.memories)"
}

await check("PATCH /people/{id}") {
    guard let unnamed else { throw SmokeError("no unnamed person") }
    let p = try await api.updatePerson(id: unnamed.id, name: "Smoke Tom")
    guard p.name == "Smoke Tom" else { throw SmokeError("name not saved") }
    return "renamed → \(p.name!)"
}

await check("GET /days/\(day)/events") {
    let evs = try await api.events(day: day)
    if expectEvent && evs.isEmpty { throw SmokeError("seeded event missing") }
    return "\(evs.count) event(s)" + (evs.first.map { ": \($0.start) \($0.place) conf=\($0.placeConfidence) photos=\($0.photoIds)" } ?? "")
}

await check("GET /days/{empty}/events") {
    "\(try await api.events(day: "2001-01-01").count) events"
}

let takenAt = ISO8601DateFormatter().date(from: "\(day)T15:20:00Z")!
let meta = PhotoMeta(id: photoID, takenAt: takenAt, lat: 32.73, lon: -97.11)
await check("POST /app/photos") {
    try await api.uploadPhoto(PhotoUpload(meta: meta, imageData: jpeg)); return "ok"
}
await check("POST /app/photos (retry, idempotent)") {
    try await api.uploadPhoto(PhotoUpload(meta: meta, imageData: jpeg)); return "ok"
}
await check("photoURL serves upload") {
    let (code, d) = try await status(api.photoURL(id: photoID))
    guard code == 200 else { throw APIError.badStatus(code) }
    guard d == jpeg else { throw SmokeError("bytes differ") }
    return "\(api.photoURL(id: photoID)) → 200, \(d.count) bytes match"
}

let visitID = "\(photoID)-visit"
let arrived = takenAt.addingTimeInterval(-900)
await check("POST /app/visits (open visit)") {
    try await api.uploadVisits([Visit(id: visitID, arrived: arrived, departed: nil, lat: 32.73, lon: -97.11, placeName: nil)])
    return "ok"
}
await check("POST /app/visits (departure upsert)") {
    try await api.uploadVisits([Visit(id: visitID, arrived: arrived, departed: arrived.addingTimeInterval(3600),
                                      lat: 32.73, lon: -97.11, placeName: "Blue Bean Café")])
    return "ok"
}

print(failures == 0 ? "ALL PASS" : "\(failures) FAILURE(S)")
exit(failures == 0 ? 0 : 1)
