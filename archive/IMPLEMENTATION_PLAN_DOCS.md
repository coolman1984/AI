# IMPLEMENTATION_PLAN_DOCS.md — Build Instructions for the Coding Agent (Word / PDF / PowerPoint Extraction)

> **READ THIS FIRST. THESE RULES OVERRIDE YOUR INSTINCTS.**
>
> 1. You are building a DOCUMENT extraction pipeline for `.docx`, `.pdf`, and
>    `.pptx` (plus their awkward cousins: `.doc`, scanned PDFs, `.ppt`).
> 2. **NEVER paste whole documents into your own context/output.** You write code
>    that extracts. A 400-page PDF is processed by Python; you only ever look at
>    a *structure profile* and short samples.
> 3. The #1 thing that breaks document pipelines: **a PDF that looks like text
>    but is actually a scanned image.** `pdfplumber` returns empty strings and a
>    naive agent reports "0 pages of text" and moves on. You MUST detect this and
>    route to OCR. This is non-negotiable (Phase 5).
> 4. Do the **Phases in order**. Do not start Phase N+1 until Phase N's
>    **Definition of Done** is fully green. Do not proceed on red.
> 5. Prefer the **explicit, defensive, boring** option. One corrupt/encrypted file
>    must not crash the whole batch — it must be logged and skipped.
> 6. Use the **exact** file paths, function names, and signatures specified.

---

## 0. GOAL (what "done" means)

Build a local Python pipeline that takes a folder of mixed documents
(`.docx`, `.doc`, `.pdf`, `.pptx`, `.ppt`) and produces, for EACH document, a
normalized JSON file capturing its **text (in reading order), tables, headings,
metadata, and per-page/per-slide structure** — plus a single `manifest.json`
summarizing the whole batch and a `failures.csv` listing every document that
could not be processed and why. Scanned/image PDFs are run through OCR. The
pipeline runs from the command line, offline (except optional OCR model files).

**Success =** `python run_all.py` turns `data/raw_docs/` into one JSON per
document under `output/docs/`, a `manifest.json`, a `failures.csv` (even if
empty), and `python scripts/07_validate.py` exits 0.

---

## 1. WHY THIS IS DIFFERENT FROM TABULAR EXTRACTION

| Spreadsheet pipeline | Document pipeline (this one) |
|---|---|
| Rows & columns, one schema | Free text, headings, tables, images — structure varies per file |
| "Profile" = column types | "Profile" = structure inventory (how many pages/tables/images, has text layer?) |
| Main risk: wrong column mapping | Main risk: **scanned PDF returns no text**, lost reading order |
| Engine = DuckDB/SQL | Engine = format-specific parsers + OCR fallback |
| Output = aggregated numbers | Output = normalized text+structure JSON per document |

The compass is the same (AI reads the map, Python reads the ocean). The terrain
is different: documents are messy in *layout*, not in *types*.

---

## 2. TECHNOLOGY STACK (use exactly these)

| Concern | Use | Notes |
|---|---|---|
| PDF text + tables + layout | **`pdfplumber`** | best for text in reading order + table extraction |
| PDF metadata / page ops / encryption check | **`pypdf`** | `is_encrypted`, page count, metadata |
| PDF fast text + image export (for OCR) | **`PyMuPDF`** (`import fitz`) | fast; renders pages to images for OCR |
| Detect scanned vs text PDF | (logic, see Phase 4) | "extracted text length per page ≈ 0" ⇒ scanned |
| OCR fallback | **`pytesseract`** + system **Tesseract** binary | for scanned/image PDFs and images-in-docs |
| Render PDF page → image for OCR | **PyMuPDF** (`page.get_pixmap`) | avoids the heavier `pdf2image`+poppler dep |
| Word `.docx` | **`python-docx`** | paragraphs, styles (headings), tables |
| Word legacy `.doc` | convert via **LibreOffice headless** (`soffice --convert-to docx`) | `.doc` is a different binary format; python-docx CANNOT read it |
| PowerPoint `.pptx` | **`python-pptx`** | slides, shapes, text frames, tables, notes |
| PowerPoint legacy `.ppt` | convert via **LibreOffice headless** | same reason as `.doc` |
| File type detection | **`python-magic`** (libmagic) + extension fallback | extension lies; sniff the bytes |
| Output validation | **`jsonschema`** | validate every output file against `schema/document.schema.json` (Phase 6/8) |
| Config | **`pyyaml`** | |
| Logging | stdlib **`logging`** → `run.log` | not `print()` |
| Tests | **`pytest`** | |
| Python | **3.11+** | |

