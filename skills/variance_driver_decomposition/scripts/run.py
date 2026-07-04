"""variance-driver-decomposition: wrap run_variance_decomposition with narrative."""

def run_variance_drivers(clean_table: str, dimension: str = "cost_center", duckdb_con=None):
    """Run variance decomposition with plain-English narrative."""
    from engines.data.drivers import run_variance_decomposition
    if duckdb_con is None:
        from engines.data.ingest import get_connection
        duckdb_con = get_connection()
    try:
        result = run_variance_decomposition(duckdb_con, clean_table, dimension=dimension)
        return {"status": "done", "drivers": result, "dimension": dimension}
    except Exception as e:
        return {"status": "failed", "error": str(e)}
