---
skill_id: SK-004
version: 1.0.0
risk_level: low
status: active
---

# Skill: reconcile-and-validate

## Purpose
Prove loaded data matches control totals before any analysis or reporting.

## Use this skill when
- After every data load (SK-003)
- Before every report (SK-005)

## Do NOT use this skill when
- Exploring data without validation needs
- Data is not yet loaded (run SK-001→SK-003 first)

## Inputs
| Input | Required | Format | Example |
|---|---|---|---|
| clean_table | yes | string | `clean_staging_CC_ACTUALS` |
| control_total | yes | float | 4700000.0 |
| control_total_source | yes | string | `SAP total row` / `owner stated` |
| tolerance | no | float | 0.01 |
| dimension | no | string | `cost_center` |

## Outputs
| Output | Location | Format | Consumer |
|---|---|---|---|
| Reconciliation statement | returned dict | dict | Owner, SK-005 |
| By-dimension drill-down | returned dict | dict | Owner |

## Allowed tools
Only these tool_ids: `T-AUDIT-001`. Anything else is a skill violation — stop and report.

## Forbidden actions
- Fabricating a control total
- Skipping reconciliation for a report
- Silently accepting a delta > tolerance

## Workflow
1. Compute SUM(amount) via SQL from the clean table
2. Compare to control total within tolerance (default 0.01)
3. If delta > tolerance: drill down by dimension, surface where the delta sits
4. Apply materiality escalation (>2% rejected value)
5. Write validation result via run_logger

## Validation
| Gate | Pass condition | On fail |
|---|---|---|
| reconciliation | ABS(actual - expected) <= tolerance | Drill down by dimension; surface delta location |

## Evidence requirements
- Expected total and source
- Actual total from SQL sum
- Delta and tolerance used
- By-dimension drill-down if gate failed

## Failure recovery
| Failure | Detection | Recovery |
|---|---|---|
| Control total includes quarantined rows | Compare against detail-only recomputation | Say so in evidence; reconcile against recomputed total |
| Table not found | DuckDB error | Return: "Run SK-001→SK-003 first" |

## Known edge cases
- Control total itself includes quarantined subtotal rows → reconcile against detail-only recomputation and note it in evidence
- Off-by-one: surface dimension drilling to pinpoint the delta

## Tests
- `tests/test_skill_reconcile.py` — matching fixture passes; off-by-one fixture fails gate WITH by-dimension drill-down.

## Improvement notes
Link lessons that shaped this version: (none yet). Next known weakness: automatic control total discovery from vault business-rule notes.
