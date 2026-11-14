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

    func testPendingIncludesSameTimestampUnlessAlreadyUploaded() {
        let t = Date(timeIntervalSince1970: 1_700_000_000)
        XCTAssertTrue(PhotoSync.isPending(taken: t.addingTimeInterval(1), id: "a", lastSync: t, uploadedAtLastSync: ["a"]))
        XCTAssertTrue(PhotoSync.isPending(taken: t, id: "b", lastSync: t, uploadedAtLastSync: ["a"]))
        XCTAssertFalse(PhotoSync.isPending(taken: t, id: "a", lastSync: t, uploadedAtLastSync: ["a"]))
        XCTAssertFalse(PhotoSync.isPending(taken: t.addingTimeInterval(-1), id: "c", lastSync: t, uploadedAtLastSync: []))
    }

    func testAdvanceTracksIdsAtMarker() {
        let t = Date(timeIntervalSince1970: 1_700_000_000)
        var state = PhotoSync.advance(lastSync: t, uploadedAtLastSync: ["a"], taken: t, id: "b")
        XCTAssertEqual(state.0, t)
        XCTAssertEqual(state.1, ["a", "b"])
        state = PhotoSync.advance(lastSync: state.0, uploadedAtLastSync: state.1, taken: t.addingTimeInterval(5), id: "c")
        XCTAssertEqual(state.0, t.addingTimeInterval(5))
        XCTAssertEqual(state.1, ["c"])
    }

    @MainActor
    func testSyncGuardRejectsReentry() {
        XCTAssertTrue(PhotoSync.beginSync())
        XCTAssertFalse(PhotoSync.beginSync())
        PhotoSync.endSync()
        XCTAssertTrue(PhotoSync.beginSync())
        PhotoSync.endSync()
    }
}
