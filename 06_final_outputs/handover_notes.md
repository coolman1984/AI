# Handover Notes

## 1. What was completed
v1 pilot of Factory Second Brain (Stages 0–7): numeric trust loop, independent audit +
human sign-off, decision/knowledge/temporal memory, documents + OCR cascade, dashboard +
PPTX, multi-department by config, role-scoped factory brain. Master Agent OS governance
instantiated in `00_control/`.

## 2. Where the final outputs are
- Run it: `python run_demo.py` → prints the full flow, writes `out/card.html`, `out/card.pptx`.
- Code: engines/, serving/, shared/, mcp_server/, gov/. Tests: tests/ (26 pass).
- Architecture: MASTER_PLAN.md · overview: FACTORY_SECOND_BRAIN.md · run: BUILD.md.

## 3. Inputs used
Sample data in data/sample/ (finance + planning CSVs, two PDFs incl. a scanned one). See
01_inputs/source_inventory.md. Raw inputs are read-only.

## 4. Assumptions made
See assumptions.md (sample≈SAP shape; on-prem LLM + graph DB to be provisioned; first
workflow ≈ monthly cost variance).

## 5. What was validated
ruff clean; pytest 26 passed; demo end-to-end; audit catches tampering; OCR recovers a
scanned PDF; temporal change detected; access scoping enforced. Evidence: evidence_log.md.

## 6. Evidence
00_control/evidence_log.md (E1–E10), 05_validation/test_results.md, out/ artifacts.

## 7. Risks remaining
Metric ambiguity (R2), prompt injection (R3), real SAP-scale untested (R7), adoption (R8).

## 8. Optional improvements
T8 price/qty/mix variance (next); activate heavy backends on infra (T9); Onyx (T10);
deployment + scheduled ingestion + DR (T11); gated self-evolution (T12).

## 9. Recommended next action
Build T8 (price/qty/mix variance decomposition) — highest management value, no infra needed.

## To continue from a cold start
Read `00_control/restart_notes.md`, then `memory_index.md`, then `task_queue.md`. Continue
from the highest-value pending task.
