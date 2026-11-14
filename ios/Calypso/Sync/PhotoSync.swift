import Photos
import UIKit

enum PhotoSync {
    private static let lastSyncKey = "photoSync.lastSync"

    /// Screenshots and hidden photos never leave the phone.
    static func shouldSync(mediaSubtypes: PHAssetMediaSubtype, isHidden: Bool) -> Bool {
        !mediaSubtypes.contains(.photoScreenshot) && !isHidden
    }

    static var lastSync: Date {
        get { UserDefaults.standard.object(forKey: lastSyncKey) as? Date ?? Date().addingTimeInterval(-86_400) }
        set { UserDefaults.standard.set(newValue, forKey: lastSyncKey) }
    }

    static func newAssets(since date: Date) -> [PHAsset] {
        let options = PHFetchOptions()
        options.predicate = NSPredicate(format: "creationDate > %@", date as NSDate)
        options.sortDescriptors = [NSSortDescriptor(key: "creationDate", ascending: true)]
        options.includeHiddenAssets = false
        let result = PHAsset.fetchAssets(with: .image, options: options)
        var assets: [PHAsset] = []
        result.enumerateObjects { asset, _, _ in
            if shouldSync(mediaSubtypes: asset.mediaSubtypes, isHidden: asset.isHidden) { assets.append(asset) }
        }
        return assets
    }

    static func upload(_ asset: PHAsset, using client: APIClient) async throws {
        guard let data = await jpegData(for: asset) else { return }
        let meta = PhotoMeta(
            id: asset.localIdentifier.replacingOccurrences(of: "/", with: "-"),
            takenAt: asset.creationDate ?? Date(),
            lat: asset.location?.coordinate.latitude,
            lon: asset.location?.coordinate.longitude
        )
        try await client.uploadPhoto(PhotoUpload(meta: meta, imageData: data))
    }

    /// Uploads photos taken since the last sync, advancing the marker as each one succeeds.
    static func syncNew(using client: APIClient) async {
        guard [.authorized, .limited].contains(PHPhotoLibrary.authorizationStatus(for: .readWrite)) else { return }
        for asset in newAssets(since: lastSync) {
            do {
                try await upload(asset, using: client)
                if let taken = asset.creationDate { lastSync = taken }
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