`requirements.txt`:

```
pdfplumber>=0.11.0
pypdf>=4.0.0
PyMuPDF>=1.24.0
pytesseract>=0.3.10
python-docx>=1.1.0
python-pptx>=0.6.23
python-magic>=0.4.27
jsonschema>=4.20.0
pyyaml>=6.0
pytest>=8.0.0
Pillow>=10.0.0
```

**System dependencies (the agent must check these exist and document them):**
- `tesseract` binary (OCR). Check: `tesseract --version`. Install: apt/brew.
- `libreoffice` / `soffice` (only if `.doc`/`.ppt` present). Check: `soffice --version`.
- `libmagic` (for python-magic). On Debian: `apt install libmagic1`. On
  **Windows**, `python-magic` needs the bundled binary — use
  `pip install python-magic-bin` instead, or fall back to extension-only
  detection and log that byte-sniffing is disabled.

> If a system dep is missing, do NOT crash the whole pipeline. Detect at startup,
> log a clear WARNING, and DISABLE the feature that needs it (e.g. skip OCR,
> mark scanned PDFs as failures with reason "tesseract_not_installed").

---

## 3. DIRECTORY LAYOUT

```
docs_pipeline/
├── IMPLEMENTATION_PLAN_DOCS.md
├── requirements.txt
├── config.yaml
├── run_all.py
├── data/
│   └── raw_docs/                # user drops all documents here (gitignored)
├── output/
│   ├── docs/                    # one <docname>.json per source document (gitignored)
│   ├── manifest.json            # batch summary (gitignored)
│   └── ocr_cache/               # rendered page images / OCR text cache (gitignored)
├── profile/
│   └── document_profile.json    # structure inventory the AI reads (committed)
├── schema/
│   └── document.schema.json     # the unified output contract (committed)
├── scripts/
│   ├── __init__.py
│   ├── common.py                # logging, config, hashing, safe-run wrapper
│   ├── 01_detect.py            # sniff type, encryption, scanned-vs-text → routing table
│   ├── 02_convert_legacy.py    # .doc/.ppt → .docx/.pptx via LibreOffice
│   ├── 03_extract_pdf.py       # pdfplumber/pymupdf → normalized blocks
│   ├── 04_extract_docx.py      # python-docx → normalized blocks
│   ├── 05_extract_pptx.py      # python-pptx → normalized blocks
│   ├── 06_ocr.py              # scanned PDFs / images → text (pytesseract)
│   ├── 06_normalize.py         # merge all extractors → output/docs/<name>.json
│   ├── 07_profile.py           # batch → profile/document_profile.json
│   └── 07_validate.py          # assertions; exit 0/1
├── tests/
│   ├── conftest.py             # builds tiny synthetic docx/pdf/pptx fixtures
│   ├── test_detect.py
│   ├── test_extract.py
│   └── test_normalize.py
├── failures.csv                # documents that could not be processed (gitignored)
├── run.log
└── .gitignore
```

`.gitignore`: `data/raw_docs/`, `output/`, `failures.csv`, `run.log`,
`__pycache__/`, `*.pyc`, `.pytest_cache/`.

---

## 4. THE UNIFIED OUTPUT SCHEMA (the contract — write this in Phase 1)

Every document, regardless of format, becomes ONE JSON file with THIS shape.
Save it as `schema/document.schema.json` and make `06_normalize.py` conform to it.
This is the single most important design decision: **one shape for all formats**,
so downstream consumers never care whether the source was Word, PDF, or PPT.

