---
skill_id: SK-006
version: 1.0.0
risk_level: medium
status: active
---

# Skill: period-close-pack

## Purpose
Chain the full period-close workflow — intake, profile/map, load, reconcile, and report — in one governed run.

## Use this skill when
- A monthly or periodic close needs to run end-to-end from a new inbox file
- The owner wants one run contract covering the whole close sequence

## Do NOT use this skill when
- Only one step is needed (use the individual SK-001–SK-005 skills)
- The file is not yet placed in `datasets/inbox/`

## Inputs
| Input | Required | Format | Example |
|---|---|---|---|
| inbox_path | yes | string | `datasets/inbox/CC_ACTUALS_MAY.xlsx` |
| period | yes | string | `2026-05` |
| db_registry | no | string/Path | path to FOREMAN SQLite registry |

## Outputs
| Output | Location | Format | Consumer |
|---|---|---|---|
| Run summary | returned dict | dict | Orchestrator, owner |
| Contract | `runs/<id>/contract.md` | MD | Audit trail |
| Reports / rejects / evidence | `runs/<id>/`, `reports/` | files | Downstream review |

## Allowed tools
No direct tool manifest references; delegates to the `tools/run_foreman.py` orchestrator, which dispatches the SK-001→SK-005 chain.

## Forbidden actions
- Editing the source file in `datasets/inbox/`
- Proceeding past a failed gate without surfacing the reason
- Skipping reconciliation for the period report

## Workflow
1. Draft a run contract for the period close
2. Dispatch `tools/run_foreman.py` with goal `Period close: {period}`
3. The orchestrator chains SK-001 → SK-002 → SK-003 → SK-004 → SK-005
4. Stop at the first failed gate and surface the gate message verbatim
5. Return the run summary and contract path

## Validation
| Gate | Pass condition | On fail |
|---|---|---|
| chain_complete | All SK-001→SK-005 steps finish | Stop; report which gate failed |
| reconciliation | SK-004 reconciliation is within tolerance | Stop; surface delta and drill-down |
| sign_off | Report is signed before final delivery | Route to approvals |

## Evidence requirements
- Run contract path and run_id
- Fingerprint and sheet locators from SK-001
- Mapping confirmation from SK-002
- Clean/reject counts from SK-003
- Reconciliation statement from SK-004
- Sign-off record from SK-005

## Failure recovery
| Failure | Detection | Recovery |
|---|---|---|
| Any gate fails | Non-success status from orchestrator | Stop; return exact gate message and run_id |

## Known edge cases
- Multi-sheet workbook: handled by SK-001
- Reject rate above threshold: handled by SK-003

## Tests
- `tests/test_foreman_end_to_end.py` exercises the chained close path.

## Improvement notes
Link lessons that shaped this version: (none yet).
