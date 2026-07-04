---
status: ARCHIVED
owner: mflma
date: 2026-07-04
---

# Skill Unification Plan

## Goal

Unify this repo onto one canonical, auto-discoverable agent skill library at
`.claude/skills/`, keep `skills/` as the FOREMAN executable layer, complete the
missing FOREMAN `SKILL.md` files, and remove routing ambiguity without touching
the numeric engines or changing published business contracts.

## Why this plan exists

Today the repo has too many overlapping "skill" surfaces:

- `agent_skills/` holds the six routing skills, but it is not auto-discovered by
  the main coding-agent ecosystems.
- `.claude/skills/` exists but is empty, so the canonical Claude skill path is
  unused.
- `skills/` contains FOREMAN executable folders, but 6 of 11 folders have
  `run.py` without `SKILL.md`.
- `registry/skills.yaml` is a machine registry, not agent instructions, yet it
  is currently part of the agent discovery burden.
- `AGENT_SKILL_MAP.md`, `AGENTS.md`, and `PROJECT_MAP.md` still point agents at
  the old flat-file routing layout.

The result is avoidable token waste, routing confusion, and partial skill
coverage.

## Final target state

```text
.claude/skills/                  # canonical agent-facing skill library
  spreadsheet-ingestion/SKILL.md
  document-evidence-extraction/SKILL.md
  cost-variance-analysis/SKILL.md
  management-reporting/SKILL.md
  knowledge-search/SKILL.md
  audit-and-trust/SKILL.md
  foreman-pipeline/SKILL.md

skills/                          # FOREMAN executable layer
  <11 folders, each with run.py + SKILL.md>

registry/skills.yaml             # FOREMAN machine registry, unchanged role
AGENT_SKILL_MAP.md               # thin routing map -> .claude/skills/*
03_design/external_skills_inventory.md
                                 # reference study, not part of routing
```

## Decision

**Canonical agent-facing skills live in `.claude/skills/<skill-name>/SKILL.md`.**

### Why this is the chosen arrangement

| Option | Verdict |
|---|---|
| Keep `agent_skills/*.md` flat files | Rejected. No auto-discovery, high routing overhead, old naming shape. |
| Make root `skills/` serve both FOREMAN code and agent instructions | Rejected. Two very different jobs in one folder, and the current code imports should stay stable. |
| Use symlinks or junctions between `skills/` and `.claude/skills/` | Rejected. Fragile on Windows and noisy in git tooling. |
| **Use `.claude/skills/` as canonical instructions and keep `skills/` as executable code** | **Chosen.** Best match for auto-discovery plus stable FOREMAN imports. |

### Division of responsibility after migration

- `.claude/skills/`
  - Agent-facing instructions only.
  - One folder per skill.
  - Each folder contains exactly one `SKILL.md`.
- `skills/`
  - FOREMAN executable skills only.
  - Python code stays where it is.
  - Every direct child with `run.py` must also contain `SKILL.md`.
- `registry/skills.yaml`
  - FOREMAN machine registry only.
  - Not a replacement for human-readable skill instructions.
- `AGENT_SKILL_MAP.md`
  - Thin routing file that points to `.claude/skills/*/SKILL.md`.
- `03_design/external_skills_inventory.md`
  - Reference study only.
  - Never part of the live routing path.

---

## Kimi K2.7 Code steering notes

This section is here because the executing agent is expected to be a low-cost
coding agent built on **`kimi-k2.7-code`** or a close Moonshot-based coding
wrapper.

These steering rules are based on Moonshot's official docs checked on
**2026-07-04**:

- Kimi docs say explicit instructions beat vague intent.
  - Give exact file paths, exact commands, exact output shape, and exact stop
    conditions.
- Kimi docs say complex tasks should be broken down before execution.
  - This plan therefore uses small, file-bounded phases and explicit gates.
