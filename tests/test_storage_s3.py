"""Tests for S3StorageBackend.

Two modes:
1. Real S3: runs against a real bucket if SOP_TEST_S3_BUCKET is set (skipped otherwise)
2. Mocked S3: uses moto to mock S3 for all unit tests
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# Skip all tests in this module if boto3 is not available
boto3 = pytest.importorskip("boto3", reason="boto3 not installed (install with: pip install sop-mcp[s3])")
moto = pytest.importorskip("moto", reason="moto not installed")

from moto import mock_aws

from src.utils.storage_s3 import S3StorageBackend

# --- Fixtures ---

SAMPLE_SOP = """# Sample SOP

## Document Information
- **Document ID**: test_sop
- **Version**: 1.0.0

## Overview
A test SOP for storage backend testing.

### Step 1: Do something
Do the thing.
"""

SAMPLE_SOP_V2 = """# Sample SOP

## Document Information
- **Document ID**: test_sop
- **Version**: 2.0.0

## Overview
Updated test SOP.

### Step 1: Do something better
Do the better thing.
"""


@pytest.fixture
def mock_s3_backend(tmp_path: Path):
    """Create an S3StorageBackend backed by moto mock."""
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-sop-bucket")
        yield S3StorageBackend(
            bucket="test-sop-bucket",
            prefix="sops/",
            local_cache=tmp_path / "cache",
        )


@pytest.fixture
def seeded_s3_backend(mock_s3_backend: S3StorageBackend):
    """Backend that already has a sample SOP written."""
    mock_s3_backend.write_sop("test_sop", "1.0.0", SAMPLE_SOP)
    return mock_s3_backend


# --- Mocked S3 Tests ---


class TestS3Init:
    def test_empty_bucket_seeds_from_bundled(self, tmp_path: Path):
        """Empty S3 bucket should be seeded with bundled SOPs."""
        with mock_aws():
            s3 = boto3.client("s3", region_name="us-east-1")
            s3.create_bucket(Bucket="seed-test-bucket")
            backend = S3StorageBackend(
                bucket="seed-test-bucket",
                prefix="sops/",
                local_cache=tmp_path / "cache",
            )
            sops = backend.list_sops()
            assert len(sops) > 0, "Should have seeded bundled SOPs"

            # Verify files are in S3 too
            resp = s3.list_objects_v2(Bucket="seed-test-bucket", Prefix="sops/")
            assert resp.get("KeyCount", 0) > 0, "S3 should have seeded files"

    def test_existing_s3_files_loaded(self, tmp_path: Path):
        """Files already in S3 should be downloaded to local cache."""
        with mock_aws():
            s3 = boto3.client("s3", region_name="us-east-1")
            s3.create_bucket(Bucket="preloaded-bucket")
            s3.put_object(
                Bucket="preloaded-bucket",
                Key="sops/my_sop/v1.0.0.md",
                Body=SAMPLE_SOP.encode(),
            )
            backend = S3StorageBackend(
                bucket="preloaded-bucket",
                prefix="sops/",
                local_cache=tmp_path / "cache",
            )
            assert "my_sop" in backend.list_sops()
            assert backend.read_sop("my_sop") == SAMPLE_SOP

    def test_not_ephemeral(self, mock_s3_backend: S3StorageBackend):
        assert not mock_s3_backend.is_ephemeral


class TestS3WriteSop:
    def test_write_persists_to_s3(self, tmp_path: Path):
        with mock_aws():
            s3 = boto3.client("s3", region_name="us-east-1")
            s3.create_bucket(Bucket="write-test")
            backend = S3StorageBackend(bucket="write-test", prefix="sops/", local_cache=tmp_path / "cache")
            backend.write_sop("new_sop", "1.0.0", SAMPLE_SOP)

            # Verify local
            assert backend.read_sop("new_sop") == SAMPLE_SOP

            # Verify S3
            obj = s3.get_object(Bucket="write-test", Key="sops/new_sop/v1.0.0.md")
            assert obj["Body"].read().decode() == SAMPLE_SOP

    def test_write_multiple_versions(self, seeded_s3_backend: S3StorageBackend):
        seeded_s3_backend.write_sop("test_sop", "2.0.0", SAMPLE_SOP_V2)
        versions = seeded_s3_backend.list_versions("test_sop")
        assert "1.0.0" in versions
        assert "2.0.0" in versions
        # Latest should be v2
        assert "Updated test SOP" in seeded_s3_backend.read_sop("test_sop")


class TestS3ReadSop:
    def test_read_latest(self, seeded_s3_backend: S3StorageBackend):
        content = seeded_s3_backend.read_sop("test_sop")
        assert "A test SOP" in content

    def test_read_specific_version(self, seeded_s3_backend: S3StorageBackend):
        content = seeded_s3_backend.read_sop("test_sop", version="1.0.0")
        assert "A test SOP" in content

    def test_read_missing_raises(self, mock_s3_backend: S3StorageBackend):
        with pytest.raises(FileNotFoundError):
            mock_s3_backend.read_sop("nonexistent")


class TestS3Feedback:
    def test_append_feedback_creates_file(self, seeded_s3_backend: S3StorageBackend):
        seeded_s3_backend.append_feedback("test_sop", "## Entry 1\nGreat SOP!\n\n")
        feedback = seeded_s3_backend.read_feedback("test_sop")
        assert feedback is not None
        assert "Great SOP!" in feedback

    def test_append_multiple_feedback(self, tmp_path: Path):
        with mock_aws():
            s3 = boto3.client("s3", region_name="us-east-1")
            s3.create_bucket(Bucket="feedback-test")
            backend = S3StorageBackend(bucket="feedback-test", prefix="sops/", local_cache=tmp_path / "cache")
            backend.write_sop("fb_sop", "1.0.0", SAMPLE_SOP)

            backend.append_feedback("fb_sop", "## Entry 1\nFirst feedback\n\n")
            backend.append_feedback("fb_sop", "## Entry 2\nSecond feedback\n\n")

            feedback = backend.read_feedback("fb_sop")
            assert "First feedback" in feedback
            assert "Second feedback" in feedback

            # Verify S3 has the combined feedback
            obj = s3.get_object(Bucket="feedback-test", Key="sops/fb_sop/feedback.md")
            s3_content = obj["Body"].read().decode()
            assert "First feedback" in s3_content
            assert "Second feedback" in s3_content

    def test_write_feedback_overwrites(self, seeded_s3_backend: S3StorageBackend):
        seeded_s3_backend.write_feedback("test_sop", "# Fresh feedback\n")
        feedback = seeded_s3_backend.read_feedback("test_sop")
        assert feedback == "# Fresh feedback\n"

    def test_read_feedback_none_when_missing(self, seeded_s3_backend: S3StorageBackend):
        assert seeded_s3_backend.read_feedback("test_sop") is None


class TestS3ColdStartSync:
    """Verify that a new Lambda instance picks up S3 state."""

    def test_second_instance_sees_writes(self, tmp_path: Path):
        with mock_aws():
            s3 = boto3.client("s3", region_name="us-east-1")
            s3.create_bucket(Bucket="sync-test")

            # First instance writes
            b1 = S3StorageBackend(bucket="sync-test", prefix="sops/", local_cache=tmp_path / "cache1")
            b1.write_sop("shared_sop", "1.0.0", SAMPLE_SOP)

            # Second instance (different local cache) should see it
            b2 = S3StorageBackend(bucket="sync-test", prefix="sops/", local_cache=tmp_path / "cache2")
            assert "shared_sop" in b2.list_sops()
            assert b2.read_sop("shared_sop") == SAMPLE_SOP


class TestS3FromEnv:
    def test_from_env_missing_bucket_raises(self):
        with mock_aws():
            with pytest.MonkeyPatch.context() as mp:
                mp.delenv("SOP_S3_BUCKET", raising=False)
                mp.setenv("SOP_STORAGE_TYPE", "s3")
                with pytest.raises(ValueError, match="SOP_S3_BUCKET"):
                    S3StorageBackend.from_env()

    def test_from_env_with_bucket(self, tmp_path: Path):
        with mock_aws():
            s3 = boto3.client("s3", region_name="us-east-1")
            s3.create_bucket(Bucket="env-test-bucket")
            with pytest.MonkeyPatch.context() as mp:
                mp.setenv("SOP_S3_BUCKET", "env-test-bucket")
                mp.setenv("SOP_S3_PREFIX", "custom/")
                backend = S3StorageBackend.from_env()
                assert isinstance(backend, S3StorageBackend)


# --- Real S3 Tests (skipped unless SOP_TEST_S3_BUCKET is set) ---

REAL_BUCKET = os.environ.get("SOP_TEST_S3_BUCKET", "")
REAL_PREFIX = "test-sops/"

real_s3 = pytest.mark.skipif(not REAL_BUCKET, reason="SOP_TEST_S3_BUCKET not set")


@real_s3
class TestRealS3:
    """Integration tests against a real S3 bucket.

    Set SOP_TEST_S3_BUCKET=your-bucket to run these.
    Uses a 'test-sops/' prefix to avoid polluting production data.
    """

    def _cleanup(self, s3, bucket: str, prefix: str):
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                s3.delete_object(Bucket=bucket, Key=obj["Key"])

    @pytest.fixture(autouse=True)
    def clean_prefix(self):
        """Clean up test prefix before and after each test."""
        s3 = boto3.client("s3")
        self._cleanup(s3, REAL_BUCKET, REAL_PREFIX)
        yield
        self._cleanup(s3, REAL_BUCKET, REAL_PREFIX)

    def test_write_and_read(self, tmp_path: Path):
        backend = S3StorageBackend(bucket=REAL_BUCKET, prefix=REAL_PREFIX, local_cache=tmp_path / "cache")
        backend.write_sop("real_test", "1.0.0", SAMPLE_SOP)
        assert backend.read_sop("real_test") == SAMPLE_SOP

    def test_cold_start_sync(self, tmp_path: Path):
        b1 = S3StorageBackend(bucket=REAL_BUCKET, prefix=REAL_PREFIX, local_cache=tmp_path / "c1")
        b1.write_sop("sync_test", "1.0.0", SAMPLE_SOP)

        b2 = S3StorageBackend(bucket=REAL_BUCKET, prefix=REAL_PREFIX, local_cache=tmp_path / "c2")
        assert "sync_test" in b2.list_sops()

    def test_feedback_persists(self, tmp_path: Path):
        backend = S3StorageBackend(bucket=REAL_BUCKET, prefix=REAL_PREFIX, local_cache=tmp_path / "cache")
        backend.write_sop("fb_test", "1.0.0", SAMPLE_SOP)
        backend.append_feedback("fb_test", "## Feedback\nLooks good\n\n")

        # New instance should see feedback
        b2 = S3StorageBackend(bucket=REAL_BUCKET, prefix=REAL_PREFIX, local_cache=tmp_path / "c2")
        feedback = b2.read_feedback("fb_test")
        assert feedback is not None
        assert "Looks good" in feedback


class TestS3ListVersions:
    def test_list_versions_sorted(self, tmp_path: Path):
        with mock_aws():
            s3 = boto3.client("s3", region_name="us-east-1")
            s3.create_bucket(Bucket="version-test")
            backend = S3StorageBackend(bucket="version-test", prefix="sops/", local_cache=tmp_path / "cache")
            backend.write_sop("my_sop", "1.0.0", SAMPLE_SOP)
            backend.write_sop("my_sop", "2.0.0", SAMPLE_SOP_V2)
            backend.write_sop("my_sop", "1.1.0", SAMPLE_SOP)

            versions = backend.list_versions("my_sop")
            assert versions == ["1.0.0", "1.1.0", "2.0.0"]

    def test_list_versions_empty_sop(self, mock_s3_backend: S3StorageBackend):
        assert mock_s3_backend.list_versions("nonexistent") == []


class TestS3SopExists:
    def test_exists_after_write(self, seeded_s3_backend: S3StorageBackend):
        assert seeded_s3_backend.sop_exists("test_sop")
        assert seeded_s3_backend.sop_exists("test_sop", version="1.0.0")

    def test_not_exists(self, mock_s3_backend: S3StorageBackend):
        assert not mock_s3_backend.sop_exists("ghost")

    def test_wrong_version_not_exists(self, seeded_s3_backend: S3StorageBackend):
        assert not seeded_s3_backend.sop_exists("test_sop", version="9.9.9")


class TestS3ReadAfterColdStart:
    """Verify specific version reads survive a cold start (new instance)."""

    def test_read_specific_version_after_sync(self, tmp_path: Path):
        with mock_aws():
            s3 = boto3.client("s3", region_name="us-east-1")
            s3.create_bucket(Bucket="version-sync")
            b1 = S3StorageBackend(bucket="version-sync", prefix="sops/", local_cache=tmp_path / "c1")
            b1.write_sop("versioned", "1.0.0", SAMPLE_SOP)
            b1.write_sop("versioned", "2.0.0", SAMPLE_SOP_V2)

            # New instance
            b2 = S3StorageBackend(bucket="version-sync", prefix="sops/", local_cache=tmp_path / "c2")
            assert "A test SOP" in b2.read_sop("versioned", version="1.0.0")
            assert "Updated test SOP" in b2.read_sop("versioned", version="2.0.0")
            # Latest should be v2
            assert "Updated test SOP" in b2.read_sop("versioned")


class TestS3PrefixIsolation:
    """Two backends with different prefixes should not see each other's data."""

    def test_different_prefixes_isolated(self, tmp_path: Path):
        with mock_aws():
            s3 = boto3.client("s3", region_name="us-east-1")
            s3.create_bucket(Bucket="shared-bucket")

            b1 = S3StorageBackend(bucket="shared-bucket", prefix="team-a/", local_cache=tmp_path / "a")
            b2 = S3StorageBackend(bucket="shared-bucket", prefix="team-b/", local_cache=tmp_path / "b")

            b1.write_sop("alpha_sop", "1.0.0", SAMPLE_SOP)
            b2.write_sop("beta_sop", "1.0.0", SAMPLE_SOP_V2)

            assert "alpha_sop" in b1.list_sops()
            assert "beta_sop" not in b1.list_sops()

            assert "beta_sop" in b2.list_sops()
            assert "alpha_sop" not in b2.list_sops()