```json
{
  "schema_version": "1.0",
  "doc_id": "sha1 of file bytes",
  "source_filename": "report_q3.pdf",
  "source_format": "pdf|docx|pptx",
  "was_converted_from": "doc|ppt|null",
  "was_ocr": false,
  "metadata": {
    "title": null, "author": null, "created": null, "modified": null,
    "page_count": 0, "slide_count": 0, "word_count": 0
  },
  "blocks": [
    {
      "block_id": 0,
      "type": "heading|paragraph|list_item|table|image_caption|slide_title|notes",
      "level": 1,
      "page": 1,
      "slide": null,
      "text": "string in correct reading order",
      "table": null
    }
  ],
  "tables": [
    {
      "table_id": 0,
      "page": 3,
      "n_rows": 4,
      "n_cols": 5,
      "rows": [["h1","h2"],["a","b"]]
    }
  ],
  "full_text": "concatenation of all block text in reading order",
  "extraction": {
    "extractor": "pdfplumber|python-docx|python-pptx|ocr",
    "warnings": [],
    "char_count": 0
  }
}
```

**Rules:** `blocks` preserve reading order (this is the hard part for PDFs).
`tables` are also embedded as a block of `type:"table"` so order is preserved,
AND listed in the top-level `tables` array for easy access. `full_text` is the
cheap thing most consumers will use.

---

## 5. THE GRAND PLAN — 8 Phases

```
PHASE 1  Scaffold          → tree, config, common.py, schema/document.schema.json
PHASE 2  Synthetic docs    → tiny fake .docx/.pdf/.pptx (+ a scanned-style PDF)
PHASE 3  Detect & Route    → sniff type, encryption, scanned-vs-text → routing
PHASE 4  Convert legacy    → .doc/.ppt → .docx/.pptx (LibreOffice), or skip+log
PHASE 5  Extract per format → pdf / docx / pptx → normalized blocks  (+ OCR path)
PHASE 6  Normalize         → unified document.json per file
PHASE 7  Profile           → document_profile.json (the map the AI reads)
PHASE 8  Validate + Orchestrate → assertions, manifest, run_all.py, tests
```

Develop against the synthetic fixtures (Phase 2), not the user's real folder.

---

## PHASE 1 — Scaffold

**Steps**
1. Create the tree (§3); `requirements.txt` (§2); `.gitignore`.
2. `config.yaml`:
   ```yaml
   paths:
     raw_dir: data/raw_docs
     out_dir: output/docs
     manifest: output/manifest.json
     ocr_cache: output/ocr_cache
     profile: profile/document_profile.json
     failures: failures.csv
     log: run.log
   features:
     ocr_enabled: true            # auto-disabled if tesseract missing
     convert_legacy: true         # auto-disabled if soffice missing
   ocr:
     dpi: 300                     # render resolution for scanned pages
     language: eng                # tesseract lang pack(s), e.g. "eng+fra"
   pdf:
     scanned_text_threshold: 20   # < this many chars on a PAGE of real text ⇒ that page is scanned
     passwords: []                # optional known passwords to TRY on encrypted PDFs
   legacy:
     soffice_timeout_sec: 120     # kill a hung LibreOffice convert
     soffice_serial: true         # run conversions ONE AT A TIME (see Phase 4 gotcha)
   limits:
     max_pages: 0                 # 0 = no limit; set to cap huge PDFs while testing
   run:
     sample_limit: 0              # 0 = all files; >0 = only first N files (dry-run)
     skip_existing: true          # if output/docs/<doc_id>.json exists, skip (resumable batches)
   ```
3. `scripts/common.py` — must include:
   - `load_config()`, `get_logger(name)` (file + stdout, no dup handlers).
   - `sha1_of_file(path) -> str` (stream in chunks; do NOT read whole file into a string).
   - `safe_process(fn, path, logger) -> result | None` — wraps each document so
     ONE bad file logs to `failures.csv` and returns None instead of crashing the batch.
   - `check_system_deps(cfg) -> dict` — returns which of {tesseract, soffice,
     libmagic} are available; logs warnings and flips off the matching `features`.
