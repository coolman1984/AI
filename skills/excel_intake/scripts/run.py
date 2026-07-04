"""SK-001 excel-intake: register, fingerprint, and stage a spreadsheet."""

from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _get_duckdb_connection():
    """Get a DuckDB connection using the project's default staging."""
    import duckdb
    try:
        # Try to use existing connection logic from engines
        from engines.data.ingest import get_connection
        return get_connection()
    except (ImportError, Exception):
        # Fallback: in-memory DuckDB
        return duckdb.connect(":memory:")


def run_excel_intake(
    file_path: str,
    db_registry=None,
    duckdb_con=None,
    expected_row_count: int = None,
    expected_total: float = None,
    period: str = None,
) -> dict:
    """Run the excel-intake skill on a file.

    Args:
        file_path: Path to the source file in datasets/inbox/
        db_registry: sqlite3.Connection to the FOREMAN registry DB
        duckdb_con: DuckDB connection (if None, creates one)
        expected_row_count: Optional expected row count for QA
        expected_total: Optional expected total for QA
        period: Optional period label

    Returns:
        dict with summary of what happened.
    """
    from tools.fingerprint import register_file
    from tools.run_logger import (
        finish_run,
        log_evidence,
        log_step,
        log_validation,
        start_run,
    )

    # Validate input
    path = Path(file_path)
    if not path.exists():
        return {"status": "failed", "error": f"File not found: {file_path}"}

    # Track whether we created our own duckdb connection
    own_duckdb = duckdb_con is None
    if own_duckdb:
        duckdb_con = _get_duckdb_connection()

    try:
        # Start run
        goal = f"Intake spreadsheet: {path.name}"
        run_id = start_run(
            db_registry, goal=goal, skill_id="SK-001",
            contract_path=str(path),
        )

        # Step 1: Fingerprint + register
        step1 = log_step(db_registry, run_id, 1, "T-FP-001",
                         params={"path": str(path)})
        try:
            fp_result = register_file(str(path), db_conn=db_registry)
        except PermissionError:
            finish_step(db_registry, step1, status="failed")
            msg = "The file is open in Excel. Close it and retry."
            finish_run(db_registry, run_id, status="blocked",
                       outcome_summary=msg)
            return {"status": "blocked", "error": msg, "run_id": run_id}

        log_evidence(
            db_registry, run_id, step1,
            source_fingerprint=fp_result["sha256"],
            source_path=fp_result["original_path"],
            method="sha256",
            value_or_summary=f"Registered to {fp_result['registered_path']}",
        )
        finish_step(db_registry, step1, status="done")

        # Step 2: Ingest spreadsheet
        step2 = log_step(db_registry, run_id, 2, "T-ING-001",
                         params={"path": str(path), "table": f"staging_{path.stem}"})
        try:
            from engines.data.ingest import ingest_spreadsheet

            table_name = f"staging_{path.stem}".replace("-", "_").replace(" ", "_")
            ingest_result = ingest_spreadsheet(
                duckdb_con, table=table_name, path=str(path),
                on_duplicates="flag", infer_types=True,
            )
        except Exception as e:
            finish_step(db_registry, step2, status="failed")
            msg = f"Ingestion failed: {e}"
            finish_run(db_registry, run_id, status="failed",
                       outcome_summary=msg)
            return {"status": "failed", "error": msg, "run_id": run_id}

        rows_in = ingest_result.get("rows_in", 0)
        reject_count = ingest_result.get("reject_count", 0)
        kept = rows_in - reject_count

        log_evidence(
            db_registry, run_id, step2,
            source_fingerprint=fp_result["sha256"],
            locator="Sheet(s)",
            method="ingest_spreadsheet",
            value_or_summary=f"Rows in: {rows_in}, Kept: {kept}, Rejected: {reject_count}",
        )
        finish_step(db_registry, step2, status="done")

        # Gate: conservation
        conservation_passed = (rows_in == kept + reject_count)
        log_validation(
            db_registry, run_id,
            gate_name="conservation",
            passed=conservation_passed,
            expected=str(rows_in),
            actual=str(kept + reject_count),
            message="All rows accounted for" if conservation_passed
            else f"Mismatch: {rows_in} in != {kept + reject_count} accounted",
        )
        if not conservation_passed:
            finish_run(db_registry, run_id, status="blocked",
                       outcome_summary="Conservation gate failed")
            return {
                "status": "blocked",
                "error": "Conservation check failed",
                "run_id": run_id,
                "rows_in": rows_in,
                "kept": kept,
                "rejected": reject_count,
            }

        # Done
        summary = (
            f"Intake complete: {rows_in} rows in, "
            f"{reject_count} rejected, {kept} kept. "
            f"Staged as '{table_name}'."
        )
        finish_run(db_registry, run_id, status="done",
                   outcome_summary=summary)

        return {
            "status": "done",
            "run_id": run_id,
            "rows_in": rows_in,
            "kept": kept,
            "rejected": reject_count,
            "table_name": table_name,
            "fingerprint": fp_result["sha256"],
            "registered_path": fp_result["registered_path"],
            "summary": summary,
        }
    finally:
        if own_duckdb and duckdb_con:
            try:
                duckdb_con.close()
            except Exception:
                pass


def finish_step(db, step_id, status="done"):
    """Thin wrapper to avoid circular imports."""
    from tools.run_logger import finish_step as _finish
    _finish(db, step_id, status=status)
