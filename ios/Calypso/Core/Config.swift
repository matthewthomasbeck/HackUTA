import Foundation

/// Reads values injected into Info.plist from the git-ignored Secrets.xcconfig.
enum Config {
    static var apiBaseURL: URL? { URL(string: string("API_BASE_URL")) }
    static var apiToken: String { string("API_TOKEN") }
    static var chertPhone: String { string("CHERT_PHONE") }

    private static func string(_ key: String) -> String {
        Bundle.main.object(forInfoDictionaryKey: key) as? String ?? ""
    }
}
