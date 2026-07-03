"""Backup and restore for brain stores and knowledge artifacts (MASTER_PLAN F.8)."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

_SECRET_PATTERNS = (".env", "secrets", "credentials", "api_key", "token")


def _is_secret_path(path: Path) -> bool:
    lowered = str(path).lower()
    return any(pattern in lowered for pattern in _SECRET_PATTERNS)


def _collect_paths(repo_root: Path) -> list[Path]:
    paths: list[Path] = []
    brain = repo_root / ".brain"
    if brain.exists():
        for item in brain.rglob("*"):
            if item.is_file() and not _is_secret_path(item):
                paths.append(item)
    knowledge = repo_root / "knowledge"
    if knowledge.exists():
        for item in knowledge.rglob("*"):
            if item.is_file():
                paths.append(item)
    return paths


def run_backup(
    *,
    repo_root: str | Path = ".",
    backup_dir: str | Path = ".brain/backups",
) -> dict:
    root = Path(repo_root).resolve()
    dest_root = Path(backup_dir)
    if not dest_root.is_absolute():
        dest_root = root / dest_root
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    bundle = dest_root / f"backup-{stamp}"
    bundle.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    skipped_secrets: list[str] = []
    for source in _collect_paths(root):
        if _is_secret_path(source):
            skipped_secrets.append(str(source.relative_to(root)))
            continue
        rel = source.relative_to(root)
        target = bundle / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied.append(str(rel))

    manifest = {
        "backup_id": bundle.name,
        "created_at": datetime.now(UTC).isoformat(),
        "files": copied,
        "skipped_secrets": skipped_secrets,
    }
    (bundle / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def restore_backup(
    *,
    backup_path: str | Path,
    target_dir: str | Path,
) -> dict:
    source = Path(backup_path).resolve()
    target = Path(target_dir).resolve()
    if not source.exists():
        raise FileNotFoundError(f"backup not found: {source}")
    target.mkdir(parents=True, exist_ok=True)

    restored: list[str] = []
    for item in source.rglob("*"):
        if item.is_file() and item.name != "manifest.json":
            rel = item.relative_to(source)
            dest = target / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dest)
            restored.append(str(rel))
    return {
        "backup_path": str(source),
        "target_dir": str(target),
        "restored_files": restored,
    }


def list_backups(backup_dir: str | Path = ".brain/backups") -> list[dict]:
    root = Path(backup_dir)
    if not root.exists():
        return []
    backups = []
    for manifest_path in sorted(root.glob("backup-*/manifest.json")):
        backups.append(json.loads(manifest_path.read_text(encoding="utf-8")))
    return backups