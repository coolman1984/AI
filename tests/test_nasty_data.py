"""Nasty-data prevention gate (Sprint 1 — number safety).

Exercises the messy real-world inputs the review found gaps for: SAP-style negative
numbers, junk quantities, uncleaned standards, missing dimension columns, and
number-dense OCR pages. Each test locks in a fix so the bug class cannot silently
come back.
"""
from __future__ import annotations

import polars as pl
import pytest
import yaml

from engines.data.clean import clean_actuals, clean_standards, parse_amount
from engines.data.drivers import run_variance_decomposition
from engines.data.ingest import get_connection, ingest_csv
from engines.data.variance import price_volume_mix
from engines.docs.ocr import extraction_quality
from engines.docs.verify import extract_numeric_tokens


def test_parse_amount_handles_sap_negative_conventions():
    assert parse_amount("(1,234.56)") == -1234.56
    assert parse_amount("1234.56-") == -1234.56
    assert parse_amount("(800)") == -800.0


def test_junk_qty_is_quarantined_not_silently_zeroed(tmp_path):
    path = tmp_path / "actuals.csv"
    path.write_text(
        "material_id,sub_assembly,period,qty,amount\n"
        "M1,Frame,2026-05,10,1000.00\n"
        "M2,Frame,2026-05,not-a-number,500.00\n"
    )
    con = get_connection()
    ingest_csv(con, "raw_actuals", str(path))
    clean, rejects, _ = clean_actuals(con, "raw_actuals", qty_col="qty")

    assert clean.height == 1
    assert len(rejects) == 1
    assert rejects[0].reason == "unparseable_qty"
    assert 2 == clean.height + len(rejects)  # conservation: nothing vanishes silently


def test_clean_standards_excludes_totals_and_dupes(tmp_path):
    path = tmp_path / "standards.csv"
    path.write_text(
        "material_id,sub_assembly,std_qty,std_price\n"
        "M1,Frame,10,95\n"
        "Total,,10,95\n"
        "M1,Frame,10,95\n"
    )
    con = get_connection()
    ingest_csv(con, "raw_std", str(path))
    clean, rejects, _ = clean_standards(con, "raw_std")

    reasons = sorted(r.reason for r in rejects)
    assert reasons == ["duplicate", "total_or_missing_key"]
    assert clean.height == 1
    assert 3 == clean.height + len(rejects)


def test_pvm_raises_on_null_qty_instead_of_silently_zeroing():
    actuals = pl.DataFrame({
        "material_id": ["M1"], "sub_assembly": ["Frame"],
        "qty": [None], "amount": [1000.0],
    })
    standards = pl.DataFrame({
        "material_id": ["M1"], "std_qty": [10.0], "std_price": [95.0],
    })
    with pytest.raises(ValueError, match="null"):
        price_volume_mix(actuals, standards)


def test_dedup_does_not_false_collide_when_dimension_column_is_absent(tmp_path):
    """Old hardcoded dup key was (key, sub_assembly, period, amount) — a lens with
    neither sub_assembly nor period would collapse to (key, None, None, amount) and
    falsely drop distinct rows. Default dedup now uses every actual column."""
    path = tmp_path / "actuals_no_dims.csv"
    path.write_text(
        "material_id,region,amount\n"
        "M1,East,1000.00\n"
        "M1,West,1000.00\n"
    )
    con = get_connection()
    ingest_csv(con, "raw_actuals_no_dims", str(path))
    clean, rejects, _ = clean_actuals(con, "raw_actuals_no_dims")

    assert clean.height == 2
    assert rejects == []


def test_extraction_quality_counts_numeric_dense_text():
    numeric_table = "1234.56 2345.67 3456.78 4567.89 5678.90 6789.01"
    assert extraction_quality(numeric_table) >= 0.5  # must not force the OCR cascade


def test_extract_numeric_tokens_handles_parenthesized_negative():
    assert extract_numeric_tokens("Variance was (1,234) units.") == ["-1234"]


def test_run_variance_decomposition_reports_standards_rejects_separately():
    cfg = yaml.safe_load(open("config.yaml"))
    out = run_variance_decomposition(
        "data/sample/finance_actuals.csv", "data/sample/finance_standards.csv", cfg
    )
    assert "actuals_rejects" in out
    assert "standards_rejects" in out
    assert out["standards_rejects"] == []  # sample standards file is already clean
    assert out["rejects"] == out["actuals_rejects"] + out["standards_rejects"]
