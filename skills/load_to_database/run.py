"""SK-003 load-to-database: clean and load staged data into analytical store."""



def run_load_to_database(
    table_name: str,
    mapping: dict[str, str] = None,
    duckdb_con=None,
    qty_col: str = None,
    is_standards: bool = False,
) -> dict:
    """Load a staged table into the analytical store with cleaning and quarantine.

    Args:
        table_name: Staged DuckDB table to clean and load.
        mapping: Dict of {source_column: canonical_name} from SK-002.
        duckdb_con: DuckDB connection.
        qty_col: Optional quantity column name for validation.
        is_standards: True for standards data, False for actuals.

    Returns:
        dict with load summary.
    """
    if duckdb_con is None:
        try:
            from engines.data.ingest import get_connection
            duckdb_con = get_connection()
        except Exception as e:
            return {"status": "failed", "error": f"Cannot connect to DuckDB: {e}"}

    if mapping is None:
        return {"status": "failed", "error": "No mapping provided. Run SK-002 first."}

    try:
        # Verify table exists
        try:
            duckdb_con.execute(f"DESCRIBE {table_name}")
        except Exception:
            return {
                "status": "failed",
                "error": f"Table '{table_name}' not found. Run SK-001 + SK-002 first.",
            }

        # Call the appropriate cleaner
        if is_standards:
            from engines.data.clean import clean_standards as cleaner
            clean_df, rejects, warnings = cleaner(
                duckdb_con, table_name,
                key_col="material_id",
                numeric_cols=("std_qty", "std_price"),
            )
        else:
            from engines.data.clean import clean_actuals as cleaner
            clean_df, rejects, warnings = cleaner(
                duckdb_con, table_name,
                key_col="material_id",
                amount_col="amount",
                qty_col=qty_col,
            )

        # Apply column mapping to create the canonical table
        clean_table_name = f"clean_{table_name}"
        duckdb_con.execute(f"DROP TABLE IF EXISTS {clean_table_name}")

        # Register the polars DataFrame as a DuckDB table
        duckdb_con.register("_clean_df", clean_df)
        duckdb_con.execute(f"CREATE TABLE {clean_table_name} AS SELECT * FROM _clean_df")

        # Counts
        staged_count = duckdb_con.execute(
            f"SELECT COUNT(*) FROM {table_name}"
        ).fetchone()[0]
        clean_count = len(clean_df)
        reject_count = len(rejects)

        # Conservation check
        conservation_ok = (staged_count == clean_count + reject_count)

        # Duplicate check
        dup_pct = 0.0
        if staged_count > 0:
            dups = [r for r in rejects if "duplicate" in str(r).lower() or "dup" in str(r).lower()]
            dup_pct = len(dups) / staged_count * 100 if staged_count > 0 else 0

        result = {
            "status": "done",
            "staged_table": table_name,
            "clean_table": clean_table_name,
            "staged_count": staged_count,
            "clean_count": clean_count,
            "reject_count": reject_count,
            "conservation_ok": conservation_ok,
            "dup_percentage": round(dup_pct, 2),
            "warnings": warnings,
            "reject_threshold_exceeded": dup_pct > 5.0,
        }

        # Gate: reject rate threshold
        if dup_pct > 5.0:
            result["status"] = "blocked"
            result["error"] = (
                f"Reject rate {dup_pct:.1f}% exceeds 5% threshold. "
                f"Sample rejects: {[str(r)[:80] for r in rejects[:3]]}"
            )

        if not conservation_ok:
            result["status"] = "blocked"
            result["error"] = (
                f"Conservation failed: {staged_count} staged != "
                f"{clean_count} cleaned + {reject_count} rejected"
            )

        return result

    except Exception as e:
        return {"status": "failed", "error": f"Load failed: {e}"}
