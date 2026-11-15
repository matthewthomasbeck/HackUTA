import SwiftUI

/// Figma "Teach your voice" (81:1152 listening, 81:1202 saved). The patient reads five sentences into the puck;
/// the phone only drives the script and never touches its own microphone, so there is no permission to ask for.
struct VoiceSetupView: View {
    var onBack: () -> Void
    var onNext: () -> Void
    @EnvironmentObject private var puck: PuckConnection
    @State private var enrollment = VoiceEnrollment()
    /// Bumped on every start so the 15 s timeout restarts, even for a retry of the same sentence.
    @State private var attempt = 0
    @ScaledMetric(relativeTo: .title2) private var disc: CGFloat = 64
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.dynamicTypeSize) private var typeSize

    private var finished: Bool { enrollment.phase == .finished }
    /// Without a puck there is nothing to read to, whatever the phase; a saved sentence or voice stays on screen.
    private var needsPuck: Bool { !puck.isConnected && enrollment.phase != .saved && !finished }

    var body: some View {
        OnboardingScaffold(step: .voiceSetup, onBack: back) {
            VStack(alignment: .leading, spacing: 16) {
                OnboardingHeading(
                    title: "Teach Calypso⁻¹ your voice",
                    message: finished
                        ? "Calypso⁻¹ can now tell your voice apart from family and friends."
                        : "Wear your puck and read each sentence out loud. Your puck listens, not your phone.")
                    .overlay(alignment: .topTrailing) {
                        Mascot(pose: finished ? .celebrating : .wave, size: .s, shadow: true)
                            .alignmentGuide(.top) { $0[.bottom] }
                    }
                if needsPuck {
                    notConnectedCard
                } else if finished {
                    savedCard
                } else {
                    sentenceCard
                }
                Spacer(minLength: 24)
                actions
            }
            .padding(.horizontal, 24)
            .frame(maxHeight: .infinity)
        }
        .animation(reduceMotion ? nil : .default, value: enrollment.phase)
        .onChange(of: puck.lastEvent) { _, event in
            // A repeat of the previous event doesn't change `lastEvent`; harmless here, because a retry
            // always passes through `recording` first and a restart is already `.recording` locally.
            if let event { enrollment.apply(event) }
        }
        .onChange(of: puck.isConnected) { _, connected in
            // Otherwise a dropped puck leaves "Listening…" / "Try again" looping with nothing to hear.
            if !connected { enrollment.puckLost() }
        }
        .onChange(of: enrollment.phase) { _, phase in announce(phase) }
        .task(id: enrollment.phase == .recording ? attempt : -1) {
            guard enrollment.phase == .recording else { return }
            try? await Task.sleep(for: .seconds(VoiceEnrollment.clipTimeout))
            guard !Task.isCancelled else { return }
            enrollment.timeout()
            // Tell the puck to drop the clip we gave up on, so it can't answer the retry.
            puck.send(.enrollCancel)
        }
    }

    // MARK: Cards

    private var sentenceCard: some View {
        PaperCard {
            VStack(alignment: .leading, spacing: 16) {
                Text("Sentence \(enrollment.index + 1) of \(VoiceEnrollment.sentences.count)")
                    .calypsoFont(.caption).foregroundStyle(Color.inkSoft)
                Text("“\(enrollment.sentence)”")
                    .calypsoFont(.title).foregroundStyle(Color.ink)
                    .fixedSize(horizontal: false, vertical: true)
                progressBar
                statusPill
            }
        }
        .accessibilityElement(children: .contain)
    }

    /// Done = periwinkleDeep, current = periwinkle, todo = periwinkleMist (Figma, 8pt tall, gap 8).
    private var progressBar: some View {
        let count = VoiceEnrollment.sentences.count
        let doneThrough = enrollment.phase == .saved ? enrollment.index : enrollment.index - 1
        return HStack(spacing: 8) {
            ForEach(0..<count, id: \.self) { i in
                RoundedRectangle(cornerRadius: 4)
                    .fill(i <= doneThrough ? Color.periwinkleDeep : i == enrollment.index ? Color.periwinkle : Color.periwinkleMist)
                    .frame(height: 8)
            }
        }
        .accessibilityElement()
        .accessibilityLabel("Sentence \(enrollment.index + 1) of \(count)")
    }

    @ViewBuilder private var statusPill: some View {
        switch enrollment.phase {
        case .recording:
            ListeningPill()
        case .saved:
            StatusCheckPill(label: "Sentence saved")
        case .failed(let message):
            Text(message).calypsoFont(.callout).foregroundStyle(Color.inkSoft)
                .frame(maxWidth: .infinity, alignment: .leading)
        case .ready, .finished:
            EmptyView()
        }
    }

    private var savedCard: some View {
        let count = VoiceEnrollment.sentences.count
        let layout = typeSize.isAccessibilitySize
            ? AnyLayout(VStackLayout(alignment: .leading, spacing: 12))
            : AnyLayout(HStackLayout(spacing: 16))
        return PaperCard(horizontalPadding: 16, verticalPadding: 12) {
            VStack(alignment: .leading, spacing: 10) {
                layout {
                    CalypsoIcon(.soundWave, relativeTo: .title2)
                        .foregroundStyle(Color.ink)
                        .frame(width: disc, height: disc)
                        .background(Color.apricotCream, in: Circle())
                    VStack(alignment: .leading, spacing: 2) {
                        Text("\(count) of \(count) sentences").calypsoFont(.headline).foregroundStyle(Color.ink)
                        Text("Your voice is saved on your puck.").calypsoFont(.callout).foregroundStyle(Color.inkSoft)
                    }
                    .fixedSize(horizontal: false, vertical: true)
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
                .accessibilityElement(children: .combine)
                StatusCheckPill(label: "Voice saved")
                    .accessibilityLabel("Voice saved")
            }
        }
    }

    private var notConnectedCard: some View {
        PaperCard {
            VStack(alignment: .leading, spacing: 8) {
                Text("Connect your puck first").calypsoFont(.headline).foregroundStyle(Color.ink)
                Text("Your puck needs to be connected to hear you.").calypsoFont(.callout).foregroundStyle(Color.inkSoft)
            }
        }
    }

    // MARK: Buttons

    @ViewBuilder private var actions: some View {
        if needsPuck {
            CalypsoButton("Go back", kind: .secondary, action: back)
            CalypsoButton("Skip for now", kind: .quiet, action: skip)
        } else {
            switch enrollment.phase {
            case .ready:
                CalypsoButton("Start reading", action: start)
            case .recording:
                EmptyView()
            case .saved:
                CalypsoButton(enrollment.isLast ? "Finish" : "Next sentence", action: next)
            case .failed:
                CalypsoButton("Try again", action: retry)
            case .finished:
                CalypsoButton("Continue", action: onNext)
            }
            if !finished {
                CalypsoButton("Skip for now", kind: .quiet, action: skip)
            }
        }
    }

    // MARK: Actions

    /// Status changes aren't focus changes, so VoiceOver would otherwise stay silent.
    private func announce(_ phase: VoiceEnrollment.Phase) {
        switch phase {
        case .recording: AccessibilityNotification.Announcement("Listening").post()
        case .saved: AccessibilityNotification.Announcement("Sentence saved").post()
        case .failed(let message): AccessibilityNotification.Announcement(message).post()
        case .ready, .finished: break
        }
    }

    private func start() { run(enrollment.start()) }

    private func retry() { run(enrollment.retry()) }

    private func next() { run(enrollment.next()) }

    private func run(_ command: PuckCommand?) {
        if enrollment.phase == .recording { attempt += 1 }
        if let command { puck.send(command) }
    }

    /// Leaving mid-clip tells the puck to stop recording.
    private func cancelIfRecording() {
        if enrollment.phase == .recording { puck.send(.enrollCancel) }
    }

    private func skip() {
        cancelIfRecording()
        onNext()
    }

    private func back() {
        cancelIfRecording()
        onBack()
    }
}

/// The "Listening…" pill. Owns its pulse so every sentence's pill animates, not only the first.
private struct ListeningPill: View {
    @State private var pulse = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        HStack(spacing: 12) {
            CalypsoIcon(.soundWave, size: 36)
            Text("Listening…").calypsoFont(.bodyStrong)
        }
        .foregroundStyle(Color.ink)
        .frame(maxWidth: .infinity, minHeight: 56)
        .background(Color.periwinkleMist, in: RoundedRectangle(cornerRadius: 24))
        .opacity(pulse || reduceMotion ? 1 : 0.55)
        .onAppear {
            guard !reduceMotion else { return }
            withAnimation(.easeInOut(duration: 0.9).repeatForever(autoreverses: true)) { pulse = true }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Listening")
    }
}

#Preview {
    VoiceSetupView(onBack: {}, onNext: {})
        .environmentObject(PuckConnection(link: FakePuckLink()))
}

#Preview("AX5") {
    VoiceSetupView(onBack: {}, onNext: {})
        .environmentObject(PuckConnection(link: FakePuckLink()))
        .dynamicTypeSize(.accessibility5)
}
