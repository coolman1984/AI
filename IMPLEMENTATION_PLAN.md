# IMPLEMENTATION_PLAN.md — Build Instructions for the Coding Agent

> **READ THIS FIRST. THESE RULES OVERRIDE YOUR INSTINCTS.**
>
> 1. You are building a data pipeline. You will be tempted to "just use pandas
>    to read the Excel." **DO NOT.** Follow the phases in order.
> 2. **NEVER load the full dataset into your own context/output.** You write code
>    that processes data. You do not read the data. If a file has 500,000 rows,
>    you look at the *profile*, never the rows.
> 3. Do each **Phase** in order. Do not start Phase N+1 until Phase N's
>    **Definition of Done** checklist is fully green.
> 4. After every phase, **run the verification command** given and paste its
>    output. If it fails, fix it before moving on. Do not proceed on red.
> 5. When unsure, prefer the **explicit, boring, defensive** option. This is data
>    engineering; cleverness causes silent wrong numbers.
> 6. Use the **exact** file paths, function names, and signatures specified. Do
>    not rename them. Other files depend on them.

---

## 0. GOAL (what "done" means)

Build a local Python pipeline that ingests **one large Excel file (~272 columns,
up to ~500k rows)** AND **a folder of additional CSV/Excel files**, lands them
into a single **DuckDB** staging database, profiles the schema, cleans and
quarantines bad rows, runs aggregations in SQL, and emits a **`report.json`**
matching a user-provided target shape. The pipeline runs from the command line
on the user's own machine. Nothing requires an internet connection at runtime.

**Success = ** `python run_all.py` produces `reports/report.json`, plus a
non-silent `rejects.csv` and `run.log`, and `python scripts/06_validate.py`
exits 0.

---

## 1. TECHNOLOGY STACK (use exactly these — do not substitute)

| Concern | Use | Do NOT use | Why |
|---|---|---|---|
| Heavy storage + aggregation | **DuckDB** (`duckdb`) | pandas for the big join | spills to disk, survives > RAM |
| Excel reading | **`openpyxl`** via pandas, `read_only=True` | default pandas Excel mode | read-only mode streams, won't OOM |
| Small dataframe shaping (final step only) | **pandas** | — | only touches tiny aggregated result |
| Config | **`pyyaml`** (`column_map.yaml`, `config.yaml`) | hardcoded constants | data changes; config shouldn't need code edits |
| CLI / orchestration | plain **`argparse`** + a `run_all.py` | a framework | keep it boring and debuggable |
| Logging | stdlib **`logging`** to `run.log` + stdout | `print()` everywhere | print() loses level/timestamp |
| Tests | **`pytest`** | manual checking | regressions are silent otherwise |
| Python version | **3.11+** | 2.x, <3.10 | match-statements, modern typing |

`requirements.txt` (create this exactly):

```
duckdb>=1.0.0
pandas>=2.0.0
openpyxl>=3.1.0
pyyaml>=6.0
pytest>=8.0.0
```

---

## 2. FINAL DIRECTORY LAYOUT (create this skeleton in Phase 1)

```
AI/
├── ARCHITECTURE.md              # already exists — read it once for context
├── IMPLEMENTATION_PLAN.md       # this file
├── requirements.txt
├── config.yaml                  # paths, engine choice, locale, header settings
├── column_map.yaml              # canonical column names ↔ source variants (HUMAN-REVIEWED)
├── run_all.py                   # orchestrates 01→06 in order
├── data/
│   ├── raw/                     # user drops big.xlsx + folder files here (gitignored)
│   └── staging.duckdb           # built by Phase 3 (gitignored)
├── reports/
│   ├── target_report.json       # user-provided destination shape (committed)
│   └── report.json              # OUTPUT (gitignored)
├── profile/
│   └── schema_profile.json      # Phase 4 output — the map the AI reads (committed)
├── scripts/
│   ├── __init__.py
│   ├── common.py                # logging setup, config loader, path helpers
│   ├── 01_ingest.py             # raw/ → staging.duckdb (text-first, chunked)
│   ├── 02_canonicalize.py       # apply column_map.yaml → unified table
│   ├── 03_profile.py            # staging → profile/schema_profile.json
│   ├── 04_clean.py              # coerce types + quarantine → rejects.csv
│   ├── 05_aggregate.sql         # heavy group-by/joins (run via duckdb)
│   ├── 05_shape.py              # aggregates → target shape → report.json
│   └── 06_validate.py           # reconciliation assertions; exit 0/1
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # builds a tiny synthetic messy dataset fixture
│   ├── test_ingest.py
│   ├── test_clean.py
│   └── test_shape.py
├── rejects.csv                  # runtime quarantine (gitignored)
├── run.log                      # runtime log (gitignored)
└── .gitignore
```

