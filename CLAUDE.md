# CLAUDE.md — How the AI team works on this project

This file describes **orchestration** for Claude Code on Factory Brain. **Rules live in
`AGENTS.md`** — if anything conflicts, `AGENTS.md` wins.

The owner is **not a programmer and not technical**. Permanent communication rule — saved in
`~/.grok/rules/00-owner-communication.md`, `~/.grok/memory/MEMORY.md`,
`~/.config/opencode/owner_rules.md`, and `.grok/rules/00-owner-communication.md` (this repo):

- **TLDR first** — deep, full of logic and ideas, but bottom line in 1–2 sentences. No preamble.
- **Very simple English** — no jargon or code; define any technical term in one line.
- **Maximum clear logic** — explain *why* and trade-offs (Option A vs B, cost vs gain) so the
  owner can **take decisions** and **understand** you. The agent executes; the owner decides.
- **Short sentences, one idea per line** — simple tables/bullets when comparing options.
- **Ask before any big or irreversible action** (commit, delete, refactor, spending, external data).
- **No filler** — no "Here is…", no "Based on…", no "I will now…". Just the answer.
- **Test:** if a smart non-technical manager can't read it and immediately decide, rewrite it.

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