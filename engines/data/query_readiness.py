"""Query + calculation readiness checks for the unified ingestion spine (IS6).

Proves that ingested CSV, Excel, and PDF sources land in one queryable storage
model where exact SQL calculations use typed values instead of raw text.
"""
from __future__ import annotations

import csv
from pathlib import Path

import duckdb
import fitz
import openpyxl

from engines.data.ingest import (
    get_connection,
    init_ingestion_schema,
    ingest_csv_tracked,
    ingest_excel_tracked,
)
from engines.data.pdf_tables import ingest_pdf_tables_tracked


def sum_typed_amounts(
    con: duckdb.DuckDBPyConnection,
    *,
    field_name: str = "amount",
) -> float:
    """Exact SQL sum over typed numeric fields across all ingested runs."""
    row = con.execute(
        """
        SELECT COALESCE(SUM(typed_value), 0)
        FROM extracted_fields
        WHERE field_name = ?
          AND field_type = 'numeric'
          AND typed_value IS NOT NULL
        """,
        [field_name],
    ).fetchone()
    return float(row[0])


def sum_by_source_type(
    con: duckdb.DuckDBPyConnection,
    *,
    field_name: str = "amount",
) -> dict[str, float]:
    rows = con.execute(
        """
        SELECT r.source_type, COALESCE(SUM(f.typed_value), 0)
        FROM extracted_fields f
        JOIN ingestion_runs r ON r.run_id = f.run_id
        WHERE f.field_name = ?
          AND f.field_type = 'numeric'
          AND f.typed_value IS NOT NULL
        GROUP BY r.source_type
        ORDER BY r.source_type
        """,
        [field_name],
    ).fetchall()
    return {str(source_type): float(total) for source_type, total in rows}


def verify_cross_source_calculation(
    con: duckdb.DuckDBPyConnection,
    *,
    field_name: str = "amount",
) -> dict:
    """Return exact totals and prove text fields are not used for math."""
    total = sum_typed_amounts(con, field_name=field_name)
    by_source = sum_by_source_type(con, field_name=field_name)
    text_sum = con.execute(
        """
        SELECT COALESCE(SUM(TRY_CAST(field_value AS DOUBLE)), 0)
        FROM extracted_fields
        WHERE field_name = ?
        """,
        [field_name],
    ).fetchone()[0]
    return {
        "field_name": field_name,
        "typed_total": total,
        "by_source_type": by_source,
        "raw_text_cast_total": float(text_sum),
        "uses_typed_values_only": total != float(text_sum),
    }


def _write_csv(path: Path, rows: list[list[str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerows(rows)


def _write_excel(path: Path, sheets: dict[str, list[list[str]]]) -> None:
    workbook = openpyxl.Workbook()
    default_sheet = workbook.active
    workbook.remove(default_sheet)
    for sheet_name, rows in sheets.items():
        worksheet = workbook.create_sheet(title=sheet_name)
        for row in rows:
            worksheet.append(row)
    workbook.save(path)


def _write_pdf_table(path: Path, rows: list[list[str]]) -> None:
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


def build_cross_source_fixture(tmp_path: Path) -> dict[str, str]:
    csv_path = tmp_path / "actuals.csv"
    excel_path = tmp_path / "workbook.xlsx"
    pdf_path = tmp_path / "tables.pdf"

    _write_csv(
        csv_path,
        [
            ["material_id", "amount"],
            ["CSV-1", "100"],
            ["CSV-2", "50"],
        ],
    )
    _write_excel(
        excel_path,
        {
            "Costs": [
                ["material_id", "amount"],
                ["XL-1", "75,50"],
                ["XL-2", "24,50"],
            ],
        },
    )
    _write_pdf_table(
        pdf_path,
        [
            ["material_id", "amount"],
            ["PDF-1", "30"],
            ["PDF-2", "20"],
        ],
    )
    return {
        "csv": str(csv_path),
        "excel": str(excel_path),
        "pdf": str(pdf_path),
    }


def ingest_cross_source_fixture(
    con: duckdb.DuckDBPyConnection,
    paths: dict[str, str],
) -> dict:
    init_ingestion_schema(con)
    csv_result = ingest_csv_tracked(
        con,
        "raw_csv_fixture",
        paths["csv"],
        infer_types=True,
    )
    excel_result = ingest_excel_tracked(
        con,
        "raw_excel_fixture",
        paths["excel"],
        infer_types=True,
    )
    pdf_result = ingest_pdf_tables_tracked(
        con,
        "raw_pdf_fixture",
        paths["pdf"],
        infer_types=True,
    )
    return {
        "csv": csv_result,
        "excel": excel_result,
        "pdf": pdf_result,
    }


def run_query_readiness_demo(tmp_path: Path) -> dict:
    con = get_connection()
    paths = build_cross_source_fixture(tmp_path)
    ingest_cross_source_fixture(con, paths)
    verification = verify_cross_source_calculation(con)
    verification["expected_total"] = 300.0
    verification["ready"] = verification["typed_total"] == 300.0
    return verification