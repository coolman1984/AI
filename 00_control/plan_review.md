# Quarterly Plan Review Checklist

> Recurring ritual (F.10). Review the approved plan against reality each quarter.
> Record owner decisions in `00_control/decisions.md` when architecture or build order changes.

## Review date

- **Quarter:** Q3 2026
- **Reviewer:** Owner + Evaluator
- **Last review:** (initial checklist — 2026-07-03)

---

## 1. Success measures

- [ ] Golden eval set exists and passes (`eval/runner.py`, `tests/test_golden_eval.py`)
- [ ] Tier 1 content cannot reach external LLM (privacy gate green)
- [ ] Executive outputs require named human sign-off
- [ ] Knowledge artifacts survive `.brain` rebuilds
- [ ] Backup/restore drill completed in the last quarter

## 2. Phase gate status

| Phase | Gate | Status | Evidence |
|---|---|---|---|
| A0 Safety rails | pytest privacy/claims/LLM chokepoint | Green | `tests/test_privacy.py` etc. |
| B HQ deck path | B.1–B.10 cards | Green | phase B tests |
| C Knowledge registry | C.1–C.8 | Green | registry/search tests |
| D Executive outputs | D.1–D.6 | Green | `tests/test_decision_brief.py` through `tests/test_feedback_loop.py` |
| E Real data | E.2–E.4 green; E.1 blocked | Waiting on owner export (P2.2) | `tests/test_ingestion_spine.py`, `tests/test_query_readiness.py` |
| F Hardening | F.1–F.10 | Green | `tests/test_golden_eval.py` through `tests/test_session_state.py` |
| T12 Self-evolution | Golden gate | Green (gated) | `tests/test_gated_evolution.py` |

## 3. Risks and drift

- [ ] Metric ambiguity (R2) — still tracked in `00_control/risks.md`
- [ ] Real SAP-scale data untested (R7) — P2.2 blocked on owner export
- [ ] Prompt injection defenses still exercised in CI
- [ ] No silent external AI fallback for Tier 1
- [ ] Graph/vector backends remain behind repo-owned contracts

## 4. Owner decisions this quarter

- [ ] Record any changed architecture decision in `00_control/decisions.md`
- [ ] Update `03_design/current_implementation_plan.md` only when build order changes
- [ ] Update `AGENT_SKILL_MAP.md` when routing changes

## 5. Next-quarter changes

- [ ] Confirm next execution slice from `00_control/task_queue.md`
- [x] T12 self-evolution gate implemented; owner must still agree on "better" before live optimization
- [ ] Schedule backup/restore drill if not run this quarter
- [ ] Plan review for AI landscape changes (models, MCP SDK, OSS adapters)

---

## Sign-off

| Role | Name | Date | Notes |
|---|---|---|---|
| Owner | | | |
| Evaluator | | | |