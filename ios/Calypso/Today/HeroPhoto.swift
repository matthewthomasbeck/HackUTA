import SwiftUI

/// The day's hero slot (Figma 20:503): the "Family photo" placeholder from the Photo component, Hero size.
/// There's no family-photo data source yet, so it never loads a real image; event photos stay in their cards.
struct FamilyPhotoPlaceholder: View {
    var body: some View {
        let shape = RoundedRectangle(cornerRadius: 16)
        VStack(spacing: 12) {
            CalypsoGlyph.photo.image
                .resizable()
                .scaledToFit()
                .frame(width: 72, height: 72)
                .foregroundStyle(Color.photoGlyph)
            Text("Family photo")
                .calypsoFont(.caption)
                .foregroundStyle(Color.ink)
        }
        .frame(maxWidth: .infinity)
        .frame(height: 180)
        .background(Color.apricotCream)
        .clipShape(shape)
        .overlay(shape.strokeBorder(Color.white, lineWidth: 4))
        .accessibilityHidden(true) // a placeholder carries no information
    }
}

#if DEBUG
#Preview {
    FamilyPhotoPlaceholder()
        .padding(24)
        .background(Color.paper)
}
#endif
