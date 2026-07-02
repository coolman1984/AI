# Memory Index (project brain — durable, compressed)

## Compressed summary (read this first)
- **Mission:** in-house Factory Second Brain; exact numbers + memory + audited, human-signed
  management answers. Pilot = Cost Control. (mission.md)
- **State:** Master plan v2 approved on 2026-07-02; Phase A safety rails are active. A0.1
  claims store passed final gate; A1 documentation consolidation is approved and passed.
- **Trust law:** numbers from the data engine only; every number cited; independent audit +
  named human sign-off before release; uncertain OCR → human-review queue.
- **Scale law:** department = lens config, not code; vault = source of truth, indexes
  rebuildable; in-house only.
- **Next action:** continue Phase A from `03_design/phase_a_cards.md` (A0.2 next after
  A0.1) while the external P2.2 real-export track remains open.

## Source-of-truth files
- Current architecture: `03_design/assistant_master_plan.md`.
- Current execution plan: `03_design/current_implementation_plan.md`.
- Current build cards: `03_design/phase_a_cards.md`.
- Historical plans/reports: `archive/` and superseded report files.
- Build/run: `BUILD.md`. Agent rules: `AGENTS.md`.
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