4. Write `schema/document.schema.json` (§4).

**Definition of Done**
- [ ] `python -c "from scripts.common import load_config,get_logger,sha1_of_file,safe_process,check_system_deps; print('ok')"` → `ok`.
- [ ] `check_system_deps` correctly reports a missing binary as unavailable (test by temporarily renaming PATH lookups, or just confirm it doesn't throw).

---

## PHASE 2 — Synthetic Documents (your dev target)

**Goal:** tiny fixtures with the messy traits, built in code so they always exist.

**Steps** — in `tests/conftest.py`, generate into a temp dir:
1. `sample.docx` via `python-docx`: a Heading 1, two paragraphs, a bulleted list,
   and a 2×3 table.
2. `sample.pptx` via `python-pptx`: 2 slides — title slide + a content slide with
   a bullet text box, a table, and **speaker notes**.
3. `sample_text.pdf`: a real text-layer PDF (render the docx via LibreOffice if
   available, OR build a simple one with `fitz`/`reportlab`). Must contain
   selectable text and one table.
4. `sample_scanned.pdf`: a PDF whose page is an **image of text with NO text
   layer** (render text to a PNG with Pillow, then place the image on a PDF page
   via `fitz`). This is the OCR trigger — it is essential.
5. (optional) an `encrypted.pdf` (password-set) to exercise the encryption branch.

**Definition of Done**
- [ ] All fixtures build in <2s.
- [ ] `pdfplumber` on `sample_scanned.pdf` returns ~0 chars (trait confirmed:
      it IS scanned), while `sample_text.pdf` returns real text.

---

## PHASE 3 — Detect & Route (`scripts/01_detect.py`)

**Goal:** for each file in `raw_dir`, decide: true format (by bytes, not just
extension), is it encrypted, is it a scanned PDF, does it need legacy conversion.
Output a routing list the later phases consume.

**Required interface**
```python
def detect_format(path) -> str        # 'pdf'|'docx'|'pptx'|'doc'|'ppt'|'unknown' via libmagic + ext
def try_unlock_pdf(path, passwords) -> str | None  # returns a working password, '' for none-needed, or None if locked
def scanned_pages(path, threshold, max_pages) -> list[int]  # PER-PAGE: which pages have < threshold chars
def build_routing(cfg) -> list[dict]   # one entry per file: {path, format, route, flags, scanned_pages}
```
Routing rules:
- `.doc`/`.ppt` → route `convert_legacy` (Phase 4), unless feature disabled →
  failure `legacy_conversion_disabled`.
- encrypted PDF → try each password in `pdf.passwords`; if one works, proceed and
  note it; if none works → failure `encrypted_no_password` (do NOT hang).
- **PER-PAGE scanned detection (critical fix):** a PDF can be PART text, PART
  scanned. Do NOT make a whole-document scanned/not decision — that silently
  loses the scanned pages of a mostly-text PDF (or wastefully OCRs a mostly-image
  one). `scanned_pages()` returns the LIST of page numbers below the char
  threshold. Route the document to `pdf` but carry `scanned_pages` so Phase 5
  extracts text pages with pdfplumber and OCRs ONLY the flagged pages, then
  merges them in page order.
- `.docx` → `docx`; `.pptx` → `pptx`.
- `unknown`/corrupt → failure `unrecognized_format`.

**Common mistakes**
- Trusting the extension. A `.pdf` can be a renamed `.docx`. Sniff bytes.
- Treating "no text extracted" as "empty document." It usually means SCANNED.
  Route those PAGES to OCR, never silently emit an empty doc.
- Deciding scanned/text for the whole PDF. It's a PER-PAGE property.

**Definition of Done**
- [ ] Routing tags `sample_scanned.pdf` with `scanned_pages: [1]`,
      `sample_text.pdf` with `scanned_pages: []`, and (if present) `encrypted.pdf`
      as a failure unless a matching password is configured.
- [ ] A synthetic MIXED pdf (one text page + one image page) reports exactly the
      image page in `scanned_pages`.
- [ ] No file crashes detection; unreadable ones land in `failures.csv`.

---

## PHASE 4 — Convert Legacy (`scripts/02_convert_legacy.py`)

**Goal:** turn `.doc`→`.docx` and `.ppt`→`.pptx` using LibreOffice headless, so
the modern parsers can read them. python-docx/python-pptx CANNOT read the old
binary formats — conversion is mandatory for those.

**Steps**
1. Command: `soffice --headless --convert-to docx --outdir <tmp> <file.doc>`
   (and `pptx` for `.ppt`). Run with a **timeout** (`legacy.soffice_timeout_sec`)
   — LibreOffice can hang; a hung convert must become a `failure`, not a stuck
   pipeline.
2. **SERIAL EXECUTION GOTCHA:** LibreOffice uses a single shared user profile and
   a second `soffice` invocation while another is running will silently fail or
   block. If you ever parallelize the batch, convert legacy files ONE AT A TIME
   (`legacy.soffice_serial: true`), OR give each invocation an isolated profile
   via `-env:UserInstallation=file:///tmp/lo_<uniqueid>`. Do not run two bare
   `soffice` converts at once.
3. Record `was_converted_from` so the final JSON keeps provenance.
4. If `soffice` missing → these files are failures with a clear reason.

**Definition of Done**
- [ ] If a `.doc` fixture is available, it converts and the result is readable by
      python-docx. If `soffice` absent, it lands in failures with the right reason
      (not a crash).

---

## PHASE 5 — Extract Per Format (03/04/05_extract + 06_ocr)

**Goal:** each extractor turns one file into a list of normalized `blocks`
(+ `tables` + `metadata`) in READING ORDER.

### 5a. `03_extract_pdf.py` (text PDFs, possibly with some scanned pages)
- Use `pdfplumber` page by page. For each page: extract words/lines for text
  blocks, and `page.extract_tables()` for tables.
- **PER-PAGE OCR MERGE:** if this page number is in the routing's `scanned_pages`,
  do NOT use pdfplumber text for it — get its text from `06_ocr.py` instead and
  insert those OCR blocks at the correct page position. The output interleaves
  text-layer pages and OCR pages in page order.
- **TABLE/TEXT DOUBLE-COUNTING (pdfplumber gotcha):** `extract_text()` and
  `extract_tables()` OVERLAP — the cells inside a table also appear in the page
  text, so naive concatenation prints every table twice (once mangled, once as a
  table). Get the table bounding boxes from `page.find_tables()` and EXCLUDE
  those regions from the text extraction (`page.outside_bbox(...)` /
  filter words whose coords fall in a table bbox). Verify the fixture's table
  text appears exactly once.
- **READING ORDER / MULTI-COLUMN LIMITATION:** simple top-to-bottom ordering is
  correct for single-column pages but SCRAMBLES two-column layouts (academic
  papers, brochures) — it reads across the columns instead of down each. Detect
  multi-column pages (a vertical gutter of whitespace splitting the words into
  left/right clusters) and order each column top-to-bottom, left column first.
  If you don't implement column detection, you MUST record a
  `warning: "multi_column_unhandled"` on such pages so the consumer knows the
  order may be wrong — never silently emit scrambled text as if it were clean.
- Strip repeated **headers/footers** (text that appears at the same y-position on
  most pages) — log how many you removed. (Common mistake: page numbers and
  running headers polluting every page's text.)
- Pull metadata via `pypdf` (title/author/dates, page_count).

### 5b. `04_extract_docx.py`
- Iterate `document.element.body` to keep paragraphs AND tables in document
  order (iterating `paragraphs` then `tables` separately LOSES order — do not do
  that). Map Word styles → block types: `Heading 1..N` → `heading` with `level`;
  `List*` → `list_item`; else `paragraph`.
- Extract tables to `rows`. Metadata via `core_properties`.

### 5c. `05_extract_pptx.py`
- For each slide: title shape → `slide_title`; body text frames → `paragraph`/
  `list_item` (use paragraph levels for bullet depth); tables → table blocks;
  **speaker notes** → `type:"notes"`. Tag every block with `slide`.
- Slides have NO inherent reading order among shapes — order by shape top/left
  position (y then x) so output is stable and human-sensible.

### 5d. `06_ocr.py` (the scanned PAGES flagged by routing)
- For each page in `scanned_pages`: render to image with PyMuPDF at `cfg.ocr.dpi`
  (`page.get_pixmap(dpi=...)`), save to `ocr_cache`, run `pytesseract.image_to_string`
  with `cfg.ocr.language`. Cache by `doc_id+page` so re-runs don't re-OCR.
- Set `was_ocr: true` on the document and a per-block/per-page note. OCR text is
  lower confidence — add `warning: "ocr_low_confidence"`. If `pytesseract`
  exposes confidence (`image_to_data`), log the mean confidence per page so a
  human can spot garbage OCR.
- A fully-scanned PDF is just the case where `scanned_pages` == every page.
- If tesseract missing → failure `tesseract_not_installed` (do not silently emit empty).

> NOTE on the tech-table mention of "images-in-docs": OCR of images EMBEDDED in
> `.docx`/`.pptx` (e.g. a screenshot pasted into a slide) is OUT OF SCOPE for v1
> — only scanned-PDF pages are OCR'd. If you want embedded-image OCR later, add
> it as a separate, explicitly-flagged pass; do not silently attempt it now.

**Common mistakes (all formats)**
- Losing reading order (the #1 quality bug). Always emit blocks in document order.
- Dropping tables into the text stream as mangled lines — extract them as tables.
- Forgetting speaker notes in PPTX (often where the real content is).
- Re-OCR'ing on every run (slow) — cache it.

**Definition of Done**
- [ ] Each extractor returns blocks in correct order for its fixture; the docx
      heading is `type:heading level:1`; the pptx notes appear as `type:notes`;
      the scanned PDF yields real text via OCR with `was_ocr:true`.

---

## PHASE 6 — Normalize (`scripts/06_normalize.py`)

**Goal:** merge whichever extractor ran into ONE `document.schema.json`-shaped
file per source, written to `output/docs/<doc_id_or_name>.json`.

**Steps**
1. Assemble `doc_id` (sha1), metadata, `blocks`, `tables`, and `full_text`
   (concatenate block text in order with `\n\n`).
2. Compute `word_count`, `char_count`. Fill `extraction.extractor` and any warnings.
3. Validate the object against `schema/document.schema.json` before writing
   (use a light check: required keys present, types correct). A doc that fails
   schema validation is a failure, logged — never write a malformed JSON.

**Definition of Done**
- [ ] Every successfully-processed fixture yields a JSON file that conforms to
      the schema and has non-empty `full_text` (including the OCR'd one).
- [ ] Filenames are unique even if two sources share a name (use `doc_id`).

---

## PHASE 7 — Profile (`scripts/07_profile.py`)

**Goal:** emit `profile/document_profile.json` — the small batch map the next AI
step reads INSTEAD of the documents. It describes the *shape* of the corpus.

**Output shape**
```json
{
  "generated_at": "ISO-8601",
  "doc_count": 42,
  "by_format": {"pdf": 30, "docx": 8, "pptx": 4},
  "ocr_used_count": 6,
  "converted_legacy_count": 2,
  "failure_count": 3,
  "block_type_histogram": {"paragraph": 5120, "heading": 410, "table": 88, "notes": 30},
  "avg_pages": 14.2,
  "samples": [
    {"source_filename": "report_q3.pdf", "first_heading": "...", "first_200_chars": "...", "n_tables": 5}
  ],
  "failures_preview": [{"file": "x.pdf", "reason": "encrypted_no_password"}]
}
```
Rules: `samples` = a handful of SHORT excerpts (first heading, first 200 chars,
table count) from RANDOM documents — never full text. Keep the file < 100 KB
regardless of corpus size.

**Definition of Done**
- [ ] `document_profile.json` validates as JSON, is < 100 KB, and its
      `block_type_histogram` reflects the fixtures (e.g. has `notes` and `table`).

---

## PHASE 8 — Validate + Orchestrate (`07_validate.py` + `run_all.py` + tests)

**Steps**
1. `07_validate.py` assertions (exit 0/1):
   - `doc_count_in == docs_out + failure_count` (no document silently vanished).
   - Every output JSON conforms to the schema (required keys, types).
   - No output `full_text` is empty UNLESS the doc is flagged a known failure.
   - `ocr_used_count` matches the number of docs with `was_ocr:true`.
2. `run_all.py`: detect → convert → extract/ocr → normalize → profile → validate,
   in order, stop-on-first-failure, with `--from <phase>` resume. Writes
   `manifest.json` summarizing counts. MUST honor `run.skip_existing` (skip docs
   whose `output/docs/<doc_id>.json` already exists, so a crashed batch resumes
   without redoing work) and `run.sample_limit` (process only the first N files,
   for a fast dry-run before committing to the full corpus).
3. Tests:
   - `test_detect.py`: scanned vs text vs encrypted classified correctly.
   - `test_extract.py`: reading order preserved; docx heading level; pptx notes
     captured; table rows correct.
   - `test_normalize.py`: output conforms to schema; doc-conservation equation holds.

**Definition of Done (project)**
- [ ] `pytest` green.
- [ ] `python run_all.py` on fixtures produces per-doc JSON, `manifest.json`,
      `failures.csv`, and `07_validate.py` exits 0.
- [ ] A short usage note explains pointing `config.yaml` at the real
      `data/raw_docs/` and rerunning.

---

## 6. TOP 12 MISTAKES TO AVOID (DOCUMENTS)

1. **Pasting whole documents into your context.** Use the profile + samples.
2. **Treating a scanned PDF as empty.** No text layer ⇒ OCR, not skip.
3. **Trusting file extensions.** Sniff bytes with libmagic; `.pdf` may be a docx.
4. **Trying to read `.doc`/`.ppt` with python-docx/pptx.** They can't — convert
   with LibreOffice first.
5. **Losing reading order** — iterating docx paragraphs then tables separately,
   or dumping pptx shapes in arbitrary order. Order by document/position.
6. **Letting one bad file kill the batch.** Wrap every doc in `safe_process`;
   log to `failures.csv` and continue.
7. **Mangling tables into text.** Extract tables AS tables (rows), not flattened.
8. **Forgetting PPTX speaker notes** — often the substantive content.
9. **Running headers/footers/page numbers polluting every page** — detect and strip.
10. **Re-OCR'ing every run.** Cache OCR output by doc_id+page.
11. **Hanging on encrypted PDFs or LibreOffice converts.** Check encryption up
    front; put a timeout on `soffice`.
12. **Proceeding past a red phase.** Each phase has a Definition of Done. Honor it.

---

## 7. EXECUTION CHEAT-SHEET

```bash
pip install -r requirements.txt
# system deps (once): tesseract-ocr, libreoffice, libmagic1

python scripts/01_detect.py          # → routing table
python scripts/02_convert_legacy.py  # .doc/.ppt → .docx/.pptx
python scripts/03_extract_pdf.py     # text PDFs
python scripts/04_extract_docx.py    # Word
python scripts/05_extract_pptx.py    # PowerPoint
python scripts/06_ocr.py             # scanned PDFs
python scripts/06_normalize.py       # → output/docs/*.json
python scripts/07_profile.py         # → profile/document_profile.json
python scripts/07_validate.py        # exit 0 = trustworthy
# or:
python run_all.py
pytest
```

**ALWAYS read `failures.csv` after a run.** A corpus where 200 scanned PDFs
silently failed is a corpus you think you extracted but didn't. That habit is
the difference between trusting the output and being fooled by it.

---

## 8. ORDER OF WORK FOR YOU (the coding agent), restated

Phase 1 → verify → Phase 2 → … → Phase 8 → verify. Develop against the synthetic
fixtures (especially the scanned PDF). Only after tests pass does the user drop
their real documents into `data/raw_docs/`, install the system deps, set
`ocr.language` for their languages, and run `python run_all.py`. Do not skip
phases. Do not proceed on red. Do not read the ocean of documents — read the map.