> NOTE on script numbering: files are prefixed `01_`–`06_`. Python can't
> `import 01_ingest`. That's fine — they are **run as scripts**
> (`python scripts/01_ingest.py`), not imported. Shared code lives in
> `common.py`, which IS imported. Keep it this way.

`.gitignore` (create exactly):

```
data/raw/
data/staging.duckdb
reports/report.json
rejects.csv
run.log
__pycache__/
*.pyc
.pytest_cache/
```

---

## 3. THE GRAND PLAN — 8 Phases

```
PHASE 1  Scaffold        → repo skeleton, config, common.py, .gitignore
PHASE 2  Synthetic data  → build a TINY fake messy dataset to develop against
PHASE 3  Ingest          → raw/ → staging.duckdb (text-first, chunked, all files)
PHASE 4  Canonicalize    → unify columns across files via column_map.yaml
PHASE 5  Profile         → emit schema_profile.json (the map)
PHASE 6  Clean           → coerce + quarantine bad rows to rejects.csv
PHASE 7  Aggregate+Shape → SQL aggregation → pour into target_report.json
PHASE 8  Validate+Orchestrate → reconciliation asserts + run_all.py + tests
```

**Develop against the synthetic data from Phase 2, not the user's real file.**
The real file is huge and the user may not have given it to you. The synthetic
data has every messy trait on purpose so your code is forced to handle them.

---

## PHASE 1 — Scaffold

**Goal:** every directory and config file exists; `common.py` works.

**Steps**
1. Create the full directory tree from §2 (empty dirs get a `.gitkeep`).
2. Write `requirements.txt` (§1) and run `pip install -r requirements.txt`.
3. Write `.gitignore` (§2).
4. Write `config.yaml`:
   ```yaml
   paths:
     raw_dir: data/raw
     staging_db: data/staging.duckdb
     profile: profile/schema_profile.json
     target_report: reports/target_report.json
     report_out: reports/report.json
     rejects: rejects.csv
     log: run.log
   engine: duckdb            # do not change without reading ARCHITECTURE.md §2
   ingest:
     big_excel_filename: big.xlsx   # the one large file in raw/
     excel_header_row: 1            # 1-based; set per real file (see Edge Case 2)
     chunk_size: 50000
     encoding: utf-8
   locale:
     decimal: "."             # "." US, "," European — set to match the data
     thousands: ","
     date_format: "%Y-%m-%d"  # set to match the data
   ```
5. Write `scripts/common.py` with EXACTLY these functions:
   ```python
   # scripts/common.py
   import logging, sys, yaml
   from pathlib import Path

   ROOT = Path(__file__).resolve().parent.parent

   def load_config(path: str = "config.yaml") -> dict:
       with open(ROOT / path) as f:
           return yaml.safe_load(f)

   def get_logger(name: str) -> logging.Logger:
       cfg = load_config()
       logger = logging.getLogger(name)
       if logger.handlers:            # avoid duplicate handlers on re-import
           return logger
       logger.setLevel(logging.INFO)
       fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s | %(message)s")
       fh = logging.FileHandler(ROOT / cfg["paths"]["log"])
       fh.setFormatter(fmt)
       sh = logging.StreamHandler(sys.stdout)
       sh.setFormatter(fmt)
       logger.addHandler(fh); logger.addHandler(sh)
       return logger

   def slugify_column(name: str) -> str:
       """lowercase, strip, spaces/punct → underscore, collapse repeats."""
       import re
       s = str(name).strip().lower()
       s = re.sub(r"[^\w]+", "_", s)
       s = re.sub(r"_+", "_", s).strip("_")
       return s or "unnamed"
   ```

**Definition of Done (Phase 1)**
- [ ] `python -c "from scripts.common import load_config, get_logger, slugify_column; print('ok')"` prints `ok`.
- [ ] `slugify_column("  Unit Cost ($) ")` returns `unit_cost`.
- [ ] All directories in §2 exist.

---

## PHASE 2 — Synthetic Messy Dataset (your development target)

**Goal:** a tiny dataset (~200 rows) that contains EVERY messy trait, so your
code is forced to be correct. Real data is huge and may be absent; develop here.

