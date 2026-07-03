# External Skills Inventory — How to Use Them Inside This Project

**Purpose:** Group the skill libraries in
`C:\Users\mflma\Downloads\Skills` by what they do, map each group to the
project's own `agent_skills/*.md`, and give concrete guidance on when and how
to use them during coding and code review in this repository.

**Source directory:** `C:\Users\mflma\Downloads\Skills`  
**Target directory:** `G:\AI\agent_skills/` (this file lives here)

---

## 1. Grouping Overview

| Group | Focus | Primary Source | Count | Maps to Project Skill |
|---|---|---|---|---|
| **A. Engineering Workflow** | Build, plan, test, review, ship software | `addyosami agent-skills-main/skills/` | 24 | All skills indirectly; strongest for `management_reporting` and task planning |
| **B. Financial Domain** | Finance/Costing operations, variance, Excel audit, modeling | `financial-services-main/plugins/vertical-plugins/` | ~75 | `cost_variance_analysis`, `spreadsheet_ingestion`, `management_reporting` |
| **C. Document & Content** | Generate/consume DOCX, PDF, PPTX, XLSX | `skills-main/skills/`, `financial-services-main` | ~20 | `document_evidence_extraction`, `management_reporting` |
| **D. MCP & Tool Building** | Build MCP servers, connectors, API clients | `skills-main/skills/mcp-builder/`, `claude-plugins-official-main/plugins/mcp-server-dev/` | 2–3 | `mcp_server/server.py`, all skill-to-tool mapping |
| **E. Agent Orchestration** | Specialist agents, code review, security audit | `addyosami agent-skills-main/agents/`, `claude-plugins-official-main/plugins/` | 10+ | Task routing, review gates, quality assurance |
| **F. Learning & Reference** | Prompt engineering, recipes, financial model examples | `prompt-eng-interactive-tutorial-master/`, `claude-cookbooks-main/` | 30+ | Training material, not runtime skills |

---

## 2. Group A — Engineering Workflow Skills

### 2.1 What is in this group

From `addyosami agent-skills-main/skills/`:

| Skill | One-line purpose | Where it lives |
|---|---|---|
| `using-agent-skills` | How to consume skill files | Meta |
| `interview-me` | Elicit requirements from a human | Define |
| `idea-refine` | Sharpen vague ideas | Define |
| `spec-driven-development` | Write contracts before code | Define |
| `planning-and-task-breakdown` | Decompose work into testable cards | Plan |
| `incremental-implementation` | Thin vertical slices | Build |
| `test-driven-development` | Red/green/refactor loop | Build |
| `context-engineering` | Pass the right context cheaply | Build |
| `source-driven-development` | Read existing code before writing | Build |
| `doubt-driven-development` | Adversarial questioning | Build |
| `frontend-ui-engineering` | UI patterns | Build |
| `api-and-interface-design` | Contract-first interfaces | Build |
| `browser-testing-with-devtools` | Web testing | Verify |
| `debugging-and-error-recovery` | Systematic debugging | Verify |
| `code-review-and-quality` | Review checklist | Review |
| `code-simplification` | Remove unnecessary complexity | Review |
| `security-and-hardening` | OWASP-style review | Review |
| `performance-optimization` | Latency/throughput/memory | Review |
| `git-workflow-and-versioning` | Branch, commit, release | Ship |
| `ci-cd-and-automation` | Pipelines | Ship |
| `deprecation-and-migration` | Safe removal of old code | Ship |
| `documentation-and-adrs` | Architecture Decision Records | Ship |
| `observability-and-instrumentation` | Logs, metrics, traces | Ship |
| `shipping-and-launch` | Release checklist | Ship |

Plus slash commands in `commands/` (`spec`, `plan`, `build`, `test`, `review`,
`webperf`, `code-simplify`, `ship`) and reference checklists in `references/`.

### 2.2 How it maps to this project

This project's `AGENTS.md` already encodes the same philosophy:

