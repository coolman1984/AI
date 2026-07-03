"""Tests for second-read OCR completeness gate."""

from __future__ import annotations

from engines.docs.completeness import (
    CompletenessReport,
    PageSecondReadResult,
    record_second_read_foreman,
    second_read_audit,
    second_read_page,
)
from tools.foreman_db import init_db


def test_second_read_complete_when_extraction_covers_ocr():
    res = second_read_page("Revenue 4,700 approved", "Revenue 4700 approved")
    assert res["flagged"] is False
    assert res["missing_numeric_tokens"] == []


def test_second_read_flags_numeric_only_in_ocr():
    res = second_read_page("Revenue approved", "Revenue 4,700 approved")
    assert res["flagged"] is True
    assert "4700" in res["missing_numeric_tokens"]


def test_second_read_one_way_extraction_extra_not_flagged():
    # OCR text has no numeric tokens and no long alphabetic words -> not flagged
    res = second_read_page("Secret value 9999 only in extraction", "n/a")
    assert res["missing_numeric_tokens"] == []
    assert res["flagged"] is False


def test_second_read_unavailable_when_ocr_quality_zero():
    report = second_read_audit(
        ["extracted text only"],
        image_loader=lambda _p: object(),
        cfg={"tools": {"ocr_quality_threshold": 0.5}},
        page_numbers=[1],
        ocr_runner=lambda _img: {"text": "@#$", "quality": 0.0, "engine": "none"},
    )
    assert report.pages[0].status == "second_read_unavailable"
    assert report.verdict == "partially_unverifiable"


def test_second_read_flags_korean_unit_only_in_ocr():
    res = second_read_page("매출 요약", "매출은 3억 원")
    assert res["flagged"] is True
    assert "300000000" in res["missing_numeric_tokens"]


def test_foreman_records_validation_and_blocks_on_gaps():
    db = init_db(":memory:")
    report = CompletenessReport(
        pages=[
            PageSecondReadResult(
                page_no=3,
                status="gaps_found",
                missing_numeric_tokens=["4700"],
                flagged=True,
                ocr_engine="tesseract",
            )
        ],
        verdict="gaps_found",
    )
    from tools.run_logger import start_run

    run_id = start_run(db, goal="doc audit", skill_id="SK-DOC")
    status = record_second_read_foreman(
        db,
        run_id,
        report,
        source_path="/tmp/demo.pdf",
        source_fingerprint="abc",
    )
    assert status == "blocked"
    row = db.execute(
        "SELECT passed, message FROM validation_results WHERE gate_name='second_read'"
    ).fetchone()
    assert row[0] == 0
    assert "4700" in row[1]
    ev = db.execute("SELECT locator, method FROM evidence_items").fetchone()
    assert ev[0] == "page:3"
    assert "tesseract" in ev[1]