"""rework-cost-analysis: rework qty/cost by cause and repeat offenders."""

def run_rework_analysis(rework_table: str, duckdb_con=None):
    """Analyze rework costs by cause code and identify repeat offenders."""
    if duckdb_con is None:
        from engines.data.ingest import get_connection
        duckdb_con = get_connection()

    try:
        by_cause = duckdb_con.execute(
            f"SELECT cause_code, COUNT(*) as count, SUM(amount) as total_cost "
            f"FROM {rework_table} GROUP BY cause_code ORDER BY total_cost DESC"
        ).fetchall()

        return {
            "status": "done",
            "by_cause": [{"cause": r[0], "count": r[1], "cost": float(r[2])} for r in by_cause],
            "total_rework_cost": sum(float(r[2]) for r in by_cause),
        }
    except Exception as e:
        return {"status": "failed", "error": str(e)}
