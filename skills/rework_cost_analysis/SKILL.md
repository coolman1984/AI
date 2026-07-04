---
skill_id: SK-009
version: 1.0.0
risk_level: low
status: active
---

# Skill: rework-cost-analysis

## Purpose
Analyze rework costs by cause code and identify repeat offenders from a validated rework table.

## Use this skill when
- A rework table exists and costs need to be grouped by cause
- The owner wants to know which cause codes drive the most rework cost

## Do NOT use this skill when
- The rework table is not yet cleaned (run SK-003 first)
- The table lacks a `cause_code` column

## Inputs
| Input | Required | Format | Example |
|---|---|---|---|
| rework_table | yes | string | `clean_rework_actuals` |
| duckdb_con | no | DuckDB connection | existing connection |

## Outputs
| Output | Location | Format | Consumer |
|---|---|---|---|
| Cost by cause | returned dict | array | Owner, reporting layer |
| Total rework cost | returned dict | float | Reporting layer |

## Allowed tools
No direct tool manifest references; delegates to a SQL `GROUP BY cause_code` query against the analytical DuckDB store.

## Forbidden actions
- Reimplementing aggregation logic outside SQL
- Modifying the rework table
- Hiding cause codes with zero cost

## Workflow
1. Confirm `rework_table` exists
2. Run SQL: `SELECT cause_code, COUNT(*), SUM(amount) FROM {rework_table} GROUP BY cause_code`
3. Order by total cost descending
4. Return by-cause breakdown and total

## Validation
| Gate | Pass condition | On fail |
|---|---|---|
| table_exists | Rework table is present | Return failed status |
| cause_code_present | Table has `cause_code` column | Return failed status |

## Evidence requirements
- Rework table name
- Count and total cost per cause_code
- Grand total rework cost

## Failure recovery
| Failure | Detection | Recovery |
|---|---|---|
| Table not found | DuckDB error | Return failed status |
| Missing cause_code | SQL error | Return failed status |

## Known edge cases
- NULL cause_code appears as its own group
- Negative amounts reduce the total

## Tests
- `tests/test_phase4_analytics.py` exercises rework cost analysis.

## Improvement notes
Link lessons that shaped this version: (none yet).
