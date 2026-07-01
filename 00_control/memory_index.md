# Memory Index (project brain — durable, compressed)

## Compressed summary (read this first)
- **Mission:** in-house Factory Second Brain; exact numbers + memory + audited, human-signed
  management answers. Pilot = Cost Control. (mission.md)
- **State:** Stages 0–7 built & verified (26 tests pass, lint clean, demo end-to-end).
- **Trust law:** numbers from the data engine only; every number cited; independent audit +
  named human sign-off before release; uncertain OCR → human-review queue.
- **Scale law:** department = lens config, not code; vault = source of truth, indexes
  rebuildable; in-house only.
- **Next action:** T8b surface the price/volume/mix drivers on the card and dashboard.

## Source-of-truth files
- Architecture: `MASTER_PLAN.md` (A–S). Overview: `FACTORY_SECOND_BRAIN.md`.
- Build/run: `BUILD.md`. Risks/upgrades: `RISK_AND_GAPS_AUDIT.md`,
  `reports/PLAN_RISK_AUDIT_AND_UPGRADE_REPORT.md`. Agent rules: `AGENTS.md`. Codex: `CODEX_PLAN.md`.
- Governance: `00_control/*`. Code: engines/, serving/, shared/, mcp_server/, gov/, tests/.

## Durable facts
- Tools real now: DuckDB, Polars, pypdf, OpenPyXL, Tesseract+RapidOCR, audit+sign-off,
  decision/knowledge/temporal memory, HTML+PPTX, lenses, access control, factory brain.
- Adapters (need infra): Docling, PaddleOCR/Surya/VLM-OCR, Cognee, Graphiti, Onyx, Open Design, vLLM.
- Methods that worked: install-and-verify heavy tools where feasible (apt tesseract, rapidocr,
  graphiti-core import); real baseline + adapter pattern; test-first; one green main.
- Lightweight bridge added: `.agent-loop/*` points fast restarts to the governed `00_control/*`
  state instead of duplicating project truth.
- Avoid: faking that GPU/LLM tools run on a CPU sandbox; uncited numbers; data leaving network.

## User preferences (stable)
- Single branch `main`, push there only, no other branches.
- Speak/work in English. Prefer action + real, verified results over plans-only.
- Best-in-class open-source tools, integrated honestly (real or activate-on-install).
