# Skill — Spreadsheet Ingestion

## Mission

Read tabular operational sources safely, profile them, normalize them, and land them in the trusted local data path without destroying row-level traceability.

## Use this skill when
- the task starts from Excel or CSV
- the source is a SAP-style export or other wide operational table
- the user asks to ingest, clean, profile, or store tabular data
- the workflow needs row rejection and conservation checks

## Do not use this skill for
- final business explanation of cost movement
- manager-facing report writing
- release approval or sign-off decisions

## Inputs expected
- file path
- source type
- ingestion goal
- target table or artifact expectation
- any known sheet names or relevant ranges if already known

## Outputs expected
- profiled columns and structure
- ingestion run record
- loaded row count
- rejected row count with reasons
- durable storage target
- issues list for downstream skills

## Shared rules from the core contract
- preserve `run_id`
- never overwrite raw input
- record rejections explicitly
- do not silently coerce suspicious values into trusted numbers
- keep row-level evidence where possible

## Standard workflow
1. identify the source and sub-source
2. inspect shape: sheets, columns, row count, suspicious totals, duplicates
3. normalize headings and obvious structural noise
4. parse values conservatively
5. reject rows that fail the trust rules with explicit reason
6. load accepted rows into the trusted local path
7. produce a short profile for downstream analysis

## Key checks
- embedded total/subtotal rows
- duplicated rows
- mixed locale amounts
- missing keys
- broken dates
- impossible signs or empty columns
- schema drift versus expected exports

## Never do
- never compute management conclusions here
- never summarize a business cause from ingestion alone
- never hide row loss
- never change core naming casually
- never let this skill become a report writer

## Typical downstream handoff
Usually hands off to:
- `agent_skills/cost_variance_analysis.md`
- or `agent_skills/audit_and_trust.md`

## Existing repo anchors
- `engines/data/AGENTS.md`
- `engines/data/ingest.py`
- `engines/data/clean.py`
- `tests/test_data_pipeline.py`
- `tests/test_ingestion_spine.py`

## Definition of done
Done means:
- the source has a tracked run
- accepted and rejected rows are accounted for
- storage target is known
- downstream analysis can start without guessing what happened during ingest