- Kimi docs say reference text improves accuracy.
  - The agent must use repo files (`AGENTS.md`, `PROJECT_MAP.md`,
    `AGENT_SKILL_MAP.md`, `registry/skills.yaml`, `registry/tools.yaml`,
    existing `SKILL.md` files) as reference text rather than guessing.
- Kimi K2.7 Code is always in thinking mode.
  - If the execution environment is API-based, do not disable thinking.
- Preserved thinking is always on for `kimi-k2.7-code`.
  - If the executor manages chat history manually, it must preserve historical
    assistant reasoning state exactly as required by the client runtime.
- Moonshot says **do not set `temperature`** for `kimi-k2.7-code`.
  - The execution wrapper should use model defaults.
- Moonshot says long multi-step tool loops should use **`max_tokens >= 16000`**.
  - If the agent is driven by raw API calls, give it enough output budget to
    finish a phase without truncation.
- Moonshot recommends structured prompts: role, goal, constraints, output
  template, and handling of edge cases.
  - This plan includes all five.
- Moonshot warns coding agents can burn tokens quickly through retries.
  - Use bounded phases, continuous local verification, and external review only
    at milestone boundaries.
- Moonshot's agent integration guide recommends disabling browser usage in some
  coding-tool setups.
  - For this repo, browser use is unnecessary during execution. All required
    inputs are local.

### What this means in practice

The cheap coding agent should be steered like this:

1. Give it **one bounded milestone at a time**, not the whole repo plus a vague
   mission.
2. Tell it **which files it may touch** and **which files are forbidden**.
3. Tell it **exactly what "done" means** for the current milestone.
4. Require **exact commands** for grep, lint, and tests.
5. Require it to **stop on ambiguity instead of inventing structure**.
6. Require it to **quote the failing gate or blocker verbatim** if blocked.
7. Do not ask it to improvise tool use policy mid-run.
8. Do not ask it to "clean up whatever looks right."
9. Keep owner checkpoints at **three milestones**, not after every micro-step.

---

## Repo rules the executing agent must obey

1. Read in this order before editing:
   `README.md` -> `AGENTS.md` -> `PROJECT_MAP.md` -> `AGENT_SKILL_MAP.md` ->
   this plan -> nearest module `AGENTS.md` if code is touched.
2. `AGENTS.md` wins over this plan if they conflict.
3. Never create a new root-level `.md`.
4. Never create branches. Never force-push.
5. Use `git mv` for moves so history is preserved.
6. Do not touch `engines/`, `shared/contracts/`, or `tools/run_foreman.py`
   imports for this migration.
7. Do not touch `.grok/`, `downloads/`, `research/`, `vault/`, or `archive/`
   except where this plan explicitly requires archive indexing at close-out.
8. Do not invent tool IDs. Only use IDs present in `registry/tools.yaml`.
9. Do not rewrite skill bodies unless this plan explicitly says to.
10. Run verification after each milestone exactly as specified below.

## Worktree safety rule

Before Phase A starts, the executing agent must inspect `git status --short`.

- If the worktree is clean for the files in this plan, proceed.
- If the worktree contains unrelated user changes, leave them alone.
- If the worktree contains **partial earlier attempts on this migration**, do
  not guess whether to keep or discard them.
  - Either continue them only after verifying they already satisfy the relevant
    phase requirements, or stop and report that the migration is in an
    interrupted state.

This matters because a half-moved skill tree can make grep and tests lie.

---

## Allowed files by milestone

### Milestone A: canonical skill library migration

Allowed to modify:

- `.claude/skills/**`
- `03_design/external_skills_inventory.md`
- `AGENT_SKILL_MAP.md`
- `AGENTS.md`
- `PROJECT_MAP.md`
- `tests/test_skill_contracts.py`
- `00_control/task_queue.md` only if a stale routing reference must be corrected
- `.gitignore` only if needed later for Milestone C

Forbidden in Milestone A:

- `skills/**`
- `registry/skills.yaml`
- `registry/tools.yaml`
- all `engines/**`
- all `shared/contracts/**`