| Project rule | Matching external skill |
|---|---|
| "Contracts-first, test-first" | `spec-driven-development` + `test-driven-development` |
| "A card says: make `tests/<x>` pass by implementing `<contract>`" | `planning-and-task-breakdown` + `incremental-implementation` |
| "Load one skill, never load the whole architecture" | `context-engineering` |
| Adversarial review in `03_design/reviews/opus_critique.md` | `doubt-driven-development` |
| "Do not change any existing logic especially in tests" | `source-driven-development` |
| CI runs `ruff check . && pytest` | `ci-cd-and-automation` |
| Every module gets an `AGENTS.md` | `documentation-and-adrs` |
| Rejects go to `rejects.csv`, failures to `failures.csv` | `observability-and-instrumentation` |

### 2.3 How to use it while coding here

**During planning (before writing code):**
1. Open `planning-and-task-breakdown/SKILL.md` for a card-decomposition checklist.
2. Open `spec-driven-development/SKILL.md` to write/update `shared/contracts/models.py` or module `AGENTS.md` first.
3. Use `test-driven-development/SKILL.md` to write the failing test before the implementation.

**During implementation:**
1. Use `incremental-implementation/SKILL.md` to keep changes small enough to explain in one commit.
2. Use `context-engineering/SKILL.md` when deciding how much of another module to load.
3. Use `source-driven-development/SKILL.md` before touching tests or existing logic.

**During code review:**
1. Use `code-review-and-quality/SKILL.md` as a checklist.
2. Use `code-simplification/SKILL.md` to flag over-engineered solutions.
3. Use `security-and-hardening/SKILL.md` for privacy/ledger/access changes.
4. Use `doubt-driven-development/SKILL.md` to question numeric trust boundaries.

### 2.4 Practical integration path

If a workflow skill improves a project-specific rule, copy the **checklist portion**
into the existing skill file rather than creating a new file. Example:
- `agent_skills/spreadsheet_ingestion.md` could add a "Before you ingest" section
  drawn from `spec-driven-development` and `source-driven-development`.
- `agent_skills/audit_and_trust.md` could add a "Doubt questions" section drawn
  from `doubt-driven-development`.

---

## 3. Group B — Financial Domain Skills

### 3.1 What is in this group

From `financial-services-main/plugins/vertical-plugins/`:

| Sub-group | Skills | Why they matter here |
|---|---|---|
| `financial-analysis/` (15) | `comps-analysis`, `dcf-model`, `lbo-model`, `3-statement-model`, `audit-xls`, `clean-data-xls`, `deck-refresh`, `competitive-analysis`, `ib-check-deck`, `pptx-author`, `xlsx-author`, `ppt-template-creator` | `audit-xls` and `clean-data-xls` map directly to `engines/data/clean.py`; `pptx-author`/`xlsx-author` map to `serving/` |
| `fund-admin/` (5) | `gl-reconciler`, `break-trace`, `accrual-schedule`, `roll-forward`, `variance-commentary`, `nav-tieout` | Direct mapping to `engines/data/variance.py`, `engines/data/drivers.py`, and `serving/card.py` |
| `investment-banking/` (9) | CIMs, teasers, process letters, buyer lists, merger models | Less direct; useful for decision memos and comparison workflows |
| `equity-research/` (9) | Earnings notes, initiations, model updates, thesis tracking | Useful for `engines/brain/comparison.py` and IR comparison |
| `private-equity/` (10) | Sourcing, screening, diligence checklists, IC memos | Diligence checklist pattern can inspire factory audit checklists |
| `wealth-management/` (6) | Client reviews, financial plans, rebalancing, reporting | Reporting/aggregation patterns |
| `operations/` (2) | `kyc-doc-parse` | Document parsing patterns for factory documents |

Plus 10 end-to-end agents in `plugins/agent-plugins/`:
`gl-reconciler`, `month-end-closer`, `statement-auditor`, `model-builder`,
`valuation-reviewer`, `earnings-reviewer`, `market-researcher`, `meeting-prep-agent`,
`pitch-agent`, `kyc-screener`.

### 3.2 How it maps to this project

