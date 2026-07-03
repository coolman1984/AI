from __future__ import annotations

import duckdb
import pytest

from engines.data.ingest import get_connection, init_ingestion_schema
from engines.data.query_readiness import (
    build_cross_source_fixture,
    ingest_cross_source_fixture,
    run_query_readiness_demo,
    sum_by_source_type,
    sum_typed_amounts,
    verify_cross_source_calculation,
)


@pytest.fixture
def con() -> duckdb.DuckDBPyConnection:
    connection = get_connection()
    init_ingestion_schema(connection)
    return connection


def test_cross_source_fixture_supports_exact_sql_sum(tmp_path, con: duckdb.DuckDBPyConnection) -> None:
    paths = build_cross_source_fixture(tmp_path)
    ingest_cross_source_fixture(con, paths)

    assert sum_typed_amounts(con) == 300.0
    by_source = sum_by_source_type(con)
    assert by_source["csv"] == 150.0
    assert by_source["excel"] == 100.0
    assert by_source["pdf_table"] == 50.0


def test_verify_cross_source_calculation_uses_typed_values_not_raw_casts(
    tmp_path,
    con: duckdb.DuckDBPyConnection,
) -> None:
    paths = build_cross_source_fixture(tmp_path)
    ingest_cross_source_fixture(con, paths)

    verification = verify_cross_source_calculation(con)

    assert verification["typed_total"] == 300.0
    assert verification["uses_typed_values_only"] is True
    assert verification["raw_text_cast_total"] != 300.0


def test_run_query_readiness_demo_reports_ready(tmp_path) -> None:
    result = run_query_readiness_demo(tmp_path)

    assert result["ready"] is True
    assert result["expected_total"] == 300.0
    assert result["typed_total"] == 300.0