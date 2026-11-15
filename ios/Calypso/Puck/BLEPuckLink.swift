import CoreBluetooth
import Foundation

/// The real puck link over CoreBluetooth. The puck is the peripheral; the phone scans for its service, subscribes to
/// `who` and `events`, and writes commands to `control`. The central manager is created lazily so the Bluetooth
/// permission prompt appears on the Connect step, not at launch.
@MainActor
final class BLEPuckLink: NSObject, PuckLink {
    static let rememberedKey = "puckPeripheralID"

    private(set) var state: PuckConnectionState = .idle {
        didSet { if state != oldValue { onStateChange?(state) } }
    }
    var onStateChange: ((PuckConnectionState) -> Void)?
    var onWho: ((WhoIsTalking) -> Void)?
    var onEvent: ((PuckEvent) -> Void)?

    private let defaults: UserDefaults
    private var central: CBCentralManager?
    private var peripheral: CBPeripheral?
    private var control: CBCharacteristic?
    private var pendingAction: (() -> Void)?
    private var wantsConnection = false
    private var timeoutTask: Task<Void, Never>?
    /// Without these a missing or silent puck would leave "Looking…" / "Connecting…" spinning forever.
    private static let scanTimeout: TimeInterval = 15
    private static let connectTimeout: TimeInterval = 15

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
    }

    func startScanning() {
        pendingAction = { [weak self] in self?.beginScan() }
        ensureCentral()
        runPendingIfPoweredOn()
    }

    func connect() {
        guard let peripheral, case .found = state else { return }
        open(peripheral, timeout: Self.connectTimeout)
    }

    var hasRemembered: Bool { rememberedID != nil }

    private var rememberedID: UUID? {
        defaults.string(forKey: Self.rememberedKey).flatMap(UUID.init(uuidString:))
    }

    func reconnectRemembered() {
        guard let id = rememberedID else { return }
        switch state {
        case .connected, .connecting, .scanning: return
        default: break
        }
        pendingAction = { [weak self] in
            guard let self, let central = self.central else { return }
            guard let known = central.retrievePeripherals(withIdentifiers: [id]).first else { return }
            self.open(known)
        }
        ensureCentral()
        runPendingIfPoweredOn()
    }

    func send(_ command: PuckCommand) {
        guard let peripheral, let control, case .connected = state,
              let data = try? JSONEncoder().encode(command) else { return }
        peripheral.writeValue(data, for: control, type: .withResponse)
    }

    func disconnect() {
        timeoutTask?.cancel()
        wantsConnection = false
        pendingAction = nil
        central?.stopScan()
        if let peripheral { central?.cancelPeripheralConnection(peripheral) }
        peripheral = nil
        control = nil
        state = .idle
    }

    private func ensureCentral() {
        if central == nil { central = CBCentralManager(delegate: self, queue: .main) }
    }

    private func runPendingIfPoweredOn() {
        guard let central, central.state == .poweredOn, let action = pendingAction else { return }
        pendingAction = nil
        action()
    }

    private func beginScan() {
        state = .scanning
        central?.scanForPeripherals(withServices: [PuckUUID.service])
        failIfStillBusy(after: Self.scanTimeout, message: "We couldn't find your puck. Make sure it is on and close by.")
    }

    /// Moves a link still `.scanning` / `.connecting` after `seconds` to `.failed`.
    private func failIfStillBusy(after seconds: TimeInterval, message: String) {
        timeoutTask?.cancel()
        timeoutTask = Task { [weak self] in
            try? await Task.sleep(nanoseconds: UInt64(seconds * 1_000_000_000))
            guard !Task.isCancelled, let self else { return }
            switch self.state {
            case .scanning, .connecting:
                self.central?.stopScan()
                self.wantsConnection = false
                if let peripheral = self.peripheral { self.central?.cancelPeripheralConnection(peripheral) }
                self.state = .failed(message)
            default: break
            }
        }
    }

    /// `timeout` is nil for reconnects, which wait until the puck is back in range.
    private func open(_ peripheral: CBPeripheral, timeout: TimeInterval? = nil) {
        central?.stopScan()
        self.peripheral = peripheral
        peripheral.delegate = self
        wantsConnection = true
        state = .connecting
        central?.connect(peripheral)
        if let timeout {
            failIfStillBusy(after: timeout, message: "Couldn't connect to the puck.")
        } else {
            timeoutTask?.cancel()
        }
    }

    /// Maps the Bluetooth radio state to a link state; nil means no change (`.poweredOn`, transient states).
    nonisolated static func linkState(for manager: CBManagerState) -> PuckConnectionState? {
        switch manager {
        case .poweredOff: return .bluetoothOff
        case .unauthorized: return .unauthorized
        case .unsupported: return .failed("Bluetooth isn't available on this device.")
        default: return nil
        }
    }

    /// Decodes one notification payload; bad payloads are dropped.
    nonisolated static func decode<T: Decodable>(_ type: T.Type, from data: Data?) -> T? {
        guard let data else { return nil }
        return try? JSONDecoder().decode(T.self, from: data)
    }
}

