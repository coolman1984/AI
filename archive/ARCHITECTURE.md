# The Grand Plan — Messy-Data → Queryable DB → JSON Report

> **The one sentence that fixes your confusion:**
> The AI never reads the data. It reads a *map* of the data (the schema profile)
> and a *destination* (the empty JSON report), then writes Python. Your machine
> runs that Python against the full volume. The AI's eyes never touch a real
> number.

This document is the architecture. It is written to be handed to an AI coding
agent **and** to a human. Read the Mental Model once. Then live in Phases 0–6.

---

## 0. Mental Model — who does what

| Role | Who | Sees | Job |
|------|-----|------|-----|
| **Architect** | The AI (Claude Code, in your IDE) | schema profile (tiny) + target JSON (tiny) | *writes* the code |
| **Bulldozer** | Python (pandas / DuckDB / sqlite3) | all 5,000,000 rows | *executes* the code on your machine |
| **Foreman** | You | the plan, the review, the rejects log | decides & verifies |

The Golden Rule: **code writes code from samples; engines execute code against volumes.**

A bricklayer is given the dimensions of one brick and the blueprint of the wall.
He is never handed the quarry. Hand the AI the quarry and it hallucinates,
overflows its context window, and bills you a fortune. Hand it the brick.

---

## 1. The Four Artifacts (not two)

The naïve version of this plan has two artifacts: a schema and a target.
**That version dies on contact with messy data.** The real plan has four.

1. **Schema Profile** — *the truth about all the data, compressed.*
   Per column: name, inferred type, % null, distinct-value count, min/max,
   3 *random* samples, and the 3 *weirdest* values. Tiny. Feeds the AI.
   This is NOT "the first 5 rows" — the first 5 rows lie (see §3, Edge Case 1).
2. **Target JSON** — *the destination.* The final report shape, empty, with
   blanks where numbers go. You write this by hand. It is the spec.
3. **Extraction Script** — *the bulldozer.* Load → clean → quarantine →
   aggregate → emit. The AI writes this. You run it.
4. **Rejects + Run Log** — *the proof.* Every row the script could not parse
   goes to `rejects.csv`; every assumption goes to `run.log`. This is how you
   know nothing was silently dropped. Messy data punishes you for skipping this.

---

## 2. The Pipeline (your case: one huge Excel + a folder of many files)

```
              ┌──────────────────────────────────────────────┐
  RAW INPUTS  │  big_272col.xlsx        folder/*.csv, *.xlsx  │
              └───────────────┬───────────────┬──────────────┘
                              │               │
            ┌─────────────────▼───────────────▼─────────────────┐
   STAGE 1  │  INGEST → land everything into ONE staging DB      │
   (load)   │  chunked, type-as-text first, never trust Excel    │
            │  output:  staging.duckdb  (or staging.sqlite)      │
            └─────────────────────────────┬─────────────────────┘
                                          │
            ┌─────────────────────────────▼─────────────────────┐
   STAGE 2  │  PROFILE → scan staging, emit schema_profile.json  │
   (map)    │  this tiny file is what the AI reads. Not the data.│
            └─────────────────────────────┬─────────────────────┘
                                          │   ← AI reads profile + target JSON here
            ┌─────────────────────────────▼─────────────────────┐
   STAGE 3  │  CLEAN → coerce types, quarantine junk to rejects  │
   (cure)   │  output:  clean tables in the DB + rejects.csv     │
            └─────────────────────────────┬─────────────────────┘
                                          │
            ┌─────────────────────────────▼─────────────────────┐
   STAGE 4  │  AGGREGATE → the heavy SQL (group by / sum / join) │
   (crunch) │  runs in the engine, not in Python memory          │
            └─────────────────────────────┬─────────────────────┘
                                          │
            ┌─────────────────────────────▼─────────────────────┐
   STAGE 5  │  SHAPE → pour aggregates into the target JSON      │
   (emit)   │  output:  report.json  +  run.log                  │
            └────────────────────────────────────────────────────┘
```

**Why a staging DB and not "just pandas"?**
Your inputs are mixed (one giant Excel + many files). `pd.read_excel()` on a
multi-GB sheet can exhaust RAM and silently mistype columns. Landing everything
as **text** into DuckDB/SQLite first means: (a) it always fits — the engine
spills to disk; (b) you clean once, in SQL, deterministically; (c) the "many
files" problem becomes a simple `INSERT … UNION ALL` instead of N special cases.