| Project component | Relevant financial skill | What to borrow |
|---|---|---|
| `engines/data/clean.py` | `audit-xls`, `clean-data-xls` | Formula tracing, hardcode detection, locale parsing, header normalization |
| `engines/data/variance.py` | `variance-commentary` | Bridge narration, dimension selection, materiality framing |
| `engines/data/drivers.py` | `gl-reconciler`, `month-end-closer` | Root-cause decomposition patterns, roll-forward logic |
| `serving/card.py` | `variance-commentary`, `meeting-prep-agent` | One-page summary structure, BLUF, key takeaways |
| `serving/decision_brief.py` | `pitch-agent`, `private-equity/ic-memo` | Decision framing, alternatives, recommendation |
| `engines/docs/verify.py` | `statement-auditor`, `audit-xls` | Figure verification, cross-footing, unit normalization |
| `mcp_server/server.py` | `financial-analysis/*` | Tool naming and dispatch patterns for finance operations |

### 3.3 How to use it while coding here

**When building data-engine features:**
1. Open `clean-data-xls/SKILL.md` before changing `engines/data/clean.py` or `ingest.py`.
2. Open `audit-xls/SKILL.md` before adding new validation rules.
3. Open `variance-commentary/SKILL.md` before changing `serving/card.py` or adding narrative output.

**When reviewing costing logic:**
1. Use `gl-reconciler` and `month-end-closer` agent cookbooks as adversarial reviewers.
2. Ask: "Would this pass a month-end closer's reconciliation check?"
3. Ask: "Is the price/volume/mix decomposition as explicit as a fund-admin roll-forward?"

**When writing executive output:**
1. Use `meeting-prep-agent` structure for `serving/meeting_pack.py`.
2. Use `pitch-agent` recommendation framing for `serving/decision_brief.py`.

### 3.4 Practical integration path

Do **not** copy finance-domain models (DCF/LBO) into this factory project.
Instead, extract the **operational workflow patterns**:
- Add a "Finance operations checklist" to `agent_skills/cost_variance_analysis.md`.
- Add an "Excel audit checklist" to `agent_skills/spreadsheet_ingestion.md`.
- Consider a new skill `agent_skills/finance_close_review.md` if the project
  expands to month-end close workflows.

---

## 4. Group C — Document & Content Generation Skills

### 4.1 What is in this group

| Source | Skills | Purpose |
|---|---|---|
| `skills-main/skills/` | `docx`, `pdf`, `pptx`, `xlsx`, `doc-coauthoring` | Headless creation of office documents |
| `financial-services-main/plugins/vertical-plugins/financial-analysis/` | `pptx-author`, `xlsx-author`, `ppt-template-creator` | Financial document generation |
| `claude-plugins-official-main/plugins/frontend-design/` | `frontend-design` | UI/design output |

### 4.2 How it maps to this project

| Project component | Relevant skill | What to borrow |
|---|---|---|
| `serving/open_design.py` (HTML/PPTX) | `pptx-author`, `pptx` | Slide layout, chart insertion, template handling |
| `serving/report_article.py` | `docx`, `doc-coauthoring` | DOCX generation for formal reports |
| `engines/docs/pptx.py` | `pptx` (Anthropic) | PPTX parsing/generation patterns |
| `engines/docs/extract.py` | `pdf` | PDF extraction patterns |
| `serving/card.py` | `frontend-design` | One-page visual layout principles |
| `engines/data/ingest.py` (Excel) | `xlsx` | Sheet handling, named ranges, formatting |

### 4.3 How to use it while coding here

**When improving rendered output:**
1. Open `pptx-author/SKILL.md` before extending `serving/open_design.py`.
2. Open `frontend-design/SKILL.md` before changing dashboard layout.
3. Open `docx/SKILL.md` before adding Word export to `serving/report_article.py`.

**When reviewing output code:**
1. Check: does the generated PPTX/DOCX follow the skill's structure conventions?
2. Check: are charts/tables styled consistently with the template guidance?

### 4.4 Practical integration path

These skills are **patterns**, not dependencies. Use them to write helper
functions in `serving/` without importing anything. If the project wants
template-driven generation, add `templates/` and reference the skill layouts.

---

## 5. Group D — MCP & Tool Building Skills

### 5.1 What is in this group

| Source | Skill | Purpose |
|---|---|---|
| `skills-main/skills/mcp-builder/` | `mcp-builder` | Build MCP servers and tools |
| `claude-plugins-official-main/plugins/mcp-server-dev/` | `mcp-server-dev` | Plugin-style MCP development |
| `financial-services-main/plugins/vertical-plugins/financial-analysis/` | Multiple data-connector skills | Patterns for external data provider integrations |

