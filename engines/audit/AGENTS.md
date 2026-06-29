# engines/audit — Audit & Human-Accountability Layer (MASTER_PLAN Part O)

**Does:** independently re-checks a draft card before any human sees it, then gates release
behind a named human sign-off.
**Public interface:** `audit.audit_card`, `audit.approve_report`.
**How:** O.1 re-run the totals in **DuckDB SQL** (different engine than the Polars path that
built the card) → four-eyes; O.2 reconcile conservation + bridge + evidence; O.3 multi-
dimensional certainty; O.5 raise deep multiple-choice questions when uncertain/material.
**Invariants:** a number mismatch (beyond tolerance) sets `passed=False`; a failed audit
cannot be signed off; `approve_report` records who/when/certainty (accountability).
**Never:** approve unsigned; let a number reach a manager without an independent re-check.
**Tests:** `pytest tests/test_card_and_audit.py`
