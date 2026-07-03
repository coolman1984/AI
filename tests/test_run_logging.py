"""Tests for the FOREMAN run logger (Step 1.2)."""


import pytest

from tools.foreman_db import init_db
from tools.run_logger import (
    finish_run,
    finish_step,
    log_evidence,
    log_step,
    log_validation,
    start_run,
)


@pytest.fixture
def db():
    """Create a temporary in-memory database for each test."""
    conn = init_db(":memory:")
    yield conn
    conn.close()


def test_start_run_creates_row(db):
    """start_run should insert a row and return a positive run_id."""
    rid = start_run(db, "Test goal", skill_id="SK-001")
    assert rid > 0
    row = db.execute("SELECT * FROM runs WHERE run_id = ?", (rid,)).fetchone()
    assert row is not None
    assert row["goal"] == "Test goal"
    assert row["skill_id"] == "SK-001"
    assert row["status"] == "running"


def test_log_step_creates_row(db):
    """log_step should insert a step linked to a run."""
    rid = start_run(db, "Goal for step test")
    sid = log_step(db, rid, seq=1, tool_id="T-TEST-001", params={"key": "val"})
    assert sid > 0
    row = db.execute("SELECT * FROM run_steps WHERE step_id = ?", (sid,)).fetchone()
    assert row["run_id"] == rid
    assert row["tool_id"] == "T-TEST-001"
    assert row["status"] == "running"


def test_finish_step_updates(db):
    """finish_step should set status and finished_at."""
    rid = start_run(db, "Goal")
    sid = log_step(db, rid, 1, "T-TEST-001")
    finish_step(db, sid, status="done", output_path="/tmp/out.csv")
    row = db.execute("SELECT * FROM run_steps WHERE step_id = ?", (sid,)).fetchone()
    assert row["status"] == "done"
    assert row["output_path"] == "/tmp/out.csv"
    assert row["finished_at"] is not None


def test_log_evidence_creates_row(db):
    """log_evidence should insert an evidence item linked to run and step."""
    rid = start_run(db, "Evidence test")
    sid = log_step(db, rid, 1, "T-TEST-001")
    eid = log_evidence(
        db,
        run_id=rid,
        step_id=sid,
        source_fingerprint="abc123",
        locator="Sheet1!A1:C10",
        method="ingest",
        value_or_summary="42 rows ingested",
    )
    assert eid > 0
    row = db.execute("SELECT * FROM evidence_items WHERE evidence_id = ?", (eid,)).fetchone()
    assert row["run_id"] == rid
    assert row["method"] == "ingest"


def test_log_validation_creates_row(db):
    """log_validation should insert a gate result."""
    rid = start_run(db, "Validation test")
    vid = log_validation(
        db, rid, gate_name="conservation", passed=True,
        expected="100", actual="100", message="All rows accounted for",
    )
    assert vid > 0
    row = db.execute("SELECT * FROM validation_results WHERE validation_id = ?", (vid,)).fetchone()
    assert row["passed"] == 1
    assert row["gate_name"] == "conservation"


def test_finish_run_updates(db):
    """finish_run should set status, timestamps, and summary."""
    rid = start_run(db, "Goal")
    finish_run(db, rid, status="done", outcome_summary="Success", model_calls_count=5, est_tokens=1500)
    row = db.execute("SELECT * FROM runs WHERE run_id = ?", (rid,)).fetchone()
    assert row["status"] == "done"
    assert row["outcome_summary"] == "Success"
    assert row["model_calls_count"] == 5
    assert row["est_tokens"] == 1500
    assert row["finished_at"] is not None


def test_full_run_produces_all_rows(db):
    """A complete scripted run should produce runs + steps + evidence + validation."""
    rid = start_run(db, "Full run test", skill_id="SK-001", contract_path="runs/test/contract.md")

    step1 = log_step(db, rid, 1, "T-FP-001", params={"path": "inbox/test.xlsx"})
    log_evidence(db, rid, step1, source_fingerprint="fp1", value_or_summary="File fingerprinted")
    finish_step(db, step1, "done")

    step2 = log_step(db, rid, 2, "T-ING-001", params={"table": "raw_test"})
    log_evidence(db, rid, step2, source_fingerprint="fp1", locator="Sheet1", value_or_summary="42 rows ingested")
    log_validation(db, rid, "conservation", passed=True, expected="42", actual="42")
    finish_step(db, step2, "done")

    finish_run(db, rid, status="done", outcome_summary="Ingested 42 rows", model_calls_count=2, est_tokens=800)

    # Verify
    runs = list(db.execute("SELECT * FROM runs"))
    steps = list(db.execute("SELECT * FROM run_steps"))
    evids = list(db.execute("SELECT * FROM evidence_items"))
    valids = list(db.execute("SELECT * FROM validation_results"))

    assert len(runs) == 1
    assert len(steps) == 2
    assert len(evids) == 2
    assert len(valids) == 1
    assert runs[0]["status"] == "done"
