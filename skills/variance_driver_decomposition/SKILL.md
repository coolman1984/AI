---
skill_id: SK-007
version: 1.0.0
risk_level: low
status: active
---

# Skill: variance-driver-decomposition

## Purpose
Wrap the trusted price/volume/mix variance decomposition engine with plain-English narrative output.

## Use this skill when
- A clean actuals table exists and drivers are needed by dimension
- The owner asks why cost changed at a granular level

## Do NOT use this skill when
- Data is not yet cleaned (run SK-003 first)
- Only a top-line variance is needed (use `T-PVM-001` directly)

## Inputs
| Input | Required | Format | Example |
|---|---|---|---|
| clean_table | yes | string | `clean_staging_CC_ACTUALS` |
| dimension | no | string | `cost_center` |
| duckdb_con | no | DuckDB connection | existing connection |

## Outputs
| Output | Location | Format | Consumer |
|---|---|---|---|
| Driver decomposition | returned dict | dict | SK-005, owner |
| Dimension | returned dict | string | Report layer |

## Allowed tools
No direct tool manifest references; delegates to `engines.data.drivers::run_variance_decomposition`.

## Forbidden actions
- Reimplementing the price/volume/mix math
- Running on uncleaned staging tables
- Silently swallowing decomposition errors

## Workflow
1. Confirm `clean_table` exists in DuckDB
2. Call `engines.data.drivers::run_variance_decomposition(clean_table, dimension)`
3. Return drivers with dimension context and status

## Validation
| Gate | Pass condition | On fail |
|---|---|---|
| decomposition_reconciles | PVM parts sum to total bridge | Report failed status and error |
| clean_input | Table is a cleaned analytical table | Return "Run SK-003 first" |

## Evidence requirements
- Source clean_table name
- Dimension used
- Driver values and reconciliation status

## Failure recovery
| Failure | Detection | Recovery |
|---|---|---|
| Table not found | DuckDB error | Return failed status with error |
| Decomposition does not reconcile | Engine check | Return failed status; do not fabricate |

## Known edge cases
- Default dimension is `cost_center`; override for other lenses
- Empty table returns empty drivers

## Tests
- `tests/test_phase4_analytics.py` exercises variance driver decomposition.

## Improvement notes
Link lessons that shaped this version: (none yet).
