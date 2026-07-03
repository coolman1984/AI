"""Tests for the FOREMAN end-to-end MVP run (Step 2.4)."""

import os
import tempfile

import pytest

from tools.foreman_db import init_db


@pytest.fixture
def db():
    conn = init_db(":memory:")
    yield conn
    conn.close()


def test_dry_run_returns_contract(db):
    """A dry run should return a run_id without executing skills."""
    from tools.run_foreman import run_foreman

    # Create a dummy inbox file
    with tempfile.TemporaryDirectory() as tmp:
        inbox_dir = os.path.join(tmp, "inbox")
        os.makedirs(inbox_dir)
        file_path = os.path.join(inbox_dir, "test.csv")
        with open(file_path, "w") as f:
            f.write("Item,Amount\nA001,100.0\n")

        result = run_foreman(
            file_path, goal="Dry run test",
            db_registry=db, dry_run=True,
        )
        assert "run_id" in result
        assert result["status"] == "running"  # dry run doesn't finish


def test_missing_file_returns_error(db):
    """A non-existent file should return an error immediately."""
    from tools.run_foreman import run_foreman

    result = run_foreman(
        "/nonexistent/file.xlsx", goal="Missing file",
        db_registry=db,
    )
    assert result["status"] == "failed"
    assert "not found" in result.get("error", "").lower()


def test_end_to_end_on_csv_fixture(db):
    """Running the full chain on a CSV fixture should produce results
    (may fail at specific steps, but must not crash)."""
    from tools.run_foreman import run_foreman

    with tempfile.TemporaryDirectory() as tmp:
        inbox_dir = os.path.join(tmp, "inbox")
        os.makedirs(inbox_dir)
        file_path = os.path.join(inbox_dir, "fixture.csv")
        with open(file_path, "w") as f:
            f.write("Item,Amount\nA001,100.0\nA002,200.0\n")

        result = run_foreman(
            file_path, goal="E2E test",
            control_total=300.0, period="2026-06",
            db_registry=db,
        )

        # Must not crash — check structure
        assert "run_id" in result
        assert "steps" in result
        assert "sk001" in result["steps"]

        # SK-001 result
        sk001 = result["steps"]["sk001"]
        assert sk001["status"] in ("done", "blocked", "failed")