**Steps**
1. Write `tests/conftest.py` that builds, into a temp dir, a fixture with:
   - `big.xlsx`: ~150 rows, ~10 columns. Header on **row 2** (row 1 is a title).
     Include: a duplicate header (`Cost`, `Cost`), a European decimal column
     (`"45,50"`), a column mixing number + text (`"approx 12"`), blanks, an
     Excel serial date, and a `#REF!` cell.
   - `folder/branch_a.csv`: same logical data, **different column names**
     (`unitcost` instead of `unit_cost`), different column order.
   - `folder/branch_b.csv`: an EXTRA column not in the others, and one MISSING
     column.
2. The fixture returns the temp `raw/` path. Tests point `config` at it.

**Tricks**
- Hardcode the messy values literally so traits are guaranteed present.
- Keep it tiny — it must run in <1 second.

**Definition of Done (Phase 2)**
- [ ] `pytest tests/conftest.py` (or a smoke test using the fixture) builds the
      files without error.
- [ ] Opening `big.xlsx` shows the header is NOT on row 1 (trait present).

---

## PHASE 3 — Ingest (`scripts/01_ingest.py`)

**Goal:** load the big Excel AND every file in the folder into `staging.duckdb`,
**as TEXT**, one table per source, plus a `__source_file` column. No type
inference yet. Text-first is non-negotiable (see Common Mistakes).

**Required interface**
```python
def ingest_excel(path: Path, header_row: int, chunk_size: int, con) -> str: ...
def ingest_csv(path: Path, encoding: str, con) -> str: ...
def main(): ...   # reads config, ingests big_excel + every folder file
```
Rules:
- Read Excel with `pandas.read_excel(path, header=header_row-1,
  dtype=str, engine="openpyxl")`. `dtype=str` forces text — DO NOT skip it.
- For very large Excel, if memory is a concern, read with `openpyxl`
  `read_only=True` row-by-row in `chunk_size` batches. (For ≤500k it usually
  fits with `dtype=str`; measure before optimizing.)
- Slugify and **de-duplicate** headers: a repeated `cost` becomes `cost`,
  `cost_2`. Log the original→final mapping.
- Add columns `__source_file` (filename) and `__row_id` (stable integer).
- Write each source to its own raw table: `raw_<sourcename>`.
- Everything stored as VARCHAR. Verify with `DESCRIBE`.

**Definition of Done (Phase 3)**
- [ ] After running against the synthetic fixture, DuckDB contains one table per
      source file; all columns are VARCHAR; `__source_file` and `__row_id` exist.
- [ ] `run.log` contains the header-remap for the duplicate-header case.
- [ ] Verification: `python scripts/01_ingest.py && duckdb data/staging.duckdb "SHOW TABLES;"` lists the expected tables.

---

## PHASE 4 — Canonicalize (`scripts/02_canonicalize.py`)

**Goal:** merge the per-source raw tables into ONE table `raw_unified`, mapping
the differently-named columns onto canonical names. **This is where wrong
numbers are born — be explicit, never fuzzy-match silently.**

**Steps**
1. Create `column_map.yaml` — the human-reviewed mapping:
   ```yaml
   # canonical_name: [list of source variants that mean the same thing]
   unit_cost:   [unit_cost, unitcost, "cost_per_unit", cost]
   material_id: [material_id, mat_id, material]
   sub_assembly:[sub_assembly, subassembly, assembly]
   # columns not listed here are CARRIED THROUGH under their slugified name
   ```
2. `02_canonicalize.py` reads each `raw_*` table, renames any column whose name
   appears in a variant list to its canonical name, then `UNION ALL BY NAME`
   (DuckDB) into `raw_unified`. Missing columns become NULL; extra columns are
   kept (do not drop data).
3. Any source column NOT found in the map and NOT obviously safe → log a WARNING
   listing it, so a human can decide whether it needs mapping.

**Common mistake to avoid:** auto-guessing that `cost` == `unit_cost`. Only map
what `column_map.yaml` explicitly says. Guessing here silently corrupts totals.

**Definition of Done (Phase 4)**
- [ ] `raw_unified` exists with canonical column names.
- [ ] The `branch_b` extra column is present (as NULL for other sources), and
      its missing column is NULL for branch_b — nothing was dropped.
- [ ] Unmapped columns produced a WARNING in `run.log`.

---

## PHASE 5 — Profile (`scripts/03_profile.py`)