### Milestone B: FOREMAN skill completion

Allowed to modify:

- `skills/**/SKILL.md`
- `tests/test_foreman_skill_lint.py`

Allowed to read:

- `skills/**/run.py`
- `registry/skills.yaml`
- `registry/tools.yaml`
- existing completed FOREMAN `skills/*/SKILL.md`
- `tools/skill_lint.py`

Forbidden in Milestone B:

- `skills/**/run.py`
- `tools/run_foreman.py`
- `engines/**`

### Milestone C: wrapper skill, de-sprawl, close-out

Allowed to modify:

- `.claude/skills/foreman-pipeline/SKILL.md`
- `AGENT_SKILL_MAP.md`
- `PROJECT_MAP.md`
- `.gitignore`
- `00_control/task_queue.md`
- `archive/INDEX.md`
- this plan file itself, only for archive handoff at the very end

---

## Owner checkpoint policy

To keep token usage low, the executing agent should not stop after every tiny
step. Use these three external checkpoints only:

- **Checkpoint 1:** end of Milestone A
- **Checkpoint 2:** end of Milestone B
- **Checkpoint 3:** end of Milestone C / final verification

Inside each milestone, the agent should continue autonomously unless blocked.

---

## Required report format after each checkpoint

The executing agent must respond in this exact structure:

```text
Milestone: <A|B|C>
Files changed:
- <path>
- <path>

Commands run:
- <command>
- <command>

Result:
- PASS | FAIL | BLOCKED

Key evidence:
- <one-line proof>
- <one-line proof>

Anything left untouched on purpose:
- <path> - <reason>
```

If blocked, append:

```text
Blocker:
- <exact failing command or exact ambiguity>
Next needed decision:
- <single owner decision>
```

---

## Milestone A
## Build the canonical `.claude/skills/` library and repoint routing

### Objective

Move the six routing skills into `.claude/skills/`, add open-spec frontmatter,
move the external inventory out of the routing folder, and repoint all routing
docs and contract tests so the live skill system points only at `.claude/skills/`.

### Files touched

Moves:

- `agent_skills/spreadsheet_ingestion.md`
  -> `.claude/skills/spreadsheet-ingestion/SKILL.md`
- `agent_skills/document_evidence_extraction.md`
  -> `.claude/skills/document-evidence-extraction/SKILL.md`
- `agent_skills/cost_variance_analysis.md`
  -> `.claude/skills/cost-variance-analysis/SKILL.md`
- `agent_skills/management_reporting.md`
  -> `.claude/skills/management-reporting/SKILL.md`
- `agent_skills/knowledge_search.md`
  -> `.claude/skills/knowledge-search/SKILL.md`
- `agent_skills/audit_and_trust.md`
  -> `.claude/skills/audit-and-trust/SKILL.md`
- `agent_skills/EXTERNAL_SKILLS_INVENTORY.md`
  -> `03_design/external_skills_inventory.md`

Edits:

- `AGENT_SKILL_MAP.md`
- `AGENTS.md`
- `PROJECT_MAP.md`
- `tests/test_skill_contracts.py`
- `00_control/task_queue.md` only if it still names the old skill path

### Exact required content rules

For each of the six moved routing skills:

1. Keep the existing body content.
2. Prepend frontmatter:

```markdown
---
name: <folder-name>
description: <one sentence, max 1024 chars, must say what it does and when to use it>
---
```

3. `name` must match the directory exactly:
   - `spreadsheet-ingestion`
   - `document-evidence-extraction`
   - `cost-variance-analysis`
   - `management-reporting`
   - `knowledge-search`
   - `audit-and-trust`
4. The description must be "pushy":
   - it must say **when** to use the skill
   - it must not be only a generic summary
5. Preserve the contract sections already enforced by tests:
   - `Token budget`
   - `Input contract`
   - `Output contract`
   - `Invariants`
6. Preserve a raw-data-ban line.

For the external inventory move:

1. Add frontmatter:

