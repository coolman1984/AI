"""PDF table extraction for the unified ingestion spine (IS3).

Extracts structured table rows from PDFs, scores confidence, and routes low-trust
rows through the same tracked ingestion lifecycle as CSV/Excel sources.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import duckdb
import fitz

from engines.data.ingest import (
    _ingest_staging_tracked,
    init_ingestion_schema,
    start_ingestion_run,
)
from shared.contracts.models import RejectRecord

REVIEW_CONFIDENCE_THRESHOLD = 0.75


@dataclass(frozen=True)
class PdfTableRow:
    page_no: int
    table_index: int
    row_index: int
    fields: dict[str, str]
    confidence: float
    needs_review: bool


@dataclass
class PdfTableExtraction:
    page_no: int
    table_index: int
    headers: list[str]
    rows: list[PdfTableRow] = field(default_factory=list)


def _normalize_header(value: str | None, index: int) -> str:
    text = str(value).strip() if value is not None else ""
    if text == "":
        return f"col_{index}"
    return text


def _row_confidence(cells: list[str]) -> float:
    if not cells:
        return 0.0
    non_empty = sum(1 for cell in cells if str(cell).strip() != "")
    fill_ratio = non_empty / len(cells)
    if non_empty == 0:
        return 0.0
    return round(min(1.0, 0.5 + 0.5 * fill_ratio), 3)


def extract_pdf_tables(path: str) -> list[PdfTableExtraction]:
    """Extract structured rows from every table found in a PDF."""
    document = fitz.open(path)
    extractions: list[PdfTableExtraction] = []
    try:
        for page_no in range(document.page_count):
            page = document[page_no]
            tables = page.find_tables()
            for table_index, table in enumerate(tables.tables):
                raw_rows = table.extract()
                if not raw_rows:
                    continue
                headers = [
                    _normalize_header(raw_rows[0][idx], idx)
                    for idx in range(len(raw_rows[0]))
                ]
                extraction = PdfTableExtraction(
                    page_no=page_no + 1,
                    table_index=table_index,
                    headers=headers,
                )
                for row_offset, raw_row in enumerate(raw_rows[1:], start=1):
                    cells = [
                        "" if idx >= len(raw_row) or raw_row[idx] is None else str(raw_row[idx]).strip()
                        for idx in range(len(headers))
                    ]
                    if all(cell == "" for cell in cells):
                        continue
                    confidence = _row_confidence(cells)
                    fields = {headers[idx]: cells[idx] for idx in range(len(headers))}
                    extraction.rows.append(
                        PdfTableRow(
                            page_no=page_no + 1,
                            table_index=table_index,
                            row_index=row_offset,
                            fields=fields,
                            confidence=confidence,
                            needs_review=confidence < REVIEW_CONFIDENCE_THRESHOLD,
                        )
                    )
                if extraction.rows:
                    extractions.append(extraction)
    finally:
        document.close()
    return extractions


def _load_pdf_rows_to_staging(
    con: duckdb.DuckDBPyConnection,
    staging: str,
    rows: list[PdfTableRow],
    headers: list[str],
) -> int:
    if not rows:
        con.execute(
            f"CREATE OR REPLACE TABLE {staging} (__row_id INTEGER)"
        )
        return 0

    import polars as pl

    records = [row.fields for row in rows]
    frame = pl.DataFrame(records, schema_overrides={header: pl.Utf8 for header in headers})
    con.register("__pdf_frame", frame)
    con.execute(
        f"""
        CREATE OR REPLACE TABLE {staging} AS
        SELECT *, row_number() OVER () AS __row_id
        FROM __pdf_frame
        """
    )
    con.unregister("__pdf_frame")
    return con.execute(f"SELECT count(*) FROM {staging}").fetchone()[0]


def ingest_pdf_tables_tracked(
    con: duckdb.DuckDBPyConnection,
    table: str,
    path: str,
    *,
    infer_types: bool = True,
) -> dict:
    """Load accepted PDF table rows into the tracked ingestion spine."""
    init_ingestion_schema(con)
    extractions = extract_pdf_tables(path)
    if not extractions:
        run_id = start_ingestion_run(con, "pdf_table", path)
        from engines.data.ingest import finish_ingestion_run

        finish_ingestion_run(con, run_id, rows_in=0, reject_count=0)
        return {
            "run_id": run_id,
            "source_type": "pdf_table",
            "source_path": path,
            "rows_in": 0,
            "reject_count": 0,
            "review_count": 0,
            "status": "completed",
            "tables_found": 0,
        }

    headers = extractions[0].headers
    accepted_rows: list[PdfTableRow] = []
    review_rows: list[PdfTableRow] = []
    for extraction in extractions:
        for row in extraction.rows:
            if row.needs_review:
                review_rows.append(row)
            else:
                accepted_rows.append(row)

    staging = f"__staging_{table}"
    _load_pdf_rows_to_staging(con, staging, accepted_rows, headers)

    result = _ingest_staging_tracked(
        con,
        table,
        staging,
        source_type="pdf_table",
        source_path=path,
        infer_types=infer_types,
    )

    review_rejects: list[RejectRecord] = []
    for row in review_rows:
        review_rejects.append(
            RejectRecord(
                row_id=row.row_index,
                reason="low_confidence_pdf_row",
                raw={
                    "page_no": row.page_no,
                    "table_index": row.table_index,
                    "confidence": row.confidence,
                    **row.fields,
                },
            )
        )

    if review_rejects:
        from engines.data.ingest import insert_ingestion_rejects

        insert_ingestion_rejects(con, result["run_id"], review_rejects)
        result["reject_count"] += len(review_rejects)
        con.execute(
            """
            UPDATE ingestion_runs
            SET reject_count = ?
            WHERE run_id = ?
            """,
            [result["reject_count"], result["run_id"]],
        )

    result["review_count"] = len(review_rows)
    result["tables_found"] = len(extractions)
    return result