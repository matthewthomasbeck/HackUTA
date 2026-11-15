import SwiftUI

enum PhotoTileStyle {
    case hero, thumb
}

/// Figma `Photo` (15:112): Apricot Cream mat, 4pt white border, radius 16. Hero is full width × 220, thumb 96×96.
/// While loading it shows the mat with the photo glyph. On failure (sensitive photos 404) or a nil URL it calls
/// `onFailure()` once and renders nothing, so there's never a broken placeholder.
struct PhotoTile: View {
    let url: URL?
    let style: PhotoTileStyle
    let onFailure: () -> Void

    /// The URL (or "nil") `onFailure` was last called for, so each URL reports at most once even when the
    /// same tile is reused with a new URL (hero candidates).
    @State private var reportedKey: String?

    init(url: URL?, style: PhotoTileStyle, onFailure: @escaping () -> Void = {}) {
        self.url = url
        self.style = style
        self.onFailure = onFailure
    }

    var body: some View {
        if let url {
            AsyncImage(url: url) { phase in
                switch phase {
                case .success(let image):
                    mat { image.resizable().scaledToFill() }
                case .failure(let error) where !Self.isCancellation(error):
                    failed
                default:
                    mat { placeholderGlyph }
                }
            }
        } else {
            failed
        }
    }

    /// AsyncImage reports a cancelled load (view scrolled away) as a failure; that's not a broken photo.
    private static func isCancellation(_ error: Error) -> Bool {
        (error as? URLError)?.code == .cancelled || error is CancellationError
    }

    private var failed: some View {
        Color.clear
            .frame(width: 0, height: 0)
            .accessibilityHidden(true)
            .onAppear {
                let key = url?.absoluteString ?? "nil"
                guard reportedKey != key else { return }
                reportedKey = key
                onFailure()
            }
    }

    private var placeholderGlyph: some View {
        Image(systemName: "photo")
            .font(.system(size: style == .hero ? 56 : 28, weight: .medium))
            .foregroundStyle(Color.photoGlyph)
            .accessibilityHidden(true)
    }

    @ViewBuilder private func mat<Content: View>(@ViewBuilder _ content: () -> Content) -> some View {
        let shape = RoundedRectangle(cornerRadius: 16)
        let tile = Color.apricotCream
            .overlay(content())
            .clipShape(shape)
            .overlay(shape.strokeBorder(Color.white, lineWidth: 4))
        switch style {
        case .hero: tile.frame(maxWidth: .infinity).frame(height: 220)
        case .thumb: tile.frame(width: 96, height: 96)
        }
    }
}

#Preview {
    VStack(spacing: 16) {
        PhotoTile(url: URL(string: "https://example.invalid/loading.jpg"), style: .hero)
        HStack(spacing: 8) {
            PhotoTile(url: URL(string: "https://example.invalid/a.jpg"), style: .thumb)
            PhotoTile(url: nil, style: .thumb) // renders nothing
        }
    }
    .padding(24)
    .background(Color.paper)
}