```markdown
---
status: REFERENCE
owner: mflma
date: 2026-07-04
---
```

2. Do not shorten or rewrite the body. It is a reference study.

### Exact routing edits required

#### `tests/test_skill_contracts.py`

Must change:

- `SKILLS_DIR = Path("agent_skills")`
  -> `SKILLS_DIR = Path(".claude/skills")`
- `_skill_files()`
  -> `sorted(SKILLS_DIR.glob("*/SKILL.md"))`
- map regex
  -> `r"\.claude/skills/([a-z-]+)/SKILL\.md"`
- map existence check
  -> `SKILLS_DIR / skill_name / "SKILL.md"`

Must add:

- a test that every `SKILL.md` has frontmatter
- a test that `name:` equals the parent folder
- a test that `description:` exists and is non-empty
- a test that `description` length is <= 1024 chars
- a test that each routing `SKILL.md` is under 500 lines

#### `AGENT_SKILL_MAP.md`

Replace every old routing path with the new `.claude/skills/.../SKILL.md` path.
Keep the routing rules and composition patterns. That file stays a routing map,
not a full instruction file.

#### `AGENTS.md`

Update read-order item 6 and the lightweight-routing section so they reference
`.claude/skills/` as the routing library.

#### `PROJECT_MAP.md`

Update all live references to:

- the quickstart routing step
- the "pick your lane" table
- the repository tree
- the architecture explanation of what counts as a skill
- the external inventory path

#### Repo-wide reference cleanup

Run:

```bash
rg -n "agent_skills" --glob "*.md" --glob "*.py" .
```

Fix every live reference outside `archive/`.

### Exact command sequence

Run in this order:

```bash
git status --short
rg --files agent_skills skills
git mv agent_skills/spreadsheet_ingestion.md .claude/skills/spreadsheet-ingestion/SKILL.md
git mv agent_skills/document_evidence_extraction.md .claude/skills/document-evidence-extraction/SKILL.md
git mv agent_skills/cost_variance_analysis.md .claude/skills/cost-variance-analysis/SKILL.md
git mv agent_skills/management_reporting.md .claude/skills/management-reporting/SKILL.md
git mv agent_skills/knowledge_search.md .claude/skills/knowledge-search/SKILL.md
git mv agent_skills/audit_and_trust.md .claude/skills/audit-and-trust/SKILL.md
git mv agent_skills/EXTERNAL_SKILLS_INVENTORY.md 03_design/external_skills_inventory.md
rg -n "agent_skills" --glob "*.md" --glob "*.py" .
pytest -q tests/test_skill_contracts.py
pytest -q
git diff --check
```

### Milestone A acceptance

All of the following must be true:

1. `.claude/skills/` contains exactly six folders at this stage.
2. Each folder contains exactly one `SKILL.md`.
3. Every routing `SKILL.md` has valid frontmatter.
4. `agent_skills/` no longer contains live routing skills.
5. `03_design/external_skills_inventory.md` exists with REFERENCE frontmatter.
6. `AGENT_SKILL_MAP.md`, `AGENTS.md`, and `PROJECT_MAP.md` all point to
   `.claude/skills/`.
7. `pytest -q` is green.
8. `rg -n "agent_skills" --glob "*.md" --glob "*.py" .` returns only archive
   references, if any.

### Common failure modes in Milestone A

- Patch failure due to encoding drift in markdown files
  - Fix by patching smaller sections, not by broad replace.
- Forgetting to update `PROJECT_MAP.md`
  - This violates `AGENTS.md` Always-rules.
- Rewriting skill bodies too aggressively
  - Not needed. This milestone is mostly move + frontmatter + routing.

---

## Milestone B
## Complete missing FOREMAN `SKILL.md` files

### Objective

Bring the executable FOREMAN layer to full documentation coverage by adding
`SKILL.md` to every direct child of `skills/` that contains `run.py`.

### Missing skill folders

