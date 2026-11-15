import SwiftUI

/// What the status card says for each `PuckConnectionState`. Pure, so every state is unit tested.
struct ConnectPuckPresentation: Equatable {
    /// The card's Headline: the puck's name, or the problem.
    let title: String
    /// The card's Callout.
    let message: String
    /// The button's label; nil while the app is busy. When connected this is the step's "Continue".
    let primaryTitle: String?
    let showsSpinner: Bool

    static func make(state: PuckConnectionState) -> ConnectPuckPresentation {
        let name = "Calypso Puck"
        switch state {
        case .idle:
            return .init(title: name, message: "Ready to look", primaryTitle: "Find my puck", showsSpinner: false)
        case .scanning:
            return .init(title: name, message: "Looking for your puck…", primaryTitle: nil, showsSpinner: true)
        case .found(let found):
            return .init(title: found, message: "Found nearby", primaryTitle: "Connect", showsSpinner: false)
        case .connecting:
            return .init(title: name, message: "Connecting…", primaryTitle: nil, showsSpinner: true)
        case .connected(let connected):
            return .init(title: connected, message: "Ready. It will listen for you.", primaryTitle: "Continue",
                         showsSpinner: false)
        case .bluetoothOff:
            return .init(title: "Bluetooth is off", message: "Turn on Bluetooth in Control Center.",
                         primaryTitle: "Try again", showsSpinner: false)
        case .unauthorized:
            return .init(title: "Bluetooth isn't allowed", message: "Allow Bluetooth for Calypso⁻¹ in Settings.",
                         primaryTitle: "Open Settings", showsSpinner: false)
        case .failed(let reason):
            return .init(title: "We couldn't connect", message: reason, primaryTitle: "Try again",
                         showsSpinner: false)
        }
    }
}

/// Figma "Connect your puck" (81:943 found, 81:1008 connected). Laid out like Permissions: a status card with
/// the puck's disc, then Skip for now. The puck is optional, so the step can always be skipped.
struct ConnectPuckView: View {
    var onBack: () -> Void
    var onNext: () -> Void
    @EnvironmentObject private var puck: PuckConnection
    @ScaledMetric(relativeTo: .title2) private var disc: CGFloat = 64
    @Environment(\.dynamicTypeSize) private var typeSize

    var body: some View {
        let presentation = ConnectPuckPresentation.make(state: puck.state)
        let connected = puck.isConnected
        OnboardingScaffold(step: .connectPuck, onBack: onBack) {
            VStack(alignment: .leading, spacing: 8) {
                OnboardingHeading(title: "Connect your puck",
                                  message: "Turn on your Calypso⁻¹ puck and keep it close to your phone.")
                    .overlay(alignment: .topTrailing) {
                        Mascot(pose: .presenting, size: .s, shadow: true)
                            .alignmentGuide(.top) { $0[.bottom] }
                    }
                statusCard(presentation, connected: connected)
                Spacer(minLength: 24)
                if connected {
                    CalypsoButton("Continue", action: onNext)
                } else {
                    CalypsoButton("Skip for now", kind: .quiet, action: onNext)
                }
            }
            .padding(.horizontal, 24)
            .frame(maxHeight: .infinity)
        }
        .animation(.default, value: puck.state)
    }

    private func statusCard(_ presentation: ConnectPuckPresentation, connected: Bool) -> some View {
        // The callout wraps, so switch on AX sizes instead of `ViewThatFits`.
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
                        Text(presentation.title).calypsoFont(.headline).foregroundStyle(Color.ink)
                        HStack(spacing: 8) {
                            if presentation.showsSpinner { ProgressView() }
                            Text(presentation.message).calypsoFont(.callout).foregroundStyle(Color.inkSoft)
                        }
                    }
                    .fixedSize(horizontal: false, vertical: true)
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
                .accessibilityElement(children: .combine)
                if connected {
                    StatusCheckPill(label: "Connected")
                        .accessibilityLabel("Puck connected")
                } else if let title = presentation.primaryTitle {
                    CalypsoButton(title, kind: .secondary, action: primaryAction)
                        .accessibilityLabel(title)
                }
            }
        }
    }

    /// The card's button, by what the link is doing.
    private func primaryAction() {
        switch puck.state {
        case .found: puck.connect()
        case .unauthorized:
            if let url = URL(string: UIApplication.openSettingsURLString) { UIApplication.shared.open(url) }
        default: puck.startScanning()
        }
    }
}

#Preview {
    ConnectPuckView(onBack: {}, onNext: {})
        .environmentObject(PuckConnection(link: FakePuckLink()))
}

#Preview("AX5") {
    ConnectPuckView(onBack: {}, onNext: {})
        .environmentObject(PuckConnection(link: FakePuckLink()))
        .dynamicTypeSize(.accessibility5)
}
