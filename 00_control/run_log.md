# Run Log

> Historical log. References to archived plan filenames below describe what was true at
> the time of each run; current architecture is `03_design/assistant_master_plan.md`
> (approved 2026-07-02).

Timestamp: 2026-06-30
Action: Adopted Master Agent OS; instantiated 00_control governance from real project state.
Inputs read: pytest (26 passed), ruff (clean), git log (Stages 0-7), module/test inventory.
Outputs changed: created project governance file tree (00_control..07_archive).
Result: governance layer live; project state captured in files.
Evidence: 00_control/evidence_log.md
Next step: continue feature work (price/qty/mix variance) under the OS loop.

---
Timestamp: 2026-06-30 (T8)
Action: Built + verified price/volume/mix variance decomposition (T8).
Reason: bottleneck B1 — managers need the "why", not just the total.
Inputs read: finance_actuals.csv, finance_standards.csv, task_queue (T8).
Outputs changed: engines/data/{variance,drivers}.py, contracts, mcp tool, tests, demo, standards sample.
Result: 29 tests pass; ruff clean; demo total -50 = price +50 + volume -99 + mix -1 (reconciles).
Evidence: E11.
Next step: T8b — surface drivers on the card + dashboard.

---
Timestamp: 2026-07-01
Action: Cloned the repository locally and aligned the project with Mohamed's new development
loop without duplicating the existing governed file OS.
Reason: start future development from a real local repo with restartable state.
Inputs read: AGENTS.md, CODEX_PLAN.md, 00_control/{mission,success_contract,task_queue,progress,
restart_notes,memory_index,evidence_log}.md, git remote/status.
Outputs changed: created `.agent-loop/{brief-contract,progress,run-log}.md`; corrected stale
references from T8 to T8b in `restart_notes.md` and `memory_index.md`.
Result: local clone ready; lightweight bridge active; next action aligned on T8b.
Evidence: E12.
Next step: implement T8b in the serving layer under test discipline.

---
Timestamp: 2026-07-01
Action: Wrote a phased implementation plan grounded in the current repo state and expanded T8b
into executable backlog slices.
Reason: Mohamed asked for the next steps as a rigorous roadmap that avoids premature infra work.
Inputs read: task_queue, bottlenecks, success_contract, progress, open_questions, issue_tracker,
serving/card.py, serving/open_design.py, shared/contracts/models.py, tests, config, BUILD.md.
Outputs changed: created `03_design/implementation_plan.md`; updated `00_control/task_queue.md`,
`00_control/decisions.md`, `00_control/restart_notes.md`, `00_control/progress.md`, and
`05_validation/issue_tracker.md`.
Result: next action clarified to T8b1; phase order fixed to T8b → real-data readiness → heavy
infra; main risks and stop conditions documented.
Evidence: E13.
Next step: implement T8b1 under the new plan.

---
Timestamp: 2026-07-01
Action: Completed T8b — surfaced the variance-driver view in the card and dashboard, then
corrected a meaning mismatch so the panel explicitly states it is a standard-cost operating view,
not the same basis as the budget headline.
Reason: Mohamed asked to continue the project; the highest-value open gap was making the "why"
visible without misleading the reader.
Inputs read: serving + orchestrator modules, tests, run_demo, module AGENTS, current task queue.
Outputs changed: `shared/contracts/models.py`, `serving/{card,open_design}.py`,
`engines/brain/orchestrator.py`, `mcp_server/server.py`, `run_demo.py`, tests, and AGENTS docs.
Result: the manager card and HTML dashboard now show price/volume/mix clearly; the wording is
truthful about basis; targeted and full test suites are green.
Evidence: E14.
Next step: start P2 with one real workflow decision and one real export profile run.

---
Timestamp: 2026-07-01
Action: Used the team workflow to complete P2.1 only: the writing worker drafted the next governance slice, the review worker narrowed the scope, and Hermes applied the smallest correct set of file changes.
Reason: Mohamed asked to continue the project using the agreed team system rather than solo execution.
Inputs read: implementation plan, task queue, current governance files, worker draft, worker review.
Outputs changed: `00_control/mission.md`, `00_control/open_questions.md`, `00_control/success_contract.md`, `00_control/task_queue.md`, `00_control/progress.md`, `00_control/evidence_log.md`.
Result: the first real workflow is now locked; heavy infrastructure remains blocked; the next move is clearly P2.2 with one real export.
Evidence: E15.
Next step: receive and profile one real export.

