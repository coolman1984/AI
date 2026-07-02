# Restart Notes (read this to continue the project)

1. **Current mission:** in-house Factory Second Brain — exact numbers, memory, and audited,
   human-signed management answers. Pilot department: Cost Control / Finance. (mission.md)

2. **Current project state:** Master plan v2 is approved (`03_design/assistant_master_plan.md`,
   2026-07-02). Phase A is active. A0.1 (claims store physically separate from facts)
   passed final gate; A1 documentation consolidation is approved and passed.

3. **Completed work:** foundation; numeric trust loop (DuckDB+Polars, messy-data defenses);
   independent audit + human sign-off; decision/knowledge/temporal memory (local, real);
   documents + OCR cascade (Tesseract+RapidOCR real); HTML dashboard + PPTX; second
   department (Planning) by config; role-scoped factory brief + cross-department links.

4. **Pending work:** follow `03_design/current_implementation_plan.md` and
   `03_design/phase_a_cards.md` for Phase A. A0.2 is the next safety-rail card after
   A0.1; A1.2 is approved and passed. External track unchanged: P2.2 still waits on the
   first real export.

5. **Active constraints:** in-house/offline only; one branch `main`; Python 3.11;
   modules small + per-module AGENTS.md; English.

6. **Active assumptions (assumptions.md):** sample shape mirrors SAP (A1); on-prem LLM (A2)
   and local graph DB (A3) will be provisioned; first workflow ≈ monthly cost variance (A4).

7. **Known risks (risks.md):** metric ambiguity (R2, open); prompt injection (R3, open); real
   SAP-scale untested (R7, open); adoption (R8, open). R1/R4/R6 mitigated.

8. **Current bottleneck (bottlenecks.md):** B3 — no real SAP-scale export has been profiled yet.

9. **Next best action:** start A0.2 (deterministic figure verifier) from
   `03_design/phase_a_cards.md`; A1 documentation cleanup is approved; keep
   waiting for the first real export for P2.2.

10. **Source-of-truth files:** `03_design/assistant_master_plan.md` (current architecture),
    `03_design/current_implementation_plan.md` (live execution plan),
    `03_design/phase_a_cards.md` (current work cards), `00_control/*` (governance),
    `AGENTS.md` and `AGENT_SKILL_MAP.md` (agent routing), `BUILD.md` (run), and the code
    under engines/ serving/ shared/ mcp_server/ gov/ tests/. Archived plans live in
    `archive/` for historical reference only.
