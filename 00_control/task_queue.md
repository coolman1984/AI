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
| IS2 | harden Excel/CSV ingestion into reusable spine | Builder→Evaluator | Pending | High | sample + real exports, IS1 contract | multi-sheet typed ingestion + reject flow | test-first + pytest `tests/test_data_pipeline.py` | – |
| IS3 | add PDF table extraction into the spine | Builder→Evaluator | Pending | High | table-bearing PDFs | structured table rows + confidence/review path | test-first + pytest `tests/test_pdf_tables.py` | – |
| IS4 | add PowerPoint extraction into the spine | Builder→Evaluator | Pending | High | synthetic + future real PPTX | slide text/table extraction to unified storage | test-first + pytest `tests/test_ppt.py` | – |
| IS5 | add email extraction into the spine | Builder→Evaluator | Pending | High | synthetic + future real email samples | body/attachment extraction to unified storage | test-first + pytest `tests/test_email.py` | – |
| IS6 | prove query + calculation readiness across ingested sources | Evaluator | Pending | High | unified storage + extractor outputs | query layer supports exact calculations safely | test-first + cross-source verification | – |
| T9 | Wire on-prem LLM + activate Cognee/Graphiti/Docling/VLM | Architect/Builder | Blocked | Med | infra + real workflow + real export + verified ingestion spine | adapters live | integration test | preconditions from implementation_plan.md |
| T10 | Onyx enterprise search | Builder | Pending | Low | many docs + proven retrieval pain | search service | relevance eval | – |
| T11 | Deployment + scheduled ingestion + backup/DR | Architect | Pending | Med | server + stable local loop | ops | restore test | – |
| T12 | Gated self-evolution (DSPy/GEPA) | Builder | Pending | Low | golden set | learning | eval gate | – |

**Next best action:** two-track move — externally, receive one real export for **P2.2**; internally, start **IS2** so Excel/CSV ingestion begins using the new storage contract instead of staying a demo-only path.
