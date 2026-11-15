import XCTest
import SwiftUI
@testable import Calypso

final class DesignSystemTests: XCTestCase {
    func testTextStyleSpecs() {
        let expected: [(CalypsoTextStyle, CGFloat, CGFloat)] = [
            (.display, 44, 52), (.title, 34, 42), (.headline, 28, 36), (.body, 24, 32),
            (.bodyStrong, 24, 32), (.callout, 22, 30), (.caption, 20, 26),
        ]
        for (style, size, leading) in expected {
            XCTAssertEqual(style.size, size, "\(style) size")
            XCTAssertEqual(style.leading, leading, "\(style) leading")
        }
        XCTAssertEqual(CalypsoTextStyle.allCases.count, expected.count)
        XCTAssertTrue(CalypsoTextStyle.allCases.allSatisfy { $0.size >= 20 })
    }

    func testFontsRegistered() {
        for name in ["Fraunces-SemiBold", "Nunito-Regular", "Nunito-SemiBold", "Nunito-Bold"] {
            XCTAssertNotNil(UIFont(name: name, size: 20), name)
        }
    }

    func testMascotAssetsExist() {
        let bundle = Bundle(for: DesignSystemTests.appClass)
        for pose in MascotPose.allCases {
            XCTAssertNotNil(UIImage(named: pose.assetName, in: bundle, with: nil), pose.assetName)
        }
        let others = ["Logo"] + ["OliveBranch", "MeanderBorder", "IslandHome", "Lighthouse",
                                  "WavesCalm", "WavesLively", "Seascape"]
        for name in others {
            XCTAssertNotNil(UIImage(named: name, in: bundle, with: nil), name)
        }
        XCTAssertEqual(MascotPose.holdingPhoto.assetName, "GullHoldingPhoto")
        XCTAssertEqual(MascotPose.wave.assetName, "GullWave")
    }

    func testDecorationRawValuesHaveAssets() {
        let bundle = Bundle(for: DesignSystemTests.appClass)
        let all = Decoration.allCases
        for d in all { XCTAssertNotNil(UIImage(named: d.rawValue, in: bundle, with: nil), d.rawValue) }
    }

    func testMascotSizes() {
        XCTAssertEqual(MascotSize.xl.width, 280)
        XCTAssertEqual(MascotSize.l.width, 200)
        XCTAssertEqual(MascotSize.m.width, 120)
        XCTAssertEqual(MascotSize.s.width, 72)
        XCTAssertEqual(MascotSize.custom(96).width, 96)
    }

    private static var appClass: AnyClass { AppDelegate.self }

    func testWordSafeTextShrinksOnlyWhenTheLongestWordDoesNotFit() {
        let font = CalypsoTextStyle.bodyStrong.scaledUIFont(for: .accessibility5)
        let word = ("Yesterday" as NSString).size(withAttributes: [.font: font]).width
        XCTAssertEqual(WordSafeText.scale(text: "‹\u{00A0}Yesterday", font: font, availableWidth: 10_000), 1)
        XCTAssertEqual(WordSafeText.scale(text: "Saturday, November 14", font: font, availableWidth: 0), 1)
        let scale = WordSafeText.scale(text: "Friday, Yesterday", font: font, availableWidth: word / 2)
        XCTAssertLessThan(scale, 0.5)
        XCTAssertLessThanOrEqual(word * scale, word / 2)
    }

    func testScaledUIFontGrowsWithDynamicType() {
        XCTAssertGreaterThan(CalypsoTextStyle.caption.scaledUIFont(for: .accessibility5).pointSize,
                             CalypsoTextStyle.caption.scaledUIFont(for: .large).pointSize)
    }
}
