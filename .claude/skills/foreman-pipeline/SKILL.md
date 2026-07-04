---
name: foreman-pipeline
description: Use whenever the task is to process a new factory spreadsheet end-to-end through the FOREMAN governance pipeline (intake → profile/map → load → reconcile → report) and the agent must not improvise the chain or skip any gate.
---

# Skill — FOREMAN Pipeline

## Mission
Drive a new spreadsheet through the full FOREMAN governance chain without improvising steps or skipping gates.

## Use this skill when
- the task starts from a new Excel/CSV/SAP export that must flow through FOREMAN
- the user asks for end-to-end processing from file to signed report
- the work needs the ordered SK-001 → SK-002 → SK-003 → SK-004 → SK-005 chain

## Do not use this skill for
- one-off ingestion only (use spreadsheet-ingestion)
- standalone variance questions on already-loaded data (use cost-variance-analysis)
- document-heavy tasks (use document-evidence-extraction)

## Token budget
- target: <= 1,500 tokens for pipeline status and gate messages
- hard cap: report only the current gate, the run_id, and the verbatim message

## Input contract
- inbox file path
- period or reporting context
- optional expected control totals

## Output contract
- run_id and contract path
- current pipeline status
- verbatim gate message if a gate fails
- next required action

## Invariants
- run the chain in the exact order SK-001, SK-002, SK-003, SK-004, SK-005
- stop at the first failed gate
- never skip a gate because a downstream step "looks fine"
- preserve all evidence and rejects at every step

## Raw data ban
- never dump full spreadsheet rows, raw OCR, or unbounded SQL result sets into agent context
- return gate status, counts, and reject summaries only

## Inputs expected
- `inbox_path`: path to the new spreadsheet in `datasets/inbox/`
- `period`: period string such as `2026-05`
- optional `expected_total` for reconciliation

## Outputs expected
- `run_id`: FOREMAN run identifier
- `contract_path`: path to the run contract
- `status`: done | blocked | failed
- `current_gate`: the gate that is active or failed
- `message`: verbatim gate output
- `next_step`: exactly what the agent or owner must do

## Shared rules from the core contract
- preserve `run_id`
- never overwrite raw input
- record rejections explicitly
- low confidence → review queue
- no human sign-off means no final release

## Standard workflow
1. Confirm the inbox file exists and is readable
2. Dispatch `tools/run_foreman.py` with goal `Period close: {period}` or equivalent
3. Wait for SK-001 fingerprint/intake to complete
4. Wait for SK-002 column profile and mapping proposal
5. Wait for SK-003 load and reject-rate gate
6. Wait for SK-004 reconciliation gate
7. Wait for SK-005 report generation and sign-off placeholder
8. If any gate returns non-success, stop and report its message verbatim

## Key checks
- file is registered and fingerprinted
- conservation holds (rows_in == kept + rejected)
- mapping is confirmed before loading
- reject rate is below threshold
- reconciliation matches within tolerance
- every report number has evidence

## Never do
- never reorder the chain
- never skip a gate
- never paraphrase a failure message
- never compute numbers in the skill layer
- never release a report without sign-off

## Typical downstream handoff
- `.claude/skills/audit-and-trust/SKILL.md` if a gate fails or trust is questioned
- `.claude/skills/management-reporting/SKILL.md` if the report needs shaping for a specific audience

## Existing repo anchors
- `tools/run_foreman.py`
- `registry/skills.yaml`
- `skills/excel_intake/SKILL.md`
- `skills/column_profile_and_map/SKILL.md`
- `skills/load_to_database/SKILL.md`
- `skills/reconcile_and_validate/SKILL.md`
- `skills/management_report/SKILL.md`
- `tests/test_foreman_end_to_end.py`

## Definition of done
Done means:
- the file ran through the full chain or stopped at the first failed gate
- the gate message is reported verbatim
- the run_id and contract path are known
- the next step is unambiguous
