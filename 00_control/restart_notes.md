# Restart Notes (read this to continue the project)

1. **Current mission:** in-house Factory Second Brain — exact numbers, memory, and audited,
   human-signed management answers. Pilot department: Cost Control / Finance. (mission.md)

2. **Current project state:** Master plan v2 is approved (`03_design/assistant_master_plan.md`,
   2026-07-02). Phase A safety rails (A0.1-A0.8) are now green, and A1 documentation
   consolidation is approved and passed.

3. **Completed work:** foundation; numeric trust loop (DuckDB+Polars, messy-data defenses);
   independent audit + human sign-off; decision/knowledge/temporal memory (local, real);
   documents + OCR cascade (Tesseract+RapidOCR real); HTML dashboard + PPTX; second
   department (Planning) by config; role-scoped factory brief + cross-department links.

4. **Pending work:** follow `03_design/current_implementation_plan.md` and
   `03_design/phase_b_to_f_cards.md` for the next execution slice. The next card is
   B.1 (native PPTX extractor, thin deterministic path). Later phases are now planned as clean
   OSS-backed adapters where appropriate: native PPTX first, `RapidOCR` as the
   first local OCR tier, `Docling` as the later hard-layout adapter, stable
   `mcp-python-sdk` for MCP hardening later, and `Cognee` / `Graphiti` only
   behind repo-owned contracts. External track unchanged: P2.2 still waits on
   the first real export.

5. **Active constraints:** in-house/offline only; one branch `main`; Python 3.11;
   modules small + per-module AGENTS.md; English.

6. **Active assumptions (assumptions.md):** sample shape mirrors SAP (A1); on-prem LLM (A2)
   and local graph DB (A3) will be provisioned; first workflow ≈ monthly cost variance (A4).

7. **Known risks (risks.md):** metric ambiguity (R2, open); prompt injection (R3, open); real
   SAP-scale untested (R7, open); adoption (R8, open). R1/R4/R6 mitigated.

8. **Current bottleneck (bottlenecks.md):** B3 — no real SAP-scale export has been profiled yet.

9. **Next best action:** start B.1 (native PPTX extractor, thin deterministic path) from
   `03_design/phase_b_to_f_cards.md`; A0 and A1 are green; keep waiting for the
   first real export for P2.2.

10. **Source-of-truth files:** `03_design/assistant_master_plan.md` (current architecture),
    `03_design/current_implementation_plan.md` (live execution plan),
    `03_design/phase_a_cards.md` (current work cards),
    `03_design/phase_b_to_f_cards.md` (later-phase card queue),
    `03_design/oss_reference_evaluation.md` (approved OSS fit and license review),
    `00_control/*` (governance), `AGENTS.md` and `AGENT_SKILL_MAP.md` (agent routing),
    `BUILD.md` (run), and the code under engines/ serving/ shared/ mcp_server/ gov/ tests/.
    Archived plans live in `archive/` for historical reference only.
