# Restart Notes (read this to continue the project)

1. **Current mission:** in-house Factory Second Brain — exact numbers, memory, and audited,
   human-signed management answers. Pilot department: Cost Control / Finance. (mission.md)

2. **Current project state:** Stages 0–7 complete and verified. Full pipeline runs via
   `python run_demo.py`. 26 pytest tests pass; ruff clean; CI configured.

3. **Completed work:** foundation; numeric trust loop (DuckDB+Polars, messy-data defenses);
   independent audit + human sign-off; decision/knowledge/temporal memory (local, real);
   documents + OCR cascade (Tesseract+RapidOCR real); HTML dashboard + PPTX; second
   department (Planning) by config; role-scoped factory brief + cross-department links.

4. **Pending work (task_queue.md):** T8 price/qty/mix variance decomposition (next, no infra);
   T9 wire on-prem LLM → activate Cognee/Graphiti/Docling/VLM (blocked on infra); T10 Onyx;
   T11 deployment + scheduled ingestion + backup/DR; T12 gated self-evolution.

5. **Active constraints:** in-house/offline only; single branch `main` (every commit green);
   Python 3.11; modules small + per-module AGENTS.md; English.

6. **Active assumptions (assumptions.md):** sample shape mirrors SAP (A1); on-prem LLM (A2)
   and local graph DB (A3) will be provisioned; first workflow ≈ monthly cost variance (A4).

7. **Known risks (risks.md):** metric ambiguity (R2, open); prompt injection (R3, open); real
   SAP-scale untested (R7, open); adoption (R8, open). R1/R4/R6 mitigated.

8. **Current bottleneck (bottlenecks.md):** B5 — the price/volume/mix decomposition exists
   (T8 done, reconciles) but is not yet shown on the card/dashboard.

9. **Next best action:** execute **T8b** — surface the price/volume/mix drivers on the
   manager card + dashboard (no infra). Then T9 (activate heavy backends) is blocked on infra.

10. **Source-of-truth files:** `00_control/*` (governance), `MASTER_PLAN.md` (architecture),
    `FACTORY_SECOND_BRAIN.md` (overview), `BUILD.md` (run), `AGENTS.md` (agent rules), and the
    code under engines/ serving/ shared/ mcp_server/ gov/ tests/.
