---
skill_id: SK-008
version: 1.0.0
risk_level: medium
status: active
---

# Skill: inventory-exception-scan

## Purpose
Apply confirmed business-rule notes to an inventory snapshot and surface exceptions for human review.

## Use this skill when
- An inventory table is loaded and exceptions need to be flagged
- Business rules exist in vault notes that should be run against current data

## Do NOT use this skill when
- The inventory table is not yet loaded (run SK-003 first)
- No confirmed rules exist (define rules first)

## Inputs
| Input | Required | Format | Example |
|---|---|---|---|
| inventory_table | yes | string | `clean_inventory_snapshot` |
| rules | no | list[dict] | `[{"column": "quantity", "condition": "< 0", "label": "Negative stock"}]` |
| duckdb_con | no | DuckDB connection | existing connection |

## Outputs
| Output | Location | Format | Consumer |
|---|---|---|---|
| Exception list | returned dict | dict | Owner, review queue |
| Rule counts | returned dict | dict | Reporting layer |

## Allowed tools
No direct tool manifest references; delegates to SQL queries against the analytical DuckDB store.

## Forbidden actions
- Auto-correcting exceptions without owner approval
- Running destructive updates against inventory data
- Silently dropping rules that fail to parse

## Workflow
1. Confirm `inventory_table` exists
2. For each rule, query rows matching `column condition`
3. Capture count and severity (high if >10 rows)
4. Return exceptions and totals

## Validation
| Gate | Pass condition | On fail |
|---|---|---|
| table_exists | Inventory table is present | Return failed status |
| rule_parse | Each rule has `column`, `condition`, `label` | Report malformed rule |

## Evidence requirements
- Inventory table name
- Rules applied with column/condition/label
- Count per rule and severity

## Failure recovery
| Failure | Detection | Recovery |
|---|---|---|
| Malformed rule | Missing key | Report rule error; continue with valid rules |
| Table not found | DuckDB error | Return failed status |

## Known edge cases
- Default rule flags negative quantities
- Limit 100 rows per rule to keep response bounded

## Tests
- `tests/test_phase4_analytics.py` exercises inventory exception scanning.

## Improvement notes
Link lessons that shaped this version: (none yet).
