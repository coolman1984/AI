# Decisions

| ID | Date | Decision | Reason | Alternatives | Evidence | Risk | Status |
|----|------|----------|--------|--------------|----------|------|--------|
| D1 | 2026-06 | MCP-first toolbox, not a chatbot | AI cannot originate numbers; tools do exact work | chatbot, BI tool | assistant_master_plan.md | low | Active |
| D2 | 2026-06 | Pilot = Finance/Cost Control | hardest accuracy, most structured data, clear value | other depts | assistant_master_plan.md | low | Active |
| D3 | 2026-06 | In-house only for factory data; owner-approved Tier 2 exception for HQ workflow docs | confidential factory data; HQ workflow docs need fast translation/summarization | all external, all local only | assistant_master_plan.md + D14 | med | Active |
| D4 | 2026-06 | Independent audit + named human sign-off mandatory | a confident wrong number to CEO = disaster | trust the model | assistant_master_plan.md | low | Active |
| D5 | 2026-06 | Real baseline + activate-on-install adapters for heavy tools | sandbox has no GPU/graph DB/LLM; stay honest | fake/skip | BUILD.md | med | Active |
| D6 | 2026-06 | Single branch `main`, every commit green | owner directive; tests gate in lieu of branch isolation | feature branches | AGENTS.md | med | Active |
| D7 | 2026-06 | Department = lens config, not engine code | scale without rebuild | per-dept apps | test_factory | low | Active |
| D8 | 2026-06 | Borrow patterns from Hermes/Karpathy/Obsidian; do not fork | governance/security/audit bar | fork repos | RISK_AND_GAPS_AUDIT 7 | low | Active |
| D9 | 2026-06 | OCR as a quality-gated cascade (Tesseract→…→VLM) | poor sources must escalate to best engine | single OCR | test_ocr_cascade | low | Active |
| D10 | 2026-06 | Adopt the Master Agent OS (file-based governance) | restartable, auditable, evidence-based truth in files | chat memory | this tree | low | Active |
| D11 | 2026-07 | Use lightweight `.agent-loop/*` as a bridge over `00_control/*` | repo already had a serious governance tree; avoid a second file OS | replace `00_control`, ignore bridge | E12 | low | Active |
| D12 | 2026-07 | Temporary `chatgpt-ai-tasks` branch policy is closed out; current rule is one branch `main` | v2 plan and root AGENTS.md restored the owner directive | temporary branch isolation | AGENTS.md + assistant_master_plan.md | med | Superseded |
| D13 | 2026-07 | Pre-v2 phase order: T8b first, real-data readiness second, heavy infra later | highest leverage then was surfacing management value | jump straight to T9/T10 | 03_design/implementation_plan.md | low | Superseded by v2 Phase A |
| D14 | 2026-07-02 | Two-tier privacy policy (owner: Path A): cloud AI MAY translate/summarize HQ workflow/process docs (e.g. Korean PPTX rollouts); factory data (financials, SAP, emails, internal docs) stays strictly in-house | HQ process decks are less sensitive than factory data; owner needs fast Korean->English understanding and no on-prem LLM exists yet | 100% local model (blocked on infra); keep full block (too slow for HQ rollouts) | owner decision in session 2026-07-02 | med | Active |
| D15 | 2026-07-02 | Master plan v2 is current; older plan docs are historical | owner approved v2 Executive Assistant Master Plan | continue older MASTER_PLAN/CODEX_PLAN guidance | 03_design/assistant_master_plan.md | low | Active |
