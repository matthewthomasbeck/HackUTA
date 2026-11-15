import SwiftUI

/// What the Today "talking with" card shows for the puck's state and current speaker. Only an `identified`
/// speaker with a name is ever named; `uncertain` and `unknown` read the same neutral wording even when the puck
/// sent a candidate name. The patient is never the subject: their voice reads as quiet.
enum TalkingToPresentation: Equatable {
    case person(Person)
    case someoneNew
    case quiet
    case notConnected

    static func make(state: PuckConnectionState, speaker: WhoIsTalking?, people: [Person]) -> TalkingToPresentation {
        guard case .connected = state else { return .notConnected }
        guard let speaker else { return .quiet }
        let stored = speaker.personId.flatMap { id in people.first { $0.id == id } }
        if speaker.personId == "patient" || stored?.isPatient == true { return .quiet }
        guard speaker.status == .identified, let name = PersonName.display(speaker.displayName) else {
            return .someoneNew
        }
        if var stored {
            // The stored person carries the photo; the puck's name fills in a still-unnamed record.
            if stored.displayName == nil { stored.name = name }
            return .person(stored)
        }
        return .person(Person(id: speaker.personId ?? "puck_\(name)", name: name, relationship: speaker.relationship))
    }

    /// A speaker is present: the card shows the live dot.
    var isLive: Bool {
        switch self {
        case .person, .someoneNew: true
        case .quiet, .notConnected: false
        }
    }

    var caption: String {
        switch self {
        case .person, .someoneNew: "Talking with"
        case .quiet: "Right now"
        case .notConnected: "Your puck"
        }
    }

    var title: String {
        switch self {
        case .person(let person): person.displayName ?? PeoplePresentation.unknownName
        case .someoneNew: "Someone new"
        case .quiet: "It’s quiet"
        case .notConnected: "Not connected"
        }
    }

    var subtitle: String? {
        switch self {
        case .person(let person): PeoplePresentation.rowRelationship(person.relationship)?.lowercased()
        case .someoneNew: "Getting to know them…"
        case .quiet: "I’ll show who you’re talking with."
        case .notConnected: "Keep your puck close to your phone."
        }
    }

    var accessibilityLabel: String {
        switch self {
        case .person:
            let who = [title, subtitle].compactMap { $0 }.joined(separator: ", ")
            return "Talking with \(who). Opens \(title)’s profile."
        case .someoneNew:
            return "Talking with someone new. Calypso⁻¹ doesn’t know this voice yet. Opens more about them."
        case .quiet:
            return "Right now it’s quiet. I’ll show who you’re talking with."
        case .notConnected:
            return "Your puck is not connected. Keep your puck close to your phone. Tap to reconnect."
        }
    }

    /// Changes only when the card's look changes, so a repeated `who` for the same person doesn't re-fade it.
    fileprivate var kind: String {
        switch self {
        case .person(let person): "person-\(person.id)"
        case .someoneNew: "someoneNew"
        case .quiet: "quiet"
        case .notConnected: "notConnected"
        }
    }
}

/// Today's hero slot (Figma `Talking With` 81:425): a 180pt-min row card with the leading visual, caption, title
/// and callout, plus a chevron when it opens something. Person 81:387 (Apricot Cream, avatar), Someone New 81:399
/// (Periwinkle Mist, sound-wave disc), Quiet 81:410 (white, resting gull), Not Connected 81:419 (Paper, dashed
/// outline; tapping reconnects). Changes crossfade; at accessibility sizes the visual sits above the text.
struct TalkingToCard: View {
    let presentation: TalkingToPresentation
    /// Nil for the quiet card, which isn't tappable.
    var action: (() -> Void)?

