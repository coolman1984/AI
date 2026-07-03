# Skill — Document Evidence Extraction

## Mission

Extract, normalize, and route evidence from PDF, Word, PowerPoint, scans, screenshots, and other document-like sources without promoting weak OCR into trusted fact.

## Use this skill when
- the task starts from PDF, Word, PowerPoint, scan, screenshot, or mixed document bundles
- the user asks to search documents, extract passages, inspect attachments, or recover text from scans
- the workflow needs cited evidence from pages, not primary numeric truth
- the task depends on OCR confidence and review gating

## Do not use this skill for
- primary numeric variance calculation
- final executive sign-off
- raw tabular ingestion when the real source is already available as Excel or CSV

## Token budget
- target: <= 2,000 tokens per extraction response
- hard cap: page/slide-bounded passages only; no full-deck dumps

## Input contract
- file path or bundle path with extraction goal
- known document type and page range when available
- privacy tier metadata for external LLM routing

## Output contract
- extracted passages with page/slide locators
- OCR confidence and review-needed flags
- coverage report for chunked summarization runs

## Invariants
- documents are evidence first, not automatic numeric truth
- weak OCR surfaces as review work
- resumable runs persist chunk checkpoints without raw full document text

## Raw data ban
- never dump raw full document text, entire decks, or unbounded OCR output into agent context
- return cited passages, chunk summaries, and coverage metadata only

## Inputs expected
- file path or bundle path
- document type when known
- extraction goal
- whether the need is passage retrieval, OCR recovery, table extraction, or evidence packaging
- any known page range, keywords, or attachment hints

## Outputs expected
- extracted text or passage set
- page-level or unit-level evidence references
- OCR confidence / quality state
- review-needed flags where quality is weak
- extracted tables only as evidence artifacts unless explicitly promoted through the trusted data path
- downstream recommendation for audit, analysis, or human review

## Shared rules from the core contract
- preserve `run_id`
- preserve source identity down to page / slide / attachment when possible
- weak OCR must surface as review work
- documents are evidence first, not automatic numeric truth
- never silently collapse uncertainty

## Standard workflow
1. identify the document type and extraction target
2. attempt native text extraction where available
3. escalate to OCR cascade only when needed
4. score extraction quality and mark weak results for review
5. preserve citations to page / slide / source unit
6. package useful passages or tables for downstream use
7. recommend the next skill based on whether the result is evidence, structured data, or blocked input

## Second-read audit (post-extraction gate)

When `config.yaml` → `tools.second_read` is not `off`, `extract_document` may run a **one-way**
OCR completeness check after native extraction (`engines/docs/completeness.py`):

- Compares **numeric tokens** (via `extract_numeric_tokens`) and **word coverage** — OCR may only
  flag tokens missing from extraction, never overwrite extraction.
- Low OCR quality → page marked `second_read_unavailable` (not “verified”).
- Modes: `off` (default, byte-identical to pre-gate behavior), `sample`, `on_report_docs`
  (`document.feed_report` or image-heavy PPTX), `always`.
- Flagged pages set `needs_review` and warnings name missing tokens (e.g. `4700`).
- FOREMAN: `record_second_read_foreman` logs `gate_name=second_read`; `gaps_found` → run `blocked`.

## Key checks
- born-digital text versus scanned image
- OCR confidence and completeness
- page-level citation integrity
- mixed Arabic / English rendering quality
- duplicate or repeated page text
- table extraction quality versus manual review threshold

## Never do
- never treat OCR output as fully trusted just because text was recovered
- never use a PDF number as the system-of-record for cost variance if the tabular source exists elsewhere
- never drop citation context
- never hide low-confidence extraction inside polished prose

## Typical downstream handoff
Usually hands off to:
- `agent_skills/audit_and_trust.md`
- `agent_skills/management_reporting.md`
- or `agent_skills/spreadsheet_ingestion.md` if extracted tables must be promoted into the trusted tabular path

## Existing repo anchors
- `engines/brain/registry.py` (document registry with hash deduplication)
- `engines/docs/AGENTS.md`
- `engines/docs/extract.py`
- `engines/docs/completeness.py`
- `engines/docs/docling_adapter.py` (hard-layout opt-in parser backend)
- `engines/docs/pptx.py`
- `engines/docs/image_profile.py`
- `engines/docs/summarize.py`
- `engines/docs/glossary.py`
- `engines/docs/provenance.py`
- `engines/docs/rapidocr_adapter.py`
- `engines/docs/translation_check.py`
- `engines/docs/run_state.py`, `engines/docs/llm_bridge.py`
- `engines/docs/workflow_record.py`
- `engines/docs/ocr.py`
- `engines/docs/search.py`
- `engines/email/extract.py`
- `mcp_server/server.py` (summarize_document + ingest_deck + extract_document_hard_layout + extract_workflow_record + register_document routing)
- `tests/test_documents.py`
- `tests/test_second_read.py`
- `tests/test_chunked_summary.py`
- `tests/test_korean_ocr_profile.py`
- `tests/test_translation_check.py`
- `tests/test_workflow_record.py`
- `tests/test_provenance_stamp.py`
- `tests/test_email_extraction.py`

## Definition of done
Done means:
- extracted evidence is citation-bearing
- OCR quality is labeled honestly
- review-needed cases are visible
- long deck/report summarization keeps coverage accounting and blocks on gaps
- structured workflow understanding keeps citations on every required field
- translated workflow fields retain source text and deterministic provenance metadata
- glossary-backed translation checks surface critical-term disagreements before release
- image-only share and OCR review load are measured before heavier OCR escalation
- email body and attachments enter the same governed evidence path with visible failures
- downstream consumers can use the artifact without guessing source reliability
