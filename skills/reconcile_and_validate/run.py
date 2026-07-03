"""SK-004 reconcile-and-validate: prove loaded data matches control totals."""


def run_reconcile(
    clean_table: str,
    control_total: float,
    duckdb_con=None,
    tolerance: float = 0.01,
    dimension: str = None,
    control_total_source: str = "owner stated",
) -> dict:
    """Reconcile a clean table against a control total.

    Args:
        clean_table: DuckDB table with cleaned data.
        control_total: Expected total from source (SAP, owner, prior report).
        duckdb_con: DuckDB connection.
        tolerance: Max acceptable delta (default 0.01).
        dimension: Optional column name for drill-down on failure.
        control_total_source: Human-readable description of where the total came from.

    Returns:
        dict with reconciliation result.
    """
    if duckdb_con is None:
        try:
            from engines.data.ingest import get_connection
            duckdb_con = get_connection()
        except Exception as e:
            return {"status": "failed", "error": f"Cannot connect to DuckDB: {e}"}

    try:
        # Try to find the amount column
        columns = duckdb_con.execute(
            f"DESCRIBE {clean_table}"
        ).fetchall()
        col_names = [row[0] for row in columns]

        # Find the amount column
        amount_col = None
        for candidate in ["amount", "actual_amount", "value", "total"]:
            if candidate in col_names:
                amount_col = candidate
                break
        if not amount_col:
            amount_col = col_names[-1] if col_names else None

        if not amount_col:
            return {
                "status": "failed",
                "error": f"Cannot find amount column in {clean_table}. "
                         f"Available: {col_names}",
            }

        # Compute sum
        actual_total = float(
            duckdb_con.execute(
                f"SELECT COALESCE(SUM({amount_col}), 0) FROM {clean_table}"
            ).fetchone()[0]
        )

        delta = abs(actual_total - control_total)
        passed = delta <= tolerance

        result = {
            "status": "done" if passed else "blocked",
            "expected": control_total,
            "actual": round(actual_total, 2),
            "delta": round(delta, 2),
            "tolerance": tolerance,
            "gate_passed": passed,
            "amount_column": amount_col,
            "control_total_source": control_total_source,
            "rows_checked": duckdb_con.execute(
                f"SELECT COUNT(*) FROM {clean_table}"
            ).fetchone()[0],
        }

        if not passed:
            message_parts = [
                f"Reconciliation FAILED: delta {delta:.2f} > tolerance {tolerance}",
                f"Expected: {control_total}, Actual: {actual_total:.2f}",
            ]

            # Drill down by dimension if provided
            if dimension and dimension in col_names:
                drill = duckdb_con.execute(
                    f"SELECT {dimension}, SUM({amount_col}) as total "
                    f"FROM {clean_table} "
                    f"GROUP BY {dimension} "
                    f"ORDER BY total DESC LIMIT 10"
                ).fetchall()
                drill_rows = [
                    {"dimension": row[0], "total": round(float(row[1]), 2)}
                    for row in drill
                ]
                result["drill_down"] = drill_rows
                message_parts.append(
                    f"Top dimensions: {drill_rows[:3]}"
                )

            result["message"] = " | ".join(message_parts)
        else:
            result["message"] = (
                f"Reconciliation PASSED: delta {delta:.2f} within tolerance {tolerance}"
            )

        return result

    except Exception as e:
        return {"status": "failed", "error": f"Reconciliation failed: {e}"}
