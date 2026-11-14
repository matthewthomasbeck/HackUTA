import Photos
import XCTest
@testable import Calypso

final class PhotoSyncTests: XCTestCase {
    func testPhotoSyncSkipsScreenshots() {
        XCTAssertFalse(PhotoSync.shouldSync(mediaSubtypes: .photoScreenshot, isHidden: false))
        XCTAssertFalse(PhotoSync.shouldSync(mediaSubtypes: [.photoScreenshot, .photoHDR], isHidden: false))
        XCTAssertTrue(PhotoSync.shouldSync(mediaSubtypes: [], isHidden: false))
        XCTAssertTrue(PhotoSync.shouldSync(mediaSubtypes: .photoHDR, isHidden: false))
    }

    func testPhotoSyncSkipsHidden() {
        XCTAssertFalse(PhotoSync.shouldSync(mediaSubtypes: [], isHidden: true))
    }
}
