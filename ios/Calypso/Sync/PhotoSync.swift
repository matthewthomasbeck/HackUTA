import Photos
import UIKit

enum PhotoSync {
    private static let lastSyncKey = "photoSync.lastSync"

    /// Screenshots and hidden photos never leave the phone.
    static func shouldSync(mediaSubtypes: PHAssetMediaSubtype, isHidden: Bool) -> Bool {
        !mediaSubtypes.contains(.photoScreenshot) && !isHidden
    }

    private static let lastIdsKey = "photoSync.lastIds"
    @MainActor private static var isSyncing = false

    enum SyncError: Error { case noImageData }

    /// Photos at exactly the marker time are included, minus those already uploaded.
    static func isPending(taken: Date, id: String, lastSync: Date, uploadedAtLastSync: Set<String>) -> Bool {
        taken > lastSync || (taken == lastSync && !uploadedAtLastSync.contains(id))
    }

    static func advance(lastSync: Date, uploadedAtLastSync: Set<String>, taken: Date, id: String) -> (Date, Set<String>) {
        if taken > lastSync { return (taken, [id]) }
        if taken == lastSync { return (lastSync, uploadedAtLastSync.union([id])) }
        return (lastSync, uploadedAtLastSync)
    }

    /// Main-actor re-entry guard: returns false while another sync is running.
    @MainActor static func beginSync() -> Bool {
        guard !isSyncing else { return false }
        isSyncing = true
        return true
    }

    @MainActor static func endSync() { isSyncing = false }

    private static var lastIds: Set<String> {
        get { Set(UserDefaults.standard.stringArray(forKey: lastIdsKey) ?? []) }
        set { UserDefaults.standard.set(Array(newValue), forKey: lastIdsKey) }
    }

    static var lastSync: Date {
        get { UserDefaults.standard.object(forKey: lastSyncKey) as? Date ?? Date().addingTimeInterval(-86_400) }
        set { UserDefaults.standard.set(newValue, forKey: lastSyncKey) }
    }

    static func newAssets(since date: Date) -> [PHAsset] {
        let options = PHFetchOptions()
        options.predicate = NSPredicate(format: "creationDate >= %@", date as NSDate)
        options.sortDescriptors = [NSSortDescriptor(key: "creationDate", ascending: true)]
        options.includeHiddenAssets = false
        let result = PHAsset.fetchAssets(with: .image, options: options)
        var assets: [PHAsset] = []
        result.enumerateObjects { asset, _, _ in
            if shouldSync(mediaSubtypes: asset.mediaSubtypes, isHidden: asset.isHidden) { assets.append(asset) }
        }
        return assets
    }

    private static func photoId(_ asset: PHAsset) -> String {
        asset.localIdentifier.replacingOccurrences(of: "/", with: "-")
    }

    static func upload(_ asset: PHAsset, using client: APIClient) async throws {
        guard let data = await jpegData(for: asset) else { throw SyncError.noImageData }
        let meta = PhotoMeta(
            id: photoId(asset),
            takenAt: asset.creationDate ?? Date(),
            lat: asset.location?.coordinate.latitude,
            lon: asset.location?.coordinate.longitude
        )
        try await client.uploadPhoto(PhotoUpload(meta: meta, imageData: data))
    }

    /// Uploads photos taken since the last sync, advancing the marker as each one succeeds.
    @MainActor
    static func syncNew(using client: APIClient) async {
        guard [.authorized, .limited].contains(PHPhotoLibrary.authorizationStatus(for: .readWrite)) else { return }
        guard beginSync() else { return }
        defer { endSync() }
        for asset in newAssets(since: lastSync) {
            guard let taken = asset.creationDate,
                  isPending(taken: taken, id: photoId(asset), lastSync: lastSync, uploadedAtLastSync: lastIds) else { continue }
            do {
                try await upload(asset, using: client)
                let next = advance(lastSync: lastSync, uploadedAtLastSync: lastIds, taken: taken, id: photoId(asset))
                lastSync = next.0
                lastIds = next.1
            } catch {
                return // retry from this photo next time
            }
        }
    }

    private static func jpegData(for asset: PHAsset) async -> Data? {
        let options = PHImageRequestOptions()
        options.isNetworkAccessAllowed = true
        options.deliveryMode = .highQualityFormat
        options.isSynchronous = false
        return await withCheckedContinuation { continuation in
            PHImageManager.default().requestImage(
                for: asset, targetSize: CGSize(width: 1600, height: 1600),
                contentMode: .aspectFit, options: options
            ) { image, info in
                if info?[PHImageResultIsDegradedKey] as? Bool == true { return }
                continuation.resume(returning: image?.jpegData(compressionQuality: 0.8))
            }
        }
    }
}
