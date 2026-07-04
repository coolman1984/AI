# Agent Skill Map

This file is the lightweight routing layer for agents working in this repository.

Its job is not to explain the whole project. Its job is to help the agent load the right depth at the right time without paying the token cost of loading the entire architecture on every task.

Current architecture reference: `03_design/assistant_master_plan.md` (REFERENCE).
Active FOREMAN build: `03_design/foreman_build_plan.md` (ACTIVE-PLAN). Live task status:
`00_control/task_queue.md`. Historical plans live in `archive/`.

The system design is:

1. **Lightweight agent** — classifies the task and orchestrates the flow.
2. **Central core** — provides shared truth: contracts, naming, trust rules, storage targets, run identity, and evidence expectations.
3. **Specialized skills** — execute narrow classes of work deeply.

If a task needs more than one skill, the agent should compose them in sequence instead of trying to solve everything from one giant prompt.

---

## Read order for an agent

See `AGENTS.md` → "Read order (start here, always)" for the canonical sequence — it
is kept single-sourced there so this file and `AGENTS.md` cannot silently disagree.
In short: `README.md` → `AGENTS.md` → `PROJECT_MAP.md` → this file → Core contract in
`AGENTS.md` → `03_design/` REFERENCE/ACTIVE-PLAN only when needed → skill file(s) → nearest module
`AGENTS.md`.

Do **not** load every skill by default.

---

## Routing rules

### Use spreadsheet ingestion skill when
- the task starts from Excel, CSV, SAP-style exports, or large tabular files
- the main need is profiling columns, cleaning structure, loading rows, or preserving row-level evidence
- the user asks how to read, normalize, or store operational tables
- the task needs multi-sheet Excel ingestion, per-column type inference, or the `ingest_spreadsheet` MCP tool

Load:
`.claude/skills/spreadsheet-ingestion/SKILL.md`

### Use document evidence extraction skill when
- the task starts from PDF, Word, PowerPoint, scans, screenshots, or mixed document bundles
- the main need is evidence extraction, OCR recovery, or citation-bearing passages
- the user asks to inspect document text, attachments, page-level evidence, or scanned content
- the task is to ingest or inspect a PPTX deck while preserving slide-level citations and table evidence
- the task is to summarize a long PDF/PPTX deck with chunk coverage accounting and no silent truncation
- the task is to normalize deck understanding into a cited workflow record with purpose, steps, owners, KPIs, changes, and open questions
- the task is to retain original-language source text and provenance metadata for translated workflow fields
- the task is to apply a Korean-English factory glossary or flag critical-term translation disagreements
- the task is to measure image-only slide share or OCR review load for Korean decks before escalating OCR/VLM paths
- the task is to ingest `.eml` messages, preserve email metadata, or route attachments into the document spine
- the task needs the explicit Docling hard-layout parser path for difficult PDF/DOCX/PPTX layouts (opt-in only)

Load:
`.claude/skills/document-evidence-extraction/SKILL.md`

### Use cost variance analysis skill when
- the task is about variance, cost drivers, budget vs actual, standard vs actual, price/volume/mix, or cost explanation
- the user asks why cost changed, what drove the change, or which factor matters most
- the task depends on trusted numeric decomposition

Load:
`.claude/skills/cost-variance-analysis/SKILL.md`

### Use management reporting skill when
- the task is to produce a manager card, dashboard, presentation, or decision-ready summary
- the task needs a one-page answer with cited facts, not raw analysis
- the task is about shaping output for leadership use
- the task is to build a decision brief, meeting pack, or cited management article from stored knowledge
- the task is to export a signed executive output to HTML or PPTX

Load:
`.claude/skills/management-reporting/SKILL.md`

### Use knowledge search skill when
- the user asks what the system knows about a process, workflow, KPI, or document family
- the task needs workflow version history, valid-time lookup, or cited diffs
- the task needs linked claims, open questions, or contradictions for a topic
- routine retrieval should return compact linked records instead of loading the whole plan
- the task needs ontology entity resolution, typed workflow edges, or factory comparison gates
- the task needs labeled `AI-SUGGESTED IDEA` synthesis after contradictions are surfaced

Load:
`.claude/skills/knowledge-search/SKILL.md`

### Use FOREMAN pipeline skill when
- the task is to process a new factory spreadsheet end-to-end through FOREMAN
- the work must follow the exact SK-001 → SK-002 → SK-003 → SK-004 → SK-005 chain
- the user wants a governed path from inbox file to signed report without improvisation

Load:
`.claude/skills/foreman-pipeline/SKILL.md`

### Use audit and trust skill when
- the task needs release gating, independent re-checking, certainty scoring, reconciliation, or human sign-off
- the user asks whether a result is safe to trust or release
- there is any ambiguity around data quality, missing evidence, or number mismatches
- the task involves LLM-originated claims, the claims store, claim quarantine, or the facts/claims wall
- the task needs an independent audit of non-numeric brief claims from documents or decks
- the task involves open questions, decision outcomes, or contradiction review
- the task is to sign off or record owner feedback on executive briefs, packs, or reports
- the task needs golden eval regression gates, MCP access review, backup/restore drills, or session resume state
- the task involves gated self-evolution (T12) after golden eval passes

Load:
`.claude/skills/audit-and-trust/SKILL.md`

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

### Pattern F — stored knowledge to answer
1. knowledge search
2. audit and trust when claims or contradictions are involved
3. management reporting when an executive output is needed

### Pattern G — regression, ops, and resume
1. audit and trust (golden eval, MCP access, backup/restore)
2. session-state write when handing off between agents
3. gated self-evolution (T12) only after golden eval passes

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

Those shared rules live in the **Core contract** section of `AGENTS.md`.

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
