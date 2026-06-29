"""Variance bridge (MASTER_PLAN Part L Phase 4) — computed in Polars.

Numbers come from data, never from generation. Each part carries an EvidenceRef. The audit
layer later recomputes the same totals via DuckDB SQL (a different engine) as a four-eyes
check (Part O).
"""
from __future__ import annotations

import polars as pl

from shared.contracts.models import EvidenceRef, VarianceBridge, VariancePart
from shared.metrics.registry import get_metric


def material_cost_variance(
    clean_actuals: pl.DataFrame, budget: pl.DataFrame
) -> VarianceBridge:
    metric = get_metric("material_cost_variance")
    grain = metric["grain"]  # sub_assembly

    actual_by = (
        clean_actuals.group_by(grain).agg(pl.col("amount").sum().alias("actual")).sort(grain)
    )
    budget = budget.with_columns(pl.col("budget_amount").cast(pl.Float64))

    joined = actual_by.join(budget, on=grain, how="full", coalesce=True).fill_null(0.0)

    parts: list[VariancePart] = []
    for r in joined.iter_rows(named=True):
        parts.append(
            VariancePart(
                dim_value=r[grain],
                actual=round(float(r["actual"]), 4),
                budget=round(float(r["budget_amount"]), 4),
                evidence=EvidenceRef(
                    source="polars:clean_actuals",
                    locator=f"{grain}='{r[grain]}'",
                    method="SUM(amount) - budget_amount",
                    value=round(float(r["actual"]) - float(r["budget_amount"]), 4),
                ),
            )
        )

    total_actual = round(sum(p.actual for p in parts), 4)
    total_budget = round(sum(p.budget for p in parts), 4)
    return VarianceBridge(
        metric="material_cost_variance",
        total_actual=total_actual,
        total_budget=total_budget,
        parts=parts,
        evidence=EvidenceRef(
            source="polars:clean_actuals",
            locator="all sub_assemblies",
            method="SUM(actual) - SUM(budget)",
            value=round(total_actual - total_budget, 4),
        ),
    )
