---
status: ARCHIVED
owner: owner
date: 2026-07-03
---

# Second-Read Audit — post-extraction OCR completeness gate

**Owner's idea (2026-07-03):** after a document is fully extracted, run one final OCR pass over
the page images and compare against what was extracted, so we are highly confident nothing was
silently left behind. This plan turns that into a buildable gate.

## Design decisions (already made — do not relitigate)

1. **Direction is one-way.** OCR output is the *noisier* reading. The audit flags only
   `found_by_ocr_but_missing_in_extraction`. It NEVER edits, "corrects", or adds to extracted
   data — diffs go to the human-review queue with evidence. (Calculation-Integrity Rule: no
   value enters the data path from this gate.)
2. **Compare tokens, not full text.** Full-text diffing of OCR vs extraction is noise. Compare:
   - **numeric tokens** (reuse `engines/docs/verify.py::extract_numeric_tokens` — already
     locale/Korean-unit aware) — these are the high-stakes misses;
   - a **word-coverage ratio**: share of OCR alphabetic words (≥4 chars, per page) that appear
     in the extracted text. Below threshold → page flagged.
3. **It's a gate, not a guarantee.** If OCR itself fails on a page (low quality score), the page
   is flagged `second_read_unavailable` — honestly reported, never counted as "verified".
4. **Cost control.** Full-document second read runs only when the doc feeds a report/brief
   (high stakes) or when `image_profile` says the doc has image-heavy pages. Otherwise sample
   N pages (config). Default thresholds/mode in `config.yaml` under `tools:`.

## What already exists (reuse, do not rebuild)

| Need | Existing code |
|---|---|
| Render PDF page to image | `engines/docs/ocr.py::render_pdf_page` |
| OCR with fallback + quality score | `engines/docs/ocr.py::ocr_cascade`, `extraction_quality` |
| Numeric token extraction (Korean-aware) | `engines/docs/verify.py::extract_numeric_tokens` |
| Image-heavy page detection | `engines/docs/image_profile.py` |
| Human-review routing pattern | `needs_review` flags in `extract.py` / OCR path |
| Evidence + validation rows (FOREMAN) | `tools/run_logger.py::log_evidence`, `log_validation` |

## Build steps (in order; suite green after each)

### Step 1 — `engines/docs/completeness.py` (new, pure logic + one OCR call site)
- `second_read_page(extracted_text: str, ocr_text: str) -> dict` — PURE function:
  returns `{missing_numeric_tokens: list[str], word_coverage: float, flagged: bool}` using
  `extract_numeric_tokens` on both sides (multiset diff: OCR-side tokens not covered by
  extraction-side counts) and the word-coverage ratio. Thresholds as parameters with defaults.
- `second_read_audit(page_texts: list[str], image_loader, cfg) -> CompletenessReport` —
  for each audited page: render → `ocr_cascade` → if OCR quality < threshold mark
  `second_read_unavailable`, else run `second_read_page`. Returns per-page results + doc-level
  verdict: `complete | gaps_found | partially_unverifiable`.
- Dataclass `CompletenessReport` in the same module (do NOT touch `shared/contracts/models.py`).
- **Test `tests/test_second_read.py` (write first, red):**
  (a) extraction contains everything OCR sees → `complete`, no flags;
  (b) OCR text contains `4,700` absent from extraction → flagged, token `4700` named;
  (c) extraction has a token OCR missed → NOT flagged (one-way rule proven);
  (d) garbage OCR (quality 0) → `second_read_unavailable`, not `complete`;
  (e) Korean unit token (`3억`) present only in OCR → flagged with normalized value.

### Step 2 — config + wiring into document extraction
- `config.yaml` → `tools:` add: `second_read: on_report_docs` (`off | sample | on_report_docs | always`),
  `second_read_word_coverage_min: 0.75`, `second_read_sample_pages: 3`.
- `engines/docs/extract.py`: after extraction, when mode applies, call `second_read_audit`;
  attach the report to the document result; flagged pages set `needs_review=True` with warning
  text naming the missing tokens ("second read found 4700 on page 3 not in extraction").
  Keep it OPTIONAL and default-safe: mode `off` must leave current behavior byte-identical
  (existing tests must pass untouched).
- **Test:** extend `tests/test_documents.py` style — fixture doc with a number only in an
  embedded image → extraction result carries the flag; mode `off` → unchanged output.

### Step 3 — FOREMAN gate + evidence
- In the FOREMAN doc-facing path (`skills/` doc skills / `tools/run_logger` users): record one
  `validation_results` row per audited doc (`gate_name='second_read'`, passed, message listing
  missing tokens) and `evidence_items` rows for each flagged page (locator = page number,
  method = `ocr_cascade:<engine>`).
- A report-feeding run with `gaps_found` must go to `blocked`/review, not silently continue.
- **Test:** run a doc skill on the gap fixture → validation row exists, run status blocked.

### Step 4 — docs
- Update `PROJECT_MAP.md` (new module line + gate in the docs-path description) and
  `agent_skills/document_evidence_extraction.md` (mention the gate, when it runs, one-way rule).
- Archive this plan per Doc Law when done.

## Acceptance (definition of done)
1. All new tests green; full suite green; `ruff` clean.
2. Demo: a PPTX/PDF fixture where a number lives ONLY inside an embedded image → pipeline
   flags exactly that number and routes to review; with `second_read: off` behavior is unchanged.
3. No code path writes OCR-derived values into any data table or report — grep-verifiable:
   `completeness.py` exposes only report/flag structures.

## Explicitly out of scope
- Auto-correcting extraction from OCR (forbidden).
- LLM comparison of the two texts (deterministic tokens only).
- Running second-read on spreadsheet/CSV ingestion (numbers path already has reconciliation).
