# AGENTS.md — Operating Manual for All AI Agents on This Repo

This file is read automatically by Codex (and is the convention for other agents).
It is the **durable, non-negotiable guidance** — rules and read order only, not live status.
Live status: `PROJECT_MAP.md` and `00_control/task_queue.md`. Architecture REFERENCE:
`03_design/assistant_master_plan.md`. Active build plan: `03_design/foreman_build_plan.md`.
Historical material lives under `archive/` (read-never for current work).

This repository builds a **factory-wide Decision Intelligence System** for a large
TV/mobile manufacturing plant. Finance/Costing is the first pilot; the platform is factory-wide.

---

## Read order (start here, always)

**This is the one canonical list.** `AGENT_SKILL_MAP.md`, `PROJECT_MAP.md`, and
`CLAUDE.md` all point back here instead of keeping their own copy — a duplicated list
is how this drifted out of sync before (four files, four different orders). If you
edit this list, you do not need to edit it anywhere else; the other files reference it
by name.

1. **`README.md`** — 15-line orientation; points here.
2. **`AGENTS.md`** (this file) — durable rules, Doc Law, core contract, commands. Read first.
3. **`PROJECT_MAP.md`** — current state: tree, modules, FOREMAN layer, charter & risks.
4. **`AGENT_SKILL_MAP.md`** — which skill to load for which task.
5. **`03_design/`** — only when needed: `assistant_master_plan.md` and `skill_os_blueprint.md`
   (REFERENCE); `foreman_build_plan.md` (ACTIVE-PLAN when building FOREMAN). No other
   `03_design/` file is current unless its frontmatter says ACTIVE-PLAN (max 2).
6. Only the relevant skill file(s) from `.claude/skills/` (or Hermes `skills/` for FOREMAN).
7. The nearest module `AGENTS.md`.
8. Then the code.

`archive/` is historical evidence only — do not treat as current guidance.

## The three rules everything obeys
1. **Golden Rule:** code writes code from samples; engines execute against volumes. The
   AI never reads raw data — it reads profiles and writes code your machine runs.
2. **Calculation-Integrity Rule:** every number comes from a SQL query. A synthesis
   model may NEVER originate a number. Numeric questions route to the Data Engine first.
3. **Decision-Memory Rule:** every useful output is stored (fact/driver/risk/
   recommendation/decision/action/lesson) **with evidence**.

## Lightweight agent architecture
- Treat this repository as **lightweight routing + central contract + specialized skills**.
- Do not load the whole architecture for every task.
- Load the **Core contract** section below plus only the relevant skill from `.claude/skills/`.
- The skills may specialize, but shared truth stays centralized.
- If a task spans multiple stages, compose skills in sequence instead of improvising one giant prompt.

---

## The build chain (who does what)
- **Architect** → produced `03_design/assistant_master_plan.md` (current architecture,
  contracts, phases, rules).
- **Lead Engineer = Codex / GPT-5.5** → expands phases into **Task Cards**, writes
  contracts as stubs + the **tests (red)**, scaffolds the repo and every `AGENTS.md`,
  integrates, runs the full suite. Implements business logic only when a card is not
  worth delegating.
- **Implementers = DeepSeek V4 Pro / V4 Flash, Kimi K2.7, MiniMax M3** → implement one
  Task Card at a time: write code until that card's (already-written) test passes.

**Method = contracts-first, test-first.** The interface and the test exist before code.
A card says: *"make `tests/<x>` pass by implementing `<contract>`, editing ONLY
`<file>`."* FOREMAN build steps: `03_design/foreman_build_plan.md`. Legacy task cards
are archived under `archive/03_design/`.

---

## Doc Law (documentation discipline)

1. Living docs are ONLY the seven below + module `AGENTS.md` files + skill files. Nothing else
   is current documentation: `README.md`, `AGENTS.md`, `CLAUDE.md`, `PROJECT_MAP.md`,
   `AGENT_SKILL_MAP.md`, `00_control/task_queue.md`, `00_control/decisions.md`.
2. Every design/plan doc in `03_design/` MUST carry frontmatter: `status: ACTIVE-PLAN | REFERENCE |
   ARCHIVED`, plus `owner` and `date`. At most **2** `ACTIVE-PLAN` docs at any time.
3. A plan that finishes or is superseded moves to `archive/` **in the same commit** that
   finishes it. Archive is write-only, read-never for agents doing current work.
4. Never create a new root-level `.md`. Never create status/progress/notes files — status in
   `task_queue.md`, decisions in `decisions.md`, knowledge in `vault/`.
5. Enforced by `tests/test_doc_system.py`. If the test blocks you, fix the docs, not the test.

---

## Core contract (all skills must obey)

Shared operational language: same run identity, storage targets, naming, trust logic, evidence,
and failure semantics.

**Run identity:** `run_id`, `task_id` when applicable, `source_type`, `source_path`, sheet/page
when applicable, `started_at`, `finished_at`, `status`.

