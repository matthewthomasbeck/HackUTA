import SwiftUI

enum Decoration: String, CaseIterable {
    case oliveBranch = "OliveBranch"
    case meander = "MeanderBorder"
    case islandHome = "IslandHome"
    case lighthouse = "Lighthouse"
    case wavesCalm = "WavesCalm"
    case wavesLively = "WavesLively"
    case seascape = "Seascape"
}

struct DecorationImage: View {
    let decoration: Decoration

    init(_ decoration: Decoration) { self.decoration = decoration }

    var body: some View {
        Image(decoration.rawValue)
            .resizable()
            .aspectRatio(contentMode: .fit)
            .accessibilityHidden(true)
    }
}
