# engines/docs — Document Engine (evidence, not numbers)

**Does:** extract text/tables from PDF/Word/PPT/scans; OCR with confidence gating; search
documents and return cited passages.
**Public interface:** `extract.extract_document`, `extract.PyPdfExtractor`,
`pptx.PptxExtractor`,
`ocr.ocr_cascade`, `ocr.extract_page_text`, `ocr.extraction_quality`, `ocr.render_pdf_page`,
`search.search_documents`, `verify.extract_numeric_tokens`,
`verify.normalize_korean_unit`, `verify.figure_matches`,
`verify.citation_supports_claim`,
`prompt_builder.build_extraction_prompt`,
`summarize.summarize_document` (chunked coverage summary + persisted manifest),
`workflow_record.extract_workflow_record` (validated workflow schema from cited fields),
`workflow_record.WorkflowRecord`, `workflow_record.WorkflowField`,
`workflow_record.stamp_workflow_record`,
`glossary.FactoryGlossary`, `glossary.GlossaryEntry`,
`translation_check.check_translation_terms`,
`provenance.build_provenance_stamp`, `provenance.compute_confidence`,
`report_reader.read_report` (takes PDF path + LLMBridge),
`report_reader.store_report_knowledge` (writes to ``.brain/reports/``),
`report_reader.LLMBridge` (Protocol, ``generate(prompt) -> str``),
`report_reader.OpencodeLLM` (subprocess wrapper, never in tests),
`report_reader.ReportKnowledge`, `report_reader.KeyPoint` (text + page).
**Real today:** `pypdf` (text PDFs) + native `.pptx` extraction + plain text +
**OCR cascade with real Tesseract & RapidOCR** + PyMuPDF page rasterizer + the quality gate +
keyword search + chunked coverage summaries for long documents.
Structured workflow understanding now has a validated record seam for purpose, steps, roles,
KPIs, changes, questions, and risks with citations, original-language retention, a deterministic
provenance stamp, and glossary-backed translation checks.
**OCR cascade (`config.yaml tools.ocr_cascade`):** tesseract → rapidocr → paddleocr →
surya → vlm. Each tier runs only if installed; if born-digital text is poor, escalate; if
all tiers are poor, flag `needs_review`. **Adapters (real-if-installed):** Docling,
PaddleOCR, Surya, VLM-OCR.
**Invariants:** documents are EVIDENCE — never a numeric source of truth (numbers come from
the data engine). A scanned/low-confidence page is flagged `needs_review` (human-review
queue, MASTER_PLAN J.2), never silently trusted. Every returned passage carries an
EvidenceRef (file + page).
**Never:** turn OCR text into a fact without review; extract numbers for the variance from a
PDF (that stays in DuckDB).
**Tests:** `pytest tests/test_documents.py`; `pytest tests/test_pptx_extraction.py`;
`pytest tests/test_chunked_summary.py`; report-reader tests:
`pytest tests/test_report_reader.py`; workflow record tests:
`pytest tests/test_workflow_record.py`; provenance tests:
`pytest tests/test_provenance_stamp.py`; translation-check tests:
`pytest tests/test_translation_check.py`
**store_report_knowledge:** `base_dir` injectable for tests (default `.brain/reports`);
`ReportKnowledge` includes `warnings: list[str]` field; out-of-range key_point pages are
dropped with a warning. Language detection: Hangul → `"ko"`, else `"en"`.