**Evidence:** Every released claim traces to source location, calculation/query path, confidence,
and rejection state when relevant.

**Skill I/O:** Declare mission, sources, upstream artifacts, acceptance and blocking conditions.
Outputs must include `artifact_type`, path, `run_id`, `status`, `confidence`, `evidence_summary`,
`issues_found`, `recommended_next_step`. Missing upstream → fail clearly, do not invent.

**Naming:** Stable terms (`cost_center`, `run_id`, `evidence`, `sign_off`, …). Map synonyms in
glossary/vault, do not rename core concepts per skill.

**Storage:** Raw inputs never overwritten; rejects persisted with reason; durable outputs in
governed locations.

**Trust:** No generated number is a fact; numeric conclusions from trusted query path; audit
independent; low confidence → review queue; human sign-off before release to decision-makers.

**Failure semantics:** success | partial (labeled) | blocked | failed | needs human review.

**Handoff:** What was produced, where stored, what is unresolved, which skill loads next.

**Priority:** trust over elegance; restartability over breadth; evidence over speed.

---

## Commands (Phase 0 must wire these up; until then they are the target)
```
pip install -r requirements.txt     # install deps (pinned)
pytest                              # run all tests  (the definition of done)
pytest tests/<module>/<file>.py    # run one card's test
ruff check . && ruff format .      # lint + format (style is enforced, not debated)
```
Every module's `AGENTS.md` must restate the exact commands to test *that* module.

## Always
- **No report reaches a human decision-maker without passing the independent Audit Layer
  (`03_design/assistant_master_plan.md`) and a recorded, named human sign-off.** The system proposes and
  checks; a human approves and owns the decision. This is non-negotiable.
- Always read `03_design/assistant_master_plan.md` + the nearest `AGENTS.md` before editing a module.
- Always work test-first: a card is done only when its named test is green.
- Always keep modules small and single-responsibility; split a file before it grows
  past its cap.
- Always update a module's `AGENTS.md` in the same change that alters its interface.
- Always update `PROJECT_MAP.md` in the same change that adds/removes/renames a file
  or module, changes a module's purpose or public interface, or changes phase/task
  status. It is the file every other routing doc tells agents to trust for
  orientation — treat it like the module `AGENTS.md` rule above, not as optional.
- Always commit and push to **`main`** (see git policy below).
- Always send unparseable rows to `rejects.csv`, failed docs to `failures.csv`, and log
  every assumption to `run.log`. Nothing vanishes silently.

## Ask first
- Ask before changing a published contract in `shared/contracts/` (it breaks other
  modules and tests).
- Ask before adding a new third-party dependency not already in `requirements.txt`.
- Ask before any action that would send factory data to an external service.

## Never
- **Never originate a number, quote, citation, or confidence score from generation.**
  Numbers come from `query_numbers`; quotes from `search_documents`/`search_emails`.
- Never load a whole large data file into memory or into a prompt. Stream into DuckDB.
- Never reach inside another module; call it only through its published contract.
- Never send factory documents, SAP exports, emails, screenshots, or OCR images to any
  external service. **All processing stays in-house.** OCR is offline (Tesseract/Paddle).
- **Never create git branches. Never push to any branch other than `main`.** All work
  commits directly to `main` — this is the repository owner's explicit directive.
- Never force-push. Never rewrite published history on `main`.

---

## Git & branch policy (owner directive — strict)
- There is exactly **one** branch: **`main`**. Do not create, request, or push other
  branches. Commit your work and push to `main`.
- Safety in place of branch isolation: **tests gate every commit.** Do not commit code
  whose card test (and the existing suite) is not green.
- Use clear, descriptive commit messages.

## First pilot: Finance/Costing (but build factory-wide)
Do not design a finance-only product. Build reusable engines + a finance **lens**.
The pilot must handle the hard cases in `03_design/assistant_master_plan.md`:
- SAP Excel exports ~200 MB, up to ~272 columns × ~600k rows.
- **Total/subtotal rows hidden inside detail rows** (detect + exclude; never sum).
- English + Arabic documents (offline OCR, RTL, mixed scripts).
- PDFs, PowerPoint, Word, emails, approvals, **screenshots, handwriting** — weak OCR is
  confidence-scored and routed to a **human-review queue**, never silently trusted.

## Module maps to create during implementation
Each major module gets its own `AGENTS.md` (purpose · public interface · inputs/outputs
· invariants · never-do · allowed libs + import examples · test commands · edge cases):
`shared/contracts/`, `shared/metrics/` (governed meaning), `engines/data/`,
`engines/docs/`, `engines/email/`, `engines/brain/`, `engines/audit/`,
`engines/learning/`, `engines/wiki/`, `mcp_server/`, `lenses/`,
`templates/`, `playbooks/finance/`, `serving/` (one-A4 card + human review UI),
`gov/security/` (threat model), `ops/observability/`, `eval/`.
