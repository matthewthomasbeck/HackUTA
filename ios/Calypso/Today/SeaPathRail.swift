import SwiftUI

/// Decorative leading column of a Today moment row (Figma "Sea Path Rail", 20:519). A dotted Periwinkle line runs
/// through the day; an Apricot dot sits level with each card's time tag, with small wave marks along the way.
/// The walking gull replaces the last dot only when the day is today. It fills the row's height, so the row must
/// give it a definite height (`fixedSize(horizontal: false, vertical: true)` on the row).
struct SeaPathRail: View {
    let isFirst: Bool
    let isLast: Bool
    let showsGull: Bool
    /// Row index; alternates which side the wave marks sit on.
    let index: Int

    static let width: CGFloat = 48

    /// Top of the 22pt dot. The card's time tag sits 22pt into the card and grows with Dynamic Type.
    @ScaledMetric(relativeTo: .footnote) private var dotTop: CGFloat = 28
    private let lineX: CGFloat = 24

    var body: some View {
        GeometryReader { geo in
            let markerCenter = dotTop + 11
            let lineTop = isFirst ? markerCenter : 0
            let lineBottom = isLast ? markerCenter : geo.size.height
            ZStack(alignment: .topLeading) {
                if lineBottom > lineTop {
                    Path { p in
                        p.move(to: CGPoint(x: lineX, y: lineTop))
                        p.addLine(to: CGPoint(x: lineX, y: lineBottom))
                    }
                    .stroke(Color.periwinkle, style: StrokeStyle(lineWidth: 5, lineCap: .round, dash: [0, 11]))
                }
                if !isLast {
                    let leftFirst = index.isMultiple(of: 2)
                    WaveMark()
                        .frame(width: 16, height: 9)
                        .offset(x: leftFirst ? 0 : 28, y: geo.size.height * 0.5)
                    WaveMark()
                        .frame(width: 14, height: 8)
                        .offset(x: leftFirst ? 28 : 0, y: geo.size.height * 0.82)
                }
                if showsGull {
                    Mascot(pose: .walking, size: .custom(52))
                        .offset(x: -2, y: dotTop - 22)
                } else {
                    MomentDot()
                        .offset(x: lineX - 11, y: dotTop)
                }
            }
        }
        .frame(width: Self.width)
        .frame(maxHeight: .infinity)
        .accessibilityHidden(true)
    }
}

/// 22pt Apricot dot with a 4pt white ring (Figma "Moment Dot").
private struct MomentDot: View {
    var body: some View {
        Circle()
            .fill(Color.apricot)
            .overlay(Circle().stroke(Color.white, lineWidth: 4))
            .frame(width: 18, height: 18)
            .padding(2)
    }
}

/// One small wave: a single sine period, Periwinkle Deep at 55%, round caps (Figma "Wave Mark").
private struct WaveMark: View {
    var body: some View {
        WaveShape()
            .stroke(Color.periwinkleDeep.opacity(0.55), style: StrokeStyle(lineWidth: 3, lineCap: .round))
    }
}

private struct WaveShape: Shape {
    func path(in rect: CGRect) -> Path {
        var p = Path()
        let midY = rect.midY
        let half = rect.width / 2
        p.move(to: CGPoint(x: rect.minX, y: midY))
        p.addCurve(to: CGPoint(x: rect.minX + half, y: midY),
                   control1: CGPoint(x: rect.minX + half * 0.3, y: rect.minY - rect.height * 0.33),
                   control2: CGPoint(x: rect.minX + half * 0.7, y: rect.minY - rect.height * 0.33))
        p.addCurve(to: CGPoint(x: rect.maxX, y: midY),
                   control1: CGPoint(x: rect.minX + half * 1.3, y: rect.maxY + rect.height * 0.33),
                   control2: CGPoint(x: rect.minX + half * 1.7, y: rect.maxY + rect.height * 0.33))
        return p
    }
}

#Preview {
    VStack(spacing: 0) {
        ForEach(0..<3) { i in
            HStack(alignment: .top, spacing: 4) {
                SeaPathRail(isFirst: i == 0, isLast: i == 2, showsGull: i == 2, index: i)
                RoundedRectangle(cornerRadius: 24).fill(Color.card).frame(height: 180).padding(.bottom, 28)
            }
            .fixedSize(horizontal: false, vertical: true)
        }
    }
    .padding(12)
    .background(Color.paper)
}