---
Timestamp: 2026-07-01
Action: Used the team workflow to redirect the project toward a unified ingestion spine under the already-locked first workflow.
Reason: Mohamed explicitly said the priority is extracting data from Excel, PDF tables, PowerPoint, and email into a database with query and calculation support.
Inputs read: current mission, task queue, implementation plan, document tests, data-pipeline tests, worker draft, worker review.
Outputs changed: `00_control/mission.md`, `00_control/task_queue.md`, `03_design/implementation_plan.md`, `05_validation/issue_tracker.md`, `03_design/unified-ingestion-spine.md`.
Result: extraction/storage/query/calculation is now a formal project backbone; missing PowerPoint/email paths are visible; heavy infrastructure remains gated.
Evidence: E16.
Next step: start IS1 internally while waiting for the first real export required by P2.2.

---
Timestamp: 2026-07-01
Action: Completed IS1 under the team workflow: writer proposed the storage-contract slice, reviewer cut abstractions and caught design mistakes, and Hermes implemented the smallest correct version with tests first.
Reason: continue the project by making the extraction/storage/query spine real rather than leaving it as governance only.
Inputs read: current contracts, ingest path, data tests, worker draft, worker review.
Outputs changed: `engines/data/ingest.py`, `tests/test_ingestion_spine.py`, `00_control/task_queue.md`, `05_validation/issue_tracker.md`, `00_control/{progress,evidence_log,restart_notes}.md`.
Result: the project now has real ingestion run tracking and reject persistence; the next internal engineering move is IS2 while P2.2 remains blocked on external data.
Evidence: E17.
Next step: start IS2 and keep waiting for the first real export.

---
Timestamp: 2026-07-01
Action: Started IS2 with the smallest real slice: added a reusable tracked CSV ingest wrapper on top of the IS1 lifecycle and verified it end-to-end.
Reason: keep moving the project forward internally while P2.2 remains blocked on external data.
Inputs read: IS1 code/tests, worker draft, worker review.
Outputs changed: `engines/data/ingest.py`, `tests/test_ingestion_spine.py`, `00_control/{task_queue,progress,evidence_log,restart_notes}.md`.
Result: CSV ingestion no longer needs manual start→ingest→finish chaining; IS2 is now live, not just planned.
Evidence: E18.
Next step: continue IS2 toward typed reusable ingestion while waiting for the first real export.

---
Timestamp: 2026-07-01
Action: Completed IS2.2 — wired real reject detection into the tracked CSV path instead of the
hardcoded zero reject count left by IS2.1.
Reason: the design doc (`03_design/unified-ingestion-spine.md`) names embedded total/subtotal
rows and duplicates as the messy-data defenses IS2 must have before Excel/PDF/PPT sources reuse
the same spine; `clean.clean_actuals` already solved this for the finance-specific columns, but
the generic spine had no equivalent.
Inputs read: `engines/data/ingest.py`, `engines/data/clean.py` (reused `TOTAL_LABELS`),
`tests/test_ingestion_spine.py`.
Outputs changed: `engines/data/ingest.py` (`_is_total_row`, rewritten `ingest_csv_tracked`),
`tests/test_ingestion_spine.py` (3 new tests), `engines/data/AGENTS.md`,
`00_control/{task_queue,progress,evidence_log,restart_notes}.md`.
Result: `ingest_csv_tracked` now quarantines total/duplicate rows to `ingestion_rejects` and the
target table holds only accepted rows; conservation (`rows_in == accepted + rejected`) is
asserted by a dedicated test. Full pytest: 42 passed, 4 skipped. Ruff clean.
Evidence: E19.
Next step: IS2.3 (multi-sheet Excel) or IS2.4 (per-column type inference) while P2.2 waits on
the first real export.

