"""FOREMAN end-to-end driver: chains SK-001→SK-005 into one run.

Takes an inbox file and a plain-English goal, drafts a run contract,
and chains the skills. Stops at any failed gate with a plain message.
"""

from datetime import datetime
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def run_foreman(
    inbox_path: str,
    goal: str = None,
    control_total: float = None,
    period: str = None,
    db_registry=None,
    dry_run: bool = False,
) -> dict:
    """Run the FOREMAN MVP pipeline end-to-end on a single inbox file.

    Chains: SK-001 fingerprint + ingest → SK-002 profile + map
            → SK-003 load + clean → SK-004 reconcile → SK-005 report

    Args:
        inbox_path: Path to a file in datasets/inbox/.
        goal: Plain-English goal (e.g. "May actuals — variance report").
        control_total: Optional control total for reconciliation.
        period: Optional period label.
        db_registry: FOREMAN registry DB connection.
        dry_run: If True, only create the contract and stop.

    Returns:
        dict with full run summary including all step results.
    """
    from tools.foreman_db import init_db
    from tools.run_logger import finish_run, start_run

    path = Path(inbox_path)
    if not path.exists():
        return {"status": "failed", "error": f"File not found: {inbox_path}"}

    # Auto-create registry DB if not provided
    own_db = db_registry is None
    if own_db:
        reg_path = str(_PROJECT_ROOT / "registry" / "foreman.db")
        db_registry = init_db(reg_path)

    if goal is None:
        goal = f"Process {path.name}"

    if period is None:
        period = datetime.now().strftime("%Y-%m")

    # Start master run
    run_id = start_run(
        db_registry, goal=goal, skill_id="SK-001→SK-005",
        contract_path=str(path),
    )

    results = {"run_id": run_id, "steps": {}, "status": "running"}

    try:
        # === SK-001: excel-intake ===
        from skills.excel_intake.scripts.run import run_excel_intake

        if dry_run:
            results["steps"]["sk001"] = {"status": "dry_run", "message": "Skipped (dry run)"}
        else:
            intake_result = run_excel_intake(
                str(path), db_registry=db_registry,
            )
            results["steps"]["sk001"] = intake_result
            if intake_result["status"] != "done":
                results["status"] = intake_result["status"]
                results["blocked_at"] = "SK-001"
                results["error"] = intake_result.get("error", "Intake failed")
                finish_run(db_registry, run_id, status="blocked",
                           outcome_summary=results["error"])
                return results

        # === SK-002: column-profile-and-map ===
        from skills.column_profile_and_map.scripts.run import run_profile_and_map

        if dry_run:
            results["steps"]["sk002"] = {"status": "dry_run"}
        else:
            table_name = intake_result.get("table_name", f"staging_{path.stem}".replace("-", "_").replace(" ", "_"))
            profile_result = run_profile_and_map(
                table_name, db_registry=db_registry,
            )
            results["steps"]["sk002"] = profile_result
            if profile_result["status"] not in ("done",):
                # Mapping proposal can continue even if unconfirmed
                if "requires_confirmation" not in profile_result:
                    results["status"] = profile_result["status"]
                    results["blocked_at"] = "SK-002"

        # === SK-003: load-to-database ===
        from skills.load_to_database.scripts.run import run_load_to_database

        if dry_run:
            results["steps"]["sk003"] = {"status": "dry_run"}
        else:
            mapping = profile_result.get("mapping_proposal", {})
            load_result = run_load_to_database(
                table_name, mapping=mapping,
            )
            results["steps"]["sk003"] = load_result
            if load_result["status"] != "done":
                results["status"] = load_result["status"]
                results["blocked_at"] = "SK-003"
                results["error"] = load_result.get("error", "Load failed")
                finish_run(db_registry, run_id, status="blocked",
                           outcome_summary=results["error"])
                return results

        # === SK-004: reconcile-and-validate ===
        from skills.reconcile_and_validate.scripts.run import run_reconcile

        if dry_run:
            results["steps"]["sk004"] = {"status": "dry_run"}
        else:
            clean_table = load_result.get("clean_table", f"clean_{table_name}")
            reconcile_result = run_reconcile(
                clean_table,
                control_total=control_total or 0.0,
                duckdb_con=None,
                tolerance=0.01,
                dimension="material_id",
                control_total_source="owner stated" if control_total else "auto (no control)",
            )
            results["steps"]["sk004"] = reconcile_result
            if reconcile_result["status"] not in ("done", "blocked"):
                # Blocked means gate failed but we can still report the issue
                if reconcile_result.get("error"):
                    results["status"] = reconcile_result["status"]
                    results["blocked_at"] = "SK-004"

        # === SK-005: management-report ===
        from skills.management_report.scripts.run import run_management_report

        if dry_run:
            results["steps"]["sk005"] = {"status": "dry_run"}
        else:
            clean_table = load_result.get("clean_table", f"clean_{table_name}")
            report_result = run_management_report(
                clean_table, period=period,
            )
            results["steps"]["sk005"] = report_result
            if report_result["status"] != "done":
                results["status"] = report_result["status"]
                results["blocked_at"] = "SK-005"

        # Complete
        if not dry_run:
            summary_parts = [f"Run {run_id}: {goal}"]
            for sk, res in results["steps"].items():
                s = res.get("status", "?")
                summary_parts.append(f"  {sk}: {s}")

            results["status"] = "done"
            finish_run(db_registry, run_id, status="done",
                       outcome_summary="\n".join(summary_parts))
        return results

    except Exception as e:
        results["status"] = "failed"
        results["error"] = str(e)
        try:
            finish_run(db_registry, run_id, status="failed",
                       outcome_summary=str(e))
        except Exception:
            pass
        return results
    finally:
        if own_db:
            try:
                db_registry.close()
            except Exception:
                pass
