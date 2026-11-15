import SwiftUI

/// Figma `Nav Header` (17:148): Caption eyebrow (Ink Soft), Display title (Ink, header trait), trailing accessory.
struct NavHeader<Accessory: View>: View {
    let caption: String
    let title: String
    let accessory: Accessory

    init(caption: String, title: String, @ViewBuilder accessory: () -> Accessory) {
        self.caption = caption
        self.title = title
        self.accessory = accessory()
    }

    var body: some View {
        HStack(alignment: .bottom, spacing: 12) {
            VStack(alignment: .leading, spacing: 4) {
                Text(caption)
                    .calypsoFont(.caption)
                    .foregroundStyle(Color.inkSoft)
                Text(title)
                    .calypsoFont(.display)
                    .foregroundStyle(Color.ink)
                    .accessibilityAddTraits(.isHeader)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            accessory
        }
    }
}

extension NavHeader where Accessory == EmptyView {
    init(caption: String, title: String) {
        self.init(caption: caption, title: title) { EmptyView() }
    }
}

#Preview {
    VStack(spacing: 32) {
        NavHeader(caption: "Saturday, November 14", title: "Today") {
            Mascot(pose: .wave, size: .s)
        }
        NavHeader(caption: "Your family and friends", title: "People")
    }
    .padding(24)
    .background(Color.paper)
}
