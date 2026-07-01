from __future__ import annotations

import csv

import duckdb
import pytest

from engines.data.ingest import (
    finish_ingestion_run,
    get_connection,
    init_ingestion_schema,
    ingest_csv,
    insert_ingestion_rejects,
    start_ingestion_run,
)
from shared.contracts.models import RejectRecord


@pytest.fixture
def con() -> duckdb.DuckDBPyConnection:
    c = get_connection()
    init_ingestion_schema(c)
    return c


def test_init_creates_expected_tables(con: duckdb.DuckDBPyConnection) -> None:
    tables = con.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'main' ORDER BY table_name"
    ).fetchall()
    names = {r[0] for r in tables}
    assert "ingestion_rejects" in names
    assert "ingestion_runs" in names


def test_ingestion_runs_columns(con: duckdb.DuckDBPyConnection) -> None:
    cols = con.execute(
        "SELECT column_name, is_nullable FROM information_schema.columns "
        "WHERE table_name = 'ingestion_runs'"
    ).fetchall()
    col_map = {r[0]: r[1] for r in cols}
    for required, nullable in [
        ("run_id", "NO"),
        ("source_type", "NO"),
        ("source_path", "NO"),
        ("status", "NO"),
        ("rows_in", "YES"),
        ("reject_count", "YES"),
        ("started_at", "YES"),
        ("completed_at", "YES"),
    ]:
        assert col_map.get(required) == nullable, f"{required} column wrong"


def test_ingestion_rejects_columns(con: duckdb.DuckDBPyConnection) -> None:
    cols = con.execute(
        "SELECT column_name, is_nullable FROM information_schema.columns "
        "WHERE table_name = 'ingestion_rejects'"
    ).fetchall()
    col_map = {r[0]: r[1] for r in cols}
    for required, nullable in [
        ("reject_id", "NO"),
        ("run_id", "NO"),
        ("row_id", "NO"),
        ("reason", "NO"),
        ("raw_json", "YES"),
    ]:
        assert col_map.get(required) == nullable, f"{required} column wrong"


def test_start_returns_monotonic_ids(con: duckdb.DuckDBPyConnection) -> None:
    id1 = start_ingestion_run(con, "csv", "data/a.csv")
    id2 = start_ingestion_run(con, "excel", "data/b.xlsx")
    assert isinstance(id1, int) and id1 > 0
    assert id2 > id1


def test_start_persists_metadata(con: duckdb.DuckDBPyConnection) -> None:
    run_id = start_ingestion_run(con, "pdf_table", "data/r.pdf")
    row = con.execute(
        "SELECT source_type, source_path, status FROM ingestion_runs WHERE run_id = ?",
        [run_id],
    ).fetchone()
    assert row == ("pdf_table", "data/r.pdf", "pending")


def test_finish_updates_counts_and_status(con: duckdb.DuckDBPyConnection) -> None:
    run_id = start_ingestion_run(con, "csv", "data/z.csv")
    finish_ingestion_run(con, run_id, rows_in=42, reject_count=3, status="completed")
    row = con.execute(
        "SELECT status, rows_in, reject_count FROM ingestion_runs WHERE run_id = ?",
        [run_id],
    ).fetchone()
    assert row == ("completed", 42, 3)


def test_finish_with_nonexistent_run_raises(con: duckdb.DuckDBPyConnection) -> None:
    with pytest.raises(ValueError, match="run_id.*not found"):
        finish_ingestion_run(con, run_id=999, rows_in=0, reject_count=0)


def test_insert_and_read_rejects(con: duckdb.DuckDBPyConnection) -> None:
    run_id = start_ingestion_run(con, "csv", "data/r.csv")
    rejects = [
        RejectRecord(row_id=1, reason="unparseable_amount", raw={"amt": "xyz"}),
        RejectRecord(row_id=5, reason="duplicate", raw={"amt": "100"}, amount=100.0),
    ]
    insert_ingestion_rejects(con, run_id, rejects)
    rows = con.execute(
        "SELECT run_id, row_id, reason, raw_json FROM ingestion_rejects ORDER BY row_id"
    ).fetchall()
    assert len(rows) == 2
    assert rows[0] == (run_id, 1, "unparseable_amount", '{"amt": "xyz"}')
    assert '"amt": "100"' in rows[1][3]


def test_insert_reject_with_bad_run_id_raises(con: duckdb.DuckDBPyConnection) -> None:
    with pytest.raises(ValueError, match="run_id.*not found"):
        insert_ingestion_rejects(con, 999, [RejectRecord(1, "test", {})])


def test_ingest_csv_with_run(tmp_path, con: duckdb.DuckDBPyConnection) -> None:
    path = tmp_path / "test.csv"
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["material_id", "amount"])
        writer.writerow(["A1", "100"])
        writer.writerow(["A2", "200"])

    run_id = start_ingestion_run(con, "csv", str(path))
    n = ingest_csv(con, "raw_test", str(path), run_id=run_id)
    finish_ingestion_run(con, run_id, rows_in=n, reject_count=0, status="completed")

    row = con.execute(
        "SELECT rows_in, reject_count, status FROM ingestion_runs WHERE run_id = ?",
        [run_id],
    ).fetchone()
    assert row == (2, 0, "completed")
    count = con.execute("SELECT count(*) FROM raw_test").fetchone()[0]
    assert count == 2
