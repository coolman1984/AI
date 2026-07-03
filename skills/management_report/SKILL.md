---
skill_id: SK-005
version: 1.0.0
risk_level: medium
status: active
---

# Skill: management-report

## Purpose
Produce a signed one-page management summary from validated numbers with full provenance tagging.

## Use this skill when
- Owner asks for a report
- Reconciliation gate (SK-004) is green

## Do NOT use this skill when
- Exploring data ad-hoc (use SK-002/SK-003)
- Reconciliation gate is red (run SK-004 first)

## Inputs
| Input | Required | Format | Example |
|---|---|---|---|
| clean_table | yes | string | `clean_staging_CC_ACTUALS` |
| period | yes | string | `2026-05` |
| lens | no | string | `cost-variance` |

## Outputs
| Output | Location | Format | Consumer |
|---|---|---|---|
| Report Markdown | `reports/<date>_<type>.md` | MD | Owner, stakeholders |
| Report HTML | `reports/<date>_<type>.html` | HTML | Browser |
| Sign-off record | DB `reports` table | row | Audit trail |

## Allowed tools
Only these tool_ids: `T-PVM-001`, `T-DRV-001`, `T-CARD-001`. Anything else is a skill violation.

## Forbidden actions
- Rendering a CLAIMED number (unvalidated)
- Shipping without sign-off
- Including unvalidated data

## Workflow
1. Run variance/PVM decomposition
2. Build manager card with provenance tags
3. Render report to MD + HTML
4. Require owner sign-off before final delivery
5. Write evidence and report record via run_logger

## Validation
| Gate | Pass condition | On fail |
|---|---|---|
| report_generation | Every number has evidence_id; tagged AUDITED | Replace unvalidated number with "OMITTED" + reason |
| final_delivery | Definition-of-done checklist all checked | Name the gap; don't mark done |

## Evidence requirements
- evidence_id per number in the report
- Sign-off record with date and owner name
- Report file path

## Failure recovery
| Failure | Detection | Recovery |
|---|---|---|
| Unvalidated number found | Missing evidence_id | Omit the number with stated reason |
| Variance doesn't reconcile | PVM bridge check | Report the blocked gate; don't ship |

## Tests
- `tests/test_skill_mgmt_report.py` — golden fixture: regenerated report numbers match expected exactly; injected CLAIMED number is refused/omitted.

## Improvement notes
Link lessons that shaped this version: (none yet). Next known weakness: HTML template needs styling.
