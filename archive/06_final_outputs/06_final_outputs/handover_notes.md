# Handover Notes

> Historical v1 handover. Current architecture and phase order are
> `03_design/assistant_master_plan.md` and `03_design/phase_a_cards.md`; current restart
> state is `00_control/restart_notes.md`.

## 1. What Was Completed

v1 pilot of Factory Second Brain (Stages 0-7): numeric trust loop, independent audit +
human sign-off, decision/knowledge/temporal memory, documents + OCR cascade, dashboard +
PPTX, multi-department by config, role-scoped factory brain. Master Agent OS governance
was instantiated in `00_control/`.

## 2. Where The Final Outputs Are

- Run it: `python run_demo.py` prints the full flow and writes `out/card.html`,
  `out/card.pptx`.
- Code: engines/, serving/, shared/, mcp_server/, gov/. Tests: tests/.
- Current architecture: `03_design/assistant_master_plan.md`.
- Current cards: `03_design/phase_a_cards.md`.
- Run guide: `BUILD.md`.

## 3. Inputs Used

Sample data in data/sample/ (finance + planning CSVs, two PDFs including a scanned one).
See `01_inputs/source_inventory.md`. Raw inputs are read-only.

## 4. Assumptions Made

See `00_control/assumptions.md`.

## 5. What Was Validated

ruff clean; pytest passed; demo end-to-end; audit catches tampering; OCR recovers a
scanned PDF; temporal change detected; access scoping enforced. Evidence:
`00_control/evidence_log.md`.

## 6. Evidence

`00_control/evidence_log.md`, `05_validation/test_results.md`, and out/ artifacts.

## 7. Risks Remaining

Use `00_control/risks.md` and `05_validation/issue_tracker.md` for current risk state.

## 8. Recommended Next Action

Read `00_control/restart_notes.md`, then continue the current Phase A card from
`03_design/phase_a_cards.md`.
