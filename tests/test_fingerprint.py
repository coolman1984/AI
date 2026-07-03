"""Tests for the fingerprint + register tool (Step 1.1)."""

import hashlib
import os
import tempfile

import pytest

from tools.fingerprint import fingerprint_file, register_file
from tools.foreman_db import init_db


def test_fingerprint_returns_expected_keys():
    """fingerprint_file should return sha256, size_bytes, original_path."""
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
        f.write("hello world")
        path = f.name
    try:
        result = fingerprint_file(path)
        assert "sha256" in result
        assert "size_bytes" in result
        assert "original_path" in result
        assert result["size_bytes"] == 11  # "hello world" is 11 bytes
        assert result["sha256"] == hashlib.sha256(b"hello world").hexdigest()
    finally:
        os.unlink(path)


def test_fingerprint_missing_file_raises():
    """fingerprint_file should raise FileNotFoundError for missing files."""
    with pytest.raises(FileNotFoundError):
        fingerprint_file("/nonexistent/path/file.txt")


def test_fingerprint_directory_raises():
    """fingerprint_file should raise ValueError for a directory."""
    with tempfile.TemporaryDirectory() as tmp:
        with pytest.raises(ValueError):
            fingerprint_file(tmp)


def test_register_file_creates_copy():
    """register_file should copy the file to datasets/registered/."""
    with tempfile.TemporaryDirectory() as reg_dir:
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
            f.write("test data for registration")
            src = f.name

        try:
            result = register_file(src, registered_dir=reg_dir)
            assert "registered_path" in result
            registered = result["registered_path"]
            assert os.path.isfile(registered), f"Registered file not found: {registered}"
            # Content should match
            with open(registered) as f:
                assert f.read() == "test data for registration"
            # Original should still exist
            assert os.path.isfile(src)
        finally:
            if os.path.isfile(src):
                os.unlink(src)


def test_register_same_bytes_dedup():
    """Registering the same file twice should produce one fingerprint row."""
    with tempfile.TemporaryDirectory() as reg_dir:
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
            f.write("dedup test content")
            src = f.name

        try:
            db_path = os.path.join(reg_dir, "test.db")
            db = init_db(db_path)

            try:
                # Register first time and second time
                r1 = register_file(src, db_conn=db, registered_dir=reg_dir)
                r2 = register_file(src, db_conn=db, registered_dir=reg_dir)

                # Query count while db is open
                count_row = db.execute(
                    "SELECT COUNT(*) as cnt FROM file_fingerprints WHERE sha256 = ?",
                    (r1["sha256"],),
                ).fetchone()
                row_count = count_row["cnt"]
            finally:
                db.close()

            # Assert on captured data (db no longer needed)
            assert r1["fingerprint_id"] == r2["fingerprint_id"]
            assert r1["registered_path"] == r2["registered_path"]
            assert row_count == 1
        finally:
            if os.path.isfile(src):
                os.unlink(src)


def test_original_untouched_after_register():
    """The original file must be byte-identical after registration."""
    with tempfile.TemporaryDirectory() as reg_dir:
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
            f.write("original content -- do not touch")
            src = f.name

        try:
            before = open(src, "rb").read()
            register_file(src, registered_dir=reg_dir)
            after = open(src, "rb").read()
            assert before == after, "Original file was modified!"
        finally:
            if os.path.isfile(src):
                os.unlink(src)
