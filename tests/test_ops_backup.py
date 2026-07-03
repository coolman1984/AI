"""Tests for scheduled ingestion, backup, restore, alerting (F.8)."""

from __future__ import annotations

import json

from mcp_server.server import dispatch
from ops.alerts import AlertStore
from ops.backup import restore_backup, run_backup
from ops.scheduler import run_scheduled_ingestion


def test_backup_includes_brain_stores_and_knowledge_artifacts(tmp_path):
    brain = tmp_path / ".brain"
    brain.mkdir()
    (brain / "document_registry.json").write_text('{"docs": []}', encoding="utf-8")
    knowledge = tmp_path / "knowledge" / "workflow"
    knowledge.mkdir(parents=True)
    (knowledge / "abc.md").write_text("# workflow", encoding="utf-8")

    manifest = run_backup(repo_root=tmp_path, backup_dir=tmp_path / "backups")
    assert any("document_registry.json" in path for path in manifest["files"])
    assert any("knowledge" in path for path in manifest["files"])


def test_restore_into_temp_directory_recreates_registry_artifact_files(tmp_path):
    brain = tmp_path / ".brain"
    brain.mkdir()
    registry = brain / "document_registry.json"
    registry.write_text('{"docs": [{"id": 1}]}', encoding="utf-8")
    manifest = run_backup(repo_root=tmp_path, backup_dir=tmp_path / "backups")
    backup_dir = tmp_path / "backups" / manifest["backup_id"]

    target = tmp_path / "restored"
    result = restore_backup(backup_path=backup_dir, target_dir=target)
    restored_registry = target / ".brain" / "document_registry.json"
    assert restored_registry.exists()
    assert json.loads(restored_registry.read_text(encoding="utf-8"))["docs"][0]["id"] == 1
    assert any("document_registry.json" in path for path in result["restored_files"])


def test_failed_scheduled_ingestion_creates_alert(tmp_path):
    alerts_path = str(tmp_path / "alerts.json")

    def failing_ingest():
        raise RuntimeError("ingest timeout")

    result = run_scheduled_ingestion(
        job_name="nightly-registry-sync",
        ingest_fn=failing_ingest,
        alerts_path=alerts_path,
    )
    assert result["status"] == "failed"
    alerts = AlertStore(path=alerts_path).list_alerts()
    assert len(alerts) == 1
    assert alerts[0]["alert_type"] == "scheduled_ingestion_failed"


def test_backup_does_not_include_unapproved_external_secrets(tmp_path):
    brain = tmp_path / ".brain"
    brain.mkdir()
    (brain / "document_registry.json").write_text("{}", encoding="utf-8")
    (brain / "secrets.env").write_text("API_KEY=secret", encoding="utf-8")
    (tmp_path / ".env").write_text("TOKEN=secret", encoding="utf-8")

    manifest = run_backup(repo_root=tmp_path, backup_dir=tmp_path / "backups")
    assert not any("secrets.env" in path for path in manifest["files"])
    assert not any(".env" in path for path in manifest["files"])


def test_dispatch_backup_and_alerts(tmp_path, monkeypatch):
    brain = tmp_path / ".brain"
    brain.mkdir()
    (brain / "document_registry.json").write_text("{}", encoding="utf-8")
    out = dispatch("run_backup", repo_root=str(tmp_path), backup_dir=str(tmp_path / "backups"))
    assert "files" in out
    alerts = dispatch(
        "list_ingestion_alerts",
        alerts_path=str(tmp_path / "alerts.json"),
    )
    assert isinstance(alerts, list)