**DuckDB or SQLite?** For *messy big* data: **DuckDB.** It queries files larger
than RAM, reads CSV/Parquet/Excel directly, and its SQL is friendlier for
aggregation. Use SQLite only if you need a single portable file other tools
already speak. The plan works with either — that choice is isolated to Stage 1.

---

## 3. Edge Cases — where the librarian story is a lie

These are the failures that *will* happen with 272 columns and messy files.
Each one has a defense baked into the pipeline above.

**Edge Case 1 — The first 5 rows lie.**
Rows 1–5 of a 272-column sheet are never representative. `Unit_Cost` is clean at
the top and blank / `"N/A"` / `"45,50"` (European comma) / number-stored-as-text
at row 400,000. Code written from the clean top crashes or *silently miscounts*
halfway down.
→ **Defense:** the AI is fed the **profile** (random + weirdest samples across
all rows), never the top slice. Stage 2.

**Edge Case 2 — The schema itself is garbage.**
Duplicate headers (`Cost`, `Cost.1`, `Cost_FINAL_v2`), merged cells, header on
row 4 not row 1, trailing empty columns, Unicode/whitespace in names.
→ **Defense:** Stage 1 normalizes headers (dedupe, slugify, detect header row)
and records the original→clean mapping in `run.log`. The AI *sees* the mess in
the profile and writes defensive code for it instead of assuming clean names.

**Edge Case 3 — One column, many types.**
The same column holds `45.50`, `"45,50"`, `"approx 45"`, `""`, `#REF!`.
→ **Defense:** Stage 3 *coerces and quarantines* — parse what's parseable, send
unparseable rows to `rejects.csv` with a reason. Nothing vanishes silently.

**Edge Case 4 — "Many files" don't agree.**
Folder files have different column sets, orders, or names for the same thing.
→ **Defense:** Stage 1 maps each file's columns to a **canonical schema** before
union; files that can't be mapped are logged, not force-fitted.

**Edge Case 5 — Bigger than RAM.**
500k × 272 columns is multiple GB; pandas dies.
→ **Defense:** heavy lifting (Stage 4) is **SQL in the engine**, which spills to
disk. Pandas only touches the already-small aggregated result in Stage 5.

**Edge Case 6 — Encodings & locales.**
UTF-8 vs Latin-1, `1.234,56` vs `1,234.56`, `25/12` vs `12/25`, Excel serial
dates (`44561`).
→ **Defense:** explicit locale/encoding settings in Stage 1, asserted and
logged — never guessed per-row.

**Edge Case 7 — Silent drift.**
A future file adds a column, or renames one. The script keeps running and
quietly produces a wrong total.
→ **Defense:** Stage 2 profile is committed to git. A schema change shows up as
a diff. The script *asserts* expected columns exist and fails loudly if not.

---

## 4. Repository Layout

```
AI/
├── ARCHITECTURE.md            ← this file (the plan)
├── data/
│   ├── raw/                   ← drop the big xlsx + the folder of files here (gitignored)
│   └── staging.duckdb         ← built by Stage 1 (gitignored)
├── reports/
│   ├── target_report.json     ← YOU write this: the empty destination shape
│   └── report.json            ← produced output (gitignored)
├── profile/
│   └── schema_profile.json    ← Stage 2 output — the map the AI reads (COMMITTED)
├── scripts/
│   ├── 01_ingest.py           ← raw → staging.duckdb (chunked, text-first)
│   ├── 02_profile.py          ← staging → schema_profile.json
│   ├── 03_clean.py            ← coerce + quarantine → rejects.csv
│   ├── 04_aggregate.sql       ← the heavy group-by/joins
│   └── 05_shape.py            ← aggregates → target shape → report.json
├── rejects.csv                ← runtime quarantine (gitignored)
└── run.log                    ← runtime decisions/assumptions (gitignored)
```

Commit the **profile** and the **target**. Gitignore the **data** and the
**outputs**. The repo holds the *map and the plan*, never the ocean.

---

## 5. The Prompt You Give the AI (Stage 3–5)

