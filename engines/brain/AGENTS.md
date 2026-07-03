# engines/brain — orchestrator + memory + claims + knowledge registry

**Does:** `orchestrator.run_pipeline` connects every layer in order (ingest → clean →
variance → optional variance decomposition → card → audit → sign-off → memory → render) —
the Hermes role. `memory.py` holds the knowledge (Cognee) and temporal (Graphiti) layers
behind Protocols. `claims.py` holds LLM-originated claims (physically separate from facts).
`registry.py` is the document registry map. `workflow_family.py` groups workflow record
versions with valid-time separate from ingest-time. `workflow_diff.py` shows cited field
changes between versions. `open_questions.py` stores queryable unknowns. `comparison.py`
compares public IR periods with citation-only claims. `contradictions.py` surfaces conflicts
without auto-resolution. `search.py` is the repo-owned knowledge search contract.

**Public interface:** `orchestrator.run_pipeline(actuals_csv, budget_csv, cfg, approver=None,
budget_pdf=None, standards_csv=None, period="2026-05", lens=None)`,
`memory.get_knowledge_memory` (`.relations_for`), `memory.get_temporal_memory`
(`.changes` = what changed over time),
`claims.ClaimsStore` (`add_claim`, `all` — stores to `.brain/claims.json`),
`registry.DocumentRegistry` (`register_document`, `update_status`, `query`, `all`),
`workflow_family.WorkflowFamilyStore` (`register_workflow_version`, `versions_for_period`,
`get_family`, `get_version`),
`workflow_diff.diff_workflow_versions`, `open_questions.OpenQuestionsStore`
(`add_question`, `resolve_question`, `list_questions`),
`comparison.compare_public_ir_quarters`, `contradictions.find_contradictions`,
`search.search_knowledge`.

**Real now:** local knowledge relations + temporal change-detection + claims store +
document registry + workflow families/diffs + open questions + contradictions + search
(no LLM needed in registry/search/diff modules).

**Adapters:** `CogneeMemory` (full knowledge graph), `GraphitiMemory` (bi-temporal graph;
`graphiti-core` imports, needs a graph DB + on-prem LLM). Switch via `config.yaml tools.*`.
Any future vector/graph search backend must sit behind `search.py`, not replace it.

**Facts/claims separation wall:**
- `.brain/knowledge.json` — auditable entity relations (Cognee / local knowledge).
- `.brain/temporal.json` — time-stamped facts (Graphiti / local temporal).
- `.brain/claims.json` — LLM-originated claims with required citation + page.
- `.brain/document_registry.json` — ingested document map with hash deduplication.
- `.brain/workflow_families.json` — workflow version families with bitemporal metadata.
- `.brain/open_questions.json` — open/resolved questions with evidence.
- No code path in `claims.py` writes to `.brain/knowledge.json` or `.brain/temporal.json`.
- No code path in `memory.py` writes to `.brain/claims.json`.
- `add_claim()` raises `ValueError` if `citation` or `page` is missing — uncited claims are
  physically rejected by the API.

**Invariants:** the vault/source-of-truth owns knowledge; the graph stores are a
rebuildable index; claims are never promoted into facts without passing through the
verifier (A0.2–A0.3) and audit layer; registry dedup is hash-based; contradictions require
human resolution.

**Never:** put authoritative numbers in the graph; numbers stay in the data engine.
Never promote a claim to a fact without verification + audit sign-off.
Never auto-resolve contradictions or invent comparison analysis.

**Tests:** `pytest tests/test_orchestrator.py`, `pytest tests/test_claims.py`,
`pytest tests/test_document_registry.py`, `pytest tests/test_workflow_family.py`,
`pytest tests/test_workflow_diff.py`, `pytest tests/test_open_questions.py`,
`pytest tests/test_ir_comparison.py`, `pytest tests/test_contradictions.py`,
`pytest tests/test_knowledge_search.py`