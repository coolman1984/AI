---
name: spreadsheet-ingestion
description: Use whenever the task starts from Excel, CSV, SAP exports, or other wide operational tables and the job is to ingest, clean, profile, or store tabular data with row rejection and conservation checks, even if the user does not say the word ingest.
---

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

## Token budget
- target: <= 1,500 tokens for ingestion profile summaries
- hard cap: sample rows only; never full export dumps

## Input contract
- file path and source type
- ingestion goal and target table expectation
- known sheet names or ranges when available

## Output contract
- column profile, row counts, reject reasons
- durable storage target and issues list for downstream skills

## Invariants
- preserve run_id and raw input immutability
- record rejections explicitly
- profile values are evidence, not management numbers

## Raw data ban
- never dump full SAP-scale exports or raw row dumps into agent context
- return profiles, counts, and sample reject rows only

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
- `source_sheet` when the workbook has multiple tabs
- typed values in `extracted_fields` when `infer_types=true`
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
5. infer per-column types and keep raw text alongside typed numeric/date values
6. reject rows that fail the trust rules with explicit reason
7. load accepted rows into the trusted local path
8. produce a short profile for downstream analysis

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
- `.claude/skills/cost-variance-analysis/SKILL.md`
- or `.claude/skills/audit-and-trust/SKILL.md`

## Existing repo anchors
- `engines/data/AGENTS.md`
- `engines/data/ingest.py`
- `engines/data/types.py`
- `engines/data/clean.py`
- `mcp_server/server.py` (`ingest_spreadsheet`)
- `tests/test_data_pipeline.py`
- `tests/test_ingestion_spine.py`

## Definition of done
Done means:
- the source has a tracked run
- accepted and rejected rows are accounted for
- storage target is known
- downstream analysis can start without guessing what happened during ingest
