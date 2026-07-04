"""cross-period-comparison: same report logic across periods with drift detection."""

def run_cross_period(clean_table_template: str, periods: list[str], duckdb_con=None):
    """Compare a metric across multiple periods and flag significant drift."""
    if duckdb_con is None:
        from engines.data.ingest import get_connection
        duckdb_con = get_connection()

    results = []
    for period in periods:
        table = clean_table_template.replace("{period}", period)
        try:
            total = float(duckdb_con.execute(
                f"SELECT COALESCE(SUM(amount), 0) FROM {table}"
            ).fetchone()[0])
            results.append({"period": period, "total": total})
        except Exception:
            results.append({"period": period, "total": None, "error": f"Table {table} not found"})

    # Detect drift
    drifts = []
    valid = [r for r in results if r["total"] is not None]
    if len(valid) >= 2:
        for i in range(1, len(valid)):
            delta = valid[i]["total"] - valid[i - 1]["total"]
            pct = delta / valid[i - 1]["total"] * 100 if valid[i - 1]["total"] else 0
            if abs(pct) > 10:
                drifts.append({
                    "from": valid[i - 1]["period"],
                    "to": valid[i]["period"],
                    "delta": round(delta, 2),
                    "pct_change": round(pct, 1),
                })

    return {"status": "done", "periods": results, "drifts": drifts}
