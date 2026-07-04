---
skill_id: SK-010
version: 1.0.0
risk_level: low
status: active
---

# Skill: cross-period-comparison

## Purpose
Compare a metric across multiple periods and flag significant drift.

## Use this skill when
- The same clean table exists for multiple periods
- The owner wants period-over-period trend detection

## Do NOT use this skill when
- Period tables are not yet loaded (run SK-003 first)
- Only one period is available

## Inputs
| Input | Required | Format | Example |
|---|---|---|---|
| clean_table_template | yes | string | `clean_actuals_{period}` |
| periods | yes | list[string] | `["2026-03", "2026-04", "2026-05"]` |
| duckdb_con | no | DuckDB connection | existing connection |

## Outputs
| Output | Location | Format | Consumer |
|---|---|---|---|
| Period totals | returned dict | array | Owner, reporting layer |
| Drift flags | returned dict | array | Owner |

## Allowed tools
No direct tool manifest references; delegates to SQL `SUM(amount)` queries against the analytical DuckDB store.

## Forbidden actions
- Inventing totals for missing periods
- Hiding periods where the table does not exist
- Silently ignoring drift above the threshold

## Workflow
1. For each period, substitute `{period}` into `clean_table_template`
2. Query `SUM(amount)` from the table
3. Record total or error if table missing
4. Compare consecutive periods; flag drift >10%
5. Return period totals and drift list

## Validation
| Gate | Pass condition | On fail |
|---|---|---|
| at_least_two_periods | `len(periods) >= 2` | Return failed status |
| table_resolves | At least one period table exists | Return failed status |

## Evidence requirements
- Template and period list
- Total per period (or error)
- Drift deltas and percentages flagged

## Failure recovery
| Failure | Detection | Recovery |
|---|---|---|
| Table missing for a period | DuckDB error | Record `total: null` with error; continue |
| Fewer than 2 periods | Input check | Return failed status |

## Known edge cases
- Missing period tables are reported as null totals, not errors
- Zero-base period causes pct_change to report 0

## Tests
- `tests/test_phase4_analytics.py` exercises cross-period comparison.

## Improvement notes
Link lessons that shaped this version: (none yet).
