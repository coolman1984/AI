"""Shared run logger for all FOREMAN skills.

Every skill uses this API to record runs, steps, evidence, and validation
results to the SQLite registry DB. No skill writes SQL directly.
"""

import json
from datetime import datetime
from typing import Any


def _now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")


def start_run(
    db,
    goal: str,
    skill_id: str = None,
    contract_path: str = None,
    privacy_tier: str = "tier1",
) -> int:
    """Record a new run in the runs table. Returns run_id."""
    cur = db.execute(
        "INSERT INTO runs (goal, skill_id, contract_path, privacy_tier, status) "
        "VALUES (?, ?, ?, ?, 'running')",
        (goal, skill_id, contract_path, privacy_tier),
    )
    db.commit()
    return cur.lastrowid


def log_step(
    db,
    run_id: int,
    seq: int,
    tool_id: str,
    params: dict[str, Any] = None,
    status: str = "running",
    output_path: str = None,
) -> int:
    """Record a step within a run. Returns step_id."""
    params_json = json.dumps(params) if params else None
    cur = db.execute(
        "INSERT INTO run_steps (run_id, seq, tool_id, params_json, status, output_path) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (run_id, seq, tool_id, params_json, status, output_path),
    )
    db.commit()
    return cur.lastrowid


def finish_step(db, step_id: int, status: str = "done", output_path: str = None):
    """Mark a step as done/failed and set its finished_at timestamp."""
    db.execute(
        "UPDATE run_steps SET status = ?, finished_at = ?, output_path = COALESCE(?, output_path) "
        "WHERE step_id = ?",
        (status, _now(), output_path, step_id),
    )
    db.commit()


def log_evidence(
    db,
    run_id: int,
    step_id: int = None,
    source_fingerprint: str = None,
    source_path: str = None,
    locator: str = None,
    method: str = None,
    value_or_summary: str = None,
) -> int:
    """Record an evidence item linked to a run and optionally a step. Returns evidence_id."""
    cur = db.execute(
        "INSERT INTO evidence_items (run_id, step_id, source_fingerprint, source_path, "
        "locator, method, value_or_summary) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (run_id, step_id, source_fingerprint, source_path, locator, method, value_or_summary),
    )
    db.commit()
    return cur.lastrowid


def log_validation(
    db,
    run_id: int,
    gate_name: str,
    rule_ref: str = None,
    passed: bool = False,
    expected: str = None,
    actual: str = None,
    message: str = None,
) -> int:
    """Record a validation gate result. Returns validation_id."""
    cur = db.execute(
        "INSERT INTO validation_results (run_id, gate_name, rule_ref, passed, expected, actual, message) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (run_id, gate_name, rule_ref, 1 if passed else 0, expected, actual, message),
    )
    db.commit()
    return cur.lastrowid


def finish_run(
    db,
    run_id: int,
    status: str = "done",
    outcome_summary: str = None,
    model_calls_count: int = 0,
    est_tokens: int = 0,
):
    """Mark a run as done/blocked/failed with summary."""
    db.execute(
        "UPDATE runs SET status = ?, finished_at = ?, outcome_summary = ?, "
        "model_calls_count = ?, est_tokens = ? "
        "WHERE run_id = ?",
        (status, _now(), outcome_summary, model_calls_count, est_tokens, run_id),
    )
    db.commit()