---
Timestamp: 2026-07-02
Action: Reworked the live planning path so later phases use repo-owned wrappers around the
strongest clean-licensed OSS components instead of assuming greenfield engine builds.
Reason: Mohamed explicitly directed the project to reuse robust open-source tools where they fit
the approved Executive Assistant Master Plan, then evaluate fit, licenses, and plug-in effort
before hand-building anything expensive.
Inputs read: `03_design/assistant_master_plan.md`, `03_design/current_implementation_plan.md`,
`03_design/phase_b_to_f_cards.md`, `00_control/task_queue.md`, downloaded OSS repos under
`G:\downloads\oss_reference`, and local README/license files for Docling, RapidOCR, PaddleOCR,
MCP Python SDK, Cognee, Graphiti, MinerU, Surya, Onyx, MCP servers, MarkItDown, Unstructured,
olmOCR, and Open Design.
Outputs changed: `03_design/oss_reference_evaluation.md`,
`03_design/current_implementation_plan.md`, `03_design/phase_b_to_f_cards.md`,
`00_control/task_queue.md`, `00_control/restart_notes.md`.
Result: the repo now has a documented OSS leverage policy, later-phase cards that explicitly use
`RapidOCR` first, `Docling` later, stable `mcp-python-sdk` for MCP hardening, and graph/memory
backends only behind repo-owned contracts; stale umbrella queue rows were archived and the full
B-F card queue was added.
Evidence: planning doc review in current workspace.
Next step: resume implementation at A0.2; later-phase execution should follow the new queue and
OSS-backed card path rather than the archived umbrella rows.

---
Timestamp: 2026-07-02
Action: Verified the A0 safety-rail stack end-to-end and fixed the remaining provenance-tagging
gap in the dashboard rendering path.
Reason: after the planning alignment, Mohamed's standing instruction was to keep moving the real
project forward; the fastest honest move was to clear the live suite failure instead of stopping at
documentation.
Inputs read: `03_design/phase_a_cards.md`, `engines/docs/AGENTS.md`, `engines/docs/verify.py`,
`tests/test_verify.py`, `serving/open_design.py`, `tests/test_serving.py`, and the full test
suite output.
Outputs changed: `serving/open_design.py`, `00_control/{task_queue,restart_notes,evidence_log,progress}.md`.
Result: targeted verifier tests were already green; the only live failure was
`test_render_dashboard_html_fails_closed_on_unknown_provenance`; the dashboard and PPTX rendering
paths now surface provenance tags and fail closed on unknown prefixes; full `pytest -q` is green
at `106 passed, 4 skipped`.
Evidence: E22.
Next step: start B.1 (native PPTX extractor, thin deterministic path); external real-data wait is
unchanged for P2.2.

---
Timestamp: 2026-07-02
Action: Implemented B.1, the native PPTX extractor, and wired it into the document evidence spine.
Reason: with Phase A rails green and the later-phase planning aligned, the next highest-value move
was to start the first HQ deck path for real rather than stop at planning.
Inputs read: `engines/docs/{extract,models}.py`, `tests/test_documents.py`, `mcp_server/server.py`,
`agent_skills/document_evidence_extraction.md`, `AGENT_SKILL_MAP.md`.
Outputs changed: `engines/docs/pptx.py`, `engines/docs/extract.py`, `mcp_server/server.py`,
`tests/test_pptx_extraction.py`, `engines/docs/AGENTS.md`,
`agent_skills/document_evidence_extraction.md`, `AGENT_SKILL_MAP.md`,
`00_control/{task_queue,restart_notes,evidence_log,progress}.md`.
Result: `.pptx` files now extract into the normalized `Document` shape with slide order preserved,
table rows captured, and a dispatchable `ingest_deck` MCP tool path; targeted and full test suites
are green.
Evidence: E23.
Next step: start B.2 (chunked map-reduce coverage); external real-data wait is unchanged for P2.2.

---
Timestamp: 2026-07-02
Action: Implemented B.2, the chunked map-reduce coverage path for long document summarization.
Reason: the plan explicitly bans silent truncation for long decks and reports; we needed the
coverage-aware chunk path in place before moving on to WorkflowRecord work.
Inputs read: `engines/docs/{report_reader,summarize}.py`, `tests/test_report_reader.py`,
`tests/test_chunked_summary.py`, `mcp_server/server.py`,
`agent_skills/document_evidence_extraction.md`, `AGENT_SKILL_MAP.md`.
Outputs changed: `engines/docs/summarize.py`, `engines/docs/report_reader.py`,
`mcp_server/server.py`, `tests/test_report_reader.py`, `tests/test_chunked_summary.py`,
`engines/docs/AGENTS.md`, `agent_skills/document_evidence_extraction.md`, `AGENT_SKILL_MAP.md`,
`00_control/{task_queue,restart_notes,evidence_log,progress}.md`.
Result: long documents now chunk deterministically, persist a coverage report, and block on gaps or
oversize pages instead of truncating; the report reader delegates to that path and the MCP surface
exposes `summarize_document`.
Evidence: E24.
Next step: start B.3 (WorkflowRecord schema); external real-data wait is unchanged for P2.2.

