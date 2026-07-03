---
skill_id: SK-001
version: 1.0.0
risk_level: low
status: active
---

# Skill: excel-intake

## Purpose
Register, fingerprint, and safely stage a spreadsheet into the ingestion spine with quarantine and conservation checks.

## Use this skill when
- A new Excel/CSV file arrives in `datasets/inbox/` for processing
- An SAP export or factory data dump needs trusted ingestion

## Do NOT use this skill when
- The file is a PDF or scan (use document skills instead)
- Data is already registered this period (use query skills instead)

## Inputs
| Input | Required | Format | Example |
|---|---|---|---|
| file_path | yes | string | `datasets/inbox/CC_ACTUALS_MAY.xlsx` |
| expected_row_count | no | integer | 41207 |
| expected_total | no | float | 4700000.0 |
| period | no | string | "2026-05" |

## Outputs
| Output | Location | Format | Consumer |
|---|---|---|---|
| Staged DuckDB table | DuckDB staging | table | SK-002 column-profile-and-map |
| Reject file | `runs/<id>/rejects/` | CSV | Owner review |
| Run summary | returned dict | dict | Orchestrator |

## Allowed tools
Only these tool_ids: `T-FP-001`, `T-ING-001`, `T-PROF-001`. Anything else is a skill violation — stop and report.

## Forbidden actions
- Editing the source file in `datasets/inbox/`
- Sending file content to any cloud model (Tier-1 default)
- Proceeding past a failed conservation check
- Reimplementing spreadsheet parsing (use the existing engine)

## Workflow
1. Register and fingerprint the file — tool: `T-FP-001` — evidence written: source_fingerprint, registered_path
2. List sheets / inspect structure — tool: `T-ING-001` (`list_excel_sheets`) — evidence written: sheet names
3. Ingest each sheet to DuckDB staging — tool: `T-ING-001` (`ingest_spreadsheet`) — evidence written: rows_in/kept/rejected
4. Conservation gate — rows_in == kept + rejected — on fail: stop and surface the mismatch
5. Profile staged data — tool: `T-PROF-001` — evidence written: column profile
6. Write run summary — finish_run via run_logger

## Validation
| Gate | Pass condition | On fail |
|---|---|---|
| fingerprint | File is registered | Stop; owner must place file in inbox |
| conservation | rows_in == kept + rejected | Stop; surface reject file for review |
| profile_complete | Columns have dtypes | Warn; continue with defaults |

## Evidence requirements
- Source fingerprint (sha256, original path, registered path)
- Sheet names and row counts per sheet
- rows_in / kept / rejected with reject reasons
- Column profile with dtypes and null percentages

## Failure recovery
| Failure | Detection | Recovery |
|---|---|---|
| File locked by Excel | PermissionError on open | Catch and return: "Close the file in Excel and retry" |
| Empty sheet | Zero rows ingested | Report as warning, continue with next sheet |
| Unsupported format | Extension not in allowed list | Return: "Use document skills for this file type" |

## Known edge cases
- Multi-sheet workbook: each sheet is ingested independently
- File locked/open in Excel: caught as PermissionError with plain guidance
- Password-protected file: engine raises; caught and reported

## Examples
### Example 1: SAP export ingestion
Input: `CC_ACTUALS_MAY.xlsx` (3 sheets, 41k rows) → register + fingerprint → ingest each sheet → conservation holds → staged to DuckDB → evidence written → summary returned.

## Tests
- `tests/test_skill_excel_intake.py` — fixture workbook: one total row, one duplicate, one junk amount → exactly those quarantined; conservation holds; evidence + run rows written.

## Improvement notes
Link lessons that shaped this version: (none yet). Next known weakness: handle password-protected files more gracefully.
