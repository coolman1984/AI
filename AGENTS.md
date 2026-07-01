# AGENTS.md — Operating Manual for All AI Agents on This Repo

This file is read automatically by Codex (and is the convention for other agents).
It is the **durable, non-negotiable guidance**. The detailed plan lives in
`MASTER_PLAN.md`; the kickoff brief lives in `CODEX_PLAN.md`.

This repository builds a **factory-wide Decision Intelligence System** for a large
TV/mobile manufacturing plant. It is currently a planning workspace about to enter
implementation. Finance/Costing is the first pilot; the platform is factory-wide.

---

## Read order (start here, always)
1. **`MASTER_PLAN.md`** — the single authoritative architecture and build plan. Read
   before proposing code or changing phases. (Parts D, H, I, J, K, L are the ones you
   implement against.)
2. **`AGENT_SKILL_MAP.md`** — the lightweight routing layer: which skill to load for which task.
3. **`AGENT_CORE_CONTRACT.md`** — the shared spine all skills must obey.
4. **`CODEX_PLAN.md`** — the lead-engineer kickoff: exactly what to build first.
5. `ARCHITECTURE.md` — founding mental model: *AI reads the map; engines read the volume.*
6. `IMPLEMENTATION_PLAN.md` — tabular/SAP/Excel→DuckDB engine spec.
7. `IMPLEMENTATION_PLAN_DOCS.md` — PDF/Word/PPT + OCR engine spec.
8. `IMPLEMENTATION_PLAN_SECONDBRAIN.md` — vault + index engine spec.
9. `REVIEW.md` — weak-point audit; read before trusting the architecture.

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
- Load `AGENT_CORE_CONTRACT.md` plus only the relevant skill from `agent_skills/`.
- The skills may specialize, but shared truth stays centralized.
- If a task spans multiple stages, compose skills in sequence instead of improvising one giant prompt.

---

## The build chain (who does what)
- **Architect** → produced `MASTER_PLAN.md` (architecture, contracts, phases, rules).
- **Lead Engineer = Codex / GPT-5.5** → expands phases into **Task Cards**, writes
  contracts as stubs + the **tests (red)**, scaffolds the repo and every `AGENTS.md`,
  integrates, runs the full suite. Implements business logic only when a card is not
  worth delegating.
- **Implementers = DeepSeek V4 Pro / V4 Flash, Kimi K2.7, MiniMax M3** → implement one
  Task Card at a time: write code until that card's (already-written) test passes.

**Method = contracts-first, test-first.** The interface and the test exist before code.
A card says: *"make `tests/<x>` pass by implementing `<contract>`, editing ONLY
`<file>`."* See `MASTER_PLAN.md` Part I for the Task Card format and model routing.

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
  (MASTER_PLAN Part O) and a recorded, named human sign-off.** The system proposes and
  checks; a human approves and owns the decision. This is non-negotiable.
- Always read `MASTER_PLAN.md` + the nearest `AGENTS.md` before editing a module.
- Always work test-first: a card is done only when its named test is green.
- Always keep modules small and single-responsibility; split a file before it grows
  past its cap.
- Always update a module's `AGENTS.md` in the same change that alters its interface.
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
The pilot must handle (defenses in `MASTER_PLAN.md` Part J):
- SAP Excel exports ~200 MB, up to ~272 columns × ~600k rows.
- **Total/subtotal rows hidden inside detail rows** (detect + exclude; never sum).
- English + Arabic documents (offline OCR, RTL, mixed scripts).
- PDFs, PowerPoint, Word, emails, approvals, **screenshots, handwriting** — weak OCR is
  confidence-scored and routed to a **human-review queue**, never silently trusted.

## Module maps to create during implementation
Each major module gets its own `AGENTS.md` (purpose · public interface · inputs/outputs
· invariants · never-do · allowed libs + import examples · test commands · edge cases):
`shared/contracts/`, `shared/metrics/` (governed meaning, Part R), `engines/data/`,
`engines/docs/`, `engines/email/`, `engines/brain/`, `engines/audit/` (Part O),
`engines/learning/` (Part P), `engines/wiki/` (Part Q), `mcp_server/`, `lenses/`,
`templates/`, `playbooks/finance/`, `serving/` (one-A4 card + human review UI),
`gov/security/` (threat model), `ops/observability/`, `eval/`.
