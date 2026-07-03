"""Ingest: land raw files text-first into DuckDB (MASTER_PLAN C.1 / Part L Phase 1).

Text-first (all_varchar) so Excel/SAP type guesses never silently corrupt data. A global
__row_id is attached so any reject can be traced to its origin row.
"""
from __future__ import annotations

import json
from datetime import UTC, date, datetime

import duckdb
import polars as pl

from engines.data.clean import TOTAL_LABELS
from engines.data.types import (
    FieldType,
    coerce_typed_value,
    infer_column_types,
    raw_field_value,
)
from shared.contracts.models import RejectRecord

INIT_INGESTION_SCHEMA_SQL = """
CREATE SEQUENCE IF NOT EXISTS ingestion_run_seq START 1;
CREATE SEQUENCE IF NOT EXISTS ingestion_reject_seq START 1;

CREATE TABLE IF NOT EXISTS ingestion_runs (
    run_id INTEGER PRIMARY KEY DEFAULT nextval('ingestion_run_seq'),
    source_type VARCHAR NOT NULL,
    source_path VARCHAR NOT NULL,
    source_sheet VARCHAR,
    status VARCHAR NOT NULL DEFAULT 'pending',
    rows_in INTEGER,
    reject_count INTEGER,
    started_at TIMESTAMP DEFAULT now(),
    completed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ingestion_rejects (
    reject_id INTEGER PRIMARY KEY DEFAULT nextval('ingestion_reject_seq'),
    run_id INTEGER NOT NULL,
    row_id INTEGER NOT NULL,
    reason VARCHAR NOT NULL,
    raw_json VARCHAR,
    amount DOUBLE
);

CREATE TABLE IF NOT EXISTS extracted_fields (
    run_id INTEGER NOT NULL,
    row_id INTEGER NOT NULL,
    field_name VARCHAR NOT NULL,
    field_value VARCHAR NOT NULL,
    field_type VARCHAR NOT NULL,
    typed_value DOUBLE,
    date_value DATE,
    PRIMARY KEY (run_id, row_id, field_name)
);
"""


def get_connection() -> duckdb.DuckDBPyConnection:
    return duckdb.connect()  # in-memory staging for the demo; file-backed in production


