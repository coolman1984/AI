# engines/brain — orchestrator + memory

**Does:** `orchestrator.run_pipeline` connects every layer in order (ingest → clean →
variance → card → audit → sign-off → memory → render) — the Hermes role. `memory.py`
holds the knowledge (Cognee) and temporal (Graphiti) layers behind Protocols.
**Public interface:** `orchestrator.run_pipeline`, `memory.get_knowledge_memory`,
`memory.get_temporal_memory`.
**Invariants:** the vault/source-of-truth owns knowledge; the graph stores are a
rebuildable index; switch real tools via `config.yaml tools.*`.
**Never:** put authoritative numbers in the graph; numbers stay in the data engine.
**Tests:** `pytest tests/test_orchestrator.py`
