"""Ingest: land raw files text-first into DuckDB (MASTER_PLAN C.1 / Part L Phase 1).

Text-first (all_varchar) so Excel/SAP type guesses never silently corrupt data. A global
__row_id is attached so any reject can be traced to its origin row.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime

import duckdb

from shared.contracts.models import RejectRecord


INIT_INGESTION_SCHEMA_SQL = """
CREATE SEQUENCE IF NOT EXISTS ingestion_run_seq START 1;
CREATE SEQUENCE IF NOT EXISTS ingestion_reject_seq START 1;

CREATE TABLE IF NOT EXISTS ingestion_runs (
    run_id INTEGER PRIMARY KEY DEFAULT nextval('ingestion_run_seq'),
    source_type VARCHAR NOT NULL,
    source_path VARCHAR NOT NULL,
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
"""


def get_connection() -> duckdb.DuckDBPyConnection:
    return duckdb.connect()  # in-memory staging for the demo; file-backed in production


def init_ingestion_schema(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(INIT_INGESTION_SCHEMA_SQL)


def start_ingestion_run(
    con: duckdb.DuckDBPyConnection,
    source_type: str,
    source_path: str,
) -> int:
    row = con.execute(
        "INSERT INTO ingestion_runs (source_type, source_path) VALUES (?, ?) RETURNING run_id",
        [source_type, source_path],
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