---
Timestamp: 2026-07-02
Action: Implemented B.3, the WorkflowRecord schema and validation path for structured deck
understanding.
Reason: the next approved seam after chunk coverage was to stop treating workflow understanding as
free-form prose and give it a cited record contract that later translation and provenance work can
build on.
Inputs read: `03_design/phase_b_to_f_cards.md`, `shared/contracts/models.py`,
`mcp_server/server.py`, `engines/docs/AGENTS.md`, and existing document-engine tests.
Outputs changed: `engines/docs/workflow_record.py`, `mcp_server/server.py`,
`tests/test_workflow_record.py`, `engines/docs/AGENTS.md`,
`agent_skills/document_evidence_extraction.md`, `AGENT_SKILL_MAP.md`,
`00_control/{task_queue,restart_notes,evidence_log,progress}.md`.
Result: workflow records now enforce citations on every required field, preserve slide/page
locators, serialize deterministically, and expose a dispatchable `extract_workflow_record` tool.
Evidence: E25.
Next step: start B.4 (original-language retention and provenance stamp); external real-data wait is
unchanged for P2.2.

---
Timestamp: 2026-07-02
Action: Implemented B.4, original-language retention and provenance stamping for workflow records.
Reason: the approved plan requires every translated workflow field to keep its Korean source text,
and every record needs deterministic provenance metadata before glossary and review logic can be
trusted.
Inputs read: `03_design/phase_b_to_f_cards.md`, `engines/docs/workflow_record.py`,
`mcp_server/server.py`, `engines/docs/AGENTS.md`, and the B.3 workflow tests.
Outputs changed: `engines/docs/provenance.py`, `engines/docs/workflow_record.py`,
`mcp_server/server.py`, `tests/test_provenance_stamp.py`, `tests/test_workflow_record.py`,
`engines/docs/AGENTS.md`, `agent_skills/document_evidence_extraction.md`, `AGENT_SKILL_MAP.md`,
`00_control/{task_queue,restart_notes,evidence_log,progress}.md`.
Result: workflow records now carry bilingual field content plus deterministic provenance stamps with
source hash, stable source identity, ingest run id, model metadata, prompt version, timestamp, and
confidence derived from explicit inputs rather than model self-rating.
Evidence: E26.
Next step: start B.5 (Korean-English glossary and critical-term check); external real-data wait is
unchanged for P2.2.

---
Timestamp: 2026-07-02
Action: Implemented B.5, the glossary-backed translation check path for workflow records.
Reason: after bilingual field retention and provenance stamping, the next approved trust seam was
to enforce accepted factory terminology and surface critical-term disagreements before any brief can
lean on a translation.
Inputs read: `03_design/phase_b_to_f_cards.md`, `engines/docs/workflow_record.py`,
`engines/docs/summarize.py`, `mcp_server/server.py`, and the B.4 workflow/provenance tests.
Outputs changed: `engines/docs/glossary.py`, `engines/docs/translation_check.py`,
`engines/docs/summarize.py`, `mcp_server/server.py`, `tests/test_translation_check.py`,
`engines/docs/AGENTS.md`, `agent_skills/document_evidence_extraction.md`, `AGENT_SKILL_MAP.md`,
`00_control/{task_queue,restart_notes,evidence_log,progress}.md`.
Result: the document stack now carries an explicit accepted-entry glossary, passes glossary context
into chunk summaries, computes glossary match ratio deterministically, and flags unknown critical
terms plus KPI back-translation disagreements through a dispatchable `check_translation_terms` tool.
Evidence: E27.
Next step: start B.6 (non-numeric brief audit); external real-data wait is unchanged for P2.2.
