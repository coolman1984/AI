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
| T8 | price/qty/mix variance decomposition | Builder | Pending | High | actuals+qty | engines/data/variance | new tests reconcile | – |
| T9 | Wire on-prem LLM + activate Cognee/Graphiti/Docling/VLM | Architect/Builder | Blocked | Med | infra | adapters live | integration test | needs infra |
| T10 | Onyx enterprise search | Builder | Pending | Low | many docs | search service | relevance eval | – |
| T11 | Deployment + scheduled ingestion + backup/DR | Architect | Pending | Med | server | ops | restore test | – |
| T12 | Gated self-evolution (DSPy/GEPA) | Builder | Pending | Low | golden set | learning | eval gate | – |

**Next best action:** T8 (price/qty/mix variance) — highest value, no infra needed.
