"""Tests for session-state persistence (F.9)."""

from __future__ import annotations

import pytest

from mcp_server.server import dispatch
from ops.session_state import update_restart_notes, write_session_state


def test_session_summary_records_phase_next_action_blockers_evidence_pointers(tmp_path):
    out = write_session_state(
        current_phase="Phase F",
        next_action="Run pytest for F cards",
        blockers=["waiting on owner export"],
        evidence_pointers=["eval/golden_manifest.json"],
        output_path=tmp_path / "session_state.md",
    )
    assert out["current_phase"] == "Phase F"
    assert out["next_action"] == "Run pytest for F cards"
    assert out["blockers"] == ["waiting on owner export"]
    assert out["evidence_pointers"] == ["eval/golden_manifest.json"]
    content = (tmp_path / "session_state.md").read_text(encoding="utf-8")
    assert "Phase F" in content
    assert "eval/golden_manifest.json" in content


def test_restart_notes_updated_from_session_state_without_deleting_manual_notes(tmp_path):
    restart_path = tmp_path / "restart_notes.md"
    restart_path.write_text(
        "1. Manual note that must stay.\n2. Another manual item.\n",
        encoding="utf-8",
    )
    summary = write_session_state(
        current_phase="Phase F",
        next_action="pytest",
        output_path=tmp_path / "session_state.md",
    )
    updated = update_restart_notes(summary, restart_notes_path=restart_path)
    assert "Manual note that must stay" in updated
    assert "Auto session" in updated
    assert "phase=Phase F" in updated


def test_sensitive_raw_data_is_not_written_to_session_state(tmp_path):
    with pytest.raises(ValueError, match="sensitive raw data"):
        write_session_state(
            current_phase="Phase F",
            next_action="store password secret",
            output_path=tmp_path / "session_state.md",
        )


def test_dispatch_write_session_state(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out = dispatch(
        "write_session_state",
        current_phase="Phase F",
        next_action="pytest",
        output_path=str(tmp_path / "session_state.md"),
        update_restart=False,
    )
    assert out["current_phase"] == "Phase F"