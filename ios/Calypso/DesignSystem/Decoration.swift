import SwiftUI

enum Decoration: String, CaseIterable {
    case oliveBranch = "OliveBranch"
    case meander = "MeanderBorder"
    case islandHome = "IslandHome"
    case lighthouse = "Lighthouse"
    case wavesCalm = "WavesCalm"
    case wavesLively = "WavesLively"
    case seascape = "Seascape"
    /// "You're all set" (Figma 37:1787): waves and shore only, no island.
    case seascapeShore = "SeascapeShore"
    /// Apricot Cream paper rock from "Meet your companion" (Figma 20:462).
    case shoreRock = "ShoreRock"
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
