# CLAUDE.md — How the AI team works on this project

This file describes **orchestration** for Claude Code on Factory Brain. **Rules live in
`AGENTS.md`** — if anything conflicts, `AGENTS.md` wins.

The owner is **non-technical**: TLDR, plain English, clear logic, owner decides / agent executes.

---

## Team roles

**Fable (main thread)** — plan, decide, direct. Minimize tokens: do not read large files or paste
long code here; delegate implementation and return compressed summaries.

**Fixed pipeline for code changes**

1. **deepseek-flash** — primary implementer (exact files, exact test).
2. **deepseek-pro** — reviewer (correctness, edge cases).
3. **sonnet-reviewer** — final gate: diff, `pytest`, `ruff`, project rules → PASS / NEEDS FIX.

Loop at most ~2 times before escalating to the owner.

**Hard decisions:** optional parallel **deep-reasoner (Opus)** + **Codex**; Fable synthesizes one
recommendation.

| Teammate | Role |
|---|---|
| Fable | Plan / decide / direct |
| deepseek-flash | Write code |
| deepseek-pro | Review code |
| sonnet-reviewer | Final gate |
| deep-reasoner / Codex | Big tradeoffs |

---

## Non-negotiables (summary — detail in AGENTS.md)

- Numbers only from the data engine; audit + named sign-off before release.
- In-house only for factory data; HQ PPTX may use cloud only when owner approves that tier.
- One branch `main`; commit when owner asks and tests are green.
- Update module `AGENTS.md` with interface changes.

---

## Read order

Canonical list: **`AGENTS.md` → "Read order"** (starts at `README.md`). Do not duplicate it here.

**Live status:** `00_control/task_queue.md` and `PROJECT_MAP.md` — not `restart_notes.md` as docs
(runtime snapshot; see header there).