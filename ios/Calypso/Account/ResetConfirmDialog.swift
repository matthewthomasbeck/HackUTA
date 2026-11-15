import SwiftUI

/// Reset confirm (Figma 20:727): an Ink 50% scrim and a centered paper card. "Keep everything" is the primary,
/// safe choice; a tap on the scrim (or the VoiceOver escape gesture) also keeps everything. Nothing is red.
/// The card springs in from 0.96 scale, or fades only under Reduce Motion, and plays out before `onKeep`.
struct ResetConfirmDialog: View {
    let onKeep: () -> Void
    let onReset: () -> Void

    @State private var shown = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    init(onKeep: @escaping () -> Void, onReset: @escaping () -> Void) {
        self.onKeep = onKeep
        self.onReset = onReset
    }

    private static let message =
        "This clears this phone’s sync history and pending visits, then starts setup again. Nothing on the server is deleted."

    private var animation: Animation {
        reduceMotion ? .easeInOut(duration: 0.2) : .spring(response: 0.35, dampingFraction: 1)
    }

    var body: some View {
        ZStack {
            Color.ink.opacity(0.5)
                .ignoresSafeArea()
                .opacity(shown ? 1 : 0)
                .onTapGesture(perform: keep)
                .accessibilityHidden(true)
            GeometryReader { proxy in
                // Scrolls only when the card is taller than the screen (large Dynamic Type).
                ScrollView {
                    card
                        .padding(24)
                        .frame(maxWidth: .infinity, minHeight: proxy.size.height)
                        .contentShape(Rectangle())
                        .onTapGesture(perform: keep)
                }
                .scrollBounceBehavior(.basedOnSize)
            }
            .opacity(shown ? 1 : 0)
            .scaleEffect(shown || reduceMotion ? 1 : 0.96)
        }
        .onAppear {
            withAnimation(animation) { shown = true }
        }
    }

    private var card: some View {
        PaperCard(cornerRadius: 32, bordered: false) { // Figma 20:727
            VStack(spacing: 16) {
                // 40pt glyph in a 72pt badge; the badge grows with the glyph under Dynamic Type.
                ResetWarningGlyph(size: 40)
                    .padding(16)
                    .background(Color.apricotCream, in: Circle())
                Text("Reset this phone?")
                    .calypsoFont(.title)
                    .foregroundStyle(Color.ink)
                    .accessibilityAddTraits(.isHeader)
                Text(Self.message)
                    .calypsoFont(.body)
                    .foregroundStyle(Color.inkSoft)
                VStack(spacing: 16) {
                    CalypsoButton("Keep everything", action: keep)
                    CalypsoButton("Reset this phone", kind: .secondary, action: onReset)
                }
                .padding(.top, 4)
            }
            .multilineTextAlignment(.center)
            .frame(maxWidth: .infinity)
            .padding(8)
        }
        // Swallow taps on the card itself so only the scrim keeps everything.
        .contentShape(RoundedRectangle(cornerRadius: 32))
        .onTapGesture {}
        .accessibilityElement(children: .contain)
        .accessibilityAddTraits(.isModal)
        .accessibilityAction(.escape, keep)
    }

    private func keep() {
        withAnimation(animation) {
            shown = false
        } completion: {
            onKeep()
        }
    }
}

#Preview {
    ZStack {
        Color.paper.ignoresSafeArea()
        ResetConfirmDialog(onKeep: {}, onReset: {})
    }
}

#Preview("AX5") {
    ZStack {
        Color.paper.ignoresSafeArea()
        ResetConfirmDialog(onKeep: {}, onReset: {})
    }
    .dynamicTypeSize(.accessibility5)
}
