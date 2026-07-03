---
status: ARCHIVED
owner: owner
date: 2026-07-03
---

# Documentation Consolidation Plan — ONE strict doc system

*2026-07-03. Status: ACTIVE-PLAN. Executor: a coding agent. When every phase is done, this file
itself moves to `archive/` — that is the test that the system works.*

## The problem
156 `.md` files. ~45 are "documentation an agent might read" — overlapping plans (3 FOREMAN docs,
4+ superseded implementation plans), 17 control files, 2 superseded root overviews. A new AI agent
cannot tell what is current, what is finished, and what is dead. Also: test runs are leaking junk
files into `approvals/` (side-bug, fixed in Phase 4).

## Target end state — THE SEVEN LIVING DOCS
After this plan, an agent may treat ONLY these as current documentation:

| # | File | Role | One rule |
|---|---|---|---|
| 1 | `README.md` (new, root) | 15-line orientation → points to AGENTS.md | Never grows past 25 lines |
| 2 | `AGENTS.md` | THE CONSTITUTION: rules, canonical read order, commands, git policy, **Doc Law (below)**. Absorbs `AGENT_CORE_CONTRACT.md` | Only durable rules, no status |
| 3 | `CLAUDE.md` | Thin: team/orchestration workflow + pointer to AGENTS.md | ≤120 lines |
| 4 | `PROJECT_MAP.md` | CURRENT STATE: tree, modules, engines, FOREMAN layer, test map, "where things stand". Absorbs the useful content of `restart_notes`, `progress`, `mission`, `project_scope` | Updated in the same commit as any structural change (rule already exists) |
| 5 | `AGENT_SKILL_MAP.md` | Routing: which skill for which task (tests scan it — keep name/location) | Routing only |
| 6 | `00_control/task_queue.md` | THE ONLY live tracker (status of all work) | Only Evaluator marks Passed |
| 7 | `00_control/decisions.md` | Append-only owner decision log | Never rewritten, only appended |

**Everything else is one of:** module `AGENTS.md` next to code (keep — interface docs) ·
`agent_skills/*.md` + `skills/*/SKILL.md` (keep — governed by tests) · `templates/`, `vault/`,
`reports/`, `runs/`, `lessons/`, `approvals/` (keep — FOREMAN data, not docs) · `archive/` (dead).

## The Doc Law (add verbatim to AGENTS.md, replacing scattered doc rules)
1. Living docs are ONLY the seven above + module AGENTS.md files + skill files. Nothing else is
   current documentation.
2. Every design/plan doc lives in `03_design/` and MUST carry frontmatter:
   `status: ACTIVE-PLAN | REFERENCE | ARCHIVED` + `owner` + `date`. At most **2 ACTIVE-PLAN**
   docs may exist at any time.
3. A plan that finishes or is superseded moves to `archive/` **in the same commit** that
   finishes it. Archive is write-only, read-never (historical evidence only).
4. Never create a new root-level `.md`. Never create a status/progress/notes file — status goes
   in `task_queue.md`, decisions in `decisions.md`, knowledge in `vault/`.
5. Enforced by `tests/test_doc_system.py` (Phase 3). If the test blocks you, fix the docs, not
   the test.

## Phase 1 — Merge then archive (the big cut)
Order matters: merge content first, archive second, tests green after each step.
**Never delete anything — `git mv` to `archive/` preserving history.** Create `archive/INDEX.md`
listing every archived file + one-line reason.

1.1 **Root:** archive `FACTORY_SECOND_BRAIN.md`, `MASTER_PLAN.md` (both already superseded).
Merge `AGENT_CORE_CONTRACT.md` into AGENTS.md as a "Core contract" section, then archive it;
update the 3 files that reference it (AGENTS.md read order, AGENT_SKILL_MAP.md, PROJECT_MAP.md).
Merge `BUILD.md` into README.md (new), archive BUILD.md.

1.2 **00_control/ (17 → 4):** KEEP `task_queue.md`, `decisions.md`. KEEP `restart_notes.md`,
`session_state.md` ONLY because `ops/session_state.py` + tests reference them — demote to
machine-written state files (add header: "runtime state, not documentation"). MERGE key content
of `mission.md`, `project_scope.md`, `success_contract.md`, `assumptions.md`, `risks.md`,
`open_questions.md`, `bottlenecks.md` into a single "Project charter & risks" section of
PROJECT_MAP.md (compress hard — one screen). Fold `progress.md`, `run_log.md`, `plan_review.md`,
`evaluation_report.md`, `evidence_log.md`, `memory_index.md` → archive (their live roles are
served by task_queue, foreman.db, vault). Then archive all 11 merged/folded files.

