from __future__ import annotations

import csv

import duckdb
import pytest

from engines.data.ingest import (
    finish_ingestion_run,
    get_connection,
    ingest_csv,
    ingest_csv_tracked,
    init_ingestion_schema,
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


def test_ingest_csv_tracked_happy_path(tmp_path, con: duckdb.DuckDBPyConnection) -> None:
    path = tmp_path / "data.csv"
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "val"])
        writer.writerow(["1", "10"])
        writer.writerow(["2", "20"])
        writer.writerow(["3", "30"])

    result = ingest_csv_tracked(con, "raw_tracked", str(path))

    assert result["status"] == "completed"
    assert result["rows_in"] == 3
    assert result["reject_count"] == 0
    assert result["source_type"] == "csv"
    assert result["source_path"] == str(path)
    assert isinstance(result["run_id"], int) and result["run_id"] > 0


def test_ingest_csv_tracked_persists_run(tmp_path, con: duckdb.DuckDBPyConnection) -> None:
    path = tmp_path / "persist.csv"
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["x"])
        writer.writerow(["a"])
        writer.writerow(["b"])

    result = ingest_csv_tracked(con, "raw_persist", str(path))

    row = con.execute(
        "SELECT run_id, source_type, source_path, status, rows_in, reject_count "
        "FROM ingestion_runs WHERE run_id = ?",
        [result["run_id"]],
    ).fetchone()
    assert row is not None
    assert row[0] == result["run_id"]
    assert row[1] == "csv"
    assert row[2] == str(path)
    assert row[3] == "completed"
    assert row[4] == 2
    assert row[5] == 0


def test_ingest_csv_tracked_multiple_invocations(tmp_path, con: duckdb.DuckDBPyConnection) -> None:
    path_a = tmp_path / "a.csv"
    path_b = tmp_path / "b.csv"
    path_a.write_text("x\n1\n2\n")
    path_b.write_text("x\n3\n4\n5\n")

    result_a = ingest_csv_tracked(con, "raw_multi_a", str(path_a))
    result_b = ingest_csv_tracked(con, "raw_multi_b", str(path_b))

    assert result_a["run_id"] != result_b["run_id"]
    assert result_a["rows_in"] == 2
    assert result_b["rows_in"] == 3
    assert con.execute("SELECT count(*) FROM raw_multi_a").fetchone()[0] == 2
    assert con.execute("SELECT count(*) FROM raw_multi_b").fetchone()[0] == 3


def test_ingest_csv_tracked_rejects_embedded_total_row(
    tmp_path, con: duckdb.DuckDBPyConnection
) -> None:
    path = tmp_path / "with_total.csv"
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["material_id", "amount"])
        writer.writerow(["A1", "100"])
        writer.writerow(["Total", "100"])  # embedded subtotal row -> must be excluded
        writer.writerow(["A2", "200"])

    result = ingest_csv_tracked(con, "raw_with_total", str(path))

    assert result["rows_in"] == 3
    assert result["reject_count"] == 1
    assert con.execute("SELECT count(*) FROM raw_with_total").fetchone()[0] == 2
    reason = con.execute(
        "SELECT reason FROM ingestion_rejects WHERE run_id = ?", [result["run_id"]]
    ).fetchone()[0]
    assert reason == "total_row"


def test_ingest_csv_tracked_rejects_duplicate_row(
    tmp_path, con: duckdb.DuckDBPyConnection
) -> None:
    path = tmp_path / "with_dupe.csv"
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["material_id", "amount"])
        writer.writerow(["A1", "100"])
        writer.writerow(["A2", "200"])
        writer.writerow(["A1", "100"])  # exact duplicate of the first data row

    result = ingest_csv_tracked(con, "raw_with_dupe", str(path))

    assert result["rows_in"] == 3
    assert result["reject_count"] == 1
    assert con.execute("SELECT count(*) FROM raw_with_dupe").fetchone()[0] == 2
    reason = con.execute(
        "SELECT reason FROM ingestion_rejects WHERE run_id = ?", [result["run_id"]]
    ).fetchone()[0]
    assert reason == "duplicate"


def test_ingest_csv_tracked_conserves_rows(tmp_path, con: duckdb.DuckDBPyConnection) -> None:
    path = tmp_path / "mixed.csv"
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["material_id", "amount"])
        writer.writerow(["A1", "100"])
        writer.writerow(["Total", "100"])
        writer.writerow(["A2", "200"])
        writer.writerow(["A2", "200"])  # duplicate

    result = ingest_csv_tracked(con, "raw_mixed", str(path))

    kept = con.execute("SELECT count(*) FROM raw_mixed").fetchone()[0]
    assert result["rows_in"] == kept + result["reject_count"]
    assert result["reject_count"] == 2