### 5.2 How it maps to this project

| Project component | Relevant skill | What to borrow |
|---|---|---|
| `mcp_server/server.py` | `mcp-builder` | Tool registration, dispatch table patterns, schema design |
| Future data connectors | `financial-analysis` data-connector skills | Provider adapter pattern, auth, caching, error handling |
| `gov/ledger.py` | `mcp-builder` | External-call logging pattern |
| `gov/access.py` | `mcp-server-dev` | Tool-level access control |

### 5.3 How to use it while coding here

**When adding a new MCP tool:**
1. Open `mcp-builder/SKILL.md` for the canonical tool definition pattern.
2. Add the tool to `mcp_server/server.py` following the existing dispatch table.
3. Update the relevant `agent_skills/*.md` file to mention the new tool.

**When reviewing MCP changes:**
1. Check tool name follows the skill's naming conventions.
2. Check input/output schemas are explicit.
3. Check access control is enforced at dispatch.

### 5.4 Practical integration path

The project already has `mcp_server/server.py`. Use `mcp-builder` primarily for:
- Naming new tools consistently.
- Adding schema validation.
- Planning future factory-data connectors.

---

## 6. Group E — Agent Orchestration & Review

### 6.1 What is in this group

| Source | Resource | Role |
|---|---|---|
| `addyosami agent-skills-main/agents/` | `code-reviewer.md` | Senior Staff Engineer review persona |
| `addyosami agent-skills-main/agents/` | `security-auditor.md` | Security review persona |
| `addyosmani agent-skills-main/agents/` | `test-engineer.md` | QA Specialist review persona |
| `addyosami agent-skills-main/agents/` | `web-performance-auditor.md` | Web performance review persona |
| `claude-plugins-official-main/plugins/code-review/` | `code-review` | Claude Code plugin review toolkit |
| `claude-plugins-official-main/plugins/pr-review-toolkit/` | `pr-review-toolkit` | PR review patterns |
| `claude-plugins-official-main/plugins/security-guidance/` | `security-guidance` | Security guidance plugin |
| `claude-plugins-official-main/plugins/skill-creator/` | `skill-creator` | Create new skills |

### 6.2 How it maps to this project

| Review need | Resource to invoke |
|---|---|
| General code review | `code-reviewer.md` + `code-review-and-quality/SKILL.md` |
| Numeric trust / access / privacy changes | `security-auditor.md` + `security-and-hardening/SKILL.md` |
| Test coverage and edge cases | `test-engineer.md` + `test-driven-development/SKILL.md` |
| New `agent_skills/*.md` file | `skill-creator/SKILL.md` |
| MCP server changes | `mcp-server-dev` + `code-reviewer.md` |

### 6.3 How to use it during review

These are **personas**, not files to import. Before declaring a change done,
run a mental role-play:

1. **Code reviewer:** "Is this the simplest change that passes the test? Are
   contracts clear? Is there duplication?"
2. **Security auditor:** "Does this touch access control, external calls, or
   private data? Is the ledger updated? Is the privacy tier respected?"
3. **Test engineer:** "What edge cases are missing? Does the test prove the
   contract, not just the implementation?"

### 6.4 Practical integration path

Do not copy these agent files into the project unless creating a specialized
review bot. Instead:
- Add review checklists to each `agent_skills/*.md` file.
- Reference the personas in module `AGENTS.md` files where helpful.

---

## 7. Group F — Learning & Reference Material

### 7.1 What is in this group

| Source | Resource | Purpose |
|---|---|---|
| `prompt-eng-interactive-tutorial-master/` | 13 notebooks | Prompt engineering fundamentals |
| `claude-cookbooks-main/skills/custom_skills/creating-financial-models/` | `creating-financial-models/SKILL.md` | Financial model workflow |
| `claude-cookbooks-main/capabilities/` | RAG, summarization, text-to-sql, knowledge_graph | Implementation recipes |
| `claude-cookbooks-main/extended_thinking/` | Long-context reasoning patterns | Complex analysis workflows |
| `claude-cookbooks-main/evals/` | Evaluation building | Golden set construction |

### 7.2 How it maps to this project

