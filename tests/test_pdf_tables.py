from __future__ import annotations

from pathlib import Path

import duckdb
import fitz
import pytest

from engines.data.ingest import get_connection, init_ingestion_schema
from engines.data.pdf_tables import extract_pdf_tables, ingest_pdf_tables_tracked


@pytest.fixture
def con() -> duckdb.DuckDBPyConnection:
    connection = get_connection()
    init_ingestion_schema(connection)
    return connection


def _write_table_pdf(path: Path, rows: list[list[str]]) -> None:
    document = fitz.open()
    page = document.new_page(width=595, height=842)
    x0, y0 = 50, 80
    column_count = max(len(row) for row in rows)
    column_widths = [140 for _ in range(column_count)]
    row_height = 24
    for row_idx in range(len(rows) + 1):
        y = y0 + row_idx * row_height
        page.draw_line((x0, y), (x0 + sum(column_widths), y))
    for col_idx in range(column_count + 1):
        x = x0 + sum(column_widths[:col_idx])
        page.draw_line((x, y0), (x, y0 + len(rows) * row_height))
    for row_idx, row in enumerate(rows):
        for col_idx, value in enumerate(row):
            page.insert_text(
                (x0 + sum(column_widths[:col_idx]) + 6, y0 + row_idx * row_height + 16),
                value,
                fontsize=11,
            )
    document.save(path)
    document.close()


def test_extract_pdf_tables_returns_structured_rows(tmp_path: Path) -> None:
    path = tmp_path / "costs.pdf"
    _write_table_pdf(
        path,
        [
            ["material_id", "amount"],
            ["A1", "100"],
            ["A2", "200"],
        ],
    )

    extractions = extract_pdf_tables(str(path))

    assert len(extractions) == 1
    assert len(extractions[0].rows) == 2
    assert extractions[0].rows[0].fields["amount"] == "100"
    assert extractions[0].rows[0].confidence >= 0.75
    assert extractions[0].rows[0].needs_review is False


def test_ingest_pdf_tables_tracked_loads_accepted_rows(tmp_path, con: duckdb.DuckDBPyConnection) -> None:
    path = tmp_path / "accepted.pdf"
    _write_table_pdf(
        path,
        [
            ["material_id", "amount"],
            ["B1", "10"],
            ["B2", "20"],
        ],
    )

    result = ingest_pdf_tables_tracked(con, "raw_pdf", str(path))

    assert result["status"] == "completed"
    assert result["rows_in"] == 2
    assert result["reject_count"] == 0
    assert result["review_count"] == 0
    assert con.execute("SELECT count(*) FROM raw_pdf").fetchone()[0] == 2
    typed = con.execute(
        """
        SELECT typed_value
        FROM extracted_fields
        WHERE run_id = ? AND field_name = 'amount'
        ORDER BY row_id
        """,
        [result["run_id"]],
    ).fetchall()
    assert [row[0] for row in typed] == [10.0, 20.0]


def test_low_confidence_pdf_rows_go_to_review(tmp_path, con: duckdb.DuckDBPyConnection) -> None:
    path = tmp_path / "sparse.pdf"
    _write_table_pdf(
        path,
        [
            ["material_id", "amount", "note"],
            ["C1", "", ""],
            ["C2", "15", "ok"],
        ],
    )

    result = ingest_pdf_tables_tracked(con, "raw_pdf_review", str(path))

    assert result["review_count"] >= 1
    assert result["reject_count"] >= 1
    reason = con.execute(
        "SELECT reason FROM ingestion_rejects WHERE run_id = ?",
        [result["run_id"]],
    ).fetchone()[0]
    assert reason == "low_confidence_pdf_row"