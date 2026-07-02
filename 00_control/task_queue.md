# Task Queue

Statuses: Pending · In Progress · Blocked · Needs Review · Failed · Passed · Archived.
Only the Evaluator marks Passed (evidence required).

| ID | Task | Role | Status | Pri | Inputs | Outputs | Validation | Evidence |
|----|------|------|--------|-----|--------|---------|-----------|----------|
| T0 | Foundation (repo, contracts, CI, tests) | Architect/Builder | Passed | – | – | engines/*, tests/ | pytest+ruff | git 4103b9e |
| T1 | Numeric trust loop (ingest/clean/variance/card) | Builder | Passed | – | sample CSV | engines/data, serving | test_data_pipeline | demo |
| T2 | Audit + human sign-off (Part O) | Builder | Passed | – | card,bridge | engines/audit | test_card_and_audit | demo |
| T3 | Decision + outcome memory | Builder | Passed | – | run | engines/learning | test_learning | demo |
| T4 | Documents + OCR cascade | Builder | Passed | – | PDFs | engines/docs | test_documents, test_ocr_cascade | demo (Tesseract 0.95) |
| T5 | Knowledge + temporal memory | Builder | Passed | – | runs | engines/brain/memory | test_memory | demo (Frame +100→+550) |
| T6 | Dashboard + PPTX | Builder | Passed | – | ctx | serving/open_design | test_serving | out/card.html,.pptx |
| T7 | 2nd dept by config + factory brain | Builder | Passed | – | lenses | engines/brain/factory, gov | test_factory | demo (CEO/analyst scope) |
| T8 | price/qty/mix variance decomposition | Builder→Evaluator | Passed | – | actuals+standards | engines/data/{variance,drivers} | test_drivers (reconciles to cent) | demo: -50 = +50 -99 -1 |
| T8b | surface price/volume/mix drivers on the card + dashboard | Builder→Evaluator | Passed | High | decomposition | serving | dashboard shows drivers | E14 |
| T8b1 | add typed driver payload to manager card contract | Builder | Passed | High | decomposition models | shared/contracts, serving/card | targeted pytest | E14 |
| T8b2 | thread decomposition into orchestrator render context | Builder | Passed | High | T8 output | engines/brain/orchestrator | targeted pytest | E14 |
| T8b3 | render price/volume/mix on card + HTML dashboard | Builder | Passed | High | ctx, card | serving/card, serving/open_design | test_serving/test_card | E14 |
| T8b4 | run full validation + demo for surfaced drivers | Evaluator | Passed | High | code changes | test results, demo output | pytest + demo | E14 |
| P2.1 | lock the first real workflow in governance files | Planner→Evaluator | Passed | High | implementation_plan, current governance | mission/open_questions/success_contract | file review | E15 |
| P2.2 | ingest and profile one real export before expansion | Builder→Evaluator | Blocked | High | first real export, source_inventory, data_map | profile report, issue log, readiness findings | profiling evidence | BLOCKED on external data |
| IS1 | define unified ingestion database schema | Builder→Evaluator | Passed | High | current contracts, source types | schema contract + storage design + minimal DuckDB lifecycle helpers | targeted pytest + full pytest | E17 |
| IS2 | harden Excel/CSV ingestion into reusable spine | Builder→Evaluator | In Progress | High | sample + real exports, IS1 contract | reusable tracked CSV path + reject flow live; multi-sheet Excel + per-column type inference remain | test-first + pytest `tests/test_data_pipeline.py` | E19 |
| IS2.1 | add tracked CSV wrapper on top of IS1 lifecycle | Builder→Evaluator | Passed | High | IS1 helpers + ingest_csv | `ingest_csv_tracked` + tests | targeted pytest + full pytest | E18 |
| IS2.2 | reject embedded total rows + exact duplicates in the tracked CSV path | Builder→Evaluator | Passed | High | IS2.1 wrapper, `clean.TOTAL_LABELS` | `ingest_csv_tracked` quarantines total/duplicate rows to `ingestion_rejects`; target table holds only accepted rows; conservation asserted | targeted pytest + full pytest | E19 |
| IS2.3 | multi-sheet Excel ingestion into the spine | Builder→Evaluator | Pending | High | IS2.2 reject flow, sample .xlsx with >1 sheet | one run per sheet, `source_sheet` tracked, sheet name in reject context | test-first + pytest `tests/test_ingestion_spine.py` | – |
| IS2.4 | per-column type inference for the tracked CSV/Excel path | Builder→Evaluator | Pending | High | IS2.2 reject flow | typed values alongside raw text; unconvertible cells quarantined with reason | test-first + pytest `tests/test_ingestion_spine.py` | – |
| IS3 | add PDF table extraction into the spine | Builder→Evaluator | Pending | High | table-bearing PDFs | structured table rows + confidence/review path | test-first + pytest `tests/test_pdf_tables.py` | – |
| IS4 | add PowerPoint extraction into the spine | Builder→Evaluator | Pending | High | synthetic + future real PPTX | slide text/table extraction to unified storage | test-first + pytest `tests/test_ppt.py` | – |
| IS5 | add email extraction into the spine | Builder→Evaluator | Pending | High | synthetic + future real email samples | body/attachment extraction to unified storage | test-first + pytest `tests/test_email.py` | – |
| IS6 | prove query + calculation readiness across ingested sources | Evaluator | Pending | High | unified storage + extractor outputs | query layer supports exact calculations safely | test-first + cross-source verification | – |
| T9 | Wire on-prem LLM + activate Cognee/Graphiti/Docling/VLM | Architect/Builder | Blocked | Med | infra + real workflow + real export + verified ingestion spine | adapters live | integration test | preconditions from implementation_plan.md |
| T10 | Onyx enterprise search | Builder | Pending | Low | many docs + proven retrieval pain | search service | relevance eval | – |
| T11 | Deployment + scheduled ingestion + backup/DR | Architect | Pending | Med | server + stable local loop | ops | restore test | – |
| T12 | Gated self-evolution (DSPy/GEPA) | Builder | Pending | Low | golden set | learning | eval gate | – |
| A0.1 | claims store physically separate from facts | Builder→Evaluator | Pending | High | shared/contracts/models.py, AGENTS.md Calculation-Integrity Rule | engines/brain/claims.py, .brain/claims.json | targeted pytest `tests/test_claims.py` + full pytest | – |
| A0.2 | deterministic figure verifier incl. Korean units (억/만/천) | Builder→Evaluator | Pending | High | AGENTS.md Calculation-Integrity Rule, assistant_master_plan.md A.1-2 | engines/docs/verify.py | targeted pytest `tests/test_verify.py` + full pytest | – |
| A0.3 | citation-support check (cited page must contain claim's numbers/terms) | Builder→Evaluator | Pending | High | A0.2 tokenizer | engines/docs/verify.py (extended) | targeted pytest `tests/test_verify.py` + full pytest | – |
| A0.4 | privacy tier gate (default Tier 1) + external-call ledger | Builder→Evaluator | Pending | High | owner decision D14 | gov/privacy.py, gov/ledger.py | targeted pytest `tests/test_privacy.py` + full pytest | – |
| A0.5 | LLM chokepoint: report_reader bridge + repo-wide bypass-guard test | Builder→Evaluator | Pending | High | A0.1–A0.4, engines/docs/report_reader.py | engines/docs/report_reader.py (edit) | targeted pytest `tests/test_llm_chokepoint.py` + full pytest | – |
| A0.6 | prompt-injection defense (delimiting) + injection-fixture test | Builder→Evaluator | Pending | High | A0.3, A0.5 | engines/docs/prompt_builder.py, report_reader.py (edit) | targeted pytest `tests/test_prompt_injection.py` + full pytest | – |
| A0.7 | repair tests/test_report_reader.py + wire report_reader through gates | Builder→Evaluator | Pending | High | A0.1–A0.6 | tests/test_report_reader.py (edit), report_reader.py (edit) | full pytest suite + ruff | – |
| A0.8 | provenance tags (AUDITED/CLAIMED) on every rendered number | Builder→Evaluator | Pending | High | A0.1, shared/contracts/models.py | shared/contracts/models.py (edit), serving/card.py (edit) | targeted pytest `tests/test_serving.py` + full pytest | – |
| A1.1 | archive 9 stale top-level plan docs, update AGENTS.md read order | Builder→Evaluator | Pending | Med | doc review list (assistant_master_plan.md item 47) | archive/*, AGENTS.md (edit) | targeted pytest `tests/test_doc_archive.py` + full pytest | – |
| A1.2 | update restart_notes.md + AGENT_SKILL_MAP.md for the new plan | Builder→Evaluator | Pending | Med | A1.1, assistant_master_plan.md | 00_control/restart_notes.md (edit), AGENT_SKILL_MAP.md (edit) | manual diff review + full pytest | – |

**Next best action:** start **A0.1** (claims store physically separate from facts) — the first card in the safety-rails gate (Phase A0) that must go green with tests before any LLM touches a real deck; A1 doc-consolidation cards run in parallel, non-blocking. (External track unchanged: still waiting on the first real export for **P2.2**.)