Once Stages 1–2 have produced `schema_profile.json`, this is the exact prompt
that turns the architect loose — and it never includes the data:

> "Attached is `schema_profile.json` — the profiled schema of a local DuckDB
> staging table `raw` containing messy manufacturing data (~500k rows, 272
> columns). Attached is `target_report.json` — the exact JSON shape I need.
> Write `03_clean.py`, `04_aggregate.sql`, and `05_shape.py` that: coerce each
> field per its profiled type, quarantine unparseable rows to `rejects.csv` with
> a reason, run the aggregation in DuckDB (not pandas memory), and emit
> `report.json` matching the target exactly. Assert expected columns exist and
> fail loudly on schema drift. Log every assumption to `run.log`."

That is the whole trick. Profile in, target in, three scripts out. The volume
stays on your machine.

---

## 6. Your Run Loop (on your own machine)

```bash
python scripts/01_ingest.py     # raw/  ->  staging.duckdb   (minutes, once per data drop)
python scripts/02_profile.py    # staging -> profile/schema_profile.json   (seconds)
# --- hand profile + target to the AI; it writes 03/04/05 ---
python scripts/03_clean.py      # coerce + quarantine
python scripts/04_aggregate.sql # via: duckdb staging.duckdb < scripts/04_aggregate.sql
python scripts/05_shape.py      # -> reports/report.json
```

Inspect `rejects.csv` and `run.log` **every run**. A report with 4,000 rejects
you didn't notice is a wrong report that looks right.

---

## 7. ARCHITECT'S REVIEW — critiquing this plan (you asked me to review it)

A plan you don't stress-test is a wish. Here is where *this* plan is strong,
where it is risky, and what I would change before trusting it with real numbers.

**Strengths**
- ✅ The AI is never exposed to volume → no context overflow, no hallucinated
  totals, low token cost. The core premise holds.
- ✅ Text-first staging makes mixed inputs (1 Excel + many files) a non-event.
- ✅ Rejects + run.log convert *silent* wrongness into *visible* wrongness.
  This is the single most valuable part for messy data.
- ✅ Heavy compute in the engine (SQL), not pandas memory → survives >RAM.

**Risks & weaknesses (be honest)**
- ⚠️ **The profile is a lossy summary.** A rare-but-critical value (one row with
  a negative cost that should be an error) can hide inside "3 weirdest values"
  and still be missed. *Mitigation:* profile also reports per-column min/max and
  count of out-of-range values, not just samples.
- ⚠️ **Header detection is the fragile joint.** Auto-detecting which row is the
  header in a merged-cell Excel is genuinely hard and can be wrong. *Mitigation:*
  make the header row a **declared config**, not a guess, when auto-detect is
  low-confidence. Human confirms once per file type.
- ⚠️ **Canonical-schema mapping (Edge Case 4) is where most real bugs live.**
  Mapping `Unit_Cost` ≈ `unitcost` ≈ `Cost/Unit` across files is judgment, and
  a wrong map produces a clean-looking wrong number. *Mitigation:* the mapping is
  an explicit, committed file (`column_map.yaml`) a human reviews — never an
  automatic fuzzy match trusted blindly.
- ⚠️ **"Run on your own machine" means the AI can't verify its own output.**
  It writes code it never sees execute. *Mitigation:* the AI must also write a
  `validate.py` of cheap assertions (row counts reconcile, totals ≥ 0, no
  aggregate references a quarantined row) that you run as Stage 6.

**Verdict:** the architecture is sound and is the correct shape for this problem.
Its failure mode is not crashing — it is **producing a confident wrong number
from a bad column-mapping or an unnoticed reject pile.** Therefore the
non-negotiable additions are: (1) a committed `column_map.yaml`, (2) a
`validate.py` reconciliation stage, and (3) always reading `rejects.csv`.
Adopt those three and the plan is trustworthy.

---

## 8. What's Next

Stages 1 and 2 are the only things you can't outsource to the AI cheaply,
because they're the parts that must touch real data to be honest. Once the
`schema_profile.json` exists, everything downstream is the §5 prompt.

Recommended first build: **`scripts/01_ingest.py` + `scripts/02_profile.py`** —
the loader and the profiler. They turn your ocean into the one-page map the AI
needs, and nothing downstream can start without them.
