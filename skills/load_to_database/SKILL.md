---
skill_id: SK-003
version: 1.0.0
risk_level: low
status: active
---

# Skill: load-to-database

## Purpose
Apply a confirmed column mapping, clean data through the canonical parser, and load into the analytical store with quarantine and conservation checks.

## Use this skill when
- A confirmed mapping exists for a staged table (run SK-002 first)
- Clean, validated data needs to enter the analytical DuckDB store

## Do NOT use this skill when
- No confirmed mapping exists (run SK-002 first)
- Data is in a PDF or document (use document skills)

## Inputs
| Input | Required | Format | Example |
|---|---|---|---|
| table_name | yes | string | `staging_CC_ACTUALS` |
| mapping_id | yes | string/JSON | confirmed mapping from SK-002 |
| qty_col | no | string | `quantity` |
| is_standards | no | bool | false |

## Outputs
| Output | Location | Format | Consumer |
|---|---|---|---|
| Clean DuckDB table | DuckDB analytical store | table | SK-004, SK-005 |
| Reject file | `runs/<id>/rejects/` | CSV | Owner review |
| Load summary | returned dict | dict | Orchestrator |

## Allowed tools
Only these tool_ids: `T-CLEAN-ACT`, `T-CLEAN-STD`. Anything else is a skill violation — stop and report.

## Forbidden actions
- Reimplementing number parsing (use the canonical engine)
- Silently proceeding past a reject-rate > 5% threshold
- Modifying source files

## Workflow
1. Apply column mapping to rename staged columns to canonical names
2. Run clean_actuals or clean_standards (canonical parser, dup detection)
3. Write rejects to `runs/<id>/rejects/`
4. Conservation gate: loaded count == cleaned count
5. Duplicate gate: dup% below 5% or stop and show samples
6. Write load summary via run_logger

## Validation
| Gate | Pass condition | On fail |
|---|---|---|
| numeric_cleaning | All numeric cells parse via canonical parser | Quarantine rows; report reject % |
| date_cleaning | All dates parse via deterministic formats | Flag ambiguous dates for owner |
| db_loading | Loaded row count == cleaned count | Rollback; investigate |
| duplicate_detection | Dup% < 5% threshold | Stop; show sample dupes to owner |

## Evidence requirements
- Counts at every stage: staged, cleaned, rejected
- Reject reasons breakdown
- Dup key used and dup count
- Clean table name in analytical store

## Failure recovery
| Failure | Detection | Recovery |
|---|---|---|
| Reject rate > 5% | Count check | Stop; surface samples to owner |
| Table not found | DuckDB error | Return: "Run SK-001 + SK-002 first" |
| No mapping provided | Missing input | Return: "Provide confirmed mapping from SK-002" |

## Known edge cases
- European/negative formats: parser handles `(1,234.56)` and `1234.56-`
- Reject % above threshold: stop and show samples, do NOT silently proceed
- Quantity column optional: only validated if `qty_col` is provided

## Examples
### Example 1: Standard clean load
Staged `staging_CC_ACTUALS` with confirmed mapping → clean_actuals → 40,988 kept, 219 rejected (0.53%) → loaded → evidence written.

## Tests
- `tests/test_skill_load_db.py` — nasty fixture → correct quarantine, conservation, reject-rate gate fires above threshold.

## Improvement notes
Link lessons that shaped this version: (none yet). Next known weakness: handle ambiguous date formats more gracefully.
