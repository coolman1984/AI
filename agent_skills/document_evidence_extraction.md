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
- `engines/docs/AGENTS.md`
- `engines/docs/extract.py`
- `engines/docs/ocr.py`
- `engines/docs/search.py`
- `tests/test_documents.py`

## Definition of done
Done means:
- extracted evidence is citation-bearing
- OCR quality is labeled honestly
- review-needed cases are visible
- downstream consumers can use the artifact without guessing source reliability