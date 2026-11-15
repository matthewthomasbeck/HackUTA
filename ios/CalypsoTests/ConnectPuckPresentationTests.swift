import XCTest
@testable import Calypso

final class ConnectPuckPresentationTests: XCTestCase {
    func testIdle() {
        let p = ConnectPuckPresentation.make(state: .idle)
        XCTAssertEqual(p.title, "Calypso Puck")
        XCTAssertEqual(p.message, "Ready to look")
        XCTAssertEqual(p.primaryTitle, "Find my puck")
        XCTAssertFalse(p.showsSpinner)
    }

    func testScanning() {
        let p = ConnectPuckPresentation.make(state: .scanning)
        XCTAssertEqual(p.message, "Looking for your puck…")
        XCTAssertNil(p.primaryTitle)
        XCTAssertTrue(p.showsSpinner)
    }

    func testFound() {
        let p = ConnectPuckPresentation.make(state: .found(name: "Calypso Puck"))
        XCTAssertEqual(p.title, "Calypso Puck")
        XCTAssertEqual(p.message, "Found nearby")
        XCTAssertEqual(p.primaryTitle, "Connect")
        XCTAssertFalse(p.showsSpinner)
    }

    func testFoundUsesTheAdvertisedName() {
        XCTAssertEqual(ConnectPuckPresentation.make(state: .found(name: "Calypso 7F")).title, "Calypso 7F")
    }

    func testConnecting() {
        let p = ConnectPuckPresentation.make(state: .connecting)
        XCTAssertEqual(p.message, "Connecting…")
        XCTAssertNil(p.primaryTitle)
        XCTAssertTrue(p.showsSpinner)
    }

    func testConnected() {
        let p = ConnectPuckPresentation.make(state: .connected(name: "Calypso Puck"))
        XCTAssertEqual(p.title, "Calypso Puck")
        XCTAssertEqual(p.message, "Ready. It will listen for you.")
        XCTAssertEqual(p.primaryTitle, "Continue")
        XCTAssertFalse(p.showsSpinner)
    }

    func testBluetoothOff() {
        let p = ConnectPuckPresentation.make(state: .bluetoothOff)
        XCTAssertEqual(p.title, "Bluetooth is off")
        XCTAssertEqual(p.message, "Turn on Bluetooth in Control Center.")
        XCTAssertEqual(p.primaryTitle, "Try again")
        XCTAssertFalse(p.showsSpinner)
    }

    func testUnauthorized() {
        let p = ConnectPuckPresentation.make(state: .unauthorized)
        XCTAssertEqual(p.title, "Bluetooth isn't allowed")
        XCTAssertEqual(p.message, "Allow Bluetooth for Calypso⁻¹ in Settings.")
        XCTAssertEqual(p.primaryTitle, "Open Settings")
    }

    func testFailedShowsReason() {
        let p = ConnectPuckPresentation.make(state: .failed("Timed out"))
        XCTAssertEqual(p.title, "We couldn't connect")
        XCTAssertEqual(p.message, "Timed out")
        XCTAssertEqual(p.primaryTitle, "Try again")
    }
}
