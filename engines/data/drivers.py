"""Driver analysis runner (T8) — explain a cost variance as price/volume/mix.

Ingests actuals + standards, cleans (same messy-data defenses), and returns the
decomposition. Numbers still come from the data engine; the decomposition reconciles
exactly (price+volume+mix == total) — a four-eyes check on the 'why', not just the 'what'.
"""
from __future__ import annotations

from engines.data.clean import clean_actuals
from engines.data.ingest import get_connection, ingest_csv
from engines.data.variance import price_volume_mix
from shared.lenses import FINANCE


def run_variance_decomposition(
    actuals_csv: str, standards_csv: str, cfg: dict, lens: dict | None = None
) -> dict:
    lens = lens or FINANCE
    con = get_connection()
    ingest_csv(con, "raw_actuals", actuals_csv)
    ingest_csv(con, "raw_std", standards_csv)
    clean, rejects, log = clean_actuals(
        con, "raw_actuals", key_col=lens["key_col"], amount_col=lens["value_col"]
    )
    standards = con.execute("SELECT * FROM raw_std").pl()
    decomp = price_volume_mix(
        clean, standards, key=lens["key_col"], group=lens["grain"],
        qty_col="qty", amount_col=lens["value_col"], metric=f"{lens['metric']}_pvm",
    )
    return {"decomposition": decomp, "rejects": rejects, "log": log}
