from engines.brain.comparison import compare_public_ir_quarters
from mcp_server.server import dispatch


def _period_record(*, period: str, revenue: int | None, kpi: str | None, source: str) -> dict:
    claims = []
    if revenue is not None:
        claims.append(
            {
                "entity": "revenue",
                "text": f"Revenue KRW {revenue:,} trillion",
                "value": revenue,
                "citation": f"{source}#page=3",
            }
        )
    if kpi is not None:
        claims.append(
            {
                "entity": "kpi",
                "text": kpi,
                "citation": f"{source}#page=5",
            }
        )
    return {"period": period, "source": source, "claims": claims}


def test_two_period_records_compare_revenue_only_when_citations_exist():
    record_a = _period_record(
        period="2025-Q1",
        revenue=79,
        kpi="DS division revenue up 8%",
        source="samsung_ir_2025_q1.pdf",
    )
    record_b = _period_record(
        period="2025-Q2",
        revenue=82,
        kpi="DS division revenue up 10%",
        source="samsung_ir_2025_q2.pdf",
    )

    result = compare_public_ir_quarters(
        period_a="2025-Q1",
        period_b="2025-Q2",
        record_a=record_a,
        record_b=record_b,
    )

    revenue_item = next(item for item in result["items"] if item["field"] == "revenue")
    kpi_item = next(item for item in result["items"] if item["field"] == "kpi")

    assert revenue_item["status"] == "comparable"
    assert revenue_item["value_a"] == 79
    assert revenue_item["value_b"] == 82
    assert revenue_item["delta"] == 3
    assert "samsung_ir_2025_q1.pdf" in str(revenue_item["citations_a"])
    assert kpi_item["status"] == "comparable"


def test_missing_comparable_field_returns_not_comparable_instead_of_invented_analysis():
    record_a = _period_record(
        period="2025-Q1",
        revenue=79,
        kpi=None,
        source="samsung_ir_2025_q1.pdf",
    )
    record_b = _period_record(
        period="2025-Q2",
        revenue=82,
        kpi="DS division revenue up 10%",
        source="samsung_ir_2025_q2.pdf",
    )
    record_b["claims"] = [claim for claim in record_b["claims"] if claim["entity"] != "revenue"]
    record_b["claims"][0]["citation"] = ""

    result = compare_public_ir_quarters(
        period_a="2025-Q1",
        period_b="2025-Q2",
        record_a=record_a,
        record_b=record_b,
    )

    revenue_item = next(item for item in result["items"] if item["field"] == "revenue")
    kpi_item = next(item for item in result["items"] if item["field"] == "kpi")

    assert revenue_item["status"] == "not_comparable"
    assert kpi_item["status"] == "not_comparable"
    assert "reason" in revenue_item
    assert "delta" not in revenue_item


def test_output_includes_period_labels_and_source_citations():
    record_a = _period_record(
        period="2025-Q1",
        revenue=79,
        kpi="DS division revenue up 8%",
        source="samsung_ir_2025_q1.pdf",
    )
    record_b = _period_record(
        period="2025-Q2",
        revenue=82,
        kpi="DS division revenue up 10%",
        source="samsung_ir_2025_q2.pdf",
    )

    result = compare_public_ir_quarters(
        period_a="2025-Q1",
        period_b="2025-Q2",
        record_a=record_a,
        record_b=record_b,
    )

    assert result["period_a"] == "2025-Q1"
    assert result["period_b"] == "2025-Q2"
    assert result["source_a"] == "samsung_ir_2025_q1.pdf"
    assert result["source_b"] == "samsung_ir_2025_q2.pdf"


def test_dispatch_compare_public_ir_quarters():
    record_a = _period_record(
        period="2025-Q1",
        revenue=79,
        kpi="DS division revenue up 8%",
        source="samsung_ir_2025_q1.pdf",
    )
    record_b = _period_record(
        period="2025-Q2",
        revenue=82,
        kpi="DS division revenue up 10%",
        source="samsung_ir_2025_q2.pdf",
    )

    out = dispatch(
        "compare_public_ir_quarters",
        period_a="2025-Q1",
        period_b="2025-Q2",
        record_a=record_a,
        record_b=record_b,
    )

    assert out["period_a"] == "2025-Q1"
    assert any(item["field"] == "revenue" for item in out["items"])