"""Public IR quarter comparison with citation-only claims (MASTER_PLAN C.6)."""

from __future__ import annotations

import re

_COMPARABLE_FIELDS = ("revenue", "operating_income", "net_income", "eps", "kpi")


def _normalize_label(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", label.strip().lower()).strip("_")


def _claim_value(claim: dict) -> str | float | None:
    if "value" in claim and claim["value"] is not None:
        return claim["value"]
    text = claim.get("text", "")
    match = re.search(r"[-+]?\d[\d,]*(?:\.\d+)?", text.replace(",", ""))
    if match:
        raw = match.group(0)
        return float(raw) if "." in raw else int(raw)
    return text.strip() or None


def _has_citation(claim: dict) -> bool:
    citation = claim.get("citation", "")
    citations = claim.get("citations", [])
    return bool(citation.strip()) or bool(citations)


def compare_period_records(
    *,
    period_a: str,
    period_b: str,
    record_a: dict,
    record_b: dict,
) -> dict:
    claims_a = {
        _normalize_label(claim.get("entity", claim.get("label", ""))): claim
        for claim in record_a.get("claims", [])
        if claim.get("entity") or claim.get("label")
    }
    claims_b = {
        _normalize_label(claim.get("entity", claim.get("label", ""))): claim
        for claim in record_b.get("claims", [])
        if claim.get("entity") or claim.get("label")
    }

    items: list[dict] = []
    for field in _COMPARABLE_FIELDS:
        claim_a = claims_a.get(field)
        claim_b = claims_b.get(field)

        if claim_a is None or claim_b is None:
            items.append(
                {
                    "field": field,
                    "status": "not_comparable",
                    "reason": "missing_in_one_or_both_periods",
                    "period_a": period_a,
                    "period_b": period_b,
                }
            )
            continue

        if not _has_citation(claim_a) or not _has_citation(claim_b):
            items.append(
                {
                    "field": field,
                    "status": "not_comparable",
                    "reason": "missing_citation",
                    "period_a": period_a,
                    "period_b": period_b,
                    "citations_a": claim_a.get("citation") or claim_a.get("citations"),
                    "citations_b": claim_b.get("citation") or claim_b.get("citations"),
                }
            )
            continue

        value_a = _claim_value(claim_a)
        value_b = _claim_value(claim_b)
        delta = None
        if isinstance(value_a, (int, float)) and isinstance(value_b, (int, float)):
            delta = round(value_b - value_a, 4)

        items.append(
            {
                "field": field,
                "status": "comparable",
                "period_a": period_a,
                "period_b": period_b,
                "value_a": value_a,
                "value_b": value_b,
                "delta": delta,
                "citations_a": claim_a.get("citation") or claim_a.get("citations"),
                "citations_b": claim_b.get("citation") or claim_b.get("citations"),
            }
        )

    return {
        "period_a": period_a,
        "period_b": period_b,
        "source_a": record_a.get("source", ""),
        "source_b": record_b.get("source", ""),
        "items": items,
    }


def compare_public_ir_quarters(
    *,
    period_a: str,
    period_b: str,
    record_a: dict,
    record_b: dict,
) -> dict:
    """Compare two public IR period records without inventing analysis."""
    return compare_period_records(
        period_a=period_a,
        period_b=period_b,
        record_a=record_a,
        record_b=record_b,
    )


def _kpi_definition(claim: dict) -> str:
    return claim.get("kpi_definition") or claim.get("definition") or claim.get("text", "")


def compare_factories(
    *,
    factory_a: str,
    factory_b: str,
    record_a: dict | None = None,
    record_b: dict | None = None,
) -> dict:
    """Compare factory reports only when comparable cited records exist."""
    if not factory_a.strip() or not factory_b.strip():
        raise ValueError("factory_a and factory_b are required")
    if record_a is None or record_b is None:
        return {
            "status": "blocked",
            "reason": "not_enough_data",
            "factory_a": factory_a,
            "factory_b": factory_b,
            "items": [],
        }

    claims_a = {
        _normalize_label(claim.get("entity", claim.get("label", ""))): claim
        for claim in record_a.get("claims", [])
        if claim.get("entity") or claim.get("label")
    }
    claims_b = {
        _normalize_label(claim.get("entity", claim.get("label", ""))): claim
        for claim in record_b.get("claims", [])
        if claim.get("entity") or claim.get("label")
    }

    shared_fields = sorted(set(claims_a) & set(claims_b))
    if not shared_fields:
        return {
            "status": "blocked",
            "reason": "not_enough_data",
            "factory_a": factory_a,
            "factory_b": factory_b,
            "items": [],
        }

    items: list[dict] = []
    for field in shared_fields:
        claim_a = claims_a[field]
        claim_b = claims_b[field]

        if not _has_citation(claim_a) or not _has_citation(claim_b):
            items.append(
                {
                    "field": field,
                    "status": "not_comparable",
                    "reason": "missing_citation",
                    "factory_a": factory_a,
                    "factory_b": factory_b,
                }
            )
            continue

        def_a = _normalize_label(_kpi_definition(claim_a))
        def_b = _normalize_label(_kpi_definition(claim_b))
        if def_a and def_b and def_a != def_b:
            items.append(
                {
                    "field": field,
                    "status": "not_directly_comparable",
                    "reason": "kpi_definition_mismatch",
                    "definition_a": _kpi_definition(claim_a),
                    "definition_b": _kpi_definition(claim_b),
                    "factory_a": factory_a,
                    "factory_b": factory_b,
                }
            )
            continue

        value_a = _claim_value(claim_a)
        value_b = _claim_value(claim_b)
        delta = None
        if isinstance(value_a, (int, float)) and isinstance(value_b, (int, float)):
            delta = round(value_b - value_a, 4)

        items.append(
            {
                "field": field,
                "status": "comparable",
                "factory_a": factory_a,
                "factory_b": factory_b,
                "value_a": value_a,
                "value_b": value_b,
                "delta": delta,
                "citations_a": claim_a.get("citation") or claim_a.get("citations"),
                "citations_b": claim_b.get("citation") or claim_b.get("citations"),
            }
        )

    comparable = [item for item in items if item["status"] == "comparable"]
    status = "ok" if comparable else "blocked"
    return {
        "status": status,
        "reason": None if comparable else "not_enough_comparable_fields",
        "factory_a": factory_a,
        "factory_b": factory_b,
        "items": items,
    }