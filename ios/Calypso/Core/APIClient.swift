import Foundation

struct PhotoUpload {
    var meta: PhotoMeta
    var imageData: Data
}

enum APIError: Error {
    case badStatus(Int)
}

struct APIClient {
    let baseURL: URL
    let token: String
    var session: URLSession = .shared

    init(baseURL: URL, token: String, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.token = token
        self.session = session
    }

    func people() async throws -> [Person] {
        try await get("people")
    }

    func events(day: String) async throws -> [DayEvent] {
        try await get("days/\(day)/events")
    }

    func uploadPhoto(_ upload: PhotoUpload) async throws {
        let boundary = "calypso-\(UUID().uuidString)"
        var body = Data()
        func append(_ s: String) { body.append(Data(s.utf8)) }
        append("--\(boundary)\r\nContent-Disposition: form-data; name=\"meta\"\r\n")
        append("Content-Type: application/json\r\n\r\n")
        body.append(try JSONEncoder.calypso.encode(upload.meta))
        append("\r\n--\(boundary)\r\n")
        append("Content-Disposition: form-data; name=\"image\"; filename=\"\(upload.meta.id).jpg\"\r\n")
        append("Content-Type: image/jpeg\r\n\r\n")
        body.append(upload.imageData)
        append("\r\n--\(boundary)--\r\n")

        var request = makeRequest("app/photos", method: "POST")
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        _ = try await send(request, body: body)
    }

    func uploadVisits(_ visits: [Visit]) async throws {
        var request = makeRequest("app/visits", method: "POST")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        _ = try await send(request, body: JSONEncoder.calypso.encode(visits))
    }

    // MARK: - Plumbing

    private func makeRequest(_ path: String, method: String) -> URLRequest {
        var request = URLRequest(url: baseURL.appendingPathComponent(path))
        request.httpMethod = method
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        return request
    }

    private func get<T: Decodable>(_ path: String) async throws -> T {
        let data = try await send(makeRequest(path, method: "GET"), body: nil)
        return try JSONDecoder.calypso.decode(T.self, from: data)
    }

    private func send(_ request: URLRequest, body: Data?) async throws -> Data {
        let (data, response) = if let body {
            try await session.upload(for: request, from: body)
        } else {
            try await session.data(for: request)
        }
        if let status = (response as? HTTPURLResponse)?.statusCode, !(200..<300).contains(status) {
            throw APIError.badStatus(status)
        }
        return data
    }
}