**Goal:** emit `profile/schema_profile.json` — the small, truthful map. THIS is
the only data-derived artifact the next AI step reads. It must summarize all
rows, not the top rows.

**Required output shape (write EXACTLY this JSON structure):**
```json
{
  "table": "raw_unified",
  "row_count": 152,
  "generated_at": "ISO-8601",
  "columns": [
    {
      "name": "unit_cost",
      "inferred_type": "numeric|date|integer|text|boolean",
      "null_pct": 12.5,
      "distinct_count": 47,
      "min": "12.00",
      "max": "990.50",
      "random_samples": ["45.50", "12.00", "880.00"],
      "weirdest_values": ["45,50", "approx 12", "#REF!"],
      "out_of_range_count": 3
    }
  ]
}
```
Rules:
- `inferred_type` = best guess from a SAMPLE + full-column regex checks. It is a
  hint, not a guarantee.
- `weirdest_values` = the values that FAIL the inferred type's parse (the ones
  that will become rejects). This is the most important field — it shows the AI
  what cleaning must handle.
- `random_samples` = `USING SAMPLE` in DuckDB, NOT `LIMIT 3` (top rows lie).
- `out_of_range_count` = count of values failing the type parse.

**Definition of Done (Phase 5)**
- [ ] `schema_profile.json` exists and validates as JSON.
- [ ] The European-decimal and `#REF!` values appear in some column's
      `weirdest_values`. (Proof the profile tells the truth.)
- [ ] File is < 50 KB regardless of dataset size. (Proof it scales.)

---

## PHASE 6 — Clean (`scripts/04_clean.py`)

**Goal:** produce a typed table `clean` where every value is correctly typed,
and send every unparseable row to `rejects.csv` WITH A REASON. Silent dropping
is forbidden.

**Steps**
1. For each column, using its profiled `inferred_type`, coerce:
   - numeric: strip thousands sep, swap locale decimal, `TRY_CAST` to DOUBLE.
   - date: parse using `config.locale.date_format`; handle Excel serials
     (integer 30000–60000 → date via `1899-12-30` epoch).
   - integer/boolean/text similarly.
2. A row where a REQUIRED column fails to parse → write the ORIGINAL row to
   `rejects.csv` with extra columns `__reject_reason` and `__source_file`.
   Required columns are listed in `config.yaml` (`clean.required_columns`).
3. Rows that parse go into the `clean` table with proper DuckDB types.
4. Log counts: rows in, rows clean, rows rejected, and rejection reasons tally.

**Tricks**
- Use DuckDB `TRY_CAST` — it returns NULL instead of throwing, so you can detect
  failures with a `WHERE cast IS NULL AND original IS NOT NULL` check.
- Distinguish "legitimately empty" (NULL in source) from "present but
  unparseable" (`"approx 12"`). Only the second is a reject.

**Definition of Done (Phase 6)**
- [ ] `clean` table has proper types (numeric columns are DOUBLE, not VARCHAR).
- [ ] `rejects.csv` exists and contains the `"approx 12"` / `#REF!` rows with
      a readable `__reject_reason`.
- [ ] `rows_in == rows_clean + rows_rejected` (logged). This equation MUST hold.

---

## PHASE 7 — Aggregate + Shape (`scripts/05_aggregate.sql` + `scripts/05_shape.py`)

**Goal:** compute the report numbers in SQL (engine does the heavy work), then
pour them into the user's `target_report.json` shape, producing `report.json`.

**Steps**
1. Read `reports/target_report.json` to learn the required output keys/structure.
   (The user provides this. If absent, create a minimal example and log that you
   did, so the user replaces it.)
2. Write `05_aggregate.sql`: the GROUP BY / SUM / JOIN that produces one row per
   reported entity (e.g. per `sub_assembly`). Run it against `clean` in DuckDB.
   Keep aggregation in SQL — do NOT pull all rows into pandas to sum them.
3. `05_shape.py`: take the small aggregated result, map it into the exact target
   JSON structure, write `reports/report.json`. Use pandas here — the data is now
   tiny.

**Common mistake:** computing aggregates in pandas after `fetchall()` of the
whole `clean` table. For 500k rows that may OOM and is slow. Aggregate in SQL;
only fetch the already-grouped result.

**Definition of Done (Phase 7)**
- [ ] `reports/report.json` exists and matches the KEY STRUCTURE of
      `target_report.json` (same keys, numbers filled in).
- [ ] Numbers are plausible (no NaN, no nulls where a sum is expected).

