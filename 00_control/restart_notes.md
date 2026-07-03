> **Runtime state — not documentation.** Machine-updated resume snapshot; canonical status is
> `task_queue.md` + `PROJECT_MAP.md`.

# Restart Notes (session resume snapshot)

1. **Current mission:** in-house Factory Second Brain - exact numbers, memory, and audited,
   human-signed management answers. Pilot department: Cost Control / Finance. (mission.md)

2. **Current project state:** Master plan v2 is approved (`03_design/assistant_master_plan.md`,
   2026-07-02). Phase A (A0.1-A0.8, A1), Phase B (B.1-B.10), Phase C (C.1-C.8), Phase D
   (D.1-D.6), ingestion spine (IS2-IS6, E.2-E.4), and Phase F (F.1-F.10, T12) are green.

3. **Completed work:** foundation; numeric trust loop; audit + human sign-off; decision/knowledge/
   temporal memory; documents + OCR cascade; HTML dashboard + PPTX; multi-department factory brain;
   price/volume/mix drivers; A0 safety rails; HQ deck path (B.1-B.10); document registry and
   knowledge corpus (C); executive outputs with sign-off (D); unified ingestion spine with
   multi-sheet Excel, type inference, PDF tables, cross-source query readiness; golden eval,
   MCP access control, ops backup/restore, gated self-evolution (F/T12).

4. **Pending work:** **P2.2 / E.1** — blocked until the owner supplies the first real SAP-scale
   export for profiling. No other non-blocked task-queue rows remain open.

5. **Active constraints:** in-house/offline only; one branch `main`; Python 3.11;
   modules small + per-module AGENTS.md; English.

6. **Active assumptions (assumptions.md):** sample shape mirrors SAP (A1); on-prem LLM (A2)
   and local graph DB (A3) will be provisioned; first workflow is approximately monthly cost
   variance (A4).

7. **Known risks (risks.md):** metric ambiguity (R2, open); prompt injection (R3, open); real
   SAP-scale untested (R7, open until E.1); adoption (R8, open). R1/R4/R6 mitigated.

8. **Current bottleneck (bottlenecks.md):** P2.2 / E.1 — no real SAP-scale export has been
   profiled yet.

9. **Next best action:** obtain the first real SAP export from the owner and run E.1 profiling.
   Until then, the system is feature-complete for synthetic/public fixtures.

10. **Source-of-truth files:** `03_design/assistant_master_plan.md` (current architecture),
    `03_design/current_implementation_plan.md` (live execution plan),
    `03_design/phase_b_to_f_cards.md` (later-phase card queue),
    `00_control/*` (governance), `AGENTS.md` and `AGENT_SKILL_MAP.md` (agent routing),
    `BUILD.md` (run), and the code under engines/ serving/ shared/ mcp_server/ gov/ tests/.
    Archived plans live in `archive/` for historical reference only.