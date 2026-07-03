---
skill_id: SK-002
version: 1.0.0
risk_level: low
status: active
---

# Skill: column-profile-and-map

## Purpose
Profile columns from a staged table and produce an owner-confirmable mapping to canonical names with historical prior matching.

## Use this skill when
- A newly staged table doesn't have a confirmed column mapping yet
- A dataset with an unknown column layout needs type inference and profiling

## Do NOT use this skill when
- Mapping already confirmed this period (reuse existing)
- Data is not yet staged (run SK-001 first)

## Inputs
| Input | Required | Format | Example |
|---|---|---|---|
| table_name | yes | string | `staging_CC_ACTUALS` |
| fingerprint_id | no | string | `fp_abc123` |
| prior_mapping_ref | no | string | `mapping-cc-actuals` |

## Outputs
| Output | Location | Format | Consumer |
|---|---|---|---|
| Column profile report | returned dict | dict | Owner, SK-003 |
| Column mapping proposal | returned dict | dict | Owner confirmation |

## Allowed tools
Only these tool_ids: `T-PROF-001`. Anything else is a skill violation — stop and report.

## Forbidden actions
- Auto-confirming a mapping without owner sign-off
- Editing the source file
- Writing mapping directly to DuckDB without confirmation

## Workflow
1. Read staged table column names from DuckDB — profile columns via T-PROF-001
2. Generate profile: column name, inferred dtype, null %, sample values, suspected key
3. If prior mapping exists for similar dataset, pre-fill from it
4. Return proposal with mapping table: source column → canonical name → dtype → confidence
5. Owner reviews and confirms → mapping is saved

## Validation
| Gate | Pass condition | On fail |
|---|---|---|
| column_mapping | Every required canonical column mapped; no source column mapped twice | Return proposal with gaps highlighted |

## Evidence requirements
- Profile stats per column (name, dtype, null %, samples)
- Mapping confirmer name and timestamp
- Prior mapping reference if used

## Failure recovery
| Failure | Detection | Recovery |
|---|---|---|
| Table not found | DuckDB error | Return: "Run SK-001 first to stage the data" |
| No required canonical columns mapped | Gate fails | Surface missing columns to owner |

## Known edge cases
- 272-column SAP export: profile in batches, propose only columns the target lens needs
- Duplicate header names: warn and deduplicate with index suffix
- Header not on row 1: engine handles this; profile reports actual header row

## Examples
### Example 1: Prior mapping reuse
File `CC_ACTUALS_MAY.xlsx` has same columns as April → saved mapping auto-proposed → owner confirms → mapping saved.

## Tests
- `tests/test_skill_column_map.py` — fixture with renamed columns → proposal matches saved mapping from prior fixture.

## Improvement notes
Link lessons that shaped this version: (none yet). Next known weakness: confidence scoring for fuzzy column matching.
