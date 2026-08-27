"""Object Storage abstraction.

Dataset Service must NOT depend on raw local file paths. It talks to an
ObjectStorage implementation only.

- LocalObjectStorage  -> default (local dev / tests)
- S3ObjectStorage     -> production target (AWS S3 / Aliyun OSS / Tencent COS / MinIO)
                          requires boto3 + DG_OBJECT_STORAGE_BACKEND=s3

Factory get_object_storage() returns the configured backend (singleton).
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO

from loguru import logger

from app.config import settings


class ObjectStorage(ABC):
    @abstractmethod
    def save(self, key: str, data: bytes) -> str:
        """Store bytes under key; returns the canonical key."""

    @abstractmethod
    def load(self, key: str) -> bytes:
        """Read bytes for key."""

    @abstractmethod
    def open(self, key: str) -> BinaryIO:
        """Open a readable binary stream for key."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        ...

    @abstractmethod
    def delete(self, key: str) -> None:
        ...


class LocalObjectStorage(ObjectStorage):
    """Simple filesystem-backed storage for local dev / tests."""

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        # normalize separators and prevent path traversal
        parts = [p for p in key.replace("\\", "/").split("/") if p and p not in (".", "..")]
        path = self._root.joinpath(*parts).resolve()
        if self._root not in path.parents and path != self._root:
            raise ValueError(f"invalid storage key: {key!r}")
        return path

    def save(self, key: str, data: bytes) -> str:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def load(self, key: str) -> bytes:
        return self._resolve(key).read_bytes()

    def open(self, key: str) -> BinaryIO:
        return self._resolve(key).open("rb")

    def exists(self, key: str) -> bool:
        return self._resolve(key).exists()

    def delete(self, key: str) -> None:
        self._resolve(key).unlink(missing_ok=True)


class S3ObjectStorage(ObjectStorage):
    """S3-compatible storage (production). Requires boto3."""

    def __init__(self) -> None:
        try:
            import boto3  # noqa: WPS433
        except ImportError as exc:  # pragma: no cover - env dependent
            raise RuntimeError(
                "DG_OBJECT_STORAGE_BACKEND=s3 requires `boto3` installed "
                "(pip install boto3)."
            ) from exc
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url or None,
            region_name=settings.s3_region or None,
            aws_access_key_id=settings.s3_access_key or None,
            aws_secret_access_key=settings.s3_secret_key or None,
        )
        self._bucket = settings.s3_bucket

    def save(self, key: str, data: bytes) -> str:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data)
        return key

    def load(self, key: str) -> bytes:
        resp = self._client.get_object(Bucket=self._bucket, Key=key)
        return resp["Body"].read()

    def open(self, key: str) -> BinaryIO:
        resp = self._client.get_object(Bucket=self._bucket, Key=key)
        return resp["Body"]

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except Exception:
            return False

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)


_storage: ObjectStorage | None = None


def get_object_storage() -> ObjectStorage:
    global _storage
    if _storage is None:
        if settings.object_storage_backend == "s3":
            _storage = S3ObjectStorage()
            logger.info("Object storage: S3-compatible ({})", settings.s3_bucket)
        else:
            _storage = LocalObjectStorage(settings.dataset_storage_dir)
            logger.info("Object storage: local ({})", settings.dataset_storage_dir)
    return _storage
