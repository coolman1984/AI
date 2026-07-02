"""Manager card (MASTER_PLAN E.2) — one-A4, BLUF-first, every number cited."""
from __future__ import annotations

from shared.contracts.models import (
    DriverSplit,
    EvidenceRef,
    ManagerCard,
    NumberFact,
    VarianceBridge,
    VarianceDecomposition,
)


def _fmt(v: float, unit: str) -> str:
    return f"${v:,.0f}" if unit == "USD" else f"{v:,.0f} {unit}"


def make_manager_card(
    bridge: VarianceBridge,
    data_quality: dict,
    lens: dict | None = None,
    decomposition: VarianceDecomposition | None = None,
) -> ManagerCard:
    lens = lens or {}
    noun = lens.get("noun", "Material cost")
    unit = lens.get("unit", "USD")
    tv = bridge.total_variance
    if tv > 0:
        direction = lens.get("direction_over", "OVER budget")
    elif tv < 0:
        direction = lens.get("direction_under", "UNDER budget")
    else:
        direction = lens.get("direction_on", "ON budget")
    drivers_sorted = sorted(bridge.parts, key=lambda p: abs(p.variance), reverse=True)
    top = drivers_sorted[0]

    headline = (
        f"{noun} is {_fmt(abs(tv), unit)} {direction} "
        f"({_fmt(bridge.total_actual, unit)} vs {_fmt(bridge.total_budget, unit)}); "
        f"biggest mover: {top.dim_value} {top.variance:+,.0f}."
    )

    key_numbers = [
        NumberFact("Total variance", tv, bridge.evidence),
        NumberFact(f"{top.dim_value} variance", top.variance, top.evidence),
    ]
    driver_split = None
    if decomposition is not None:
        driver_split = DriverSplit(
            total=NumberFact(
                "Driver total",
                decomposition.total,
                EvidenceRef(
                    source="polars:driver_decomposition",
                    locator="all matched materials",
                    method="price + volume + mix",
                    value=decomposition.total,
                ),
            ),
            price=NumberFact(
                "Price effect",
                decomposition.price,
                EvidenceRef(
                    source="polars:driver_decomposition",
                    locator="all matched materials",
                    method="SUM((actual_price-std_price)*actual_qty)",
                    value=decomposition.price,
                ),
            ),
            volume=NumberFact(
                "Volume effect",
                decomposition.volume,
                EvidenceRef(
                    source="polars:driver_decomposition",
                    locator="all matched materials",
                    method="SUM((scale*std_qty-std_qty)*std_price)",
                    value=decomposition.volume,
                ),
            ),
            mix=NumberFact(
                "Mix effect",
                decomposition.mix,
                EvidenceRef(
                    source="polars:driver_decomposition",
                    locator="all matched materials",
                    method="SUM((actual_qty-scale*std_qty)*std_price)",
                    value=decomposition.mix,
                ),
            ),
        )
    drivers = [f"{p.dim_value}: {p.variance:+,.0f}" for p in drivers_sorted[:3]]
    risks = []
    if data_quality["confidence"] == "Low":
        risks.append(
            f"Data quality LOW: {data_quality['reject_count']} rows rejected "
            f"({data_quality['reject_ratio']:.0%}) — verify before deciding."
        )
    actions = [f"Review {top.dim_value} cost driver with the owner before sign-off."]
    evidence = [n.evidence for n in key_numbers]
    if driver_split is not None:
        evidence.extend(
            [
                driver_split.total.evidence,
                driver_split.price.evidence,
                driver_split.volume.evidence,
                driver_split.mix.evidence,
            ]
        )

    card = ManagerCard(
        headline=headline,
        decision_needed="Investigate" if tv != 0 else "Monitor",
        key_numbers=key_numbers,
        driver_split=driver_split,
        drivers=drivers,
        risks=risks,
        actions=actions,
        confidence=data_quality,
        evidence=evidence,
    )
    card.validate()  # trust wall: refuse a number without evidence
    return card


def render_text(card: ManagerCard) -> str:
    lines = [
        "================ MANAGER CARD (one A4) ================",
        f"HEADLINE : {card.headline}",
        f"DECISION : {card.decision_needed}",
        "KEY NUMBERS:",
    ]
    for n in card.key_numbers:
        lines.append(
            f"  - {n.label}: {n.value:+,.2f}   "
            f"[{n.tag}; {n.evidence.source} {n.evidence.method}]"
        )
    if card.driver_split is not None:
        lines.append(
            "OPERATING VIEW (vs standard cost): "
            f"total {card.driver_split.total.value:+,.2f} [{card.driver_split.total.tag}] = "
            f"price {card.driver_split.price.value:+,.2f} [{card.driver_split.price.tag}]; "
            f"volume {card.driver_split.volume.value:+,.2f} [{card.driver_split.volume.tag}]; "
            f"mix {card.driver_split.mix.value:+,.2f} [{card.driver_split.mix.tag}]"
        )
    lines.append("DRIVERS  : " + "; ".join(card.drivers))
    if card.risks:
        lines.append("RISKS    : " + "; ".join(card.risks))
    lines.append("ACTIONS  : " + "; ".join(card.actions))
    lines.append(
        f"CONFIDENCE: {card.confidence['confidence']} "
        f"(rejects {card.confidence['reject_ratio']:.0%}, "
        f"materiality {card.confidence['materiality_ratio']:.0%})"
    )
    lines.append("======================================================")
    return "\n".join(lines)


def compute_data_quality(rows_in: int, rejects: list, total_amount: float, cfg: dict) -> dict:
    reject_ratio = len(rejects) / rows_in if rows_in else 0.0
    material_rejected = sum(r.amount for r in rejects if getattr(r, "amount", None))
    materiality_ratio = (material_rejected / total_amount) if total_amount else 0.0
    if reject_ratio > 0.05 or materiality_ratio > cfg.get("materiality_warn_ratio", 0.02):
        confidence = "Low"
    elif reject_ratio > 0.01:
        confidence = "Medium"
    else:
        confidence = "High"
    return {
        "confidence": confidence,
        "reject_count": len(rejects),
        "reject_ratio": reject_ratio,
        "materiality_ratio": materiality_ratio,
    }


# placeholder to satisfy EvidenceRef import lint when re-exported
_ = EvidenceRef