---

## PHASE 8 — Validate + Orchestrate (`scripts/06_validate.py` + `run_all.py` + tests)

**Goal:** prove correctness automatically and make the whole thing one command.

**Steps**
1. `06_validate.py` — reconciliation assertions; exit 0 if all pass, else exit 1
   and log each failure. Minimum assertions:
   - `rows_in == rows_clean + rows_rejected` (no rows vanished).
   - Every numeric aggregate in `report.json` is `>= 0` (or per business rule).
   - No aggregate references a quarantined row.
   - Sum of a per-group total reconciles to the grand total within rounding.
2. `run_all.py` — runs phases 3→7 then 8 in order; stops on first failure with a
   clear message. Supports `--from <phase>` to resume.
3. Tests in `tests/`:
   - `test_ingest.py`: after ingest, all columns VARCHAR; source/row_id present.
   - `test_clean.py`: the row-conservation equation holds; known-bad rows land
     in rejects with a reason.
   - `test_shape.py`: report.json keys match target keys; a known synthetic total
     equals the hand-computed expected value.

**Definition of Done (Phase 8 — and the whole project)**
- [ ] `pytest` passes (all tests green).
- [ ] `python run_all.py` against the synthetic fixture produces `report.json`,
      `rejects.csv`, `run.log`, and `06_validate.py` exits 0.
- [ ] README/usage note explains how the user points `config.yaml` at their real
      `data/raw/` and reruns.

---

## 4. THE TOP 12 MISTAKES A CODING AGENT MAKES HERE (AVOID ALL)

1. **Reading the whole dataset into context/output.** Never. Use the profile.
2. **Skipping `dtype=str` on ingest.** Pandas will silently mistype mixed columns
   and you'll never see the bad values. Always ingest as text first.
3. **Trusting the first N rows** (`LIMIT 5` / `df.head()`) as representative.
   They lie. Use random sampling for the profile.
4. **Assuming header is on row 1.** It's often row 2–4 with a title above.
   Make it config-driven.
5. **Fuzzy-matching column names automatically.** A wrong map = a confident wrong
   total. Map only what `column_map.yaml` declares; WARN on the rest.
6. **Dropping unparseable rows silently** (e.g. `errors="coerce"` then ignoring
   the NaNs). Every dropped row MUST land in `rejects.csv` with a reason.
7. **Confusing empty with unparseable.** NULL source = legitimately empty;
   `"approx 12"` = a reject. Treat them differently.
8. **Aggregating in pandas after fetching all rows.** OOM + slow. Aggregate in
   SQL; fetch only the grouped result.
9. **European decimals / thousands separators.** `"1.234,56"` parsed naively
   becomes `1.234`. Handle locale from config.
10. **Excel serial dates** (`44561`) parsed as integers. Convert via the
    `1899-12-30` epoch.
11. **`print()` instead of logging.** You lose the audit trail. Use the logger;
    everything important goes to `run.log`.
12. **Proceeding past a red phase.** Each phase has a Definition of Done. Do not
    advance until it's green. A broken Phase 3 makes Phases 4–8 meaningless.

---

## 5. EXECUTION ORDER CHEAT-SHEET

```bash
# one-time
pip install -r requirements.txt

# the pipeline (also wrapped by run_all.py)
python scripts/01_ingest.py        # raw/ → staging.duckdb (text)
python scripts/02_canonicalize.py  # → raw_unified
python scripts/03_profile.py       # → profile/schema_profile.json
python scripts/04_clean.py         # → clean table + rejects.csv
duckdb data/staging.duckdb < scripts/05_aggregate.sql
python scripts/05_shape.py         # → reports/report.json
python scripts/06_validate.py      # exit 0 = trustworthy

# or just
python run_all.py
pytest
```

**ALWAYS read `rejects.csv` and `run.log` after a run.** A report with 4,000
unnoticed rejects is a wrong report that looks right. That single habit is the
difference between a pipeline you can trust and one you can't.

---

## 6. ORDER OF WORK FOR YOU (the coding agent), restated

Build Phase 1 → verify → Phase 2 → verify → … → Phase 8 → verify. Develop and
test entirely against the synthetic fixture from Phase 2. Only after all tests
pass does the user swap in their real `big.xlsx` + folder, point `config.yaml`
at them, set the real `excel_header_row`/`locale`, review `column_map.yaml`, and
run `python run_all.py`. Do not skip phases. Do not proceed on red. Do not read
the ocean.