| Topic | Resource |
|---|---|
| Writing better prompts for `engines/docs/prompt_builder.py` | `prompt-eng-interactive-tutorial-master/` |
| Financial model examples | `creating-financial-models/SKILL.md` |
| Improving `engines/brain/search.py` / RAG | `claude-cookbooks-main/capabilities/retrieval_augmented_generation/` |
| Improving `engines/docs/summarize.py` | `claude-cookbooks-main/capabilities/summarization/` |
| Converting questions to SQL for `engines/data/` | `claude-cookbooks-main/capabilities/text_to_sql/` |
| Building the golden eval set in `eval/` | `claude-cookbooks-main/evals/` |

### 7.3 How to use it

Read these **before designing** a new capability, not during implementation.
Use them for inspiration, then translate patterns into the project's
contracts-first style.

---

## 8. Quick-Reference Matrix: "I am doing X → open Y"

| I am doing... | External skill(s) to open | Project skill to update |
|---|---|---|
| Adding a new MCP tool | `mcp-builder` | Relevant `agent_skills/*.md` |
| Adding ingestion cleaning rules | `clean-data-xls`, `audit-xls` | `spreadsheet_ingestion.md` |
| Adding variance/drive logic | `variance-commentary`, `gl-reconciler` | `cost_variance_analysis.md` |
| Adding PPTX/DOCX output | `pptx-author`, `docx` | `management_reporting.md` |
| Writing a new skill file | `skill-creator`, `using-agent-skills` | New file in `agent_skills/` |
| Code review | `code-review-and-quality`, `code-reviewer.md` | None (process) |
| Security/privacy review | `security-and-hardening`, `security-auditor.md` | `audit_and_trust.md` |
| Test design | `test-driven-development`, `test-engineer.md` | Relevant skill's test section |
| Debugging a failing test | `debugging-and-error-recovery` | None (process) |
| Planning a new phase | `planning-and-task-breakdown`, `spec-driven-development` | `03_design/phase_a_cards.md` |
| Writing module docs | `documentation-and-adrs` | Module `AGENTS.md` |
| Building eval fixtures | `claude-cookbooks/evals` | `eval/README.md` |

---

## 9. Integration Rules for This Repo

1. **Do not blindly copy.** Compare each external skill against the existing
   `agent_skills/*.md` and `AGENTS.md` rules. Merge only the missing pieces.
2. **Preserve the three non-negotiables.** No external skill overrides:
   - Golden Rule (code writes code from samples)
   - Calculation-Integrity Rule (every number from SQL)
   - Decision-Memory Rule (every output stored with evidence)
3. **Keep skills small.** If a financial skill adds >5 steps, split it into a
   separate project-specific skill file.
4. **Link, don't duplicate.** Reference external skill paths in checklists
   instead of copying whole files when the source is stable on disk.
5. **Test-first still applies.** Any skill integration must be proven by a
   passing test in `tests/`.

---

## 10. Suggested Next Steps

If the owner wants to start using these skills, the lowest-risk order is:

1. **Engineering workflow hygiene** — add review checklists from Group A into
   existing `agent_skills/*.md` files.
2. **Finance operations patterns** — add a "Finance operations checklist"
   section to `cost_variance_analysis.md` from Group B.
3. **Spreadsheet audit patterns** — add an "Excel audit checklist" section to
   `spreadsheet_ingestion.md` from `audit-xls` / `clean-data-xls`.
4. **Document generation templates** — use Group C to improve `serving/open_design.py`
   layout and styling.
5. **MCP tool discipline** — use Group D when adding the next MCP tool.
6. **Review personas** — adopt Group E personas during code review, optionally
   as a documented checklist in `AGENTS.md`.

---

*Last updated: 2026-07-03. Source inventory is based on the contents of
`C:\Users\mflma\Downloads\Skills` as observed at that date.*

---

## Required contract sections (compliance with test_skill_contracts.py)

### Token budget
This is an inventory document, not an executable skill. Token budget is N/A.

### Input contract
Reads the file listing from the local Downloads directory. No runtime inputs.

### Output contract
Produces a grouping table and guidance recommendations. No executable output.

### Invariants
- This document is reference-only; it does not execute code.
- Never dump raw external skill content into agent context without attribution.
- All external skill paths are treated as untrusted references until verified.
