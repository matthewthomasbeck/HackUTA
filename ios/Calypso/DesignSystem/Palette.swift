import SwiftUI

extension Color {
    init(hex: UInt32) {
        self.init(.sRGB,
                  red: Double((hex >> 16) & 0xFF) / 255,
                  green: Double((hex >> 8) & 0xFF) / 255,
                  blue: Double(hex & 0xFF) / 255,
                  opacity: 1)
    }

    static let paper = Color(hex: 0xFBF6EE)
    static let card = Color(hex: 0xFFFFFF)
    static let ink = Color(hex: 0x1E2A44)
    static let inkSoft = Color(hex: 0x4A4759)
    static let periwinkle = Color(hex: 0x9AA6E8)
    static let periwinkleDeep = Color(hex: 0x3E4A9E)
    static let periwinkleMist = Color(hex: 0xC9D0F5)
    static let apricot = Color(hex: 0xF4A97A)
    static let apricotCream = Color(hex: 0xFAD3B5)
    /// Decorative only; never text.
    static let olive = Color(hex: 0xA99A4C)
    /// Decorative only; never text.
    static let terracotta = Color(hex: 0xC2603F)
}
