"""S3-backed storage backend for SOP files.

Syncs SOP files between an S3 bucket and a local cache directory (/tmp).
On init, downloads all files from S3. On write, persists back to S3.
"""

from __future__ import annotations

import logging
from pathlib import Path

import boto3

from .storage_local import BUNDLED_SOPS_DIR, LocalFilesystemBackend

logger = logging.getLogger(__name__)

DEFAULT_LOCAL_CACHE = Path("/tmp/sop-storage")


class S3StorageBackend(LocalFilesystemBackend):
    """Storage backend that uses S3 for persistence with a local cache.

    On init: syncs S3 → local cache (seeding from bundled SOPs if S3 is empty).
    On write: writes locally then syncs file to S3.
    """

    def __init__(
        self,
        bucket: str,
        prefix: str = "sops/",
        local_cache: Path = DEFAULT_LOCAL_CACHE,
    ) -> None:
        self._bucket = bucket
        self._prefix = prefix.rstrip("/") + "/" if prefix else ""
        self._s3 = boto3.client("s3")

        # Init local cache without seeding yet
        super().__init__(base_dir=local_cache, is_ephemeral=False)

        # Sync: S3 → local
        s3_has_files = self._sync_from_s3()

        # If S3 was empty, seed from bundled SOPs and push to S3
        if not s3_has_files:
            logger.info("S3 bucket empty, seeding from bundled SOPs")
            self._seed(BUNDLED_SOPS_DIR)
            self._sync_to_s3()

    @classmethod
    def from_env(cls) -> S3StorageBackend:
        """Create from environment variables.

        Required: ``SOP_S3_BUCKET``
        Optional: ``SOP_S3_PREFIX`` (default: ``sops/``)
        """
        import os

        bucket = os.environ.get("SOP_S3_BUCKET", "").strip()
        if not bucket:
            raise ValueError("SOP_S3_BUCKET is required when SOP_STORAGE_TYPE=s3")
        prefix = os.environ.get("SOP_S3_PREFIX", "sops/").strip()
        return cls(bucket=bucket, prefix=prefix)

    # --- Override writes to also persist to S3 ---

    def write_sop(self, name: str, version: str, content: str) -> None:
        super().write_sop(name, version, content)
        key = f"{self._prefix}{name}/v{version}.md"
        self._put_object(key, content)

    def write_feedback(self, name: str, content: str) -> None:
        super().write_feedback(name, content)
        key = f"{self._prefix}{name}/feedback.md"
        self._put_object(key, content)

    def append_feedback(self, name: str, entry: str) -> None:
        super().append_feedback(name, entry)
        # Re-read the full file and sync
        content = self.read_feedback(name)
        if content:
            key = f"{self._prefix}{name}/feedback.md"
            self._put_object(key, content)

    # --- S3 sync helpers ---

    def _sync_from_s3(self) -> bool:
        """Download all SOP files from S3 to local cache. Returns True if files found."""
        paginator = self._s3.get_paginator("list_objects_v2")
        found = False
        for page in paginator.paginate(Bucket=self._bucket, Prefix=self._prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                rel = key[len(self._prefix) :]
                if not rel:
                    continue
                local_path = self._base_dir / rel
                local_path.parent.mkdir(parents=True, exist_ok=True)
                self._s3.download_file(self._bucket, key, str(local_path))
                found = True
                logger.debug("Downloaded s3://%s/%s → %s", self._bucket, key, local_path)
        if found:
            logger.info("Synced %s files from S3", self._bucket)
        return found

    def _sync_to_s3(self) -> None:
        """Upload all local SOP files to S3."""
        for sop_dir in self._base_dir.iterdir():
            if not sop_dir.is_dir():
                continue
            for f in sop_dir.iterdir():
                if f.is_file():
                    key = f"{self._prefix}{sop_dir.name}/{f.name}"
                    self._put_object(key, f.read_text(encoding="utf-8"))

    def _put_object(self, key: str, content: str) -> None:
        self._s3.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=content.encode("utf-8"),
            ContentType="text/markdown",
        )
        logger.debug("Uploaded s3://%s/%s", self._bucket, key)
