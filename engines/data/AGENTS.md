# engines/data — Data Engine (the only source of numbers)

**Does:** ingest files text-first into DuckDB; clean/quarantine; compute governed variance;
run the unified ingestion spine's tracked lifecycle (MASTER_PLAN L + `03_design/
unified-ingestion-spine.md`, stage IS2).
**Public interface:** `ingest.ingest_csv`, `ingest.ingest_csv_tracked`, `clean.clean_actuals`,
`clean.parse_amount`, `variance.material_cost_variance`.
**Invariants:** numbers come from here, never from generation; conservation law
(`rows_in == clean + rejected`) is asserted in both `clean.clean_actuals` and
`ingest.ingest_csv_tracked`; the variance bridge must reconcile.
**Never:** load a whole large file into memory (stream via DuckDB — `ingest_csv_tracked`'s
use of `.pl()` is bounded to the already-landed staging table, not the raw file); aggregate
a total/subtotal row; silently drop a row (every drop is a `RejectRecord`).
**Tests:** `pytest tests/test_data_pipeline.py tests/test_ingestion_spine.py`
**Edge cases:** embedded total rows, duplicates, locale amounts (1.234,56 / 45,50),
missing keys — column-mapped in `clean.py` (MASTER_PLAN J.1), column-name-agnostic in
`ingest.ingest_csv_tracked` (`_is_total_row` reuses `clean.TOTAL_LABELS`; duplicate = exact
match across all columns since the generic spine has no known key column). Still open for
the spine: multi-sheet Excel (IS2.3), per-column type inference for unconvertible values
(IS2.4).
