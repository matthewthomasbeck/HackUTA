import SwiftUI

/// Account (Figma 20:386, reset confirm 20:727): header, a hero panel, the connection details, then "Run setup
/// again" and "Reset this phone". `confirmingReset` opens with the dialog shown (DEBUG `-screen reset` route).
struct AccountView: View {
    @AppStorage("onboarded") private var onboarded = true
    @State private var confirmingReset: Bool

    init(confirmingReset: Bool = false) {
        _confirmingReset = State(initialValue: confirmingReset)
    }

    private static let resetExplanation =
        "This clears this phone’s sync history and pending visits, then starts setup again. Nothing on the server is deleted."

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                NavHeader(caption: "Calypso⁻¹", title: "Account")
                hero
                connection
                CalypsoButton("Run setup again", kind: .secondary) { onboarded = false }
                resetButton
                Text(Self.resetExplanation)
                    .calypsoFont(.callout)
                    .foregroundStyle(Color.inkSoft)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            .padding(.horizontal, 24)
            .padding(.top, 16)
            .padding(.bottom, 24)
        }
        .background(Color.paper.ignoresSafeArea())
        .paperTopEdge()
        // The dialog is hosted full screen with a clear background so its scrim also dims the tab bar. The system
        // slide is turned off both ways; the dialog runs its own spring (or fade under Reduce Motion).
        .fullScreenCover(isPresented: $confirmingReset) {
            ResetConfirmDialog(onKeep: { setConfirmingReset(false) }, onReset: reset)
                .presentationBackground(.clear)
        }
    }

    // MARK: Sections

    private var hero: some View {
        // Bottom-aligned so the gull stands on the same line as the lighthouse; the logo is centered in its column.
        HStack(alignment: .bottom, spacing: 0) {
            Logo(size: 76)
                .frame(height: 156)
            Spacer(minLength: 8)
            Mascot(pose: .lantern, size: .custom(96), shadow: true)
            Spacer(minLength: 8)
            DecorationImage(.lighthouse)
                .frame(width: 104, height: 156)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 24)
        .frame(maxWidth: .infinity)
        .background(Color.periwinkleMist, in: RoundedRectangle(cornerRadius: 32)) // Figma 20:386
    }

    private var connection: some View {
        PaperCard {
            VStack(alignment: .leading, spacing: 18) {
                Text("Connection")
                    .calypsoFont(.headline)
                    .lineLimit(1)
                    .minimumScaleFactor(0.6) // one word: shrink at AX sizes rather than break mid-word
                    .foregroundStyle(Color.ink)
                    .accessibilityAddTraits(.isHeader)
                VStack(alignment: .leading, spacing: 20) {
                    detail("Server", value: Config.apiBaseURL?.host() ?? "Not set")
                    detail("Calypso⁻¹ phone", value: Config.chertPhone.isEmpty ? "Not set" : Config.chertPhone)
                }
            }
        }
    }

    private func detail(_ label: String, value: String) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(label)
                .calypsoFont(.callout)
                .foregroundStyle(Color.inkSoft)
            Text(value)
                .calypsoFont(.bodyStrong)
                .foregroundStyle(Color.ink)
                .textSelection(.enabled)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .accessibilityElement(children: .combine)
    }

    private var resetButton: some View {
        Button {
            setConfirmingReset(true)
        } label: {
            HStack(spacing: 12) {
                ResetWarningGlyph(size: 36)
                Text("Reset this phone")
            }
        }
        .buttonStyle(CalypsoButtonStyle(.secondary))
    }

    private func setConfirmingReset(_ value: Bool) {
        var transaction = Transaction()
        transaction.disablesAnimations = true
        withTransaction(transaction) { confirmingReset = value }
    }

    private func reset() {
        if let domain = Bundle.main.bundleIdentifier {
            UserDefaults.standard.removePersistentDomain(forName: domain)
        }
        onboarded = false
    }
}

/// Apricot warning triangle with an Ink mark (never red). Decorative: the button or dialog text says what it does.
struct ResetWarningGlyph: View {
    @ScaledMetric private var box: CGFloat

    init(size: CGFloat) {
        _box = ScaledMetric(wrappedValue: size, relativeTo: .body)
    }

    var body: some View {
        Image(systemName: "exclamationmark.triangle.fill")
            .symbolRenderingMode(.palette)
            .foregroundStyle(Color.ink, Color.apricot)
            .font(.system(size: box * 0.8, weight: .semibold))
            .frame(width: box, height: box)
            .accessibilityHidden(true)
    }
}

#Preview("Account") {
    AccountView()
        .safeAreaInset(edge: .bottom, spacing: 0) { CalypsoTabBar(selection: .constant(.account)) }
}

#Preview("Account AX5") {
    AccountView()
        .dynamicTypeSize(.accessibility5)
}
