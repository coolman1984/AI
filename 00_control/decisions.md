# Decisions

| ID | Date | Decision | Reason | Alternatives | Evidence | Risk | Status |
|----|------|----------|--------|--------------|----------|------|--------|
| D1 | 2026-06 | MCP-first toolbox, not a chatbot | AI cannot originate numbers; tools do exact work | chatbot, BI tool | MASTER_PLAN B | low | Active |
| D2 | 2026-06 | Pilot = Finance/Cost Control | hardest accuracy, most structured data, clear value | other depts | MASTER_PLAN L | low | Active |
| D3 | 2026-06 | In-house only; on-prem synthesis LLM default | confidential factory data | external API | MASTER_PLAN G.5/K | med | Active |
| D4 | 2026-06 | Independent audit + named human sign-off mandatory | a confident wrong number to CEO = disaster | trust the model | MASTER_PLAN O | low | Active |
| D5 | 2026-06 | Real baseline + activate-on-install adapters for heavy tools | sandbox has no GPU/graph DB/LLM; stay honest | fake/skip | BUILD.md | med | Active |
| D6 | 2026-06 | Single branch `main`, every commit green | owner directive; tests gate in lieu of branch isolation | feature branches | AGENTS.md | med | Active |
| D7 | 2026-06 | Department = lens config, not engine code | scale without rebuild | per-dept apps | test_factory | low | Active |
| D8 | 2026-06 | Borrow patterns from Hermes/Karpathy/Obsidian; do not fork | governance/security/audit bar | fork repos | RISK_AND_GAPS_AUDIT 7 | low | Active |
| D9 | 2026-06 | OCR as a quality-gated cascade (Tesseract→…→VLM) | poor sources must escalate to best engine | single OCR | test_ocr_cascade | low | Active |
| D10 | 2026-06 | Adopt the Master Agent OS (file-based governance) | restartable, auditable, evidence-based truth in files | chat memory | this tree | low | Active |
| D11 | 2026-07 | Use lightweight `.agent-loop/*` as a bridge over `00_control/*` | repo already had a serious governance tree; avoid a second file OS | replace `00_control`, ignore bridge | E12 | low | Active |
| D12 | 2026-07 | Work on branch `chatgpt-ai-tasks` until merge readiness | owner explicitly approved branch isolation for ChatGPT work | stay on `main` | git branch + user approval | med | Active |
| D13 | 2026-07 | Enforce phase order: T8b first, real-data readiness second, heavy infra later | highest leverage now is surfacing management value, not adding systems | jump straight to T9/T10 | 03_design/implementation_plan.md | low | Active |
