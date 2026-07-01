# Brief Contract

## Objective
Work inside the local clone of the AI repository using Mohamed's development loop without duplicating the repo's existing governance system.

## Project path
`/root/projects/AI`

## Durable truth
The governed source of truth already lives in:

- `00_control/*`
- `MASTER_PLAN.md`
- `AGENTS.md`
- `CODEX_PLAN.md`

This `.agent-loop` folder is a lightweight execution bridge, not a replacement.

## Current development target
Execute `T8b` next: surface the price, volume, and mix drivers on the manager card and dashboard.

## Acceptance criteria for setup
1. Repository exists locally at the stated path.
2. Git remote points to `https://github.com/coolman1984/AI.git`.
3. The repo's existing governance files remain intact.
4. `.agent-loop` exists with clear restart pointers.
5. Current next action is aligned across lightweight and governed state.

## Non-goals
- Do not rebuild project governance from scratch.
- Do not create extra duplicate operating systems.
- Do not start feature implementation yet.

## Verification
- `git status -sb`
- `git remote -v`
- file existence checks for `.agent-loop/*` and `00_control/*`
