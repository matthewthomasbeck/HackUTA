import Foundation

/// The "Teach your voice" flow: five sentences read aloud, one puck clip each. Pure, so every transition is unit
/// tested; the view only turns the returned `PuckCommand`s into `puck.send` calls.
struct VoiceEnrollment: Equatable {
    static let sentences = [
        "My name is easy to remember, and so is my family.",
        "This morning I had a cup of tea by the window.",
        "I love hearing stories about the people I care about.",
        "The sea is calm today, and the sky is bright.",
        "Thank you for helping me remember my day.",
    ]
    static let genericFailure = "We didn't hear that. Let's try again."
    static let quietFailure = "That was a little quiet. Let's try once more."
    /// The phone gives up on a clip after this long without `saved` or `failed`.
    static let clipTimeout: TimeInterval = 15

    enum Phase: Equatable { case ready, recording, saved, failed(String), finished }

    private(set) var index = 0
    private(set) var phase = Phase.ready
    /// Set when a clip timed out: the puck may still answer it late, so the retry ignores `saved`/`failed` until
    /// it has announced its own `recording`.
    private var awaitingRecording = false

    init() {}

    /// For tests: resume mid-flow.
    init(index: Int, phase: Phase) {
        self.index = index
        self.phase = phase
    }

    var sentence: String { Self.sentences[index] }
    var isLast: Bool { index == Self.sentences.count - 1 }

    /// Asks the puck to record the current sentence.
    mutating func start() -> PuckCommand? {
        guard phase == .ready else { return nil }
        phase = .recording
        return .enrollStart(index: index, text: sentence)
    }

    /// Only the current sentence's events count, and only while recording. `done` is ignored: finishing is
    /// fire-and-forget (see `next`).
    mutating func apply(_ event: PuckEvent) {
        guard phase == .recording else { return }
        if awaitingRecording {
            if case .recording(let i) = event, i == index { awaitingRecording = false }
            return
        }
        switch event {
        case .saved(let i) where i == index:
            phase = .saved
        case .failed(let i, let reason) where i == index:
            phase = .failed(reason == "too_quiet" ? Self.quietFailure : Self.genericFailure)
        case .recording, .saved, .failed, .done:
            break
        }
    }

    /// No `saved`/`failed` arrived in time.
    mutating func timeout() {
        guard phase == .recording else { return }
        phase = .failed(Self.genericFailure)
        awaitingRecording = true
    }

    /// The puck dropped mid-flow: whatever was recording or had failed starts over from `ready` on reconnect.
    mutating func puckLost() {
        switch phase {
        case .recording, .failed:
            phase = .ready
            awaitingRecording = false
        case .ready, .saved, .finished:
            break
        }
    }

    /// Moves past a saved sentence. After the last one this asks the puck to finish and is `finished` at once:
    /// the UI doesn't wait for `enroll_done`, so a puck that fails to finalize still reads as saved.
    mutating func next() -> PuckCommand? {
        guard phase == .saved else { return nil }
        guard !isLast else {
            phase = .finished
            return .enrollFinish(count: Self.sentences.count)
        }
        index += 1
        phase = .ready
        return nil
    }

    /// Records the same sentence again after a failure.
    mutating func retry() -> PuckCommand? {
        guard case .failed = phase else { return nil }
        phase = .ready
        return start()
    }
}
