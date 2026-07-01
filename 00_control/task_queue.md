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
| P2.2 | ingest and profile one real export before expansion | Builder→Evaluator | Pending | High | first real export, source_inventory, data_map | profile report, issue log, readiness findings | profiling evidence | – |
| T9 | Wire on-prem LLM + activate Cognee/Graphiti/Docling/VLM | Architect/Builder | Blocked | Med | infra + real workflow + real export | adapters live | integration test | preconditions from implementation_plan.md |
| T10 | Onyx enterprise search | Builder | Pending | Low | many docs + proven retrieval pain | search service | relevance eval | – |
| T11 | Deployment + scheduled ingestion + backup/DR | Architect | Pending | Med | server + stable local loop | ops | restore test | – |
| T12 | Gated self-evolution (DSPy/GEPA) | Builder | Pending | Low | golden set | learning | eval gate | – |

**Next best action:** execute **P2.2** — receive one real export, profile its structure and dirt,
and log every real-data issue before any heavy infrastructure work.
