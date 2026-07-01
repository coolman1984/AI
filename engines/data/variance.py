"""Variance bridge (MASTER_PLAN Part L Phase 4) — computed in Polars.

Numbers come from data, never from generation. Each part carries an EvidenceRef. The audit
layer later recomputes the same totals via DuckDB SQL (a different engine) as a four-eyes
check (Part O).
"""
from __future__ import annotations

import polars as pl

from shared.contracts.models import (
    DriverPart,
    EvidenceRef,
    VarianceBridge,
    VarianceDecomposition,
    VariancePart,
)


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


def price_volume_mix(
    actuals: pl.DataFrame,
    standards: pl.DataFrame,
    *,
    key: str = "material_id",
    group: str = "sub_assembly",
    qty_col: str = "qty",
    amount_col: str = "amount",
    std_qty_col: str = "std_qty",
    std_price_col: str = "std_price",
    metric: str = "cost_pvm",
) -> VarianceDecomposition:
    """Explain a cost variance as price + volume + mix (T8).

    price  = (actual_price - std_price) * actual_qty        (paid more/less per unit)
    volume = (scale*std_qty - std_qty) * std_price           (overall scale, scale=SUM(aq)/SUM(sq))
    mix    = (actual_qty - scale*std_qty) * std_price         (shifted the proportion of items)
    The three reconcile exactly to line_total = actual_cost - std_cost.
    """
    a = actuals.with_columns(
        pl.col(qty_col).cast(pl.Float64, strict=False).alias("_aq"),
        pl.col(amount_col).cast(pl.Float64, strict=False).alias("_ac"),
    ).select([key, group, "_aq", "_ac"])
    s = standards.with_columns(
        pl.col(std_qty_col).cast(pl.Float64, strict=False).alias("_sq"),
        pl.col(std_price_col).cast(pl.Float64, strict=False).alias("_sp"),
    ).select([key, "_sq", "_sp"])

    matched = a.join(s, on=key, how="inner")
    unmatched = sorted(set(a[key].to_list()) - set(s[key].to_list()))

    aq_total = float(matched["_aq"].sum() or 0.0)
    sq_total = float(matched["_sq"].sum() or 0.0)
    scale = (aq_total / sq_total) if sq_total else 1.0

    parts: list[DriverPart] = []
    t_price = t_vol = t_mix = t_total = 0.0
    for r in matched.iter_rows(named=True):
        aq, ac, sq, sp = r["_aq"] or 0.0, r["_ac"] or 0.0, r["_sq"] or 0.0, r["_sp"] or 0.0
        ap = (ac / aq) if aq else 0.0
        price = (ap - sp) * aq
        volume = (scale * sq - sq) * sp
        mix = (aq - scale * sq) * sp
        line_total = ac - sq * sp
        parts.append(DriverPart(r[key], r[group], round(line_total, 4),
                                round(price, 4), round(volume, 4), round(mix, 4)))
        t_price += price
        t_vol += volume
        t_mix += mix
        t_total += line_total

    return VarianceDecomposition(
        metric=metric, total=round(t_total, 4), price=round(t_price, 4),
        volume=round(t_vol, 4), mix=round(t_mix, 4), parts=parts, unmatched=unmatched,
    )
