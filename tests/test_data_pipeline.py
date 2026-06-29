from engines.data.clean import clean_actuals, parse_amount
from engines.data.ingest import get_connection, ingest_csv
from engines.data.variance import material_cost_variance


def _load():
    con = get_connection()
    rows_in = ingest_csv(con, "raw_actuals", "data/sample/finance_actuals.csv")
    ingest_csv(con, "raw_budget", "data/sample/finance_budget.csv")
    budget = con.execute("SELECT sub_assembly, budget_amount FROM raw_budget").pl()
    clean, rejects, _ = clean_actuals(con, "raw_actuals")
    return rows_in, clean, rejects, budget


def test_parse_amount_locales():
    assert parse_amount("1,234.56") == 1234.56
    assert parse_amount("1.234,56") == 1234.56
    assert parse_amount("45,50") == 45.50
    assert parse_amount("800.00") == 800.0


def test_clean_excludes_totals_dupes_and_junk():
    rows_in, clean, rejects, _ = _load()
    reasons = sorted(r.reason for r in rejects)
    assert reasons == ["duplicate", "total_or_missing_key", "unparseable_amount"]
    # conservation: nothing vanishes silently
    assert rows_in == clean.height + len(rejects)
    assert clean.height == 5


def test_variance_bridge_reconciles_and_is_correct():
    _, clean, _, budget = _load()
    bridge = material_cost_variance(clean, budget)
    assert bridge.reconciles()
    assert bridge.total_actual == 4700.0      # 1500 Frame + 2400 Panel + 800 Board
    assert bridge.total_budget == 4600.0
    assert bridge.total_variance == 100.0
