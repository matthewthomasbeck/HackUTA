import SwiftUI

/// Figma `Place Row` (16:104). Known: pin + place (Body). Uncertain: waveform glyph and the place in a
/// dashed Apricot Cream chip (Callout, Ink), never a pin.
struct PlaceRow: View {
    let place: String
    let isUncertain: Bool

    init(place: String, isUncertain: Bool) {
        self.place = place
        self.isUncertain = isUncertain
    }

    static func accessibilityLabel(place: String, isUncertain: Bool) -> String {
        guard isUncertain else { return "At \(place)" }
        return "Place not certain: " + place.prefix(1).lowercased() + place.dropFirst()
    }

    var body: some View {
        Group {
            if isUncertain {
                uncertain
            } else {
                HStack(spacing: 12) {
                    CalypsoIcon("mappin.and.ellipse").foregroundStyle(Color.periwinkleDeep)
                    Text(place)
                        .calypsoFont(.body)
                        .foregroundStyle(Color.ink)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
        }
        .fixedSize(horizontal: false, vertical: true)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(Self.accessibilityLabel(place: place, isUncertain: isUncertain))
    }

    private var uncertain: some View {
        let shape = RoundedRectangle(cornerRadius: 28)
        return HStack(spacing: 10) {
            CalypsoIcon("waveform", relativeTo: .callout).foregroundStyle(Color.ink)
            Text(place)
                .calypsoFont(.callout)
                .foregroundStyle(Color.ink)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(.leading, 16)
        .padding(.trailing, 20)
        .padding(.vertical, 10)
        .background(Color.apricotCream, in: shape)
        .overlay(shape.strokeBorder(Color.inkSoft, style: StrokeStyle(lineWidth: 2, dash: [7, 5])))
    }
}

#Preview {
    VStack(spacing: 16) {
        PlaceRow(place: "Blue Bean Café", isUncertain: false)
        PlaceRow(place: "Somewhere with park sounds", isUncertain: true)
    }
    .padding(24)
    .background(Color.paper)
}

#Preview("AX5") {
    VStack(spacing: 16) {
        PlaceRow(place: "Blue Bean Café", isUncertain: false)
        PlaceRow(place: "Somewhere with park sounds", isUncertain: true)
    }
    .padding(24)
    .background(Color.paper)
    .dynamicTypeSize(.accessibility5)
}
