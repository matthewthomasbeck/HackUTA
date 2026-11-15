import SwiftUI

/// The day's hero photo (Figma 20:503). Tries `candidates` in order and shows the first one that loads; a photo
/// that fails (sensitive photos 404) moves on to the next. When every candidate fails, or there are none, it
/// renders nothing, so there's never an empty frame. No caption: there's no data source for one (plan ruling).
struct HeroPhoto: View {
    let candidates: [String]
    let photoURL: (String) -> URL?

    @State private var index = 0
    /// The candidate list `index` belongs to. When `candidates` changes, the index starts over at 0.
    @State private var indexCandidates: [String] = []

    private var currentIndex: Int { indexCandidates == candidates ? index : 0 }

    var body: some View {
        if currentIndex < candidates.count {
            PhotoTile(url: photoURL(candidates[currentIndex]), style: .hero) {
                let next = currentIndex + 1
                indexCandidates = candidates
                index = next
            }
            .accessibilityLabel("A photo from this day")
        }
    }
}

#if DEBUG
#Preview {
    VStack(spacing: 16) {
        HeroPhoto(candidates: ["missing_a", "b"], photoURL: ComponentSamples.photoURL)
        HeroPhoto(candidates: ["missing_only"], photoURL: ComponentSamples.photoURL) // renders nothing
        Text("Your day").calypsoFont(.headline)
    }
    .padding(24)
    .background(Color.paper)
}
#endif
