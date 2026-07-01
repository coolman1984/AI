# engines/brain — orchestrator + memory

**Does:** `orchestrator.run_pipeline` connects every layer in order (ingest → clean →
variance → optional variance decomposition → card → audit → sign-off → memory → render) —
the Hermes role. `memory.py` holds the knowledge (Cognee) and temporal (Graphiti) layers
behind Protocols.

**Public interface:** `orchestrator.run_pipeline(actuals_csv, budget_csv, cfg, approver=None,
budget_pdf=None, standards_csv=None, period="2026-05", lens=None)`,
`memory.get_knowledge_memory` (`.relations_for`), `memory.get_temporal_memory`
(`.changes` = what changed over time).

**Real now:** local knowledge relations + temporal change-detection (no LLM needed).

**Adapters:** `CogneeMemory` (full knowledge graph), `GraphitiMemory` (bi-temporal graph;
`graphiti-core` imports, needs a graph DB + on-prem LLM). Switch via `config.yaml tools.*`.

**Invariants:** the vault/source-of-truth owns knowledge; the graph stores are a
rebuildable index.

**Never:** put authoritative numbers in the graph; numbers stay in the data engine.

**Tests:** `pytest tests/test_orchestrator.py`
