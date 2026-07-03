"""inventory-exception-scan: apply rule notes to an inventory snapshot."""

def run_inventory_scan(inventory_table: str, rules: list[dict] = None, duckdb_con=None):
    """Apply confirmed business rules to an inventory snapshot. Returns exceptions."""
    if duckdb_con is None:
        from engines.data.ingest import get_connection
        duckdb_con = get_connection()

    if rules is None:
        rules = [{"column": "quantity", "condition": "< 0", "label": "Negative stock"}]

    exceptions = []
    for rule in rules:
        try:
            rows = duckdb_con.execute(
                f"SELECT * FROM {inventory_table} WHERE {rule['column']} {rule['condition']} LIMIT 100"
            ).fetchall()
            exceptions.append({
                "rule": rule["label"],
                "count": len(rows),
                "severity": "high" if len(rows) > 10 else "medium",
            })
        except Exception as e:
            exceptions.append({"rule": rule["label"], "error": str(e)})

    return {"status": "done", "exceptions": exceptions, "total_rules": len(rules)}
