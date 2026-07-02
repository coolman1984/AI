# Progress

> Historical progress log. For current architecture and next work, read
> `03_design/assistant_master_plan.md`, `03_design/phase_a_cards.md`, and
> `00_control/restart_notes.md`. Older entries keep their original task labels
> for audit history.

Date: 2026-06-30
Completed: Stages 0-7 of Factory Second Brain (foundation -> numeric trust loop -> audit +
sign-off -> decision memory -> documents + OCR cascade -> knowledge + temporal memory ->
dashboard + PPTX -> multi-department + factory brain). Adopted the Master Agent OS and
instantiated the governance file tree from real state.
Files changed: engines/*, serving/*, shared/*, mcp_server/*, gov/*, tests/*, run_demo.py,
docs (MASTER_PLAN, FACTORY_SECOND_BRAIN, BUILD, RISK_AND_GAPS_AUDIT, AGENTS, CODEX_PLAN),
governance (00_control..07_archive).
Validation performed: ruff clean; pytest 26 passed; run_demo end-to-end OK.
Evidence recorded: E1-E10.
Problems found: none open (see issue_tracker.md for by-design adapter gaps).
Next task: T8 - price/qty/mix variance decomposition.
Confidence level: High (verified by tests + demo), with honest caveats on heavy adapters.

---
Date: 2026-06-30 (T8)
Completed: T8 price/volume/mix variance decomposition (`engines/data/variance.price_volume_mix`
+ `engines/data/drivers` runner + MCP tool `explain_variance` + `finance_standards.csv`). It
explains why a cost variance moved and reconciles exactly (`price + volume + mix == total`).
Files changed: `engines/data/variance.py`, `engines/data/drivers.py`, `shared/contracts/models.py`,
`mcp_server/server.py`, `run_demo.py`, `tests/test_drivers.py`, `data/sample/finance_standards.csv`.
Validation performed: ruff clean; pytest 29 passed; demo shows -50 = +50 -99 -1.
Evidence recorded: E11.
Problems found: none.
Next task: T8b - surface the drivers on the card + dashboard.
Confidence level: High (reconciliation proven by test + demo).

---
Date: 2026-07-01
Completed: audited the architecture-vs-reality gap, verified the local baseline on `.venv`
(`pytest 28 passed, 1 skipped`), created a governed implementation plan for the next phases,
and expanded T8b into execution slices.
Files changed: `03_design/implementation_plan.md`, `00_control/task_queue.md`,
`00_control/decisions.md`, `05_validation/issue_tracker.md`.
Validation performed: `. .venv/bin/activate && pytest -q`.
Evidence recorded: E13.
Problems found: branch-policy divergence is controlled (I4); heavy infrastructure remains
intentionally blocked behind P2 gates (I1).
Next task: T8b1 - add a typed driver payload to the manager card contract.
Confidence level: High (plan grounded in current code + green tests).

---
Date: 2026-07-01 (T8b)
Completed: surfaced the price/volume/mix view in the manager card and HTML dashboard, with a
truth-preserving refinement: the driver panel is labeled explicitly as an operating view against
standard cost, so it cannot be confused with the main budget variance headline.
Files changed: `shared/contracts/models.py`, `serving/{card,open_design}.py`,
`engines/brain/orchestrator.py`, `mcp_server/server.py`, `run_demo.py`, tests, and module
`AGENTS.md` files.
Validation performed: targeted pytest => `8 passed, 1 skipped`; full pytest => `29 passed, 1 skipped`;
`python run_demo.py` confirmed the card text and visual output include the new driver view.
Evidence recorded: E14.
Problems found: none in this slice; the next bottleneck is real data, not rendering.
Next task: P2 - lock the first real finance workflow and profile one real export.
Confidence level: High (feature implemented, tested, and demoed with honest labeling).

---
Date: 2026-07-01 (P2.1)
Completed: locked the first real workflow in governance files as monthly material cost variance
review for Cost Control / Finance, and made the current non-goals explicit so the team cannot drift
into heavy infrastructure early.
Files changed: `00_control/mission.md`, `00_control/open_questions.md`,
`00_control/success_contract.md`, `00_control/task_queue.md`.
Validation performed: writer worker draft reviewed by reviewer worker; final scope trimmed to the
smallest correct slice and re-read in repo.
Evidence recorded: E15.
Problems found: no real export has landed yet, so P2.2 remains the active bottleneck.
Next task: P2.2 - receive and profile one real export.
Confidence level: High (scope locked, next move clarified).

---
Date: 2026-07-01 (IS1)
Completed: turned the unified ingestion storage contract into working code: run lifecycle tracking,
reject persistence, and a minimal DuckDB schema now exist and are verified by dedicated tests.
Files changed: `engines/data/ingest.py`, `tests/test_ingestion_spine.py`, plus governance files
reflecting the new project state.
Validation performed: new targeted pytest => `10 passed`; data-slice pytest => `13 passed`; full
pytest => `39 passed, 1 skipped`.
Evidence recorded: E17.
Problems found: the contract exists, but Excel/CSV still uses the old demo-style path and needs
IS2; P2.2 still waits on the first real export.
Next task: two-track move - P2.2 externally and IS2 internally.
Confidence level: High (contract implemented, tested, and integrated without breaking the project).

---
Date: 2026-07-01 (IS2.1)
Completed: started IS2 for real by adding a tracked CSV ingestion path on top of the new storage
contract, so callers can create, run, and finish a tracked ingest in one reusable step instead of
manual three-step chaining.
Files changed: `engines/data/ingest.py`, `tests/test_ingestion_spine.py`, and governance files
reflecting that IS2 has begun.
Validation performed: targeted pytest => `13 passed`; data-slice pytest => `16 passed`; full pytest
=> `42 passed, 1 skipped`.
Evidence recorded: E18.
Problems found: CSV is now tracked cleanly, but the path is still text-first demo ingestion and
needs the next IS2 slice for typed reusable ingestion; P2.2 still waits on the first real export.
Next task: continue IS2 internally while waiting for P2.2 externally.
Confidence level: High (IS2 has moved from plan to code without fake Excel breadth).

---
Date: 2026-07-01 (IS2.2)
Completed: closed the gap IS2.1 left open - `ingest_csv_tracked` previously always reported
`reject_count=0`; it now detects embedded total/subtotal rows and exact-duplicate rows, quarantines
them to `ingestion_rejects` with a reason, and keeps only accepted rows in the target table.
Files changed: `engines/data/ingest.py`, `tests/test_ingestion_spine.py`, `engines/data/AGENTS.md`,
`00_control/{task_queue,evidence_log,restart_notes}.md`.
Validation performed: targeted pytest `tests/test_ingestion_spine.py` => `16 passed`; full pytest
=> `42 passed, 4 skipped`; `ruff check .` => clean.
Evidence recorded: E19.
Problems found: none in this slice; multi-sheet Excel (IS2.3) and per-column type inference
(IS2.4) are still open, and P2.2 still waits on the first real export.
Next task: IS2.3 or IS2.4.
Confidence level: High (reject flow implemented test-first, conservation law asserted).

---
Date: 2026-07-01 (Ingestion focus)
Completed: translated Mohamed's new priority into project governance: extraction from Excel, PDF
tables, PowerPoint, and email into local storage with query + calculation readiness is now the
explicit engineering backbone under the locked workflow.
Files changed: `00_control/mission.md`, `00_control/task_queue.md`, `03_design/implementation_plan.md`,
`05_validation/issue_tracker.md`, `03_design/unified-ingestion-spine.md`.
Validation performed: writing worker draft reviewed by reviewer worker; schema design corrected to
avoid all-text generic columns; repo files re-read after patching; `pytest -q` => `29 passed, 1 skipped`.
Evidence recorded: E16.
Problems found: P2.2 still depends on an external real export; PowerPoint and email remain planned
but not yet implemented.
Next task: two-track move - wait for the first real export externally, and start IS1 internally.
Confidence level: High (priority clarified without fake breadth).

---
Date: 2026-07-02 (OSS-backed planning alignment)
Completed: reworked the live planning path so later phases use repo-owned wrappers around
clean-licensed OSS where the approved plan allows it, instead of assuming greenfield engine builds
across the board. The queue now matches the B-F card structure and archives the stale umbrella rows
it replaced.
Files changed: `03_design/oss_reference_evaluation.md`,
`03_design/current_implementation_plan.md`, `03_design/phase_b_to_f_cards.md`,
`00_control/task_queue.md`, `00_control/restart_notes.md`, `00_control/run_log.md`.
Validation performed: re-read the approved master plan, local OSS README/license files, the revised
B-F cards, and the rewritten task queue; checked that the next-action pointer still lands on A0.2
and that stale rows (`IS4`, `IS5`, `T9`, `T10`, `T11`) are now archived.
Evidence recorded: E21.
Problems found: this is planning/governance progress only; no product code or tests were changed in
this slice, and Phase A implementation still resumes at A0.2.
Next task: A0.2, then later-phase execution should follow the OSS-backed queue (`RapidOCR` first,
`Docling` later, stable `mcp-python-sdk` later, graph backends only behind contracts).
Confidence level: High (live planning docs and queue now tell one consistent story).

---
Date: 2026-07-02 (A0 gate green)
Completed: verified that the deterministic verifier, citation-support checks, privacy gate,
external-call ledger, LLM chokepoint, prompt-injection defense, report-reader gate wiring, and
render-time provenance tagging are all green together. The one live failure was the dashboard HTML
path not forcing provenance tags; that path now renders tags visibly and fails closed on unknown
sources.
Files changed: `serving/open_design.py`, `00_control/{task_queue,restart_notes,evidence_log}.md`.
Validation performed: targeted pytest `tests/test_verify.py` => `14 passed`; targeted pytest
`tests/test_serving.py` => `3 passed, 1 skipped`; full `pytest -q` => `106 passed, 4 skipped`;
`ruff check serving/open_design.py` => clean.
Evidence recorded: E22.
Problems found: none in the Phase A rail stack after the serving fix; the project is now ready to
start B.1 while P2.2 remains externally blocked.
Next task: B.1 - native PPTX extractor (thin deterministic path).
Confidence level: High (suite green and queue now matches the repo state).

---
Date: 2026-07-02 (B.1)
Completed: built the native PPTX extraction path into the document evidence spine without adding a
new dependency. The repo now reads `.pptx` package XML directly, preserves slide numbers, captures
table rows, routes `.pptx` through `extract_document`, and exposes the deck path through the MCP
tool surface as `ingest_deck`.
Files changed: `engines/docs/pptx.py`, `engines/docs/extract.py`, `mcp_server/server.py`,
`tests/test_pptx_extraction.py`, `engines/docs/AGENTS.md`,
`agent_skills/document_evidence_extraction.md`, `AGENT_SKILL_MAP.md`,
`00_control/{task_queue,restart_notes,evidence_log}.md`.
Validation performed: `pytest tests/test_pptx_extraction.py -q` => `2 passed`; document slice
pytest => `7 passed`; full `pytest -q` => `108 passed, 4 skipped`; targeted `ruff check` on the
edited code and docs-facing files => clean.
Evidence recorded: E23.
Problems found: none in this slice; the next planned build step is B.2 chunked map-reduce coverage.
Next task: B.2 - chunked map-reduce coverage.
Confidence level: High (native deck extraction is green and routed through the real repo seams).

---
Date: 2026-07-02 (B.2)
Completed: built chunked map-reduce coverage for long document summarization. The new summarizer
chunks pages/slides, persists a coverage report, and blocks on missing or oversize pages instead of
silently truncating.
Files changed: `engines/docs/summarize.py`, `engines/docs/report_reader.py`,
`mcp_server/server.py`, `engines/docs/AGENTS.md`, `agent_skills/document_evidence_extraction.md`,
`AGENT_SKILL_MAP.md`, `tests/test_chunked_summary.py`, `tests/test_report_reader.py`,
`00_control/{task_queue,restart_notes,evidence_log,progress}.md`.
Validation performed: targeted `pytest tests/test_chunked_summary.py tests/test_report_reader.py -q`
=> `29 passed`; `ruff check` on changed Python files => clean; full `pytest -q` => `112 passed,
4 skipped`.
Evidence recorded: E24.
Problems found: none in this slice; the next planned build step is B.3 WorkflowRecord schema.
Next task: B.3 - WorkflowRecord schema.
Confidence level: High (chunk coverage is green, persisted, and routed through the real repo seams).

---
Date: 2026-07-02 (B.3)
Completed: built the WorkflowRecord schema for cited deck understanding. The new record normalizes
purpose, steps, roles, KPIs, changes, open questions, and optional risks into a validated
structure, and the MCP surface now exposes a normalization path through `extract_workflow_record`.
Files changed: `engines/docs/workflow_record.py`, `mcp_server/server.py`,
`tests/test_workflow_record.py`, `engines/docs/AGENTS.md`,
`agent_skills/document_evidence_extraction.md`, `AGENT_SKILL_MAP.md`,
`00_control/{task_queue,restart_notes,evidence_log,progress}.md`.
Validation performed: targeted `pytest tests/test_workflow_record.py tests/test_chunked_summary.py
tests/test_report_reader.py -q` => `34 passed`; `ruff check` on changed Python files => clean;
full `pytest -q` => `117 passed, 4 skipped`.
Evidence recorded: E25.
Problems found: none in this slice; the next planned build step is B.4 original-language retention
and provenance stamp.
Next task: B.4 - original-language retention and provenance stamp.
Confidence level: High (workflow schema is green, cited, and routed through the real repo seams).

---
Date: 2026-07-02 (B.4)
Completed: extended workflow records to retain original-language source text beside translated
fields and added deterministic provenance stamping with source hash, stable source identity, run
metadata, and confidence inputs.
Files changed: `engines/docs/provenance.py`, `engines/docs/workflow_record.py`,
`mcp_server/server.py`, `tests/test_provenance_stamp.py`, `tests/test_workflow_record.py`,
`engines/docs/AGENTS.md`, `agent_skills/document_evidence_extraction.md`, `AGENT_SKILL_MAP.md`,
`00_control/{task_queue,restart_notes,evidence_log,progress}.md`.
Validation performed: targeted `pytest tests/test_workflow_record.py tests/test_provenance_stamp.py
tests/test_chunked_summary.py tests/test_report_reader.py -q` => `39 passed`; `ruff check` on
changed Python files => clean; full `pytest -q` => `122 passed, 4 skipped`.
Evidence recorded: E26.
Problems found: none in this slice; the next planned build step is B.5 Korean-English glossary and
critical-term check.
Next task: B.5 - Korean-English glossary and critical-term check.
Confidence level: High (bilingual workflow fields and provenance stamps are green in the live repo).

---
Date: 2026-07-02 (B.5)
Completed: added an accepted-entry factory glossary and a deterministic translation-check path for
workflow records. The repo now computes glossary match ratio from actual text, flags unknown
critical terms, and blocks KPI back-translation disagreements without relying on model self-scores.
Files changed: `engines/docs/glossary.py`, `engines/docs/translation_check.py`,
`engines/docs/summarize.py`, `mcp_server/server.py`, `tests/test_translation_check.py`,
`engines/docs/AGENTS.md`, `agent_skills/document_evidence_extraction.md`, `AGENT_SKILL_MAP.md`,
`00_control/{task_queue,restart_notes,evidence_log,progress}.md`.
Validation performed: targeted `pytest tests/test_translation_check.py tests/test_workflow_record.py
tests/test_provenance_stamp.py tests/test_chunked_summary.py tests/test_report_reader.py -q` =>
`45 passed`; `ruff check` on changed Python files => clean; full `pytest -q` => `128 passed,
4 skipped`.
Evidence recorded: E27.
Problems found: none in this slice; the next planned build step is B.6 non-numeric brief audit.
Next task: B.6 - non-numeric brief audit.
Confidence level: High (glossary checks are green, local, and wired into the live document seams).

---
Date: 2026-07-02 (B.6)
Completed: added the non-numeric brief audit path as a real independent check for document-derived
claims. The new audit does second extraction, citation re-check, disagreement routing, and keeps
numeric claims on the existing verifier path.
Files changed: `engines/audit/brief_audit.py`, `mcp_server/server.py`, `tests/test_brief_audit.py`,
`engines/audit/AGENTS.md`, `agent_skills/audit_and_trust.md`, `AGENT_SKILL_MAP.md`,
`00_control/{task_queue,restart_notes,evidence_log,progress}.md`.
Validation performed: targeted `pytest tests/test_brief_audit.py tests/test_card_and_audit.py
tests/test_translation_check.py tests/test_workflow_record.py tests/test_provenance_stamp.py
tests/test_chunked_summary.py tests/test_report_reader.py -q` => `56 passed`; `ruff check` on
changed Python files => clean; full `pytest -q` => `133 passed, 4 skipped`.
Evidence recorded: E28.
Problems found: none in this slice; the next planned build step is B.7 Korean image-share
measurement and first local OCR tier.
Next task: B.7 - Korean image-share measurement and first local OCR tier.
Confidence level: High (non-numeric claim audit is green and now uses the repo's real audit shape).

---
Date: 2026-07-02 (B.7)
Completed: added Korean deck image-share profiling and the first repo-owned local RapidOCR seam.
The document stack now measures born-digital versus image-only slides, surfaces OCR readiness
warnings, and routes low-confidence image-only pages to review before any heavier OCR escalation.
Files changed: `engines/docs/image_profile.py`, `engines/docs/rapidocr_adapter.py`,
`engines/docs/ocr.py`, `engines/docs/extract.py`, `mcp_server/server.py`,
`tests/test_korean_ocr_profile.py`, `engines/docs/AGENTS.md`,
`agent_skills/document_evidence_extraction.md`, `AGENT_SKILL_MAP.md`,
`00_control/{task_queue,restart_notes,evidence_log,progress}.md`.
Validation performed: targeted `pytest tests/test_korean_ocr_profile.py tests/test_ocr_cascade.py
tests/test_pptx_extraction.py tests/test_translation_check.py tests/test_workflow_record.py
tests/test_provenance_stamp.py tests/test_brief_audit.py tests/test_chunked_summary.py
tests/test_report_reader.py -q` => `57 passed, 3 skipped`; `ruff check` on changed Python files
=> clean; full `pytest -q` => `138 passed, 4 skipped`.
Evidence recorded: E29.
Problems found: none in this slice; the next planned build step is B.8 email and attachment intake
baseline.
Next task: B.8 - email and attachment intake baseline.
Confidence level: High (image-share measurement and local OCR review routing are green in the live repo).

---
Date: 2026-07-02 (B.8)
Completed: added the governed email and attachment intake baseline. The repo now extracts local
`.eml` metadata and body text, defaults privacy to Tier 1, routes attachments into the document
spine, and records attachment failures without aborting the email.
Files changed: `engines/email/extract.py`, `engines/email/AGENTS.md`, `mcp_server/server.py`,
`tests/test_email_extraction.py`, `agent_skills/document_evidence_extraction.md`,
`AGENT_SKILL_MAP.md`, `00_control/{task_queue,restart_notes,evidence_log,progress}.md`.
Validation performed: targeted `pytest tests/test_email_extraction.py tests/test_korean_ocr_profile.py
tests/test_translation_check.py tests/test_workflow_record.py tests/test_provenance_stamp.py
tests/test_brief_audit.py tests/test_chunked_summary.py tests/test_report_reader.py -q` =>
`60 passed`; `ruff check` on changed Python files => clean; full `pytest -q` => `143 passed,
4 skipped`.
Evidence recorded: E30.
Problems found: none in this slice; the next planned build step is B.9 first HQ deck brief gate.
Next task: B.9 - first HQ deck brief gate.
Confidence level: High (email intake is green and follows the same governed evidence path as documents).

---
Date: 2026-07-02 (B.9)
Completed: added the first HQ deck brief gate as a minimal one-page brief assembly path. The repo
now composes workflow record, glossary flags, non-numeric audit, coverage report, and sign-off
placeholder into one brief object with trusted versus review-routed claims.
Files changed: `serving/decision_brief.py`, `mcp_server/server.py`, `tests/test_hq_deck_brief.py`,
`agent_skills/management_reporting.md`, `00_control/{task_queue,restart_notes,evidence_log,progress}.md`.
Validation performed: targeted `pytest tests/test_hq_deck_brief.py tests/test_email_extraction.py
tests/test_korean_ocr_profile.py tests/test_translation_check.py tests/test_workflow_record.py
tests/test_provenance_stamp.py tests/test_brief_audit.py tests/test_chunked_summary.py
tests/test_report_reader.py -q` => `64 passed`; `ruff check` on changed Python files => clean;
full `pytest -q` => `147 passed, 4 skipped`.
Evidence recorded: E31.
Problems found: none in this slice; the next planned build step is B.10 Docling hard-layout
adapter.
Next task: B.10 - Docling hard-layout adapter.
Confidence level: High (the first HQ deck brief gate is green and owner-reviewable against source slides).
