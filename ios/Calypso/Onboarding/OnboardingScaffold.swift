import SwiftUI

/// Shared frame for every onboarding step: optional `BackButton` at the top, the step's content, and
/// `StepDots` at the bottom. Content scrolls when it doesn't fit (large Dynamic Type) and otherwise fills
/// the screen, so a `Spacer` in it pins the buttons above the dots.
///
/// `bleedsTop` steps (Welcome, Meet your companion, All set) draw a scene from the very top of the screen,
/// under the status bar, as in Figma; the back button then sits over the scene.
struct OnboardingScaffold<Content: View>: View {
    let step: OnboardingStep
    let onBack: (() -> Void)?
    let bleedsTop: Bool
    let content: Content

    init(step: OnboardingStep, onBack: (() -> Void)?, bleedsTop: Bool = false,
         @ViewBuilder content: () -> Content) {
        self.step = step
        self.onBack = onBack
        self.bleedsTop = bleedsTop
        self.content = content()
    }

    var body: some View {
        GeometryReader { proxy in
            let topInset = proxy.safeAreaInsets.top
            ScrollView {
                VStack(spacing: 12) {
                    VStack(alignment: .leading, spacing: 0) {
                        if !bleedsTop {
                            Color.clear.frame(height: topInset)
                            if let onBack {
                                BackButton(action: onBack).padding(.horizontal, 24)
                            }
                        }
                        content
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
                    .overlay(alignment: .topLeading) {
                        if bleedsTop, let onBack {
                            BackButton(action: onBack)
                                .padding(.leading, 16)
                                .padding(.top, topInset)
                        }
                    }
                    StepDots(current: step.number, total: OnboardingStep.total)
                        .padding(.horizontal, 24)
                }
                .frame(minHeight: proxy.size.height + topInset)
            }
            .scrollBounceBehavior(.basedOnSize)
            .ignoresSafeArea(edges: .top)
        }
        .background(Color.paper.ignoresSafeArea())
    }
}

/// Lays out decorative art on a fixed Figma canvas (393pt wide), scaled to the screen width.
/// `content` gets the scale factor; place children with `.onCanvas(x:y:width:scale:)`.
struct OnboardingScene<Content: View>: View {
    let designSize: CGSize
    let content: (CGFloat) -> Content

    init(width: CGFloat = 393, height: CGFloat, @ViewBuilder content: @escaping (CGFloat) -> Content) {
        self.designSize = CGSize(width: width, height: height)
        self.content = content
    }

    var body: some View {
        Color.clear
            .aspectRatio(designSize.width / designSize.height, contentMode: .fit)
            .frame(maxWidth: .infinity)
            // Keep the full scene height when the step's Spacer competes for space.
            .fixedSize(horizontal: false, vertical: true)
            .overlay(alignment: .topLeading) {
                GeometryReader { proxy in
                    ZStack(alignment: .topLeading) {
                        content(proxy.size.width / designSize.width)
                    }
                }
            }
            .clipped()
            .accessibilityHidden(true)
    }
}

extension View {
    /// Places a view at Figma canvas coordinates inside an `OnboardingScene`.
    func onCanvas(x: CGFloat, y: CGFloat, width: CGFloat, height: CGFloat? = nil, scale: CGFloat) -> some View {
        frame(width: width * scale, height: height.map { $0 * scale })
            .offset(x: x * scale, y: y * scale)
    }
}

/// Title + body block used by every step, in the 24pt content column.
struct OnboardingHeading: View {
    let title: String
    let message: String?
    var display = false

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(title)
                .calypsoFont(display ? .display : .title)
                .foregroundStyle(Color.ink)
                .accessibilityAddTraits(.isHeader)
            if let message {
                Text(message)
                    .calypsoFont(.body)
                    .foregroundStyle(Color.inkSoft)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .fixedSize(horizontal: false, vertical: true)
    }
}
