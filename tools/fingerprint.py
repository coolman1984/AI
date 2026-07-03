"""Fingerprint and register files for immutable audit trail.

fingerprint_file(path)  → sha256, size_bytes, original_path
register_file(path, db) → copies to datasets/registered/, writes file_fingerprints row
"""

import hashlib
import shutil
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_REGISTERED_DIR = _PROJECT_ROOT / "datasets" / "registered"


def fingerprint_file(path: str | Path) -> dict:
    """Compute SHA-256 hash and file metadata without modifying the original.

    Returns dict with keys: sha256, size_bytes, original_path.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if not path.is_file():
        raise ValueError(f"Not a regular file: {path}")

    size_bytes = path.stat().st_size
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)

    return {
        "sha256": sha256.hexdigest(),
        "size_bytes": size_bytes,
        "original_path": str(path.resolve()),
    }


def _copy_to_registered(
    original_path: Path,
    sha256: str,
    registered_dir: str | Path = None,
) -> str:
    """Copy file to datasets/registered/<sha8>_<original_name>, return the new path."""
    if registered_dir is None:
        registered_dir = _DEFAULT_REGISTERED_DIR
    registered_dir = Path(registered_dir)
    registered_dir.mkdir(parents=True, exist_ok=True)

    sha8 = sha256[:8]
    name = f"{sha8}_{original_path.name}"
    dest = registered_dir / name

    # Only copy if not already there (dedup by path)
    if not dest.exists():
        shutil.copy2(str(original_path), str(dest))

    return str(dest)


def register_file(
    path: str | Path,
    db_conn=None,
    registered_dir: str | Path = None,
) -> dict:
    """Register a file: fingerprint it, copy to registered/, write DB row.

    Returns dict with fingerprint results + registered_path.
    If the same bytes are already registered (sha256 match), returns
    the existing registration without duplicating the file.

    Requires an optional db_conn (sqlite3.Connection) to persist the
    registration. If None, returns the fingerprint data without DB write.
    """
    path = Path(path)
    fp = fingerprint_file(path)
    dest = _copy_to_registered(path, fp["sha256"], registered_dir)

    fp["registered_path"] = dest

    # Check for existing fingerprint in DB
    if db_conn is not None:
        row = db_conn.execute(
            "SELECT fingerprint_id, registered_path FROM file_fingerprints WHERE sha256 = ?",
            (fp["sha256"],),
        ).fetchone()
        if row is None:
            db_conn.execute(
                "INSERT INTO file_fingerprints (sha256, original_path, registered_path, size_bytes) "
                "VALUES (?, ?, ?, ?)",
                (fp["sha256"], fp["original_path"], dest, fp["size_bytes"]),
            )
            db_conn.commit()
            row = db_conn.execute(
                "SELECT fingerprint_id, registered_path FROM file_fingerprints WHERE sha256 = ?",
                (fp["sha256"],),
            ).fetchone()
        fp["fingerprint_id"] = row["fingerprint_id"]

        # If the registered path differs (dedup), use the existing one
        existing_path = row["registered_path"]
        if existing_path != dest and Path(existing_path).exists():
            fp["registered_path"] = existing_path

    return fp
