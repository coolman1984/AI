---
skill_id: SK-011
version: 1.0.0
risk_level: medium
status: active
---

# Skill: decision-brief

## Purpose
Produce an evidence-backed decision brief from validated data, with every projection labeled and evidence-linked.

## Use this skill when
- The owner needs a one-page decision brief on a named topic
- Validated data exists to support option analysis

## Do NOT use this skill when
- Data is not yet validated (run SK-004 first)
- The request is purely narrative with no data grounding

## Inputs
| Input | Required | Format | Example |
|---|---|---|---|
| topic | yes | string | `Should we increase safety stock?` |
| clean_table | no | string | `clean_inventory_snapshot` |
| options | no | list[dict] | `[{"name": "...", "description": "...", "impact": "..."}]` |
| duckdb_con | no | DuckDB connection | existing connection |

## Outputs
| Output | Location | Format | Consumer |
|---|---|---|---|
| Brief | returned dict | dict | Owner, reporting layer |
| Evidence list | returned dict | array | Audit trail |
| Recommendation | returned dict | string | Owner |

## Allowed tools
No direct tool manifest references; delegates to SQL summaries against the analytical DuckDB store and the `serving/decision_brief.py` engine.

## Forbidden actions
- Inventing evidence when no data is available
- Presenting unlabeled projections as facts
- Shipping without stating data limitations

## Workflow
1. Confirm topic and optional clean_table
2. If table provided, gather row count and total amount as evidence
3. Build option analysis with evidence-linked projections
4. Return brief, evidence, and recommendation

## Validation
| Gate | Pass condition | On fail |
|---|---|---|
| evidence_or_data | Either a clean_table is provided or options are explicit | Return "Insufficient data" |
| projection_labeled | Every option carries an evidence-linked projection label | Flag missing evidence |

## Evidence requirements
- Topic and options considered
- Evidence sources (table name, row count, total)
- Recommendation and governance statement

## Failure recovery
| Failure | Detection | Recovery |
|---|---|---|
| Table query fails | DuckDB error | Record error in evidence; continue with reduced data |
| No data and no options | Input check | Return "Insufficient data for recommendation" |

## Known edge cases
- Default options are provided if none supplied
- Projections are labeled even when evidence is partial

## Tests
- `tests/test_phase4_analytics.py` exercises decision brief generation.

## Improvement notes
Link lessons that shaped this version: (none yet).
