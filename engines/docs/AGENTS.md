# engines/docs — Document Engine (evidence, not numbers)

**Does:** extract text/tables from PDF/Word/PPT/scans; OCR with confidence gating; search
documents and return cited passages.
**Public interface:** `extract.extract_document`, `extract.PyPdfExtractor`,
`ocr.handle_scanned_page`, `ocr.get_ocr_engine`, `search.search_documents`.
**Real today:** `pypdf` (text PDFs) + plain text + the OCR routing logic + keyword search.
**Adapters (real-if-installed):** `DoclingExtractor` (layout/tables), `PaddleOcrEngine`
(offline EN+AR). Switch via `config.yaml` `tools.document_extractor` / `tools.ocr_engine`.
**Invariants:** documents are EVIDENCE — never a numeric source of truth (numbers come from
the data engine). A scanned/low-confidence page is flagged `needs_review` (human-review
queue, MASTER_PLAN J.2), never silently trusted. Every returned passage carries an
EvidenceRef (file + page).
**Never:** turn OCR text into a fact without review; extract numbers for the variance from a
PDF (that stays in DuckDB).
**Tests:** `pytest tests/test_documents.py`
