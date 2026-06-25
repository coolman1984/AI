# REVIEW.md — Weak-Point Audit & Resolutions (all plans)

Date: 2026-06-25. This is a full review pass over `ARCHITECTURE.md`,
`IMPLEMENTATION_PLAN.md` (tabular), `IMPLEMENTATION_PLAN_DOCS.md` (documents),
and the config/schema starters. Every weakness found is listed with a severity
and exactly how it was resolved. Severity legend:

- **S1 — silent-wrong-output:** produces a confident WRONG answer with no error. Worst kind.
- **S2 — crash / data-loss:** fails loudly or loses data, but at least visibly.
- **S3 — robustness / scale:** works on the toy case, struggles on the real one.
- **S4 — polish / clarity.**

---

## A. TABULAR PIPELINE (`IMPLEMENTATION_PLAN.md`)

| # | Sev | Weak point found | Resolution (now in the plan) |
|---|-----|------------------|------------------------------|
| A1 | **S1** | `__row_id` was a per-table integer restarting at 0; after Phase 4's UNION it's no longer unique, so a reject couldn't be traced to its origin row. | `__row_id` is now a globally-unique string `<file>:<sheet>:<n>`; rejects carry `__row_id`. Phase 3 DoD asserts global uniqueness. |
| A2 | **S1** | Re-running ingest could APPEND into existing tables → every downstream number doubles. No idempotency rule. | Phase 3 now mandates `CREATE OR REPLACE` / drop-staging; DoD requires running ingest twice to yield identical counts. |
| A3 | **S1** | Money summed as floating-point `DOUBLE` drifts (cents wrong, won't reconcile) over 500k rows. | Phase 6 now types money columns as `DECIMAL(18,4)` via `clean.money_columns`; DoD checks it. |
| A4 | **S1** | Exact-duplicate rows (common in messy exports) were never addressed → double-counting. | Phase 6 adds duplicate detection with `clean.on_duplicates: flag\|drop` (default `flag`, recorded in `data_quality`, never silent). |
| A5 | **S2** | Multi-sheet workbooks: plan assumed one sheet; extra sheets silently lost. | Phase 3 now enumerates `sheet_names` and ingests each as `raw_<file>_<sheet>` with a `__sheet` column. |
| A6 | **S2** | Big-Excel memory: `pd.read_excel(dtype=str)` on 500k×272 can be 5–15 GB and OOM. Originally hedged as "measure before optimizing." | Phase 3 now states the risk plainly and requires streaming (`openpyxl read_only` + chunked append) or CSV-convert for large files; whole-file load only for small/medium. |
| A7 | **S2** | CSV encoding assumed UTF-8 for all folder files; wrong encoding mangles text silently. | Phase 3 now sniffs per file with `charset-normalizer` (added to requirements) and logs the detected encoding. |
| A8 | S3 | No dry-run / sample mode to validate on a slice before the full batch. | Added `run.sample_limit` to config. |

**Tabular residual risks (accepted, by design — documented so you know):**
- **Type inference is sample-based** and can mislabel a column. Mitigated by
  `out_of_range_count` + `weirdest_values` in the profile and by `rejects.csv`,
  but a human should still skim the profile. (Already flagged in ARCHITECTURE §7.)
- **Per-column locale:** `config.locale` is global. If different columns/files use
  different decimal conventions, set them per-run or split the inputs. Rare; not
  worth complicating v1.

---

## B. DOCUMENT PIPELINE (`IMPLEMENTATION_PLAN_DOCS.md`)

| # | Sev | Weak point found | Resolution (now in the plan) |
|---|-----|------------------|------------------------------|
| B1 | **S1** | Scanned/text decided per WHOLE document (`pdf_is_scanned -> bool`). A mostly-text PDF with a few image pages loses those pages silently. | Replaced with PER-PAGE `scanned_pages()`; Phase 5 extracts text pages with pdfplumber and OCRs ONLY flagged pages, merged in page order. New DoD: a mixed PDF reports exactly its image page. |
| B2 | **S1** | pdfplumber `extract_text()` and `extract_tables()` overlap → table content emitted TWICE (once mangled in text, once as table). | Phase 5a now excludes table bounding boxes from text extraction; DoD verifies table text appears exactly once. |
| B3 | **S1** | Multi-column PDFs: top-to-bottom ordering reads ACROSS columns, scrambling reading order, presented as clean text. | Phase 5a now requires column detection OR an explicit `multi_column_unhandled` warning on such pages — never silent scrambled output. |
| B4 | **S2** | LibreOffice serial-execution gotcha: parallel `soffice` invocations silently fail/block (shared profile). | Phase 4 adds `legacy.soffice_serial` + isolated `UserInstallation` profile guidance, plus the existing timeout. |
| B5 | **S2** | Encrypted PDFs were always a failure even when the password is known. | Phase 3 adds `pdf.passwords` list to try; only a genuinely locked file becomes `encrypted_no_password`. |
| B6 | S3 | No resumability: a crash at doc 9,000/10,000 reprocessed everything. | Added `run.skip_existing` (skip if `output/docs/<doc_id>.json` exists) + `run.sample_limit` dry-run. |
| B7 | S4 | Tech table implied OCR of images embedded in docx/pptx, but no phase did it → scope confusion. | Phase 5d now explicitly scopes embedded-image OCR OUT of v1, to be added as a separate flagged pass. |
| B8 | S4 | `python-magic` needs a different package/binary on Windows. | System-deps note now covers `python-magic-bin` / extension-only fallback. |
| B9 | S4 | No output schema version → can't tell which contract an output was built against. | `schema_version: "1.0"` added to `document.schema.json` (required, `const`) and the plan's inline schema. `jsonschema` added to requirements. |

**Document residual risks (accepted, by design):**
- **OCR quality** depends on scan resolution and language packs. Mitigated by
  logging mean per-page OCR confidence; truly poor scans need human review.
- **Complex layouts** (nested tables, text in figures, rotated pages) are not
  fully solved by any library. The pipeline degrades to warnings, not silence.

---

## C. CROSS-CUTTING IMPROVEMENTS (both pipelines)

| # | Sev | Item | Resolution |
|---|-----|------|------------|
| C1 | S2 | "No row/doc vanished" was only asserted tabular-side originally. | Both pipelines now have the conservation law in their validate phase: `rows_in == clean + rejected` / `docs_in == docs_out + failures`. |
| C2 | S3 | Long runs had no resume/sample controls. | `sample_limit` (both) + `skip_existing` (docs) added. |
| C3 | S4 | Schema/contract versioning. | `schema_version` in the document contract; tabular report carries `report_metadata` (add a version field there if the report shape evolves). |
| C4 | S4 | The two `jsonschema`/`charset-normalizer` deps weren't listed. | Added to the respective `requirements.txt` blocks. |

---

## D. WHAT WAS ALREADY STRONG (kept, not changed)

- The core premise — AI reads the profile/map, never the data — holds in both
  pipelines and is the right architecture.
- Text-first staging (tabular) and one-unified-schema (docs) are correct
  foundational choices.
- `rejects.csv` / `failures.csv` + run logs convert silent wrongness into visible
  wrongness — the single most valuable property for messy data.
- Definition-of-Done gates per phase and the "don't proceed on red" rule are the
  right way to steer a weaker agent. Untouched.
- Explicit human-owned config (`column_map.yaml`, `target_report.json`,
  `document.schema.json`) keeps judgment calls out of the AI's hands.

---

## E. THE ONE THEME ACROSS EVERY S1 FINDING

Every silent-wrong-output bug had the same shape: **a whole-batch assumption
applied to per-item reality.** One row-id space across many tables; one
scanned/text verdict for a mixed PDF; one float type for money; one copy of a
duplicated row; one encoding for many files. The fix is always the same move —
**push the decision down to the smallest correct unit** (per row, per page, per
column, per file) and **record what you did** so a human can see it. That is the
discipline to apply to any new edge case you discover later.
