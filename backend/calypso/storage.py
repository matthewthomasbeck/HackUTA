"""File storage for face crops and photos (audio is never stored long-term).

`CALYPSO_STORAGE=local` writes under `data/files/` (tests, laptops).
`CALYPSO_STORAGE=s3` uses the Vultr Object Storage enrollment bucket via boto3;
credentials come from the standard AWS env vars or `AWS_PROFILE`.
"""
from pathlib import Path
from typing import Protocol

from .config import Settings


class Storage(Protocol):
    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None: ...
    def get(self, key: str) -> bytes | None: ...
    def delete(self, key: str) -> None: ...


class LocalStorage:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root not in path.parents:
            raise ValueError(f"bad storage key {key!r}")
        return path

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, key: str) -> bytes | None:
        path = self._path(key)
        return path.read_bytes() if path.is_file() else None

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


class S3Storage:
    def __init__(self, endpoint: str, bucket: str) -> None:
        import boto3
        from botocore.config import Config

        self.bucket = bucket
        self.client = boto3.Session().client(
            "s3", endpoint_url=endpoint, config=Config(signature_version="s3v4")
        )

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)

    def get(self, key: str) -> bytes | None:
        try:
            return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except self.client.exceptions.NoSuchKey:
            return None

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)


def get_storage(settings: Settings) -> Storage:
    if settings.storage == "s3":
        return S3Storage(settings.s3_endpoint, settings.enrollment_bucket)
    return LocalStorage(Path(settings.data_dir) / "files")
