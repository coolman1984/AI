"""T8: price/volume/mix variance decomposition — the 'why' behind the number."""
import polars as pl
import yaml

from engines.data.drivers import run_variance_decomposition
from engines.data.variance import price_volume_mix


def test_pvm_reconciles_and_known_price():
    actuals = pl.DataFrame({
        "material_id": ["M1", "M2"], "sub_assembly": ["Frame", "Frame"],
        "qty": [10.0, 5.0], "amount": [1000.0, 500.0],  # actual price 100 each
    })
    standards = pl.DataFrame({
        "material_id": ["M1", "M2"], "std_qty": [10.0, 4.0], "std_price": [95.0, 100.0],
    })
    d = price_volume_mix(actuals, standards)
    assert d.reconciles()                       # price + volume + mix == total
    # M1 price effect = (100-95)*10 = 50 ; M2 price effect = 0
    assert round(d.price, 2) == 50.0
    assert d.unmatched == []


def test_pvm_on_samples_reconciles_to_the_cent():
    cfg = yaml.safe_load(open("config.yaml"))
    out = run_variance_decomposition(
        "data/sample/finance_actuals.csv", "data/sample/finance_standards.csv", cfg
    )
    d = out["decomposition"]
    assert d.reconciles(0.01)
    assert round(d.total, 2) == -50.00          # actual 4700 vs std 4750
    assert round(d.price, 2) == 50.00           # net price effect
    # messy rows are still rejected before the decomposition
    assert any(r.reason == "total_or_missing_key" for r in out["rejects"])


def test_pvm_flags_items_without_a_standard():
    actuals = pl.DataFrame({
        "material_id": ["M1", "MX"], "sub_assembly": ["Frame", "Frame"],
        "qty": [10.0, 3.0], "amount": [1000.0, 300.0],
    })
    standards = pl.DataFrame({"material_id": ["M1"], "std_qty": [10.0], "std_price": [95.0]})
    d = price_volume_mix(actuals, standards)
    assert d.unmatched == ["MX"]                 # cannot explain what has no standard
