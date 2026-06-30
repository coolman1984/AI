"""Variance bridge (MASTER_PLAN Part L Phase 4) — computed in Polars.

Numbers come from data, never from generation. Each part carries an EvidenceRef. The audit
layer later recomputes the same totals via DuckDB SQL (a different engine) as a four-eyes
check (Part O).
"""
from __future__ import annotations

import polars as pl

from shared.contracts.models import EvidenceRef, VarianceBridge, VariancePart


def category_variance(
    clean_actuals: pl.DataFrame,
    baseline: pl.DataFrame,
    *,
    grain: str,
    value_col: str,
    baseline_col: str,
    metric: str,
) -> VarianceBridge:
    """Generic actual-vs-baseline variance by a grain column. Lens-driven (Stage 7) —
    the same code serves Finance (cost vs budget) and Planning (output vs plan)."""
    actual_by = (
        clean_actuals.group_by(grain).agg(pl.col(value_col).sum().alias("actual")).sort(grain)
    )
    baseline = baseline.with_columns(pl.col(baseline_col).cast(pl.Float64))
    joined = actual_by.join(baseline, on=grain, how="full", coalesce=True).fill_null(0.0)

    parts: list[VariancePart] = []
    for r in joined.iter_rows(named=True):
        parts.append(
            VariancePart(
                dim_value=r[grain],
                actual=round(float(r["actual"]), 4),
                budget=round(float(r[baseline_col]), 4),
                evidence=EvidenceRef(
                    source="polars:clean_actuals",
                    locator=f"{grain}='{r[grain]}'",
                    method=f"SUM({value_col}) - {baseline_col}",
                    value=round(float(r["actual"]) - float(r[baseline_col]), 4),
                ),
            )
        )

    total_actual = round(sum(p.actual for p in parts), 4)
    total_budget = round(sum(p.budget for p in parts), 4)
    return VarianceBridge(
        metric=metric,
        total_actual=total_actual,
        total_budget=total_budget,
        parts=parts,
        evidence=EvidenceRef(
            source="polars:clean_actuals",
            locator=f"all {grain}",
            method="SUM(actual) - SUM(baseline)",
            value=round(total_actual - total_budget, 4),
        ),
    )


def material_cost_variance(clean_actuals: pl.DataFrame, budget: pl.DataFrame) -> VarianceBridge:
    """Finance wrapper (back-compat) over the generic category_variance."""
    return category_variance(
        clean_actuals, budget,
        grain="sub_assembly", value_col="amount",
        baseline_col="budget_amount", metric="material_cost_variance",
    )