def init_ingestion_schema(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(INIT_INGESTION_SCHEMA_SQL)
    con.execute(
        """
        ALTER TABLE ingestion_runs
        ADD COLUMN IF NOT EXISTS source_sheet VARCHAR
        """
    )


def start_ingestion_run(
    con: duckdb.DuckDBPyConnection,
    source_type: str,
    source_path: str,
    *,
    source_sheet: str | None = None,
) -> int:
    row = con.execute(
        """
        INSERT INTO ingestion_runs (source_type, source_path, source_sheet)
        VALUES (?, ?, ?)
        RETURNING run_id
        """,
        [source_type, source_path, source_sheet],
    ).fetchone()
    if row is None:
        raise RuntimeError("failed to create ingestion run")
    return int(row[0])


def finish_ingestion_run(
    con: duckdb.DuckDBPyConnection,
    run_id: int,
    *,
    rows_in: int,
    reject_count: int,
    status: str = "completed",
) -> None:
    result = con.execute(
        """
        UPDATE ingestion_runs
        SET status = ?,
            rows_in = ?,
            reject_count = ?,
            completed_at = ?
        WHERE run_id = ?
        RETURNING run_id
        """,
        [status, rows_in, reject_count, datetime.now(UTC), run_id],
    ).fetchone()
    if result is None:
        raise ValueError(f"run_id {run_id} not found")


def insert_ingestion_rejects(
    con: duckdb.DuckDBPyConnection,
    run_id: int,
    rejects: list[RejectRecord],
) -> int:
    exists = con.execute(
        "SELECT 1 FROM ingestion_runs WHERE run_id = ?",
        [run_id],
    ).fetchone()
    if exists is None:
        raise ValueError(f"run_id {run_id} not found")

    for reject in rejects:
        con.execute(
            """
            INSERT INTO ingestion_rejects (run_id, row_id, reason, raw_json, amount)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                run_id,
                reject.row_id,
                reject.reason,
                json.dumps(reject.raw, ensure_ascii=False),
                reject.amount,
            ],
        )
    return len(rejects)


def ingest_csv(
    con: duckdb.DuckDBPyConnection,
    table: str,
    path: str,
    run_id: int | None = None,
) -> int:
    """Load a CSV as text-first into DuckDB with a global row id. Returns row count.

    `run_id` is accepted so source adapters can participate in the unified ingestion spine.
    Count ownership stays with the caller, which passes the final counts to finish_ingestion_run.
    """
    _ = run_id
    con.execute(
        f"CREATE OR REPLACE TABLE {table} AS "
        f"SELECT *, row_number() OVER () AS __row_id "
        f"FROM read_csv_auto(?, all_varchar=true)",
        [path],
    )
    return con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _sanitize_column_name(name: str, index: int) -> str:
    text = str(name).strip() if name is not None else ""
    if text == "":
        return f"col_{index}"
    return text


def list_excel_sheets(path: str) -> list[str]:
    import openpyxl

    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        return list(workbook.sheetnames)
    finally:
        workbook.close()


def _load_excel_sheet_to_staging(
    con: duckdb.DuckDBPyConnection,
    staging: str,
    path: str,
    *,
    sheet_name: str,
) -> int:
    import openpyxl

    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        worksheet = workbook[sheet_name]
        row_iter = worksheet.iter_rows(values_only=True)
        try:
            header_row = next(row_iter)
        except StopIteration:
            con.execute(
                f"CREATE OR REPLACE TABLE {staging} (__row_id INTEGER)"
            )
            return 0

        columns = [
            _sanitize_column_name(header_row[idx], idx)
            for idx in range(len(header_row))
        ]
        records: list[dict[str, str | None]] = []
        for row in row_iter:
            if row is None:
                continue
            values = list(row)
            if all(value is None or str(value).strip() == "" for value in values):
                continue
            record = {
                columns[idx]: None if idx >= len(values) or values[idx] is None else str(values[idx])
                for idx in range(len(columns))
            }
            records.append(record)

        if not records:
            frame = pl.DataFrame({column: [] for column in columns})
        else:
            frame = pl.DataFrame(records, schema_overrides={column: pl.Utf8 for column in columns})

        con.register("__excel_frame", frame)
        con.execute(
            f"""
            CREATE OR REPLACE TABLE {staging} AS
            SELECT *, row_number() OVER () AS __row_id
            FROM __excel_frame
            """
        )
        con.unregister("__excel_frame")
        return con.execute(f"SELECT count(*) FROM {staging}").fetchone()[0]
    finally:
        workbook.close()


def ingest_excel_sheet(
    con: duckdb.DuckDBPyConnection,
    table: str,
    path: str,
    *,
    sheet_name: str,
    run_id: int | None = None,
) -> int:
    """Load one Excel sheet as text-first into DuckDB with a global row id."""
    _ = run_id
    return _load_excel_sheet_to_staging(con, table, path, sheet_name=sheet_name)


def _is_total_row(fields: dict) -> bool:
    """A row is a subtotal/grand-total row if any cell matches a known total label.

    Column-name-agnostic (the generic spine doesn't know which column is the key),
    unlike `clean.clean_actuals` which also excludes rows with a blank key column.
    """
    return any(str(v).strip().lower() in TOTAL_LABELS for v in fields.values() if v is not None)


def _staging_data_columns(con: duckdb.DuckDBPyConnection, staging: str) -> list[str]:
    columns = [
        row[1]
        for row in con.execute(f"PRAGMA table_info('{staging}')").fetchall()
    ]
    return [column for column in columns if column != "__row_id"]


def _persist_extracted_fields(
    con: duckdb.DuckDBPyConnection,
    *,
    run_id: int,
    data_cols: list[str],
    column_types: dict[str, FieldType],
    rows: list[tuple],
) -> None:
    for row in rows:
        row_id = int(row[0])
        for idx, column in enumerate(data_cols):
            raw = row[idx + 1]
            field_type = column_types[column]
            typed_value: float | None = None
            date_value: date | None = None
            if field_type in {"numeric", "date"}:
                typed_value, date_value = coerce_typed_value(raw, field_type)
            con.execute(
                """
                INSERT INTO extracted_fields (
                    run_id, row_id, field_name, field_value, field_type, typed_value, date_value
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    run_id,
                    row_id,
                    column,
                    raw_field_value(raw),
                    field_type,
                    typed_value,
                    date_value,
                ],
            )


def _ingest_staging_tracked(
    con: duckdb.DuckDBPyConnection,
    table: str,
    staging: str,
    *,
    source_type: str,
    source_path: str,
    source_sheet: str | None = None,
    on_duplicates: str = "flag",
    infer_types: bool = False,
) -> dict:
    if on_duplicates not in {"flag", "drop"}:
        raise ValueError("on_duplicates must be 'flag' or 'drop'")

    run_id = start_ingestion_run(
        con,
        source_type,
        source_path,
        source_sheet=source_sheet,
    )
    rows_in = con.execute(f"SELECT count(*) FROM {staging}").fetchone()[0]
    data_cols = _staging_data_columns(con, staging)
    quoted_cols = [_quote_ident(column) for column in data_cols]
    total_labels = ", ".join(f"'{label}'" for label in sorted(TOTAL_LABELS))
    total_predicate = " OR ".join(
        [
            f"lower(trim(COALESCE(CAST({_quote_ident(column)} AS VARCHAR), ''))) IN ({total_labels})"
            for column in data_cols
        ]
    )
    duplicate_partition = ", ".join(quoted_cols)

    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE __annotated_ingest AS
        SELECT
            *,
            CASE
                WHEN {total_predicate} THEN TRUE
                ELSE FALSE
            END AS __is_total_row,
            row_number() OVER (PARTITION BY {duplicate_partition} ORDER BY __row_id) AS __dup_rank
        FROM {staging}
        """
    )

    duplicate_count = con.execute(
        "SELECT count(*) FROM __annotated_ingest WHERE NOT __is_total_row AND __dup_rank > 1"
    ).fetchone()[0]

    reject_where = "__is_total_row"
    if on_duplicates == "drop":
        reject_where = f"{reject_where} OR __dup_rank > 1"

    type_rejects: list[RejectRecord] = []
    column_types: dict[str, FieldType] = {}
    if infer_types and rows_in > 0:
        sample_rows = con.execute(
            f"""
            SELECT __row_id, {", ".join(quoted_cols)}
            FROM __annotated_ingest
            WHERE NOT ({reject_where})
            ORDER BY __row_id
            """
        ).fetchall()
        sample_dicts = [
            {column: row[idx + 1] for idx, column in enumerate(data_cols)}
            for row in sample_rows
        ]
        column_types = infer_column_types(data_cols, sample_dicts)

        typed_keep_ids: list[int] = []
        for row in sample_rows:
            row_id = int(row[0])
            fields = {column: row[idx + 1] for idx, column in enumerate(data_cols)}
            reject_reason: str | None = None
            for column, field_type in column_types.items():
                if field_type not in {"numeric", "date"}:
                    continue
                raw = fields.get(column)
                if raw is None or str(raw).strip() == "":
                    continue
                try:
                    coerce_typed_value(raw, field_type)
                except (ValueError, TypeError):
                    reject_reason = f"unconvertible_{column}"
                    break
            if reject_reason is None:
                typed_keep_ids.append(row_id)
            else:
                reject_payload = dict(fields)
                if source_sheet is not None:
                    reject_payload["source_sheet"] = source_sheet
                type_rejects.append(
                    RejectRecord(row_id, reject_reason, reject_payload)
                )

        if typed_keep_ids:
            id_list = ", ".join(str(row_id) for row_id in typed_keep_ids)
            keep_filter = f"__row_id IN ({id_list})"
        else:
            keep_filter = "FALSE"

        con.execute(
            f"""
            CREATE OR REPLACE TABLE {table} AS
            SELECT *
            EXCLUDE (__is_total_row, __dup_rank)
            FROM __annotated_ingest
            WHERE NOT ({reject_where}) AND {keep_filter}
            ORDER BY __row_id
            """
        )
    else:
        con.execute(
            f"""
            CREATE OR REPLACE TABLE {table} AS
            SELECT *
            EXCLUDE (__is_total_row, __dup_rank)
            FROM __annotated_ingest
            WHERE NOT ({reject_where})
            ORDER BY __row_id
            """
        )

    reject_rows = con.execute(
        f"""
        SELECT
            __row_id,
            CASE
                WHEN __is_total_row THEN 'total_row'
                WHEN __dup_rank > 1 THEN 'duplicate'
            END AS reason,
            {", ".join(quoted_cols)}
        FROM __annotated_ingest
        WHERE {reject_where}
        ORDER BY __row_id
        """
    ).fetchall()

    rejects: list[RejectRecord] = []
    for row in reject_rows:
        row_id = int(row[0])
        reason = str(row[1])
        fields = {column: row[idx + 2] for idx, column in enumerate(data_cols)}
        if source_sheet is not None:
            fields["source_sheet"] = source_sheet
        if _is_total_row(fields):
            reason = "total_row"
        rejects.append(RejectRecord(row_id, reason, fields))

    rejects.extend(type_rejects)

    if infer_types and column_types:
        kept_rows = con.execute(
            f"SELECT __row_id, {', '.join(quoted_cols)} FROM {table} ORDER BY __row_id"
        ).fetchall()
        if kept_rows:
            _persist_extracted_fields(
                con,
                run_id=run_id,
                data_cols=data_cols,
                column_types=column_types,
                rows=kept_rows,
            )

    con.execute("DROP TABLE __annotated_ingest")
    con.execute(f"DROP TABLE {staging}")

    if rejects:
        insert_ingestion_rejects(con, run_id, rejects)
    finish_ingestion_run(con, run_id, rows_in=rows_in, reject_count=len(rejects))

    return {
        "run_id": run_id,
        "source_type": source_type,
        "source_path": source_path,
        "source_sheet": source_sheet,
        "rows_in": rows_in,
        "reject_count": len(rejects),
        "duplicate_count": duplicate_count,
        "on_duplicates": on_duplicates,
        "infer_types": infer_types,
        "column_types": column_types,
        "status": "completed",
    }


def ingest_csv_tracked(
    con: duckdb.DuckDBPyConnection,
    table: str,
    path: str,
    *,
    source_type: str = "csv",
    on_duplicates: str = "flag",
    infer_types: bool = False,
) -> dict:
    """Ingest a CSV into a target table with a tracked run lifecycle.

    Quarantines embedded total/subtotal rows before they land in `table`.
    Exact duplicates are flagged by default and only quarantined when
    `on_duplicates="drop"`. Conservation law: rows_in == kept + rejected.
    """
    staging = f"__staging_{table}"
    ingest_csv(con, staging, path)
    return _ingest_staging_tracked(
        con,
        table,
        staging,
        source_type=source_type,
        source_path=path,
        on_duplicates=on_duplicates,
        infer_types=infer_types,
    )


def ingest_excel_sheet_tracked(
    con: duckdb.DuckDBPyConnection,
    table: str,
    path: str,
    *,
    sheet_name: str,
    on_duplicates: str = "flag",
    infer_types: bool = False,
) -> dict:
    """Ingest one Excel sheet with tracked run context and reject flow."""
    staging = f"__staging_{table}"
    ingest_excel_sheet(con, staging, path, sheet_name=sheet_name)
    return _ingest_staging_tracked(
        con,
        table,
        staging,
        source_type="excel",
        source_path=path,
        source_sheet=sheet_name,
        on_duplicates=on_duplicates,
        infer_types=infer_types,
    )


def ingest_excel_tracked(
    con: duckdb.DuckDBPyConnection,
    table_prefix: str,
    path: str,
    *,
    on_duplicates: str = "flag",
    infer_types: bool = False,
) -> dict:
    """Ingest every sheet in a workbook with one tracked run per sheet."""
    sheet_results: list[dict] = []
    for sheet_name in list_excel_sheets(path):
        safe_sheet = "".join(ch if ch.isalnum() else "_" for ch in sheet_name)
        table_name = f"{table_prefix}_{safe_sheet}"
        sheet_results.append(
            ingest_excel_sheet_tracked(
                con,
                table_name,
                path,
                sheet_name=sheet_name,
                on_duplicates=on_duplicates,
                infer_types=infer_types,
            )
        )

    return {
        "source_type": "excel",
        "source_path": path,
        "sheet_count": len(sheet_results),
        "sheets": sheet_results,
        "rows_in": sum(result["rows_in"] for result in sheet_results),
        "reject_count": sum(result["reject_count"] for result in sheet_results),
        "status": "completed",
    }


def ingest_spreadsheet(
    con: duckdb.DuckDBPyConnection,
    table: str,
    path: str,
    *,
    on_duplicates: str = "flag",
    infer_types: bool = False,
) -> dict:
    """Dispatch CSV or Excel ingestion through the tracked spine."""
    lowered = path.lower()
    if lowered.endswith(".csv"):
        return ingest_csv_tracked(
            con,
            table,
            path,
            on_duplicates=on_duplicates,
            infer_types=infer_types,
        )
    if lowered.endswith((".xlsx", ".xlsm", ".xltx", ".xltm")):
        return ingest_excel_tracked(
            con,
            table,
            path,
            on_duplicates=on_duplicates,
            infer_types=infer_types,
        )
    raise ValueError(f"unsupported spreadsheet format: {path}")