    @Environment(\.dynamicTypeSize) private var dynamicTypeSize
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        ZStack {
            content
                .id(presentation.kind)
                .transition(reduceMotion ? .opacity : .opacity.combined(with: .scale(scale: 0.98)))
        }
        .animation(.easeInOut(duration: 0.3), value: presentation.kind)
    }

    @ViewBuilder private var content: some View {
        if let action, presentation != .quiet {
            Button(action: action) { card }
                .buttonStyle(PressableStyle())
        } else {
            card
        }
    }

    private var showsChevron: Bool { presentation.isLive }

    private var card: some View {
        let shape = RoundedRectangle(cornerRadius: 16)
        return Group {
            if dynamicTypeSize.isAccessibilitySize {
                VStack(alignment: .leading, spacing: 16) {
                    HStack {
                        visual
                        Spacer(minLength: 12)
                        if showsChevron { chevron }
                    }
                    text
                }
            } else {
                HStack(spacing: 16) {
                    visual
                    text
                    if showsChevron { chevron }
                }
            }
        }
        .padding(20)
        .frame(maxWidth: .infinity, minHeight: 180, alignment: .leading)
        .background(background, in: shape)
        .overlay { border(shape) }
        .contentShape(shape)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(presentation.accessibilityLabel)
        .accessibilityAddTraits(action != nil && presentation != .quiet ? .isButton : [])
    }

    private var background: Color {
        switch presentation {
        case .person: .apricotCream
        case .someoneNew: .periwinkleMist
        case .quiet: .card
        case .notConnected: .paper
        }
    }

    @ViewBuilder private func border(_ shape: RoundedRectangle) -> some View {
        switch presentation {
        case .person, .someoneNew:
            shape.strokeBorder(Color.white, lineWidth: 4)
        case .quiet:
            EmptyView()
        case .notConnected:
            shape.strokeBorder(Color.periwinkle, style: StrokeStyle(lineWidth: 2.5, dash: [8, 6]))
        }
    }

    @ViewBuilder private var visual: some View {
        switch presentation {
        case .person(let person):
            Avatar(urlString: person.facePhotoUrl, isKnown: true, size: 104)
        case .someoneNew:
            disc(size: 104, fill: .card) {
                CalypsoGlyph.soundWave.image
                    .resizable()
                    .scaledToFit()
                    .frame(width: 48, height: 48)
                    .foregroundStyle(Color.ink)
            }
        case .quiet:
            disc(size: 104, fill: .apricotCream) {
                Mascot(pose: .resting, size: .s)
            }
        case .notConnected:
            disc(size: 88, fill: .periwinkleMist) {
                CalypsoGlyph.soundWave.image
                    .resizable()
                    .scaledToFit()
                    .frame(width: 40, height: 40)
                    .foregroundStyle(Color.ink)
                    .opacity(0.6)
            }
        }
    }

    private func disc<Inner: View>(size: CGFloat, fill: Color, @ViewBuilder inner: () -> Inner) -> some View {
        ZStack {
            Circle().fill(fill)
            inner()
        }
        .frame(width: size, height: size)
        .accessibilityHidden(true)
    }

    private var text: some View {
        VStack(alignment: .leading, spacing: 2) {
            HStack(spacing: 8) {
                if presentation.isLive { LiveDot() }
                Text(presentation.caption)
                    .calypsoFont(.caption)
                    .foregroundStyle(Color.ink)
            }
            Text(presentation.title)
                .calypsoFont(isPerson ? .title : .headline)
                .foregroundStyle(Color.ink)
            if let subtitle = presentation.subtitle {
                Text(subtitle)
                    .calypsoFont(.callout)
                    .foregroundStyle(Color.inkSoft)
            }
        }
        .multilineTextAlignment(.leading)
        .frame(maxWidth: .infinity, alignment: .leading)
        .fixedSize(horizontal: false, vertical: true)
    }

    private var isPerson: Bool {
        if case .person = presentation { return true }
        return false
    }

    private var chevron: some View {
        CalypsoIcon(.chevronRight, size: 32, relativeTo: .headline)
            .foregroundStyle(Color.ink)
    }
}

/// 12pt Terracotta dot beside "Talking with" while someone is speaking. Pulses gently unless Reduce Motion is on.
private struct LiveDot: View {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var dimmed = false

    var body: some View {
        Circle()
            .fill(Color.terracotta)
            .frame(width: 12, height: 12)
            .opacity(dimmed ? 0.35 : 1)
            .onAppear { dimmed = !reduceMotion }
            .onChange(of: reduceMotion) { _, reduce in dimmed = !reduce }
            .animation(reduceMotion ? nil : .easeInOut(duration: 1).repeatForever(autoreverses: true), value: dimmed)
            .accessibilityHidden(true)
    }
}

/// "Someone new" sheet (Figma 81:502), opened from the Someone New card.
struct SomeoneNewSheet: View {
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        PaperSheet {
            Mascot(pose: .thinking, size: .m)
                .frame(maxWidth: .infinity)
            Text("Someone new")
                .calypsoFont(.title)
                .foregroundStyle(Color.ink)
                .accessibilityAddTraits(.isHeader)
            Text("Calypso⁻¹ doesn’t know this voice yet. You can ask their name. Family can add them in People later.")
                .calypsoFont(.body)
                .foregroundStyle(Color.inkSoft)
                .fixedSize(horizontal: false, vertical: true)
            CalypsoButton("Okay") { dismiss() }
        }
    }
}

#if DEBUG
#Preview("Talking With") {
    ScrollView {
        VStack(spacing: 16) {
            TalkingToCard(presentation: .person(Person(id: "p_sarah", name: "Sarah", relationship: "daughter"))) {}
            TalkingToCard(presentation: .someoneNew) {}
            TalkingToCard(presentation: .quiet)
            TalkingToCard(presentation: .notConnected) {}
        }
        .padding(24)
    }
    .background(Color.paper)
}

#Preview("Talking With AX5") {
    ScrollView {
        VStack(spacing: 16) {
            TalkingToCard(presentation: .person(Person(id: "p_sarah", name: "Sarah", relationship: "daughter"))) {}
            TalkingToCard(presentation: .notConnected) {}
        }
        .padding(24)
    }
    .background(Color.paper)
    .dynamicTypeSize(.accessibility5)
}

#Preview("Someone new sheet") {
    Color.paper.sheet(isPresented: .constant(true)) { SomeoneNewSheet() }
}
#endif
