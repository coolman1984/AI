# engines/data — Data Engine (the only source of numbers)

**Does:** ingest files text-first into DuckDB; clean/quarantine; compute governed variance.
**Public interface:** `ingest.ingest_csv`, `clean.clean_actuals`, `clean.parse_amount`,
`variance.material_cost_variance`.
**Invariants:** numbers come from here, never from generation; conservation law
(`rows_in == clean + rejected`) is asserted in `clean`; the variance bridge must reconcile.
**Never:** load a whole large file into memory (stream via DuckDB); aggregate a total/
subtotal row; silently drop a row (every drop is a `RejectRecord`).
**Tests:** `pytest tests/test_data_pipeline.py`
**Edge cases:** embedded total rows, duplicates, locale amounts (1.234,56 / 45,50),
missing keys — all in `clean.py` (MASTER_PLAN J.1).