- `skills/cross_period_comparison/`
- `skills/decision_brief/`
- `skills/inventory_exception_scan/`
- `skills/period_close_pack/`
- `skills/rework_cost_analysis/`
- `skills/variance_driver_decomposition/`

### Source of truth for content

For each missing `SKILL.md`, derive content from:

1. that folder's `run.py`
2. its entry in `registry/skills.yaml`
3. valid tool IDs in `registry/tools.yaml`
4. structure from the already-complete FOREMAN skills:
   - `skills/excel_intake/SKILL.md`
   - `skills/column_profile_and_map/SKILL.md`
   - `skills/load_to_database/SKILL.md`
   - `skills/reconcile_and_validate/SKILL.md`
   - `skills/management_report/SKILL.md`

Do not invent:

- tool IDs
- validation gates
- outputs not implied by `run.py` or registry data
- risk level beyond what the registry or pattern clearly supports

### Required file structure

Each new `SKILL.md` must include frontmatter:

```markdown
---
skill_id: <from registry>
version: 1.0.0
risk_level: <low|medium|high>
status: active
---
```

And all 10 required sections from `tools/skill_lint.py`:

- `## Purpose`
- `## Use this skill when`
- `## Do NOT use this skill when`
- `## Inputs`
- `## Outputs`
- `## Allowed tools`
- `## Forbidden actions`
- `## Workflow`
- `## Validation`
- `## Evidence requirements`

### Guardrail test to add

In `tests/test_foreman_skill_lint.py`, add a test:

- for every direct child of `skills/`
- if `run.py` exists
- then `SKILL.md` must also exist

This test exists to stop the coverage gap from reopening.

### Exact command sequence

Run in this order:

```bash
rg --files skills registry
python -m tools.skill_lint
pytest -q tests/test_foreman_skill_lint.py
pytest -q tests/test_skill_excel_intake.py tests/test_skill_column_map.py tests/test_skill_load_db.py tests/test_skill_reconcile.py tests/test_skill_mgmt_report.py
pytest -q
git diff --check
```

### Milestone B acceptance

All of the following must be true:

1. Every direct child of `skills/` with `run.py` also has `SKILL.md`.
2. `python -m tools.skill_lint` reports clean.
3. The new coverage test passes.
4. Full `pytest -q` is green.

### Common failure modes in Milestone B

- Copying structure from existing skills but inventing unregistered tools
- Writing vague workflows that do not match the `run.py` behavior
- Missing one of the 10 required sections
- Changing executable Python code when only documentation was needed

---

## Milestone C
## Add the wrapper skill, de-sprawl leftovers, and close out

### Objective

Finish the unified system with one Claude-facing wrapper for the FOREMAN
pipeline, ignore the external nested repo correctly, mark non-canonical skill
systems explicitly, update the task queue, and archive this plan cleanly.

### Required changes

#### 1. Add wrapper skill

Create:

- `.claude/skills/foreman-pipeline/SKILL.md`

It must:

- use the same frontmatter style as the six routing skills
- include the contract sections required by `tests/test_skill_contracts.py`
- say clearly when to use it:
  - when the task is to process a new spreadsheet end-to-end through FOREMAN
- instruct the agent not to improvise the chain
- instruct the agent to run the ordered path:
  - `SK-001` intake
  - `SK-002` profile/map
  - `SK-003` load
  - `SK-004` reconcile
  - `SK-005` report
- instruct the agent to stop at the first failed gate
- instruct the agent to report the gate message verbatim

Then add this wrapper to `AGENT_SKILL_MAP.md`.

#### 2. Ignore external nested repo

In `.gitignore`, add:

```text
hermes-agent-self-evolution/
```

Do not delete that directory. It is a separate project.

#### 3. Mark external skill systems clearly in `PROJECT_MAP.md`

Add one explicit line that:

- `~/AppData/Local/hermes/skills/` is **EXTERNAL** and not part of this repo's
  canonical skill system

Add one explicit line that:

- `.grok/skills/` is tool-local to Grok and not canonical for this repo

