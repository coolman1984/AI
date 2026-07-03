"""Tests for factory comparison availability gate (F.6)."""

from __future__ import annotations

from engines.brain.comparison import compare_factories
from mcp_server.server import dispatch


def _factory_record(*, factory: str, revenue: int | None, kpi_def: str | None) -> dict:
    claims = []
    if revenue is not None:
        claims.append(
            {
                "entity": "revenue",
                "text": kpi_def or f"Revenue {revenue}",
                "value": revenue,
                "kpi_definition": kpi_def or "total revenue in KRW trillion",
                "citation": f"{factory}_report.pdf#page=2",
            }
        )
    return {"factory": factory, "claims": claims}


def test_missing_second_factory_returns_blocked_not_enough_data():
    result = compare_factories(
        factory_a="plant-a",
        factory_b="plant-b",
        record_a=_factory_record(factory="plant-a", revenue=100, kpi_def="total revenue"),
        record_b=None,
    )
    assert result["status"] == "blocked"
    assert result["reason"] == "not_enough_data"


def test_different_kpi_definitions_return_not_directly_comparable():
    record_a = _factory_record(
        factory="plant-a",
        revenue=100,
        kpi_def="total revenue in KRW trillion",
    )
    record_b = _factory_record(
        factory="plant-b",
        revenue=95,
        kpi_def="net revenue after rebates",
    )
    result = compare_factories(
        factory_a="plant-a",
        factory_b="plant-b",
        record_a=record_a,
        record_b=record_b,
    )
    item = result["items"][0]
    assert item["status"] == "not_directly_comparable"
    assert item["reason"] == "kpi_definition_mismatch"


def test_comparable_cited_records_produce_comparison_output():
    record_a = _factory_record(
        factory="plant-a",
        revenue=100,
        kpi_def="total revenue in KRW trillion",
    )
    record_b = _factory_record(
        factory="plant-b",
        revenue=110,
        kpi_def="total revenue in KRW trillion",
    )
    result = compare_factories(
        factory_a="plant-a",
        factory_b="plant-b",
        record_a=record_a,
        record_b=record_b,
    )
    assert result["status"] == "ok"
    item = result["items"][0]
    assert item["status"] == "comparable"
    assert item["value_a"] == 100
    assert item["value_b"] == 110
    assert item["delta"] == 10


def test_dispatch_compare_factories():
    out = dispatch(
        "compare_factories",
        factory_a="plant-a",
        factory_b="plant-b",
        record_a=_factory_record(factory="plant-a", revenue=100, kpi_def="total revenue in KRW trillion"),
        record_b=_factory_record(factory="plant-b", revenue=110, kpi_def="total revenue in KRW trillion"),
    )
    assert out["status"] == "ok"