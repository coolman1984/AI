# engines/data — Data Engine (the only source of numbers)

**Does:** ingest files text-first into DuckDB; clean/quarantine; compute governed variance;
run the unified ingestion spine's tracked lifecycle (MASTER_PLAN L + `03_design/
unified-ingestion-spine.md`, stages IS2–IS3, IS6).
**Public interface:** `ingest.ingest_csv`, `ingest.ingest_csv_tracked`,
`ingest.ingest_excel_tracked`, `ingest.ingest_spreadsheet`, `types.infer_column_type`,
`pdf_tables.ingest_pdf_tables_tracked`, `query_readiness.sum_typed_amounts`,
`clean.clean_actuals`, `clean.parse_amount`, `variance.material_cost_variance`.
**Invariants:** numbers come from here, never from generation; conservation law
(`rows_in == clean + rejected`) is asserted in both `clean.clean_actuals` and
`ingest.ingest_csv_tracked` / Excel/PDF tracked paths; the variance bridge must reconcile;
type inference keeps raw text and writes typed values to `extracted_fields`.
**Never:** load a whole large file into memory (the tracked spine must classify totals /
duplicates in DuckDB SQL, not by materializing the full staging table in Python); aggregate
a total/subtotal row; silently drop a row (every drop is a `RejectRecord`); coerce
unconvertible numeric/date cells into trusted typed values. Duplicate policy
in the generic spine is explicit: `on_duplicates="flag"` by default, `drop` only when the
caller asks for it.
**Tests:** `pytest tests/test_data_pipeline.py tests/test_ingestion_spine.py tests/test_pdf_tables.py tests/test_query_readiness.py`
**Edge cases:** embedded total rows, duplicates, locale amounts (1.234,56 / 45,50),
missing keys — column-mapped in `clean.py` (MASTER_PLAN J.1), column-name-agnostic in
`ingest.ingest_csv_tracked` (`_is_total_row` reuses `clean.TOTAL_LABELS`; duplicate = exact
match across all columns since the generic spine has no known key column); multi-sheet Excel
tracks `source_sheet` with one run per sheet; PDF table rows below confidence threshold go to
review rejects; cross-source SQL sums use `extracted_fields.typed_value`, not raw text casts.