# Task Queue

Statuses: Pending · In Progress · Blocked · Needs Review · Failed · Passed · Archived.
Only the Evaluator marks Passed (evidence required).

| ID | Task | Role | Status | Pri | Inputs | Outputs | Validation | Evidence |
|----|------|------|--------|-----|--------|---------|------------|----------|
| T0 | Foundation (repo, contracts, CI, tests) | Architect/Builder | Passed | - | - | engines/*, tests/ | pytest + ruff | git 4103b9e |
| T1 | Numeric trust loop (ingest/clean/variance/card) | Builder | Passed | - | sample CSV | engines/data, serving | test_data_pipeline | demo |
| T2 | Audit + human sign-off (Part O) | Builder | Passed | - | card, bridge | engines/audit | test_card_and_audit | demo |
| T3 | Decision + outcome memory | Builder | Passed | - | run | engines/learning | test_learning | demo |
| T4 | Documents + OCR cascade | Builder | Passed | - | PDFs | engines/docs | test_documents, test_ocr_cascade | demo (Tesseract 0.95) |
| T5 | Knowledge + temporal memory | Builder | Passed | - | runs | engines/brain/memory | test_memory | demo (Frame +100 to +550) |
| T6 | Dashboard + PPTX | Builder | Passed | - | ctx | serving/open_design | test_serving | out/card.html, .pptx |
| T7 | 2nd dept by config + factory brain | Builder | Passed | - | lenses | engines/brain/factory, gov | test_factory | demo (CEO/analyst scope) |
| T8 | price/qty/mix variance decomposition | Builder->Evaluator | Passed | - | actuals + standards | engines/data/{variance,drivers} | test_drivers (reconciles to cent) | demo: -50 = +50 -99 -1 |
| T8b | surface price/volume/mix drivers on the card + dashboard | Builder->Evaluator | Passed | High | decomposition | serving | dashboard shows drivers | E14 |
| T8b1 | add typed driver payload to manager card contract | Builder | Passed | High | decomposition models | shared/contracts, serving/card | targeted pytest | E14 |
| T8b2 | thread decomposition into orchestrator render context | Builder | Passed | High | T8 output | engines/brain/orchestrator | targeted pytest | E14 |
| T8b3 | render price/volume/mix on card + HTML dashboard | Builder | Passed | High | ctx, card | serving/card, serving/open_design | test_serving/test_card | E14 |
| T8b4 | run full validation + demo for surfaced drivers | Evaluator | Passed | High | code changes | test results, demo output | pytest + demo | E14 |
| P2.1 | lock the first real workflow in governance files | Planner->Evaluator | Passed | High | implementation_plan, current governance | mission/open_questions/success_contract | file review | E15 |
| P2.2 | ingest and profile one real export before expansion | Builder->Evaluator | Blocked | High | first real export, source_inventory, data_map | profile report, issue log, readiness findings | profiling evidence | BLOCKED on external data |
| IS1 | define unified ingestion database schema | Builder->Evaluator | Passed | High | current contracts, source types | schema contract + storage design + minimal DuckDB lifecycle helpers | targeted pytest + full pytest | E17 |
| IS2 | harden Excel/CSV ingestion into reusable spine | Builder->Evaluator | In Progress | High | sample + real exports, IS1 contract | reusable tracked CSV path + reject flow live; multi-sheet Excel + per-column type inference remain | test-first + pytest `tests/test_data_pipeline.py` | E19 |
| IS2.1 | add tracked CSV wrapper on top of IS1 lifecycle | Builder->Evaluator | Passed | High | IS1 helpers + ingest_csv | `ingest_csv_tracked` + tests | targeted pytest + full pytest | E18 |
| IS2.2 | reject embedded total rows + exact duplicates in the tracked CSV path | Builder->Evaluator | Passed | High | IS2.1 wrapper, `clean.TOTAL_LABELS` | `ingest_csv_tracked` quarantines total/duplicate rows to `ingestion_rejects`; target table holds only accepted rows; conservation asserted | targeted pytest + full pytest | E19 |
| IS2.3 | multi-sheet Excel ingestion into the spine | Builder->Evaluator | Pending | High | IS2.2 reject flow, sample .xlsx with >1 sheet | one run per sheet, `source_sheet` tracked, sheet name in reject context | test-first + pytest `tests/test_ingestion_spine.py` | - |
| IS2.4 | per-column type inference for the tracked CSV/Excel path | Builder->Evaluator | Pending | High | IS2.2 reject flow | typed values alongside raw text; unconvertible cells quarantined with reason | test-first + pytest `tests/test_ingestion_spine.py` | - |
| IS3 | add PDF table extraction into the spine | Builder->Evaluator | Pending | High | table-bearing PDFs | structured table rows + confidence/review path | test-first + pytest `tests/test_pdf_tables.py` | - |
| IS4 | add PowerPoint extraction into the spine | Builder->Evaluator | Archived | High | synthetic + future real PPTX | superseded by `B.1` native PPTX extractor and `B.10` Docling hard-layout adapter | phase-card alignment review | superseded 2026-07-02 |
| IS5 | add email extraction into the spine | Builder->Evaluator | Archived | High | synthetic + future real email samples | superseded by `B.8` email and attachment intake baseline | phase-card alignment review | superseded 2026-07-02 |
| IS6 | prove query + calculation readiness across ingested sources | Evaluator | Pending | High | unified storage + extractor outputs | query layer supports exact calculations safely | test-first + cross-source verification | - |
| T9 | Wire on-prem LLM + activate Cognee/Graphiti/Docling/VLM | Architect/Builder | Archived | Med | old pre-v2 umbrella row | superseded by `B.10`, `F.4`, `F.5`, and the OSS wrapper policy in `03_design/current_implementation_plan.md` | phase-card alignment review | superseded 2026-07-02 |
| T10 | Onyx enterprise search | Builder | Archived | Low | many docs + proven retrieval pain | not a primary build block under the approved OSS fit review | OSS fit review | superseded 2026-07-02 |
| T11 | Deployment + scheduled ingestion + backup/DR | Architect | Archived | Med | server + stable local loop | superseded by `F.8` scheduled ingestion, backup, restore, alerting | phase-card alignment review | superseded 2026-07-02 |
| T12 | Gated self-evolution (DSPy/GEPA) | Builder | Pending | Low | golden set | learning | eval gate | - |
| A0.1 | claims store physically separate from facts | Builder->Evaluator | Passed | High | shared/contracts/models.py, AGENTS.md Calculation-Integrity Rule | engines/brain/claims.py, .brain/claims.json | targeted pytest `tests/test_claims.py` + full pytest | final gate passed 2026-07-02 |
| A0.2 | deterministic figure verifier incl. Korean units (eok/man/cheon) | Builder->Evaluator | Passed | High | AGENTS.md Calculation-Integrity Rule, assistant_master_plan.md A.1-2 | engines/docs/verify.py | targeted pytest `tests/test_verify.py` + full pytest | E22 |
| A0.3 | citation-support check (cited page must contain claim numbers/terms) | Builder->Evaluator | Passed | High | A0.2 tokenizer | engines/docs/verify.py (extended) | targeted pytest `tests/test_verify.py` + full pytest | E22 |
| A0.4 | privacy tier gate (default Tier 1) + external-call ledger | Builder->Evaluator | Passed | High | owner decision D14 | gov/privacy.py, gov/ledger.py | targeted pytest `tests/test_privacy.py` + full pytest | E22 |
| A0.5 | LLM chokepoint: report_reader bridge + repo-wide bypass-guard test | Builder->Evaluator | Passed | High | A0.1-A0.4, engines/docs/report_reader.py | engines/docs/report_reader.py (edit) | targeted pytest `tests/test_llm_chokepoint.py` + full pytest | E22 |
| A0.6 | prompt-injection defense (delimiting) + injection-fixture test | Builder->Evaluator | Passed | High | A0.3, A0.5 | engines/docs/prompt_builder.py, report_reader.py (edit) | targeted pytest `tests/test_prompt_injection.py` + full pytest | E22 |
| A0.7 | repair tests/test_report_reader.py + wire report_reader through gates | Builder->Evaluator | Passed | High | A0.1-A0.6 | tests/test_report_reader.py (edit), report_reader.py (edit) | full pytest suite + ruff | E22 |
| A0.8 | provenance tags (AUDITED/CLAIMED) on every rendered number | Builder->Evaluator | Passed | High | A0.1, shared/contracts/models.py | shared/contracts/models.py (edit), serving/card.py, serving/open_design.py | targeted pytest `tests/test_serving.py` + full pytest | E22 |
| A1.1 | archive stale top-level plan docs, update AGENTS.md read order | Builder->Evaluator | Passed | Med | doc review list (assistant_master_plan.md item 47) | archive/*, AGENTS.md (edit) | targeted pytest `tests/test_doc_archive.py` + full pytest | completed before A1.2 |
| A1.2 | update restart_notes.md + AGENT_SKILL_MAP.md for the new plan | Builder->Evaluator | Passed | Med | A1.1, assistant_master_plan.md | docs/control routing updates | owner approval + full pytest | E20 |
| B.1 | native PPTX extractor (thin deterministic path) | Builder->Evaluator | Pending | High | A0 gate, synthetic PPTX | `engines/docs/pptx.py`, unified `Document` output | pytest `tests/test_pptx_extraction.py` + full pytest | - |
| B.2 | chunked map-reduce coverage | Builder->Evaluator | Pending | High | A0 gate, B.1, long synthetic deck | `engines/docs/summarize.py`, coverage manifest | pytest `tests/test_chunked_summary.py` + full pytest | - |
| B.3 | WorkflowRecord schema | Builder->Evaluator | Pending | High | B.1, B.2 | cited workflow record contract + MCP tool + skill/map updates | pytest `tests/test_workflow_record.py` + full pytest | - |
| B.4 | original-language retention and provenance stamp | Builder->Evaluator | Pending | High | B.3 | Korean source-text retention + provenance stamp | pytest `tests/test_provenance_stamp.py` + full pytest | - |
| B.5 | Korean-English glossary and critical-term check | Builder->Evaluator | Pending | High | B.3, B.4 | glossary logic + translation review flags | pytest `tests/test_translation_check.py` + full pytest | - |
| B.6 | non-numeric brief audit | Builder->Evaluator | Pending | High | A0 gate, B.3 | `engines/audit/brief_audit.py`, audit tool + skill/map updates | pytest `tests/test_brief_audit.py` + full pytest | - |
| B.7 | Korean image-share measurement + first local OCR tier | Builder->Evaluator | Pending | High | B.1, OCR fixtures | `engines/docs/image_profile.py`, `rapidocr_adapter.py`, OCR routing | pytest `tests/test_korean_ocr_profile.py` + full pytest | - |
| B.8 | email and attachment intake baseline | Builder->Evaluator | Pending | High | A0 gate, synthetic `.eml` samples | `engines/email/extract.py`, governed email spine path | pytest `tests/test_email_extraction.py` + full pytest | - |
| B.9 | first HQ deck brief gate | Builder->Evaluator | Pending | High | B.1-B.7, synthetic Tier 2 deck | one-page deck brief with citations, audit status, sign-off placeholder | pytest `tests/test_hq_deck_brief.py` + full pytest | - |
| B.10 | Docling hard-layout adapter | Builder->Evaluator | Pending | Med | B.1, local Docling install | `engines/docs/docling_adapter.py`, explicit hard-layout tool path | pytest `tests/test_docling_adapter.py` + full pytest | - |
| C.1 | document registry | Builder->Evaluator | Pending | High | B gate | `engines/brain/registry.py`, document registry MCP tools | pytest `tests/test_document_registry.py` + full pytest | - |
| C.2 | workflow families and versioning | Builder->Evaluator | Pending | High | C.1 | family/version contract with valid-time and ingest-time | pytest `tests/test_workflow_family.py` + full pytest | - |
| C.3 | workflow diff view | Builder->Evaluator | Pending | High | C.2 | deterministic cited workflow diff output | pytest `tests/test_workflow_diff.py` + full pytest | - |
| C.4 | open questions and decision outcomes | Builder->Evaluator | Pending | High | C.1, B.3 | queryable open questions + workflow outcome links | pytest `tests/test_open_questions.py` + full pytest | - |
| C.5 | knowledge artifacts in git | Builder->Evaluator | Pending | Med | C.1, C.2 | markdown artifacts with dedup/provenance | pytest `tests/test_knowledge_artifacts.py` + full pytest | - |
| C.6 | Samsung IR quarter comparison | Builder->Evaluator | Pending | Med | C.1-C.3, public IR fixtures | public comparison proof with citations | pytest `tests/test_ir_comparison.py` + full pytest | - |
| C.7 | contradiction-surfacing view | Builder->Evaluator | Pending | High | C.1, C.2, C.4 | contradiction listing across claims/records | pytest `tests/test_contradictions.py` + full pytest | - |
| C.8 | knowledge search skill and tool | Builder->Evaluator | Pending | High | C.1-C.7 | `engines/brain/search.py`, `agent_skills/knowledge_search.md`, MCP search tool | pytest `tests/test_knowledge_search.py` + full pytest | - |
| D.1 | decision brief generator | Builder->Evaluator | Pending | High | C gate, A0.8, B.6, C.8 | one-page decision brief generator | pytest `tests/test_decision_brief.py` + full pytest | - |
| D.2 | meeting pack assembler | Builder->Evaluator | Pending | High | D.1 | meeting pack assembler | pytest `tests/test_meeting_pack.py` + full pytest | - |
| D.3 | report and article generator | Builder->Evaluator | Pending | Med | D.1 | report/article renderer | pytest `tests/test_report_article.py` + full pytest | - |
| D.4 | all-output sign-off enforcement | Builder->Evaluator | Pending | High | D.1-D.3 | executive sign-off gate in serving | pytest `tests/test_executive_signoff.py` + full pytest | - |
| D.5 | rendering reuse for briefs and packs | Builder->Evaluator | Pending | Med | D.1, D.4 | shared serving/open_design rendering path | pytest `tests/test_serving_outputs.py` + full pytest | - |
| D.6 | owner feedback loop | Builder->Evaluator | Pending | Med | D.1, D.4 | feedback capture and trust-loop hooks | pytest `tests/test_feedback_loop.py` + full pytest | - |
| E.1 | real export profiling gate | Builder->Evaluator | Pending | High | first real export, P2.2 unblock | real export profile and issue log | file profile + validation review | - |
| E.2 | multi-sheet Excel ingestion | Builder->Evaluator | Pending | High | IS2.2, sample/real workbook | one run per sheet with `source_sheet` tracking | pytest `tests/test_ingestion_spine.py` + full pytest | - |
| E.3 | per-column type inference | Builder->Evaluator | Pending | High | IS2.2, tracked CSV/Excel path | typed/raw dual storage + quarantine flow | pytest `tests/test_ingestion_spine.py` + full pytest | - |
| E.4 | real-data issue promotion | Planner->Evaluator | Pending | Med | E.1-E.3 findings | owned issue list and follow-on queue rows | doc-control review | - |
| F.1 | golden evaluation set | Builder->Evaluator | Pending | High | B gate | eval manifest, runner, regression gate | pytest `tests/test_golden_eval.py` + full pytest | - |
| F.2 | MCP access control at dispatch | Builder->Evaluator | Pending | High | C gate, stable MCP SDK if adopted | dispatch access enforcement | pytest `tests/test_mcp_access.py` + full pytest | - |
| F.3 | skill token budgets and output contracts | Builder->Evaluator | Pending | Med | C.8 | enforced skill contract metadata | pytest `tests/test_skill_contracts.py` + full pytest | - |
| F.4 | fallback models and resumable runs | Builder->Evaluator | Pending | Med | B.2, B.4, A0 gate | resumable run state + provider fallback chain | pytest `tests/test_resumable_runs.py` + full pytest | - |
| F.5 | ontology and typed workflow edges | Builder->Evaluator | Pending | Med | C gate, measured trigger | ontology contract + edge model, graph backend seam | pytest `tests/test_ontology.py` + full pytest | - |
| F.6 | factory comparison availability gate | Builder->Evaluator | Pending | Low | C.6, F.5, comparable reports | gated factory comparison path | pytest `tests/test_factory_comparison_gate.py` + full pytest | - |
| F.7 | idea synthesis, last and labeled | Builder->Evaluator | Pending | Low | C.7, D.4, F.1 | labeled `AI-SUGGESTED IDEA` output path | pytest `tests/test_idea_synthesis.py` + full pytest | - |
| F.8 | scheduled ingestion, backup, restore, alerting | Builder->Evaluator | Pending | Med | stable local loop, C.1, C.5 | ops scheduler/backup/restore/alerts | pytest `tests/test_ops_backup.py` + full pytest | - |
| F.9 | session-state persistence | Builder->Evaluator | Pending | Low | D.6 | session-state/restart-note persistence | pytest `tests/test_session_state.py` + full pytest | - |
| F.10 | quarterly plan review ritual | Planner->Evaluator | Pending | Low | D gate | review checklist and decision log | doc review | - |

**Next best action:** start **B.1** (native PPTX extractor, thin deterministic path). A0.1-A0.8 and A1.1-A1.2 are now green. External track unchanged: P2.2 still waits on the first real export.
