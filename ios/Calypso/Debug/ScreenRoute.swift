import SwiftUI

/// DEBUG-only `-screen <route>` launch argument, so any screen can be opened directly in the simulator.
enum ScreenRoute {
    static var current: String? {
        #if DEBUG
        let args = ProcessInfo.processInfo.arguments
        guard let i = args.firstIndex(of: "-screen"), i + 1 < args.count else { return nil }
        return args[i + 1]
        #else
        return nil
        #endif
    }

    /// Later tasks add a case per route here.
    static func view(for route: String) -> AnyView {
        switch route {
        case "design-system":
            return AnyView(DesignSystemSpecimen())
        #if DEBUG
        case "components":
            return AnyView(ComponentsSpecimen(page: 1))
        case "components-2":
            return AnyView(ComponentsSpecimen(page: 2))
        case "components-3":
            return AnyView(ComponentsSpecimen(page: 3))
        case "components-4":
            return AnyView(ComponentsSpecimen(page: 4))
        case "components-ax":
            return AnyView(ComponentsSpecimen(page: 5).dynamicTypeSize(.accessibility5))
        #endif
        default:
            return AnyView(Text("Unknown route").calypsoFont(.body).padding())
        }
    }
}

struct DesignSystemSpecimen: View {
    private let colors: [(String, Color)] = [
        ("paper", .paper), ("card", .card), ("ink", .ink), ("inkSoft", .inkSoft),
        ("periwinkle", .periwinkle), ("periwinkleDeep", .periwinkleDeep), ("periwinkleMist", .periwinkleMist),
        ("apricot", .apricot), ("apricotCream", .apricotCream), ("olive", .olive), ("terracotta", .terracotta),
    ]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                Text("Colors").calypsoFont(.title)
                LazyVGrid(columns: [GridItem(.adaptive(minimum: 110), spacing: 8)], spacing: 8) {
                    ForEach(colors, id: \.0) { name, color in
                        VStack(spacing: 4) {
                            RoundedRectangle(cornerRadius: 12).fill(color).frame(height: 48)
                                .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color.ink.opacity(0.2)))
                            Text(name).font(.system(size: 12)).foregroundStyle(Color.ink)
                        }
                    }
                }
                Text("Type").calypsoFont(.title)
                ForEach(CalypsoTextStyle.allCases, id: \.self) { style in
                    Text("\(String(describing: style)) \(Int(style.size))/\(Int(style.leading))")
                        .calypsoFont(style).foregroundStyle(Color.ink)
                }
                Text("Mascot").calypsoFont(.title)
                LazyVGrid(columns: [GridItem(.adaptive(minimum: 120), spacing: 12)], spacing: 12) {
                    ForEach(MascotPose.allCases, id: \.self) { pose in
                        VStack {
                            Mascot(pose: pose, size: .m, shadow: true)
                            Text(pose.rawValue).calypsoFont(.caption).foregroundStyle(Color.inkSoft)
                        }
                    }
                }
                Text("Decorations").calypsoFont(.title)
                ForEach(Decoration.allCases, id: \.self) {
                    DecorationImage($0).frame(height: 100)
                }
            }
            .padding(24)
        }
        .background(Color.paper)
    }
}