extension BLEPuckLink: @preconcurrency CBCentralManagerDelegate {
    func centralManagerDidUpdateState(_ central: CBCentralManager) {
        if let mapped = Self.linkState(for: central.state) {
            state = mapped
        } else if central.state == .poweredOn {
            if state == .bluetoothOff || state == .unauthorized { state = .idle }
            runPendingIfPoweredOn()
            // After a Bluetooth power cycle the old peripheral is stale: fetch it again and resume.
            if wantsConnection, state == .idle, let id = peripheral?.identifier,
               let known = central.retrievePeripherals(withIdentifiers: [id]).first {
                open(known)
            }
        }
    }

    func centralManager(_ central: CBCentralManager, didDiscover peripheral: CBPeripheral,
                        advertisementData: [String: Any], rssi RSSI: NSNumber) {
        guard case .scanning = state else { return }
        self.peripheral = peripheral
        let name = (advertisementData[CBAdvertisementDataLocalNameKey] as? String) ?? peripheral.name ?? "Calypso Puck"
        central.stopScan()
        state = .found(name: name)
    }

    func centralManager(_ central: CBCentralManager, didConnect peripheral: CBPeripheral) {
        peripheral.discoverServices([PuckUUID.service])
    }

    func centralManager(_ central: CBCentralManager, didFailToConnect peripheral: CBPeripheral, error: Error?) {
        state = .failed("Couldn't connect to the puck.")
    }

    func centralManager(_ central: CBCentralManager, didDisconnectPeripheral peripheral: CBPeripheral, error: Error?) {
        control = nil
        state = .idle
        // Pending connects don't time out, so this resumes whenever the puck comes back in range.
        if wantsConnection { open(peripheral) }
    }
}

extension BLEPuckLink: @preconcurrency CBPeripheralDelegate {
    func peripheral(_ peripheral: CBPeripheral, didDiscoverServices error: Error?) {
        guard error == nil, let service = peripheral.services?.first(where: { $0.uuid == PuckUUID.service }) else {
            state = .failed("This puck is missing a feature. Update its software.")
            return
        }
        peripheral.discoverCharacteristics([PuckUUID.who, PuckUUID.control, PuckUUID.events], for: service)
    }

    func peripheral(_ peripheral: CBPeripheral, didDiscoverCharacteristicsFor service: CBService, error: Error?) {
        guard let characteristics = service.characteristics else { return }
        for c in characteristics {
            if c.uuid == PuckUUID.control { control = c }
            if c.uuid == PuckUUID.who || c.uuid == PuckUUID.events { peripheral.setNotifyValue(true, for: c) }
        }
        guard control != nil else {
            state = .failed("This puck is missing a feature. Update its software.")
            return
        }
        timeoutTask?.cancel()
        defaults.set(peripheral.identifier.uuidString, forKey: Self.rememberedKey)
        let name = peripheral.name ?? "Calypso Puck"
        state = .connected(name: name)
    }

    func peripheral(_ peripheral: CBPeripheral, didUpdateValueFor characteristic: CBCharacteristic, error: Error?) {
        if characteristic.uuid == PuckUUID.who {
            if let who = Self.decode(WhoIsTalking.self, from: characteristic.value) { onWho?(who) }
        } else if characteristic.uuid == PuckUUID.events {
            if let event = Self.decode(PuckEvent.self, from: characteristic.value) { onEvent?(event) }
        }
    }
}
