# Agent Skill Map

This file is the lightweight routing layer for agents working in this repository.

Its job is not to explain the whole project. Its job is to help the agent load the right depth at the right time without paying the token cost of loading the entire architecture on every task.

Current architecture reference: `03_design/assistant_master_plan.md`. Current execution
plan: `03_design/current_implementation_plan.md`. Current Phase A work cards:
`03_design/phase_a_cards.md`. Historical plans live in `archive/`.

The system design is:

1. **Lightweight agent** — classifies the task and orchestrates the flow.
2. **Central core** — provides shared truth: contracts, naming, trust rules, storage targets, run identity, and evidence expectations.
3. **Specialized skills** — execute narrow classes of work deeply.

If a task needs more than one skill, the agent should compose them in sequence instead of trying to solve everything from one giant prompt.

---

## Read order for an agent

1. `AGENTS.md`
2. `AGENT_SKILL_MAP.md`
3. `AGENT_CORE_CONTRACT.md`
4. `03_design/current_implementation_plan.md` when build order or gates matter
5. `03_design/assistant_master_plan.md` only when architecture context is needed
6. Only the relevant skill file(s)
7. Then the nearest module `AGENTS.md`

Do **not** load every skill by default.

---

## Routing rules

### Use spreadsheet ingestion skill when
- the task starts from Excel, CSV, SAP-style exports, or large tabular files
- the main need is profiling columns, cleaning structure, loading rows, or preserving row-level evidence
- the user asks how to read, normalize, or store operational tables

Load:
`agent_skills/spreadsheet_ingestion.md`

### Use document evidence extraction skill when
- the task starts from PDF, Word, PowerPoint, scans, screenshots, or mixed document bundles
- the main need is evidence extraction, OCR recovery, or citation-bearing passages
- the user asks to inspect document text, attachments, page-level evidence, or scanned content

Load:
`agent_skills/document_evidence_extraction.md`

### Use cost variance analysis skill when
- the task is about variance, cost drivers, budget vs actual, standard vs actual, price/volume/mix, or cost explanation
- the user asks why cost changed, what drove the change, or which factor matters most
- the task depends on trusted numeric decomposition

Load:
`agent_skills/cost_variance_analysis.md`

### Use management reporting skill when
- the task is to produce a manager card, dashboard, presentation, or decision-ready summary
- the task needs a one-page answer with cited facts, not raw analysis
- the task is about shaping output for leadership use

Load:
`agent_skills/management_reporting.md`

### Use audit and trust skill when
- the task needs release gating, independent re-checking, certainty scoring, reconciliation, or human sign-off
- the user asks whether a result is safe to trust or release
- there is any ambiguity around data quality, missing evidence, or number mismatches
- the task involves LLM-originated claims, the claims store, claim quarantine, or the facts/claims wall

Load:
`agent_skills/audit_and_trust.md`

---

## Composition patterns

### Pattern A — file to answer
1. spreadsheet ingestion
2. cost variance analysis
3. audit and trust
4. management reporting

### Pattern B — file to profile only
1. spreadsheet ingestion
2. audit and trust

### Pattern C — document to evidence package
1. document evidence extraction
2. audit and trust
3. management reporting

### Pattern D — existing numbers to management output
1. management reporting
2. audit and trust

### Pattern E — explain a suspicious result
1. cost variance analysis
2. audit and trust
3. management reporting

---

## Central core responsibilities

The following must stay centralized and must **not** be redefined inside each skill:

- source and run identity
- evidence requirements
- naming conventions
- storage targets
- field and entity meaning
- trust and release rules
- row rejection semantics
- confidence language
- where outputs belong

Those shared rules live in:
`AGENT_CORE_CONTRACT.md`

---

## Anti-patterns

Do not do these:

- do not treat `AGENTS.md` as a giant encyclopedia
- do not load every skill for every task
- do not let two skills use different names for the same business concept
- do not let one skill invent output locations or confidence wording
- do not let report-generation skills compute their own numbers
- do not let ingestion skills decide final management conclusions

---

## Minimal decision tree

- If the task begins with a file → start with spreadsheet ingestion or the source-specific skill.
- If the task begins with a document or screenshot → start with document evidence extraction.
- If the task begins with a business question about cost movement → start with cost variance analysis.
- If the task begins with “prepare a report / card / dashboard / deck” → start with management reporting.
- If the task begins with “can we trust this / release this / approve this?” → start with audit and trust.

When uncertain, prefer loading one skill plus the central contract, not all skills.
