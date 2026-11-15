import Foundation

/// A speaker script for `FakePuckLink`, pinned with `-fakeSpeaker sarah|unknown|none` for screenshots.
enum FakeSpeaker: String {
    case sarah, unknown, none

    static func from(arguments: [String]) -> FakeSpeaker? {
        guard let i = arguments.firstIndex(of: "-fakeSpeaker"), i + 1 < arguments.count else { return nil }
        return FakeSpeaker(rawValue: arguments[i + 1])
    }
}

/// Scripted puck for the simulator and tests. Delays are multiplied by `timeScale` so tests run fast.
@MainActor
final class FakePuckLink: PuckLink {
    static let puckName = "Calypso Puck"
    static let pairedKey = "puckPaired"

    private(set) var state: PuckConnectionState = .idle {
        didSet { if state != oldValue { onStateChange?(state) } }
    }
    var onStateChange: ((PuckConnectionState) -> Void)?
    var onWho: ((WhoIsTalking) -> Void)?
    var onEvent: ((PuckEvent) -> Void)?

    private let timeScale: Double
    private let pinnedSpeaker: FakeSpeaker?
    private let defaults: UserDefaults
    private var tasks: [Task<Void, Never>] = []
    private var speakerTask: Task<Void, Never>?

    init(timeScale: Double = 1,
         pinnedSpeaker: FakeSpeaker? = nil,
         arguments: [String] = ProcessInfo.processInfo.arguments,
         defaults: UserDefaults = .standard) {
        self.timeScale = timeScale
        self.pinnedSpeaker = pinnedSpeaker ?? FakeSpeaker.from(arguments: arguments)
        self.defaults = defaults
    }

    func startScanning() {
        cancelAll()
        state = .scanning
        later(1.5) { [weak self] in
            guard let self, self.state == .scanning else { return }
            self.state = .found(name: Self.puckName)
        }
    }

    func connect() {
        guard case .found = state else { return }
        beginConnecting()
    }

    func reconnectRemembered() {
        guard defaults.bool(forKey: Self.pairedKey) else { return }
        beginConnecting()
    }

    func send(_ command: PuckCommand) {
        guard case .connected = state else { return }
        switch command {
        case .enrollStart(let index, _):
            onEvent?(.recording(index: index))
            later(3) { [weak self] in self?.onEvent?(.saved(index: index)) }
        case .enrollFinish:
            onEvent?(.done)
        case .enrollCancel:
            break
        }
    }

    func disconnect() {
        cancelAll()
        state = .idle
    }

    private func beginConnecting() {
        cancelAll()
        state = .connecting
        later(1) { [weak self] in
            guard let self, self.state == .connecting else { return }
            self.defaults.set(true, forKey: Self.pairedKey)
            self.state = .connected(name: Self.puckName)
            self.runSpeakerLoop()
        }
    }

    /// Sarah every 4 s for 16 s, silence for 25 s, unknown every 4 s for 12 s, repeat. Pinned: one state forever.
    private func runSpeakerLoop() {
        speakerTask = Task { [weak self] in
            while !Task.isCancelled {
                if let pinned = self?.pinnedSpeaker {
                    await self?.pulse(pinned, every: 4, for: .infinity)
                } else {
                    await self?.pulse(.sarah, every: 4, for: 16)
                    await self?.pause(25)
                    await self?.pulse(.unknown, every: 4, for: 12)
                }
            }
        }
    }

    private func pulse(_ speaker: FakeSpeaker, every period: Double, for duration: Double) async {
        var elapsed = 0.0
        while elapsed < duration, !Task.isCancelled {
            switch speaker {
            case .sarah:
                onWho?(WhoIsTalking(status: .identified, personId: "p_sarah", displayName: "Sarah",
                                    relationship: "daughter", score: 0.81))
            case .unknown:
                onWho?(WhoIsTalking(status: .unknown))
            case .none:
                break
            }
            await pause(period)
            elapsed += period
        }
    }

    private func pause(_ seconds: Double) async {
        try? await Task.sleep(nanoseconds: UInt64(seconds * timeScale * 1_000_000_000))
    }

    private func later(_ seconds: Double, _ body: @escaping @MainActor () -> Void) {
        tasks.append(Task { [weak self] in
            await self?.pause(seconds)
            guard !Task.isCancelled else { return }
            body()
        })
    }

    private func cancelAll() {
        tasks.forEach { $0.cancel() }
        tasks = []
        speakerTask?.cancel()
        speakerTask = nil
    }
}