#### 4. Update task queue

Add or update a row in `00_control/task_queue.md` marking the skill-unification
work complete in the repo-control lane.

#### 5. Archive this plan correctly

In the same final change:

- move this file to `archive/03_design/skill_unification_plan.md`
- change frontmatter `status` to `ARCHIVED`
- add an entry to `archive/INDEX.md`

This is required by Doc Law rule 3.

### Exact command sequence

Run in this order:

```bash
rg -n "AppData/Local/hermes/skills|.grok/skills|foreman-pipeline|skill_unification" PROJECT_MAP.md AGENT_SKILL_MAP.md 00_control/task_queue.md archive/INDEX.md .gitignore
pytest -q tests/test_skill_contracts.py tests/test_foreman_skill_lint.py
pytest -q
ruff check .
git diff --check
git status --short
```

### Milestone C acceptance

All of the following must be true:

1. `.claude/skills/` now contains seven skill folders.
2. `foreman-pipeline/SKILL.md` passes the routing skill contract tests.
3. `.gitignore` suppresses `hermes-agent-self-evolution/` from untracked noise.
4. `PROJECT_MAP.md` explicitly marks Hermes machine-level skills and
   `.grok/skills/` as non-canonical.
5. `00_control/task_queue.md` records this migration as done.
6. This plan is archived with an `archive/INDEX.md` entry.
7. `pytest -q` is green.
8. `ruff check .` is green.

---

## Recommended execution prompt for Kimi K2.7 Code

Use this as the **system or top-level execution steer** for the cheap coding
agent:

```text
You are executing one bounded repo migration in G:\AI.

Follow this order before editing:
README.md -> AGENTS.md -> PROJECT_MAP.md -> AGENT_SKILL_MAP.md -> 03_design/skill_unification_plan.md.

Use the plan as the execution contract.

Rules:
- Do not touch files outside the current milestone allowlist.
- Do not invent paths, tool IDs, or file structure.
- Use git mv for moves.
- Preserve existing skill bodies unless the plan explicitly says to rewrite them.
- Quote failing commands or failing gates verbatim.
- If blocked, stop with one exact blocker and one exact next decision.
- Do not browse the web during execution. All required reference text is local.
- Do not set temperature if your runtime exposes it for kimi-k2.7-code.
- Keep outputs concise and structured.

Return after each milestone in this exact shape:
Milestone
Files changed
Commands run
Result
Key evidence
Anything left untouched on purpose
```

## Recommended per-milestone user prompt

Use this as the **execution packet** for each milestone:

```text
Execute Milestone <A|B|C> from 03_design/skill_unification_plan.md.

Only touch the files explicitly allowed for this milestone.
Before editing, inspect git status --short and tell me if the milestone files are already in a partial-migration state.
Then execute the milestone fully, run the required commands, and return only the required checkpoint report.
Do not continue into the next milestone unless this milestone is green or you are blocked.
```

---

## Final definition of done

The migration is complete only when all of the following are true:

1. `.claude/skills/` is the only live routing library for agent-facing skills in
   this repo.
2. `AGENT_SKILL_MAP.md`, `AGENTS.md`, and `PROJECT_MAP.md` all route to
   `.claude/skills/`.
3. `skills/` remains the FOREMAN executable layer and every direct child with
   `run.py` also has `SKILL.md`.
4. `03_design/external_skills_inventory.md` is a REFERENCE document, not a
   routing input.
5. Hermes machine-level skills and `.grok/skills/` are explicitly marked as
   non-canonical for this repo.
6. The task queue records the migration.
7. This plan has been archived properly.
8. `pytest -q` and `ruff check .` are both green.

## Sources used to shape the Kimi steering

Checked on 2026-07-04:

- Moonshot prompt best practices
- Moonshot Kimi K2.7 Code quickstart
- Moonshot thinking-model guidance
- Moonshot model-parameter reference
- Moonshot coding-agent integration guide for Claude Code, Cline, RooCode, and OpenCode

