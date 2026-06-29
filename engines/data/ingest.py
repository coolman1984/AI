"""Ingest: land raw files text-first into DuckDB (MASTER_PLAN C.1 / Part L Phase 1).

Text-first (all_varchar) so Excel/SAP type guesses never silently corrupt data. A global
__row_id is attached so any reject can be traced to its origin row.
"""
from __future__ import annotations

import duckdb


def get_connection() -> duckdb.DuckDBPyConnection:
    return duckdb.connect()  # in-memory staging for the demo; file-backed in production


def ingest_csv(con: duckdb.DuckDBPyConnection, table: str, path: str) -> int:
    """Load a CSV as text-first into DuckDB with a global row id. Returns row count."""
    con.execute(
        f"CREATE OR REPLACE TABLE {table} AS "
        f"SELECT *, row_number() OVER () AS __row_id "
        f"FROM read_csv_auto(?, all_varchar=true)",
        [path],
    )
    return con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
