# engines/brain — orchestrator + memory + claims

**Does:** `orchestrator.run_pipeline` connects every layer in order (ingest → clean →
variance → optional variance decomposition → card → audit → sign-off → memory → render) —
the Hermes role. `memory.py` holds the knowledge (Cognee) and temporal (Graphiti) layers
behind Protocols. `claims.py` holds LLM-originated claims (physically separate from facts).

**Public interface:** `orchestrator.run_pipeline(actuals_csv, budget_csv, cfg, approver=None,
budget_pdf=None, standards_csv=None, period="2026-05", lens=None)`,
`memory.get_knowledge_memory` (`.relations_for`), `memory.get_temporal_memory`
(`.changes` = what changed over time),
`claims.ClaimsStore` (`add_claim`, `all` — stores to `.brain/claims.json`).

**Real now:** local knowledge relations + temporal change-detection + claims store (no LLM needed).

**Adapters:** `CogneeMemory` (full knowledge graph), `GraphitiMemory` (bi-temporal graph;
`graphiti-core` imports, needs a graph DB + on-prem LLM). Switch via `config.yaml tools.*`.

**Facts/claims separation wall:**
- `.brain/knowledge.json` — auditable entity relations (Cognee / local knowledge).
- `.brain/temporal.json` — time-stamped facts (Graphiti / local temporal).
- `.brain/claims.json` — LLM-originated claims with required citation + page.
- No code path in `claims.py` writes to `.brain/knowledge.json` or `.brain/temporal.json`.
- No code path in `memory.py` writes to `.brain/claims.json`.
- `add_claim()` raises `ValueError` if `citation` or `page` is missing — uncited claims are
  physically rejected by the API.

**Invariants:** the vault/source-of-truth owns knowledge; the graph stores are a
rebuildable index; claims are never promoted into facts without passing through the
verifier (A0.2–A0.3) and audit layer.

**Never:** put authoritative numbers in the graph; numbers stay in the data engine.
Never promote a claim to a fact without verification + audit sign-off.

**Tests:** `pytest tests/test_orchestrator.py`, `pytest tests/test_claims.py`
