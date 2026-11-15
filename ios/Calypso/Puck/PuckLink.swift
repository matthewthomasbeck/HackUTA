import Foundation

enum PuckConnectionState: Equatable {
    case idle, bluetoothOff, unauthorized, scanning
    case found(name: String)
    case connecting
    case connected(name: String)
    case failed(String)
}

/// The phone's side of the puck BLE link. `BLEPuckLink` talks CoreBluetooth; `FakePuckLink` is scripted for the
/// simulator and tests. Callbacks fire on the main actor.
@MainActor
protocol PuckLink: AnyObject {
    var state: PuckConnectionState { get }
    var onStateChange: ((PuckConnectionState) -> Void)? { get set }
    var onWho: ((WhoIsTalking) -> Void)? { get set }
    var onEvent: ((PuckEvent) -> Void)? { get set }

    func startScanning()
    /// Connects to the puck found by `startScanning`.
    func connect()
    /// True once a puck has been paired on this phone.
    var hasRemembered: Bool { get }
    /// Reconnects to a previously paired puck without a new scan. Does nothing while already connected,
    /// connecting or scanning, so it is safe to call on every foreground.
    func reconnectRemembered()
    func send(_ command: PuckCommand)
    func disconnect()
}

/// What the UI observes: one link's state, the current speaker (cleared when the puck goes quiet) and the last
/// enrollment event.
@MainActor
final class PuckConnection: ObservableObject {
    /// The phone treats the speaker as gone after this long with no `who` message.
    static let speakerExpiry: TimeInterval = 20

    @Published private(set) var state: PuckConnectionState
    @Published private(set) var speaker: WhoIsTalking?
    @Published private(set) var lastEvent: PuckEvent?

    var isConnected: Bool {
        if case .connected = state { return true }
        return false
    }

    private let link: PuckLink
    private let expiry: TimeInterval
    private var expiryTask: Task<Void, Never>?

    init(link: PuckLink, expiry: TimeInterval = PuckConnection.speakerExpiry) {
        self.link = link
        self.expiry = expiry
        self.state = link.state
        link.onStateChange = { [weak self] state in
            guard let self else { return }
            self.state = state
            if case .connected = state {} else { self.clearSpeaker() }
        }
        link.onWho = { [weak self] who in self?.receive(who) }
        link.onEvent = { [weak self] event in self?.lastEvent = event }
    }

    /// Fake on the simulator or with `-fakePuck`; the real CoreBluetooth link otherwise.
    static func make(arguments: [String] = ProcessInfo.processInfo.arguments) -> PuckConnection {
        #if targetEnvironment(simulator)
        let useFake = true
        #else
        let useFake = arguments.contains("-fakePuck")
        #endif
        return PuckConnection(link: useFake ? FakePuckLink(arguments: arguments) : BLEPuckLink())
    }

    var hasRemembered: Bool { link.hasRemembered }

    func startScanning() { link.startScanning() }
    func connect() { link.connect() }
    func reconnectRemembered() { link.reconnectRemembered() }
    func send(_ command: PuckCommand) { link.send(command) }
    func disconnect() { link.disconnect() }

    private func receive(_ who: WhoIsTalking) {
        speaker = who
        expiryTask?.cancel()
        let delay = expiry
        expiryTask = Task { [weak self] in
            try? await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))
            guard !Task.isCancelled else { return }
            self?.speaker = nil
        }
    }

    private func clearSpeaker() {
        expiryTask?.cancel()
        speaker = nil
    }
}
