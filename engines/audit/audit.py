"""The Audit & Human-Accountability Layer (MASTER_PLAN Part O).

INDEPENDENT of the creator: it recomputes the headline number via a DIFFERENT engine
(DuckDB SQL vs the Polars path used to build the card) — the four-eyes principle. It then
scores certainty, and when unsure or the rejects are material, it raises deep
multiple-choice questions for the human and blocks release until a named human signs off.
Nothing reaches the CEO unsigned.
"""
from __future__ import annotations

import duckdb
import polars as pl

from shared.contracts.models import (
    AuditResult,
    ManagerCard,
    SignOff,
    VarianceBridge,
    VarianceDecomposition,
)


def audit_card(
    card: ManagerCard,
    bridge: VarianceBridge,
    decomposition: VarianceDecomposition | None,
    clean_actuals: pl.DataFrame,
    budget: pl.DataFrame,
    rows_in: int,
    reject_count: int,
    cfg: dict,
    value_col: str = "amount",
    baseline_col: str = "budget_amount",
) -> AuditResult:
    issues: list[str] = []
    tol = cfg.get("recompute_tolerance", 0.01)

    # --- O.1 INDEPENDENT RE-RUN (different engine: DuckDB SQL vs the Polars path) ---
    con = duckdb.connect()
    con.register("clean", clean_actuals)
    con.register("bud", budget)
    re_actual = con.execute(f"SELECT COALESCE(SUM(TRY_CAST({value_col} AS DOUBLE)),0) FROM clean").fetchone()[0]
    re_budget = con.execute(f"SELECT COALESCE(SUM(TRY_CAST({baseline_col} AS DOUBLE)),0) FROM bud").fetchone()[0]
    re_variance = round(float(re_actual) - float(re_budget), 4)
    numbers_match = abs(re_variance - bridge.total_variance) <= tol
    if not numbers_match:
        issues.append(
            f"independent re-run mismatch: card={bridge.total_variance} vs audit={re_variance}"
        )

    # --- O.2 LOGIC REASSESSMENT ---
    conservation_ok = rows_in == (clean_actuals.height + reject_count)
    if not conservation_ok:
        issues.append("conservation broken: rows_in != clean + rejected")
    bridge_ok = bridge.reconciles(tol)
    if not bridge_ok:
        issues.append("variance bridge does not reconcile to total")
    evidence_ok = all(n.evidence and n.evidence.resolves() for n in card.key_numbers)
    if not evidence_ok:
        issues.append("a key number lacks resolving evidence")
    driver_split_ok = True
    if card.driver_split is not None:
        driver_numbers = [
            card.driver_split.total,
            card.driver_split.price,
            card.driver_split.volume,
            card.driver_split.mix,
        ]
        driver_evidence_ok = all(n.evidence and n.evidence.resolves() for n in driver_numbers)
        if not driver_evidence_ok:
            driver_split_ok = False
            issues.append("a driver number lacks resolving evidence")
        if decomposition is None:
            driver_split_ok = False
            issues.append("driver view shown without an audited decomposition")
        else:
            expected = {
                "total": round(decomposition.total, 4),
                "price": round(decomposition.price, 4),
                "volume": round(decomposition.volume, 4),
                "mix": round(decomposition.mix, 4),
            }
            actual = {
                "total": round(card.driver_split.total.value, 4),
                "price": round(card.driver_split.price.value, 4),
                "volume": round(card.driver_split.volume.value, 4),
                "mix": round(card.driver_split.mix.value, 4),
            }
            if not decomposition.reconciles(tol):
                driver_split_ok = False
                issues.append("driver decomposition does not reconcile to its total")
            if actual != expected:
                driver_split_ok = False
                issues.append("driver view does not match the decomposed numbers")

    # --- O.3 CERTAINTY (multi-dimensional, calibrated placeholder) ---
    dq = card.confidence
    certainty = {
        "numbers": 1.0 if numbers_match else 0.0,
        "evidence": 1.0 if evidence_ok else 0.0,
        "drivers": 1.0 if driver_split_ok else 0.0,
        "data_quality": max(0.0, 1.0 - dq["reject_ratio"]),
        "materiality": max(0.0, 1.0 - dq["materiality_ratio"]),
    }
    certainty["overall"] = round(min(certainty.values()), 3)

    passed = numbers_match and conservation_ok and bridge_ok and evidence_ok and driver_split_ok
    needs_human = (
        certainty["overall"] < cfg.get("certainty_release_threshold", 0.80)
        or dq["materiality_ratio"] > cfg.get("materiality_warn_ratio", 0.02)
    )

    # --- O.5 DEEP MULTIPLE-CHOICE QUESTIONS (only when uncertain/high-stakes) ---
    questions: list[dict] = []
    if needs_human and dq["confidence"] != "High":
        questions.append(
            {
                "question": (
                    f"{dq['reject_count']} rows ({dq['reject_ratio']:.0%}) were rejected "
                    f"before this ${bridge.total_variance:+,.0f} variance was computed. "
                    "How should we proceed?"
                ),
                "options": [
                    "A) Accept — rejected rows are non-material (totals/dupes), release as is",
                    "B) Review the rejected rows first (open rejects.csv)",
                    "C) Re-ingest the source file and recompute",
                    "D) Hold — do not send to management yet",
                ],
            }
        )

    return AuditResult(
        passed=passed,
        needs_human=needs_human,
        certainty=certainty,
        issues=issues,
        questions=questions,
        recomputed={"actual": float(re_actual), "budget": float(re_budget), "variance": re_variance},
    )


def approve_report(audit: AuditResult, approver: str, note: str = "") -> SignOff:
    """O.6 accountable human sign-off. A hard-failed audit cannot be signed off."""
    if not audit.passed:
        return SignOff(approver, approved=False,
                       certainty_at_approval=audit.certainty["overall"],
                       note="BLOCKED: audit failed — " + "; ".join(audit.issues))
    return SignOff(approver, approved=True,
                   certainty_at_approval=audit.certainty["overall"],
                   note=note or "Reviewed and approved; responsibility accepted.")