1.3 **03_design/ (16 → 4):** KEEP: `assistant_master_plan.md` (status: REFERENCE — the
architecture), `skill_os_blueprint.md` (REFERENCE — FOREMAN design), `foreman_build_plan.md`
(ACTIVE-PLAN — the one live plan), this file (ACTIVE-PLAN until done). ARCHIVE:
`architecture.md` (pointer), `codex_planning_prompt.md`, `current_implementation_plan.md`,
`implementation_plan.md`, `oss_reference_evaluation.md`, `phase_a_cards.md`,
`phase_b_to_f_cards.md`, `rollback_plan.md`, `unified-ingestion-spine.md`, `validation_plan.md`,
`foreman_review_brief.md` (review done — findings live in task_queue as fix items),
`foreman_code_execution_plan.md` (superseded by foreman_build_plan), `reviews/opus_critique.md`.
Before archiving `current_implementation_plan.md`: move any still-open gates/rules into
foreman_build_plan.md or AGENTS.md.

1.4 **Numbered folders:** merge the 2–3 useful facts from `01_inputs/`, `02_understanding/`,
`04_execution/`, `05_validation/`, `06_final_outputs/` into PROJECT_MAP.md (terminology →
vault glossary notes instead if factual), then archive the folders wholesale
(`archive/01_inputs/` etc.). Grep tests first; nothing should reference them.

## Phase 2 — Rewrite the seven
2.1 New `README.md` (≤25 lines): what this repo is, the two-window workflow, "AI agents: read
AGENTS.md first", test/lint commands.
2.2 AGENTS.md: update canonical read order to exactly: README → AGENTS.md → PROJECT_MAP.md →
AGENT_SKILL_MAP.md → (03_design REFERENCE docs only when needed) → skill file → module
AGENTS.md → code. Add the Doc Law. Absorb core contract.
2.3 PROJECT_MAP.md: add "Project charter & risks" (from 1.2) and "FOREMAN layer" section
(tools/, skills/, registry/, vault/ — currently missing); refresh tree and test count; remove
sections that duplicate archived docs.
2.4 CLAUDE.md: cut to team workflow + pointers (it currently restates rules AGENTS.md owns).
2.5 All four 03_design keepers get the status frontmatter.

## Phase 3 — Enforcement (the part that keeps it fixed)
`tests/test_doc_system.py`:
- Root allowlist: root `.md` ∈ {README, AGENTS, CLAUDE, PROJECT_MAP, AGENT_SKILL_MAP}.md — fail otherwise.
- `00_control/` allowlist: {task_queue, decisions, restart_notes, session_state}.md.
- Every `03_design/*.md` has valid `status:` frontmatter; count(ACTIVE-PLAN) ≤ 2.
- `archive/INDEX.md` lists every file in `archive/` (no unindexed corpses).
- Numbered stale folders (`01_inputs` … `06_final_outputs`) do not exist at root.
Update `tests/test_doc_archive.py` expectations (it asserts specific archive contents/AGENTS.md
text) — adjust to the new reality, don't fight it.

## Phase 4 — Side-bug: approvals/ test pollution
Tests currently write real files into `approvals/pending|decided/` (~40 junk files dated today).
Fix: approval tests must use `tmp_path`; add the junk files to cleanup (delete the
`*_runnone.md` artifacts — they are test artifacts, not owner decisions; the 3 `run1/run2`
pending ones: ask owner before deleting). Add a test asserting no test writes to real
`approvals/` (e.g., snapshot dir before/after in a fixture, or ban via conftest monkeypatch).

## Verification (definition of done)
1. `pytest` fully green incl. new `test_doc_system.py`; `ruff` clean.
2. Count check: root has exactly 5 `.md`; `00_control/` has 4; `03_design/` has ≤4 + frontmatter.
3. Cold-start drill: a fresh agent given only "read README.md" can state (a) the rules,
   (b) current project status, (c) which skill to load for an Excel task — in under 3 minutes of
   reading. Owner runs this drill with a new session.
4. `archive/INDEX.md` complete; `git log --follow` works on a sample archived file.
5. Finish: set this file's status to ARCHIVED, `git mv` it to `archive/`, update task_queue.

## Executor rules
- Work in the phase order. Full suite green after every numbered step (1.1, 1.2, …).
- Merge = compress, don't concatenate. Target: PROJECT_MAP.md stays under ~600 lines.
- Grep for a filename in `tests/`, `ops/`, `mcp_server/`, `tools/` before moving ANY file.
- Do not commit until the owner approves. Do not touch `vault/`, `research/`, `downloads/`.
