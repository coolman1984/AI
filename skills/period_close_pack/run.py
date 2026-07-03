"""period-close-pack: chain intake→load→reconcile→reports for the whole close."""

def run_period_close(inbox_path: str, period: str, db_registry=None):
    """Chain the full close workflow for a period. Wraps run_foreman."""
    from tools.run_foreman import run_foreman
    return run_foreman(inbox_path, goal=f"Period close: {period}", period=period, db_registry=db_registry)
