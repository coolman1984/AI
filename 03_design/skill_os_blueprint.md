---
status: REFERENCE
owner: architect
date: 2026-07-03
---

# FOREMAN — Local-First AI Skill Operating System (Improved Blueprint v1)

*Prepared 2026-07-03. This document is the improved, criticized, and buildable version of the
owner's "AI Skill Operating System" idea. It is designed to sit ON TOP of the existing
Factory Brain repo (`g:\AI`), not to replace it. Roughly 60% of the requested system already
exists here and is tested — the biggest single improvement in this blueprint is refusing to
rebuild that 60%.*

---

# 1. Project Name

**FOREMAN** — the Factory Operations & Reporting Engine with Memory, Agents, and Numbers.

A foreman doesn't do the manual labor. He receives the job, decides which crew (skill) does
it, checks the work against the drawing (validation), signs the paperwork (evidence), and
remembers which crew botched what last month (lessons). That is exactly this system's job.

# 2. One-Sentence Mission

FOREMAN turns mature AI agents into a supervised factory work crew: every task runs through a
contract, a registered skill, deterministic tools, validation gates, and an evidence ledger —
so the owner gets audited business answers, not chatbot output.

# 3. What My Original Idea Got Right

1. **Skills as professional workflows, not prompts.** This is the single most important idea.
   A prompt produces different behavior every run; a skill with inputs, forbidden actions,
   validation, and tests produces repeatable work. Keep this as the constitution.
2. **Deterministic tools do the math; the agent only routes and explains.** This matches the
   existing repo's Calculation-Integrity Rule and is the correct division of labor.
3. **Evidence ledger + validation gates.** Correct instinct: in factory finance, an unproven
   number is worse than no number.
4. **Run contract before work.** Forces scope, risk level, and definition-of-done to exist
   before tokens are spent. Prevents the #1 real-world failure: the agent solving the wrong task.
5. **Lesson loop with a promotion gate.** Letting the agent *propose* skill changes but never
   *silently apply* them is the right governance shape.
6. **Local-first, privacy-tiered, non-programmer operable.** All correct and already partially
   proven in the existing repo (two-tier privacy, offline OCR, plain-English reporting).
7. **Starting small (5 skills, not 50).** Right. Skill bloat is the disease that kills these systems.

# 4. What My Original Idea Was Missing

Be warned — several of these are the reasons similar systems die in month two.

1. **It ignores what you already built.** The Factory Brain repo already has: a tested
   ingestion spine with quarantine and conservation laws, a canonical number parser, variance
   + price/volume/mix engines, an audit layer, provenance-tagged reporting, a claims/facts
   wall, a document registry, six written skills, an MCP tool surface, and 285 green tests.
   Designing a fresh folder tree and fresh database as if from zero would throw away months
   of validated work. **FOREMAN must be a layer over Factory Brain, reusing its engines as the
   tool manifest's first entries.**
2. **No file fingerprinting / "which version of the file did we analyze?"** Factory Excel
   files get re-sent, renamed, and quietly edited. Without a SHA-256 fingerprint per input,
   two runs on "the same file" can silently disagree and you cannot prove why. This is in your
   requested DB schema but was missing from the workflow logic — it must be step 1 of every run.
3. **No token/cost accounting.** You ask "does it save tokens?" in the scorecard but nothing
   records spend. Every run must log model calls, model name, and approximate tokens, or the
   scorecard is fiction.
4. **The lesson loop will produce garbage by default.** After-action reviews run by an LLM
   generate plausible non-lessons ("consider adding more validation!"). Your admission rules
   help, but the missing piece is: **a lesson may only be created from a logged failure,
   a human correction, or a pattern seen ≥2 times with run IDs as evidence.** No run IDs, no lesson.
5. **Skill/code drift.** A SKILL.md that describes a workflow and the code that implements it
   WILL drift apart. Missing: a test per skill that exercises the skill's happy path end-to-end
   (the repo already does this per module — extend it per skill), and a linter that fails when
   a skill references a tool not in the manifest (the repo's `test_skill_contracts.py` is the seed).
6. **Excel reality is nastier than the design assumes.** Merged cells, formulas-vs-values,
   hidden rows, subtotal rows *inside* data, two tables on one sheet, European/Korean number
   formats, dates as text, 272-column SAP exports. The existing `clean.py`/`ingest.py` handle
   several of these (totals, dupes, locale, negative conventions — hardened 2026-07-03); the
   blueprint must treat "sheet profiling before any mapping" as a mandatory gate, not an option.
7. **No "who validates the validator."** If a validation rule is wrong (e.g., wrong expected
   total), the system confidently blocks correct work or passes wrong work. Missing: validation
   rules themselves live in the vault as reviewable business-rule notes with an owner and a source.
8. **Approvals were listed but not designed as a queue.** A non-programmer needs ONE place to
   see "what is waiting for my yes" — a plain `approvals/pending/` folder with one Markdown file
   per request, moved to `approvals/decided/` with the decision recorded. No web app needed.
9. **No backup/restore story.** SQLite + vault + registry must be backed up as one snapshot
   (the repo's `ops/backup.py` exists — wire it in, don't reinvent).
10. **Dashboard ambition too early.** A local dashboard is Phase 5, and even then it should be
    generated static HTML (the repo already renders HTML cards) — never a live server to maintain.
11. **Model routing missed the refusal/fallback reality and the privacy interaction.** Routing
    isn't only about cost: Tier-1 factory data may not go to ANY cloud model, which forces some
    tasks to local deterministic tools + local summaries regardless of quality tradeoffs. The
    router must check privacy tier BEFORE model choice, not after.
12. **Nothing stops skill bloat structurally.** Add a hard rule: a new skill requires a
    demonstrated ≥2-occurrence need logged as lessons, and the registry caps at ~25 active
    skills; adding #26 requires archiving or merging one.
13. **Windows-specific frictions unaddressed** (paths, PowerShell vs bash, file locks while
    Excel is open). Tools must fail loudly with "close the file in Excel" guidance, not corrupt reads.
14. **"Second brain" duplication risk with the existing repo's memory.** The repo already has
    claims, registry, lessons-adjacent structures, and `.brain/` JSON. The vault must be the
    *human-readable* layer that LINKS to those stores — not a third competing copy of the truth.

# 5. Final Improved Mental Model

| Element | Role | Plain meaning |
|---|---|---|
| Agent | Brain | Understands the goal, picks the skill, calls tools, explains results. Never invents numbers. |
| Skills | Professional workflows | Written procedures a new "employee" (any model) can follow identically. |
| Tools | Hands | Deterministic Python (existing engines/) that touch files and compute. Only hands touch data. |
| Skill map | Router | Decides which skill(s) handle the task; refuses tasks with no skill match instead of improvising. |
| Run contract | Task agreement | One small file: goal, inputs, risk, outputs, definition of done — agreed before work starts. |
| Evidence ledger | Proof | Fingerprints, locators, checks — enough to reproduce any number a year later. |
| Validation gates | Quality control | Deterministic checks between every stage; failing a gate stops the line, like an andon cord. |
| Reports | Business output | Plain-English deliverables with provenance tags; the reason the system exists. |
| Second brain | Memory | Obsidian vault of confirmed rules, mappings, lessons, decisions — linked, versioned, curated. |
| Lesson loop | Improvement engine | Failures become lessons; ≥2 similar lessons become a proposed skill update; approval promotes it. |

One added element the original model lacked:

| Element | Role | Plain meaning |
|---|---|---|
| Approval queue | The owner's inbox | The single folder where anything irreversible, sensitive, or version-changing waits for a human yes. |

# 6. Architecture Recommendation

**Overarching decision: FOREMAN = a thin orchestration + governance shell around the existing
Factory Brain engines.** New code is mostly: run contracts, the runs/evidence SQLite layer,
the vault, the approval queue, and 5 skill documents. The heavy machinery (ingest, clean,
variance, audit, OCR, reporting) already exists and is tested.

### Layer 1 — User Interface
- **Purpose:** Let a non-programmer start work, answer approvals, and read results.
- **Inputs:** Plain-English request + files dropped in `datasets/inbox/`.
- **Outputs:** A run contract to confirm; reports in `reports/`; approval requests in `approvals/pending/`.
- **Main files:** Claude Code chat (the UI for MVP), `approvals/`, `reports/`, Obsidian on `vault/`.
- **Risks:** Owner confusion about where things are. Mitigation: every run ends with a 3-line "what happened / why it matters / what to do next" plus file paths.
- **Validation:** Owner can locate the latest report and pending approvals in <30 seconds (test with a drill).

### Layer 2 — Agent Orchestration
- **Purpose:** Turn a request into: contract → skill selection → tool calls → gates → report → lesson.
- **Inputs:** Contract, skill registry, tool manifest.
- **Outputs:** Completed run row + artifacts; or a clean "blocked" state naming the missing input.
- **Main files:** `CLAUDE.md`/`AGENTS.md` (behavior), `registry/skills.yaml`, existing `engines/brain/orchestrator.py`.
- **Risks:** Agent improvising outside skills. Mitigation: "no matching skill → propose a skill, don't freelance" rule in AGENTS.md.
- **Validation:** Every run row must reference a skill_id; runs with skill_id=NULL fail CI audit.

### Layer 3 — Skill Routing
- **Purpose:** Map task → skill or skill chain (the repo's `AGENT_SKILL_MAP.md` already does this; extend it).
- **Inputs:** Task classification + triggers/anti-triggers from registry.
- **Outputs:** Ordered skill list written into the contract.
- **Main files:** `AGENT_SKILL_MAP.md`, `registry/skills.yaml`.
- **Risks:** Two skills claiming the same trigger. Mitigation: registry linter rejects overlapping triggers.
- **Validation:** Routing decision recorded in the contract; spot-audited weekly.

### Layer 4 — Tool Execution
- **Purpose:** All file reading and computation, deterministic only.
- **Inputs:** Validated parameters from the skill workflow.
- **Outputs:** Data + machine-readable results + reject files.
- **Main files:** existing `engines/*`, `mcp_server/server.py`, `registry/tools.yaml` (new manifest describing them).
- **Risks:** A tool silently writing where it shouldn't. Mitigation: manifest marks every tool read-only/write; write tools always target `runs/<id>/` or `exports/`, never source folders.
- **Validation:** Existing pytest suite (285 tests) + manifest linter.

### Layer 5 — Data
- **Purpose:** Store metadata (SQLite `foreman.db`), analytical data (DuckDB, existing), knowledge (Markdown vault), configs (YAML).
- **Inputs:** Tool outputs, run events.
- **Outputs:** Queryable history, report inputs.
- **Main files:** `registry/foreman.db`, existing DuckDB staging, `vault/`, `config/settings.yaml`.
- **Risks:** SQLite and vault disagreeing. Mitigation: SQLite is truth for runs/evidence; vault is truth for human knowledge; neither duplicates the other's content, they link by ID.
- **Validation:** Nightly integrity check: every report row's file exists on disk; every vault note's run links resolve.

### Layer 6 — Validation
- **Purpose:** Deterministic gates between stages (Section 14).
- **Inputs:** Stage outputs + business rules from vault.
- **Outputs:** validation_results rows; hard stop on fail.
- **Main files:** existing `engines/audit/audit.py`, `engines/data/clean.py` conservation asserts, new thin gate wrappers.
- **Risks:** Wrong validation rules blocking good work. Mitigation: rules are vault notes with owner + source; a gate failure message always names the rule note.
- **Validation:** Gates themselves have tests (existing `test_nasty_data.py` pattern).

### Layer 7 — Reporting
- **Purpose:** Business deliverables from validated data.
- **Inputs:** Validated numbers + templates + provenance tags.
- **Outputs:** Markdown/HTML/PPTX in `reports/`.
- **Main files:** existing `serving/*`, `templates/`.
- **Risks:** A report rendering an unvalidated number. Mitigation: reporting layer only accepts `NumberFact`-style values with evidence refs (already enforced by contracts).
- **Validation:** Existing card validation (max numbers, evidence required) + report gate (Section 14).

### Layer 8 — Second Brain
- **Purpose:** Curated, linked, human-readable memory (Section 16).
- **Inputs:** Admitted notes only (Section 17).
- **Outputs:** Context that makes future runs cheaper and safer.
- **Main files:** `vault/` opened in Obsidian.
- **Risks:** Bloat and duplication. Mitigation: admission rules + monthly 15-minute curation review.
- **Validation:** Duplicate-title check on save; orphan-note report monthly.

### Layer 9 — Governance
- **Purpose:** Approvals, privacy tiers, versioning, rollback.
- **Inputs:** Approval requests, privacy classifications.
- **Outputs:** Signed decisions, ledger entries.
- **Main files:** `approvals/`, existing `gov/privacy.py`, `gov/ledger.py`, `gov/access.py`.
- **Risks:** Approval fatigue → rubber-stamping. Mitigation: only 4 things ever require approval (Section 19), keeping the queue short and meaningful.
- **Validation:** Every external model call for Tier-1 data must have a ledger entry or CI fails.

### Layer 10 — Improvement
- **Purpose:** Lessons → skill updates → promotion (Sections 18–19).
- **Inputs:** Run outcomes, corrections, failures.
- **Outputs:** Lesson notes, versioned skill updates.
- **Main files:** `lessons/`, `registry/skills.yaml` version history, `approvals/`.
- **Risks:** Fake lessons. Mitigation: run-ID evidence requirement.
- **Validation:** Every skill update PR-style file cites ≥1 lesson; every lesson cites ≥1 run.

# 7. Local-First Folder Structure

Placed alongside the existing repo (new folders marked ★; existing repo folders are reused, not duplicated):

```
G:\AI\
├── .claude/skills/    ★ Canonical agent-facing skill library: one folder per skill with SKILL.md
├── skills/            ★ FOREMAN executable layer: SKILL.md + run.py per skill
├── tools/             ★ Tool manifest docs only — code stays in engines/ (one MD per tool family, pointing at real code)
├── runs/              ★ One folder per run: contract.md, steps.log, outputs/, rejects/
├── reports/           ★ Final business reports, named YYYY-MM-DD_<type>_<topic>.md/.html/.pptx
├── vault/             ★ Obsidian second brain (Section 16)
├── lessons/           ★ Raw lesson captures awaiting curation into vault/lessons/
├── schemas/           ★ JSON schemas: run_contract, skill, tool (validated by a linter test)
├── templates/         ★ SKILL.md, RUN_CONTRACT.md, MANAGEMENT_REPORT.md, LESSON.md
├── tests/             (existing — 285 tests; new skill tests join here)
├── dashboards/        ★ Generated static HTML only (Phase 5; empty until then)
├── datasets/          ★ inbox/ (drop files here), registered/ (fingerprinted copies), samples/ (existing data/sample merges here later)
├── logs/              ★ Run logs + model-call/cost log (append-only CSV)
├── approvals/         ★ pending/ + decided/ — the owner's approval inbox
├── config/            ★ settings.yaml (privacy tiers, model routing, thresholds; existing config.yaml stays for engines)
├── registry/          ★ skills.yaml, tools.yaml, foreman.db (SQLite)
├── evidence/          ★ Evidence exports per run when needed outside the DB (CSV extracts of ledger)
├── exports/           ★ Anything leaving the machine (redacted packs) — the ONLY folder cloud-bound files may come from
└── engines/, serving/, gov/, shared/, mcp_server/, ops/   (existing — the actual hands; untouched)
```

Rule: **source files in `datasets/inbox/` are never edited.** Registration copies them (with
fingerprint) into `datasets/registered/`; all work happens on the copy.

# 8. Core Database Design

One SQLite file: `registry/foreman.db`. MVP builds only the tables marked **[MVP]**; the rest
are defined now, created when their phase arrives (empty tables cost nothing but adding them
later without a plan costs rework).

| Table | Key fields |
|---|---|
| **skills** | skill_id, name, domain, risk_level, version, status(active/archived), file_path, last_test_pass_at |
| **tools** | tool_id, name, engine_path, read_only(bool), risk_level, approval_required(bool), version |
| **runs [MVP]** | run_id, started_at, finished_at, status, goal, skill_id, contract_path, privacy_tier, model_calls_count, est_tokens, outcome_summary |
| **run_steps [MVP]** | step_id, run_id, seq, tool_id, params_json, status, started_at, finished_at, output_path |
| **evidence_items [MVP]** | evidence_id, run_id, step_id, source_fingerprint, source_path, locator(sheet/page/range), method, value_or_summary, created_at |
| **validation_results [MVP]** | validation_id, run_id, gate_name, rule_ref(vault note), passed(bool), expected, actual, message |
| **reports [MVP]** | report_id, run_id, type, audience, file_path, signed_off_by, signed_off_at |
| **memory_notes** | note_id, vault_path, note_type, title, created_from_run, status(active/superseded), superseded_by |
| **lessons [MVP]** | lesson_id, run_id, category(failure/correction/pattern), description, evidence_run_ids, status(raw/curated/promoted/rejected) |
| **skill_updates** | update_id, skill_id, from_version, to_version, lesson_ids, status(proposed/approved/rejected/rolled_back), approved_by |
| **approvals [MVP]** | approval_id, run_id, type(external_send/skill_promotion/write_action/sensitive_memory), request_path, decision, decided_by, decided_at |
| **file_fingerprints [MVP]** | fingerprint_id, sha256, original_path, registered_path, size_bytes, first_seen_at, source_note |
| **datasets** | dataset_id, name, fingerprint_id, row_count, period_covered, load_status, duckdb_table |
| **column_mappings** | mapping_id, dataset_id, source_column, canonical_name, dtype, confirmed_by, confirmed_at |
| **business_rules** | rule_id, vault_path, statement, owner, source, applies_to, active(bool) |
| **kpis** | kpi_id, name, definition_vault_path, formula_tool_id, unit, direction_good |

# 9. Skill Registry Schema

```yaml
# registry/skills.yaml — one entry per skill
- skill_id: SK-001
  name: excel-intake
  domain: data_ingestion            # data_ingestion | analysis | reporting | documents | memory
  purpose: >
    Register, fingerprint, and safely stage a spreadsheet into the ingestion
    spine with quarantine and conservation checks.
  triggers:
    - "new Excel/CSV file to analyze"
    - "SAP export arrived"
  anti_triggers:
    - "file is a PDF or scan (use document skills)"
    - "data already registered this period (use query skills)"
  required_inputs: [file_path]
  optional_inputs: [expected_row_count, expected_total, period]
  allowed_tools: [T-FP-001, T-ING-001, T-PROF-001]   # by tool_id
  forbidden_actions:
    - editing the source file
    - sending file content to any cloud model (Tier-1 default)
    - proceeding past a failed conservation check
  output_types: [staged_table, profile_report, reject_file]
  validation_rules: [gate.fingerprint, gate.conservation, gate.profile_complete]
  evidence_required: [source_fingerprint, sheet_locators, row_counts]
  risk_level: low                    # low | medium | high
  approval_required: false
  version: 1.0.0
  owner: mflma
  dependencies: []                   # other skill_ids this chains from
  known_failures:
    - "file open in Excel -> lock error; ask owner to close it"
  test_cases: [tests/test_skill_excel_intake.py]
  last_updated: 2026-07-03
```

# 10. Professional SKILL.md Template

```markdown
---
skill_id: SK-XXX
version: 1.0.0
risk_level: low
status: active
---

# Skill: <name>

## Purpose
One paragraph: what business outcome this produces and for whom.

## Use this skill when
- <trigger 1>
- <trigger 2>

## Do NOT use this skill when
- <anti-trigger and which skill to use instead>

## Inputs
| Input | Required | Format | Example |
|---|---|---|---|

## Outputs
| Output | Location | Format | Consumer |
|---|---|---|---|

## Allowed tools
Only these tool_ids: <list>. Anything else is a skill violation — stop and report.

## Forbidden actions
- <explicit list — the agent must refuse, not work around>

## Workflow
1. <step> — tool: <tool_id> — evidence written: <what>
2. <step> — gate: <gate name> — on fail: <recovery ref>
3. ...
(Every step names its tool or gate. No step says "figure out".)

## Validation
| Gate | Pass condition | On fail |
|---|---|---|

## Evidence requirements
What must exist in the ledger before this skill may report success.

## Failure recovery
| Failure | Detection | Recovery |
|---|---|---|

## Known edge cases
- <case>: <handling>

## Examples
### Example 1: <realistic case with real-shaped fake data>
Input → key steps → output → evidence produced.

## Tests
- tests/<file>::<test> — what it proves.

## Improvement notes
Link lessons that shaped this version: [[lesson-...]]. Next known weakness: <one line>.
```

# 11. Tool Manifest Schema

```yaml
# registry/tools.yaml — one entry per tool; code lives in engines/, this is the passport
- tool_id: T-ING-001
  name: ingest_spreadsheet
  purpose: Load CSV/Excel text-first into DuckDB with total-row/duplicate quarantine and conservation check.
  engine_path: engines/data/ingest.py::ingest_spreadsheet
  input_schema:
    path: {type: string, required: true}
    table: {type: string, required: true}
    on_duplicates: {type: string, enum: [flag, drop], default: flag}
    infer_types: {type: boolean, default: false}
  output_schema:
    rows_in: integer
    reject_count: integer
    run_id: integer
  allowed_file_types: [.csv, .xlsx, .xlsm]
  read_only_or_write: write          # writes ONLY to DuckDB staging, never to source files
  side_effects: "creates/replaces DuckDB staging tables; appends ingestion_runs/rejects"
  risk_level: low
  approval_required: false
  validation_method: "conservation: rows_in == kept + rejected (asserted in code + tests)"
  example_call: "ingest_spreadsheet(con, 'raw_actuals', 'datasets/registered/abc123_actuals.xlsx')"
  failure_modes:
    - "file locked by Excel -> tell owner to close it"
    - "unsupported extension -> route to document skills"
  fallback_tool: null                # deterministic tools generally have no fallback; fail loudly
```

# 12. Run Contract Template

```markdown
---
task_id: RUN-2026-07-03-001
created: 2026-07-03T09:00
status: proposed        # proposed -> approved -> running -> done/blocked/failed
---

# Run Contract

**User goal (plain English):** <one sentence in the owner's words>

**Input files:** <paths + fingerprints once registered>
**Sensitive data level:** tier1_inhouse | tier2_cloud_ok   (default: tier1)
**Selected skills:** <skill_ids in order>
**Selected tools:** <tool_ids>
**Constraints:** <deadlines, scope limits, "May actuals only", etc.>
**Expected outputs:** <report type + location>
**Risk level:** low | medium | high
**Approval required before start:** yes/no (why)
**Validation required:** <gate list>
**Evidence required:** <ledger items list>
**Report required:** <template name>
**Second-brain update expected:** yes/no — <what kind of note, if known>

**Definition of done:**
- [ ] All gates passed (or failures explained and accepted by owner)
- [ ] Report exists at the stated path with provenance tags
- [ ] Evidence ledger complete for every number in the report
- [ ] Lesson capture done (even if "nothing notable")
```

Contracts under ~10 lines of real content take <1 minute to confirm. For repeat monthly runs,
a saved contract template pre-fills everything except the file and period.

# 13. Evidence Ledger Design

Every run writes evidence_items rows forming an unbroken chain:

1. **Source fingerprint** — SHA-256 + size + original path, recorded at registration.
2. **Locator** — sheet name / page number / table index / row-column range actually read.
3. **Extraction method** — tool_id + version + parameters (so it can be re-run identically).
4. **Transformation steps** — each cleaning/mapping step with counts in/out and reject reasons.
5. **Calculation checks** — expected vs actual totals, reconciliation deltas, tolerance used.
6. **Validation results** — each gate, pass/fail, the rule note it enforced.
7. **Report output** — file path + which evidence_ids back each number (the existing
   `EvidenceRef`/`NumberFact` contracts already enforce this at render time).
8. **Human approval** — who signed, when, at what certainty (existing `SignOff` contract).
9. **Final artifact fingerprint** — hash of the delivered report, so later edits are detectable.

**How this prevents hallucination:** a number can only appear in a report if it carries an
evidence_id; an evidence_id can only exist if a deterministic tool wrote it; the tool recorded
the exact file/sheet/range it came from. The agent can phrase and explain, but it physically
has no path to *introduce* a number. Anything without a chain renders as `CLAIMED` not
`AUDITED` (already implemented in serving/) — and management reports refuse CLAIMED values.

# 14. Validation Gates

| Gate | Check | Pass | Fail | Recovery | Evidence produced |
|---|---|---|---|---|---|
| Excel extraction | Conservation: rows_in == kept + rejected; sheet list matches profile | Counts balance | Any row unaccounted | Stop; inspect rejects; re-profile | rows_in/kept/rejected counts |
| PDF extraction | Extraction quality score ≥ threshold OR routed to OCR cascade; page count matches | Quality path chosen deliberately | Silent low-quality text accepted | Escalate cascade or human-review queue | per-page quality scores |
| Column mapping | Every required canonical column mapped; no source column mapped twice; dtype sample-check passes | 100% required mapped + confirmed | Unmapped required or ambiguous | Present mapping proposal to owner; save confirmed mapping | mapping table + confirmer |
| Numeric cleaning | All numeric cells parse via canonical parser; unparseable → rejects | 0 silent nulls | Any strict-cast null | Quarantine rows; report reject % vs threshold (5%) | reject file + reasons |
| Date cleaning | All dates parse via deterministic formats; ambiguous (03/07 vs 07/03) flagged | 0 ambiguous unflagged | Ambiguous date silently chosen | Ask owner once; save format as business rule | format rule note |
| DB loading | Loaded row count == cleaned count; PK uniqueness holds | Exact match | Mismatch or PK violation | Rollback load; investigate dupes | load counts |
| Duplicate detection | Dup definition from registry key; dup% below threshold | Below threshold or approved | Above threshold unexplained | Show sample dupes to owner | dup count + key used |
| Reconciliation | Sum of detail == control total (source subtotal, prior report, or SAP total) within 0.01 | Delta ≤ tolerance | Delta > tolerance | Stop; drill into by-dimension deltas | expected/actual/delta |
| Variance calculation | Bridge reconciles; PVM parts sum to total (existing `reconciles()`) | Exact within tolerance | Doesn't sum | Bug — never release; open failure lesson | decomposition check row |
| Report generation | Every number has evidence_id; provenance tags present; template sections complete | All AUDITED | Any CLAIMED number in a numbers section | Replace with queried value or remove | report row + refs |
| Dashboard generation | Static HTML renders; numbers match source report exactly | Byte-identical values | Any divergence | Regenerate from report data, never re-compute | checksum comparison |
| Second-brain update | Admission rules pass (Section 17); no duplicate title/topic | Unique + evidenced | Duplicate or unevidenced | Merge into existing note or discard | note_id + source run |
| Skill update | Tests pass incl. regression; version bumped; lesson cited; approval recorded | All four present | Any missing | Return to proposed state | skill_updates row |
| Final delivery | Definition-of-done checklist in contract all checked | All checked | Any unchecked | Name the gap to owner; don't mark done | contract status=done |

# 15. Reporting System

| Report | Audience | Purpose | Sections | Data needed | Validation | Format |
|---|---|---|---|---|---|---|
| Management summary | Plant leadership | One-page decision view | BLUF, 5 key numbers, drivers, risks, actions, confidence | Validated KPIs + variance | Report gate + sign-off | MD → HTML/PPTX (existing card) |
| Cost variance report | CFO/controllers | Explain cost vs budget/standard | Bridge, PVM decomposition, top items, unmatched, rejects note | actuals, budget, standards | Reconciliation + PVM gates | MD + HTML |
| Inventory exception report | Materials manager | Surface slow/negative/expired stock | Exception lists by rule, aging, value at risk | inventory snapshot + rules | Rule notes cited per exception | MD table + CSV export |
| Production performance | Ops manager | Output vs plan | Plan-vs-actual by line, trend, downtime notes | production actuals + plan | Reconciliation gate | MD + HTML |
| Quality & rework | Quality manager | Rework cost + causes | Rework qty/cost by cause, trend, repeat offenders | rework records + costs | Numeric cleaning gate | MD |
| Technical run report | Owner (audit mode) | What the system did | Steps, tools, gates, rejects, cost/tokens | run_steps + validation_results | Auto-generated, no numbers invented | MD in runs/<id>/ |
| Evidence report | Auditor/owner | Prove any number | Full chain for selected numbers | evidence_items | Chain completeness check | MD/CSV in evidence/ |
| Skill improvement report | Owner (monthly) | Improvement engine health | Lessons logged, updates proposed/approved, failure recurrence | lessons + skill_updates | Counts from DB only | MD |

Every report ends with the same 3-line footer: **What happened / Why it matters / What to do next.**

# 16. Second Brain Design

Obsidian vault at `vault/`. Frontmatter is uniform; only `type` and type-specific fields vary.

Common frontmatter: `type, title, created, updated, status(active/superseded), source_runs, links`.

| Note type | Extra frontmatter | Body structure | Linking rules | Create when | Do NOT create when |
|---|---|---|---|---|---|
| Company workflow | owner_dept, frequency | Purpose → steps → systems → owners → pain points | → business rules, datasets, KPIs | A real process is documented/confirmed | Speculating about a process |
| Business rule | rule_owner, source_doc | Statement → rationale → applies-to → exceptions | ← validation gates cite these | Owner confirms a rule ("freight is allocated by weight") | Rule inferred but unconfirmed |
| Report logic | report_type, template | Definition of every section/number | → KPIs, business rules | A report is approved as "correct shape" | Draft reports |
| Skill | skill_id, version | Mirror of SKILL.md summary + links | → tools, lessons | Skill promoted to active | Proposals (stay in approvals/) |
| Tool | tool_id | Purpose, limits, gotchas in plain English | ← skills | Tool added to manifest | — |
| Dataset | fingerprint, period | What it is, columns, quirks, owner | → column mappings | A source is registered and profiled | One-off scratch files |
| Column mapping | dataset, confirmer | Source→canonical table + dtype notes | ← datasets | Owner confirms a mapping | Auto-proposed unconfirmed maps |
| KPI | unit, direction_good | Definition, formula (tool ref), source, frequency | → report logic | KPI definition confirmed | Ad hoc metrics |
| Failure | run_id, severity | What broke, detection, impact | → lessons | A gate failed or output was wrong | Trivial retries |
| Lesson | category, evidence_runs | What we learned → what changes | → skills/tools it should change | Admission rules pass (Sec 17) | Single unrepeated observation (unless a failure) |
| Decision | decided_by, date | Options considered → decision → why → revisit-when | ← everything affected | Owner makes a lasting call | Routine choices |
| Question | asked_of, due | The open question + what's blocked by it | → blocked runs | Something blocks work | Rhetorical/answered questions |
| Meeting note | attendees, date | Decisions + actions only (not minutes) | → decisions, questions | Meeting produced decisions/actions | Meetings with neither |
| Improvement proposal | target(skill/tool), lessons | Current → proposed → evidence → test plan | → lessons cited | ≥1 lesson supports it | Ideas without lesson evidence |
| Glossary term | language(EN/KR/AR) | Definition + synonyms + SAP field names | ← everywhere | A term caused confusion once | Common words |

# 17. Memory Admission Rules

**Save (with evidence):** confirmed business rules (confirmer named) · owner-validated column
mappings · failures and repeated patterns (run IDs attached) · approved workflows · formulas
that produced a validated report · report definitions after sign-off · stated manager
preferences ("CFO wants variance in USD thousands") · discovered tool limitations · promoted
skill improvements.

**Never save:** temporary noise (paths of scratch files, one-off values) · unverified
assumptions (park as Question notes instead) · duplicate lessons (merge, don't multiply) ·
conclusions later proven wrong (mark superseded, keep for history, exclude from context) ·
personal data (names+salaries etc.) unless explicitly approved · raw confidential rows —
store fingerprints, schemas, and aggregates, not row contents, unless the owner approves a
specific exception.

Enforcement: the second-brain gate (Section 14) runs before any note is written; sensitive
memory admission is one of the four approval types.

# 18. Lesson Extraction Loop

Runs at the end of every task, answers written to `lessons/RUN-<id>.md`, 5 minutes max:

1. What worked? (only if reusable — else "standard")
2. What failed? (link gate failures automatically)
3. What was corrected by the owner? (highest-value signal — always capture verbatim)
4. What was confusing to the owner? (usability lesson)
5. What edge case appeared? (candidate for skill's edge-case list)
6. Which skill should change? (only with evidence)
7. Which tool should change?
8. Which validation test should be added? (a correction with no new test is a lesson wasted)
9. Which memory note should be created? (apply admission rules now, not later)
10. Which old note is now wrong? (mark superseded)
11. What should be ignored? (explicitly discard noise so it isn't re-analyzed)

Rule: **"nothing notable" is an acceptable and common answer.** Forced lessons are noise.
Weekly, raw lessons are curated: promoted to vault notes, merged, or rejected — with status
recorded in the lessons table.

# 19. Skill Update Governance

```
raw lesson(s) ──▶ improvement proposal ──▶ review ──▶ tests ──▶ approval ──▶ promotion
 (lessons/)      (vault, cites lessons)   (agent      (new test  (owner,     (version bump,
                                          different    + full     approvals/  registry update,
                                          session or   suite      queue)      vault note)
                                          reviewer     green)
                                          role)
                                                            └─▶ rollback plan: previous
                                                                SKILL.md kept in git; revert
                                                                = git revert + version note
```

Hard rules: the agent may propose, never promote. A promotion without a cited lesson,
a passing new test, a green full suite, and an approvals/ record is invalid — the skill-update
gate (Section 14) checks all four. Only four things EVER need owner approval, keeping the
queue meaningful: (1) sending anything external, (2) skill promotion, (3) write actions
outside runs//exports/, (4) sensitive memory admission.

# 20. First Five MVP Skills

### SK-001 excel-intake
- **Purpose:** Register + fingerprint + stage a spreadsheet safely.
- **Trigger:** New Excel/CSV arrives in `datasets/inbox/`.
- **Inputs:** file path; optional expected totals/rows.
- **Outputs:** registered copy, staged DuckDB table, reject file, intake summary.
- **Tools:** fingerprinter, existing `ingest_spreadsheet`.
- **Validation:** fingerprint gate; conservation gate.
- **Evidence:** fingerprint, sheet list, rows in/kept/rejected.
- **Edge cases:** file locked by Excel; multi-sheet workbooks; empty sheets; password-protected (reject with message).
- **Test:** fixture workbook with a total row + duplicate + junk amount → exactly those rows quarantined, conservation holds.

### SK-002 column-profile-and-map
- **Purpose:** Profile columns and produce an owner-confirmable mapping to canonical names.
- **Trigger:** Newly staged table without a confirmed mapping.
- **Inputs:** staged table; existing mappings for similar datasets.
- **Outputs:** profile report (dtypes, null %, sample values, suspected keys), proposed mapping.
- **Tools:** existing type inference (`engines/data/types.py`), profiler.
- **Validation:** column-mapping gate (owner confirms; saved as vault note).
- **Evidence:** profile stats per column, mapping confirmer + timestamp.
- **Edge cases:** 272-column SAP exports (profile in batches, propose only needed columns); duplicate header names; header not on row 1.
- **Test:** fixture with renamed columns → proposal matches saved mapping from a prior "confirmed" fixture.

### SK-003 load-to-database
- **Purpose:** Load mapped, cleaned data into the analytical store with quarantine.
- **Trigger:** Confirmed mapping exists for a staged table.
- **Inputs:** staged table + confirmed mapping.
- **Outputs:** clean DuckDB table, rejects file, load summary.
- **Tools:** existing `clean_actuals`/`clean_standards` (canonical parser, dup detection, qty validation).
- **Validation:** numeric/date cleaning gates; DB loading gate; duplicate gate.
- **Evidence:** counts at every stage, reject reasons breakdown.
- **Edge cases:** European/negative formats (parser handles: `(1,234.56)`, `1234.56-`); reject % above 5% threshold → stop and show samples.
- **Test:** `tests/test_nasty_data.py` pattern extended per dataset type.

### SK-004 reconcile-and-validate
- **Purpose:** Prove loaded data matches control totals before any analysis.
- **Trigger:** After every load; before every report.
- **Inputs:** clean table + control total source (SAP total row, prior report, owner-stated figure).
- **Outputs:** reconciliation statement (expected/actual/delta/tolerance/verdict).
- **Tools:** existing audit re-computation (`engines/audit/audit.py`) + SQL sums.
- **Validation:** reconciliation gate (0.01 tolerance); materiality escalation (>2% rejected value).
- **Evidence:** both totals, delta, tolerance, by-dimension drill if failed.
- **Edge cases:** control total itself includes the subtotal rows we quarantined (reconcile against detail-only recomputation and say so).
- **Test:** fixture where detail sums to control → pass; off-by-one fixture → gate fails with drill-down.

### SK-005 management-report
- **Purpose:** Produce the signed one-page management summary from validated numbers.
- **Trigger:** Owner asks for a report; reconciliation gate green.
- **Inputs:** validated tables, report-logic vault note, period.
- **Outputs:** report MD/HTML with provenance tags, sign-off record.
- **Tools:** existing variance/PVM engines + `serving/card.py`.
- **Validation:** report-generation gate (every number AUDITED); final-delivery gate.
- **Evidence:** evidence_id per number; sign-off row.
- **Edge cases:** a wanted number is unvalidated → report ships without it and says why, never with a CLAIMED value.
- **Test:** golden-report fixture — regenerated report matches expected numbers exactly.

# 21. Next Ten Expansion Skills

1. **pdf-evidence-extract** — pull cited tables/figures from PDFs into the evidence chain (existing engines/docs).
2. **hq-deck-brief** — Korean HQ PPTX → cited English one-page brief (exists; wrap as skill).
3. **inventory-exception-scan** — apply confirmed rules to inventory snapshots, list exceptions with value at risk.
4. **variance-driver-decomposition** — full price/volume/mix with narrative (exists; wrap as skill).
5. **period-close-pack** — chain intake→load→reconcile→reports for the monthly close in one run.
6. **rework-cost-analysis** — quantify rework by cause and repeat offender.
7. **email-evidence-intake** — .eml + attachments into the registry (exists; wrap).
8. **cross-period-comparison** — same report logic across periods with drift detection.
9. **data-quality-audit** — standalone profiling of any registered dataset against its history.
10. **decision-brief** — evidence-backed options brief for a named decision (exists; wrap).

Note: four of ten are wrapping already-tested engines — cheap wins.

# 22. End-to-End Factory Example

**Scenario:** SAP cost-center export `CC_ACTUALS_MAY.xlsx` (3 sheets, 41k rows, one sheet has
subtotal rows embedded, amounts include `1.234,56`-style values and `(...)` credits).

1. Owner drops the file in `datasets/inbox/` and says: *"May actuals — reconcile against the
   4,700k control total and give me the variance report vs budget."*
2. Agent drafts `runs/RUN-2026-07-03-004/contract.md`: goal, tier1, skills SK-001→005, expected
   output = cost variance report, DoD checklist. Owner replies "go" (low risk → no formal approval needed).
3. **SK-001:** SHA-256 `9f3a…` recorded; copy to `datasets/registered/9f3a_CC_ACTUALS_MAY.xlsx`;
   3 sheets found, `Data` sheet staged: 41,207 rows in.
4. **SK-002:** profile finds 38 columns; proposes mapping (KOSTL→cost_center, WKG001→amount…)
   using the saved mapping from April (vault note `mapping-cc-actuals`). Two new columns flagged;
   owner confirms in one message; mapping note updated.
5. **SK-003:** clean run — 40,988 kept, 219 rejected (183 subtotal rows, 29 duplicates,
   7 unparseable amounts → `runs/.../rejects/rejects.csv` with reasons). Conservation:
   41,207 == 40,988 + 219 ✓. Reject rate 0.53% — under the 5% threshold.
6. **SK-004:** SUM(amount) = 4,699,982.14 vs control 4,700,000 → delta 17.86 > 0.01 tolerance
   → **gate fails.** Drill-down: delta concentrated in the 7 unparseable-amount rows. Report to
   owner: "7 rows totaling ~18 couldn't be parsed (samples shown) — accept exclusion or fix source?"
   Owner: "accept, they're header junk." Acceptance recorded in contract; gate re-run against
   detail-recomputed control ✓.
7. Variance + PVM run on validated data; bridge reconciles to the cent.
8. **SK-005:** `reports/2026-07-03_cost-variance_CC-May.md` + HTML — 5 key numbers, all tagged
   AUDITED, drivers section from PVM, footer: what happened / why it matters / what to do next.
   Owner signs off; sign-off row written.
9. Evidence ledger now holds: fingerprint → sheet locators → mapping → stage counts →
   reject reasons → reconciliation deltas → report refs. Any number in the report traces back
   in one query.
10. Lesson capture: owner correction ("header junk rows") → lesson with run ID → proposal:
    add those header patterns to SK-003's junk detection + a test. Proposal sits in
    `approvals/pending/` — the owner approves next week, version 1.0.1, regression suite green.
11. Next month, the same run takes minutes: mapping is saved, junk pattern is handled, the
    contract is a template. **That compounding is the whole point.**

# 23. User Interface Recommendation

| Option | Verdict |
|---|---|
| CLI (raw) | Too hostile for a non-programmer as the primary surface. |
| Local web dashboard | Real maintenance burden (server, auth, bugs). Not MVP. Phase 5, and only as *generated static HTML*. |
| Obsidian vault | Excellent for READING memory, reports, approvals. Wrong for RUNNING tasks. |
| Desktop wrapper | Pure overhead at this stage. |

**MVP combination (decided):** **Claude Code chat as the control surface** (you already
operate it well — plain-English requests, contract confirmations, approvals by replying) **+
Obsidian on `vault/` + `reports/` + `approvals/` as the reading surface.** Two windows, zero
new software to build or maintain. Add generated static HTML dashboards in Phase 5 only if a
monthly report proves insufficient.

# 24. Build Roadmap

| Phase | Goal | Deliverables | Tools | Risks | Validation | Done when |
|---|---|---|---|---|---|---|
| 0 — Trustworthy skeleton | Folders, DB, schemas, templates exist and are linted | Folder tree (§7), foreman.db MVP tables, schemas/, templates/, registry stubs listing existing engines as tools | SQLite, JSON-schema linter test | Overbuilding — resist adding tables/folders beyond MVP list | New test: schemas validate, registry lints, DB opens | One fake run can be written end-to-end into the DB by hand |
| 1 — Excel-to-database MVP | SK-001…003 real | 3 SKILL.md + registry entries + tests; intake→map→load works on a real file | Existing ingest/clean/types | Mapping confirmation flow feels clunky — iterate wording | Skill tests + existing suite green | A real factory export loads with quarantine + confirmed mapping |
| 2 — Reporting & validation | SK-004, SK-005 real | Reconciliation skill, management report skill, evidence report | Existing audit/variance/serving | Wrong control totals blocking work | Golden-report test; reconciliation fixtures | Owner receives a signed report whose every number traces |
| 3 — Second brain & lessons | Vault + loop live | vault/ with note templates, admission gate, lesson capture, weekly curation habit | Obsidian, templates | Note bloat | Duplicate-check on save; monthly orphan report | 10 useful confirmed notes exist and got reused in a run |
| 4 — Factory analytics | Expansion skills 1,3,4,5,6 | Inventory exceptions, PVM wrap, period-close chain, rework analysis | Existing engines + new rules notes | Rule confirmation bottleneck — batch them | Per-skill tests + rule notes cited | Monthly close runs as one chained contract |
| 5 — Dashboard & UI | Static HTML views | Generated dashboards from report data (never recomputing) | serving/open_design | Scope creep to live server — forbidden | Checksum: dashboard values == report values | Owner opens one HTML file for the month at a glance |
| 6 — Multi-agent orchestration | Re-enable the team pipeline for scale | Writer/reviewer/gate roles per CLAUDE.md, cost logging per model | Existing agent definitions | Token spend; coordination overhead | Cost per run tracked and trending down | Two skills run in parallel with review gates, cheaper than solo |
| 7 — Advanced decision support | Decision briefs, cross-period intelligence | decision-brief skill, contradiction surfacing on numbers, what-if from validated models | brain/ modules | Overreach into ungoverned prediction | Every projection labeled and evidence-linked | Owner uses a brief in a real management decision |

# 25. Practical Build Tickets

| # | Title | Goal | Files | Acceptance criteria | Test | Pri | Difficulty (AI-assisted) |
|---|---|---|---|---|---|---|---|
| 1 | Foreman skeleton | Create folders + foreman.db MVP tables | folder tree, `registry/foreman.db`, `tools/init_db.py` | Folders exist; 8 MVP tables created; init idempotent | `test_foreman_db.py` — tables + rerun safe | P0 | Easy |
| 2 | Schemas + linter | Machine-check contracts/skills/tools | `schemas/*.json`, linter test | Invalid YAML/contract fails the test with a plain message | `test_registry_lint.py` | P0 | Easy |
| 3 | Templates pack | All templates ready | `templates/SKILL.md`, `RUN_CONTRACT.md`, `MANAGEMENT_REPORT.md`, `LESSON.md` | Each renders with a filled example | manual + lint | P0 | Easy |
| 4 | Fingerprint + register tool | Never analyze an unregistered file | `tools/fingerprint.py` (thin, calls hashlib) | SHA-256 + copy to registered/; re-register detects same hash | `test_fingerprint.py` | P0 | Easy |
| 5 | Tool manifest of existing engines | Passport the hands we already have | `registry/tools.yaml` (≈10 entries) | Every entry's engine_path imports; read_only flags accurate | `test_tools_manifest.py` | P0 | Easy |
| 6 | SK-001 excel-intake | First real skill | `skills/excel-intake/SKILL.md` + registry row + test | Real file → staged + rejects + evidence rows in DB | `test_skill_excel_intake.py` | P1 | Medium |
| 7 | SK-002 profile & map | Mapping with memory | skill files + mapping save/load | April mapping auto-proposed for May file | `test_skill_column_map.py` | P1 | Medium |
| 8 | SK-003 load-to-db | Clean load with quarantine | skill files (wraps clean.py) | Nasty fixture → correct quarantine, conservation | extends `test_nasty_data.py` | P1 | Medium |
| 9 | Run + evidence writer | Every step recorded | `tools/run_logger.py` | A skill run produces runs/run_steps/evidence rows | `test_run_logging.py` | P1 | Medium |
| 10 | SK-004 reconcile | The trust gate | skill files (wraps audit) | Delta fixtures: pass, fail-with-drilldown | `test_skill_reconcile.py` | P1 | Medium |
| 11 | SK-005 management report | The payoff | skill files (wraps serving) | Golden report matches; CLAIMED numbers refused | `test_skill_mgmt_report.py` | P1 | Medium |
| 12 | Approval queue | Owner's inbox | `approvals/` convention + helper | Request file created; decision recorded to DB | `test_approvals.py` | P2 | Easy |
| 13 | Lesson capture | Improvement engine v1 | `templates/LESSON.md` flow + lessons table writes | Run without lesson row can't be marked done | `test_lesson_gate.py` | P2 | Easy |
| 14 | Vault seed | Second brain v1 | `vault/index.md` + note templates + 5 seed notes | Obsidian opens it; links resolve | manual drill | P2 | Easy |
| 15 | Cost log | Token accounting | `logs/model_calls.csv` convention | Every run row has est_tokens filled | spot audit | P2 | Easy |

# 26. MVP File Pack

Content outlines for the exact starter files:

- **config/settings.yaml** — privacy: default_tier: tier1, cloud_allowed_types: [hq_pptx]; thresholds: reject_warn 0.05, materiality 0.02, recompute_tolerance 0.01 (mirror existing config.yaml, don't fork values — reference it); paths: inbox, registered, reports; model_routing: see §27 table as YAML.
- **registry/skills.yaml** — the 5 MVP skills in §9's schema, statuses `active`.
- **registry/tools.yaml** — ~10 passports for existing engines (§11 schema): fingerprint, ingest_spreadsheet, profile/types, clean_actuals, clean_standards, price_volume_mix, audit recompute, render_card, extract_document, backup.
- **schemas/run_contract.schema.json** — required: task_id, user_goal, sensitive_data_level, selected_skills, risk_level, definition_of_done.
- **schemas/skill.schema.json** — §9 fields, enums for domain/risk, semver pattern for version.
- **schemas/tool.schema.json** — §11 fields, read_only_or_write enum, engine_path pattern.
- **templates/SKILL.md** — §10 verbatim.
- **templates/RUN_CONTRACT.md** — §12 verbatim.
- **templates/MANAGEMENT_REPORT.md** — BLUF; 5 key numbers (table: value, vs baseline, provenance tag, evidence_id); drivers; risks; actions; confidence + sign-off block; 3-line footer.
- **templates/LESSON.md** — the 11 questions of §18 as headings with "n/a allowed" noted.
- **vault/index.md** — map of content: links to note-type folders, the 5 seed notes, "how to read this vault in 5 minutes" for the owner.
- **README.md** — what FOREMAN is (10 lines), the two-window workflow (Claude Code + Obsidian), where things live, the four approval types, how to start a run, how to restore from backup.

# 27. Model Usage Strategy

| Work | Use | Why |
|---|---|---|
| Architecture, hard multi-step reasoning, complex document understanding, run-contract synthesis for novel tasks | Fable 5 | Highest capability; used sparingly — it's the expensive foreman, not the crew |
| Implementation, refactoring, test writing | Claude Code (Sonnet/Opus) or Codex | Strong code agents; cheaper per unit of code than Fable reasoning |
| Classification, summaries, routine cleanup, lesson drafting | Cheaper models (Haiku/DeepSeek) | Quality sufficient; volume work |
| Extraction, math, validation, reconciliation | Local Python tools ONLY | Determinism is the point — no model does arithmetic here |
| Sign-off, rule confirmation, approvals, ambiguous mappings | Human (owner) | Judgment and accountability can't be delegated |

**Privacy rules (binding, order matters):** (1) classify tier BEFORE choosing any model;
(2) Tier-1 factory data never reaches any cloud model — local tools produce schemas,
profiles, and aggregates, and the agent reasons over those; (3) Tier-2 (HQ workflow decks)
may go to cloud per the standing owner decision D14 — every send gets a ledger entry;
(4) anything leaving the machine goes through `exports/` so there is exactly one door to
watch; (5) when tier is uncertain, it's Tier-1 until the owner says otherwise.
**Fallback:** if the primary model refuses or is unavailable, fall back per routing table —
but a fallback NEVER changes the privacy tier of the data.

# 28. Risk Register

| Risk | Impact | Early warning | Prevention | Recovery |
|---|---|---|---|---|
| Hallucinated mapping | Wrong numbers everywhere downstream | Mapping proposed with no similar-dataset precedent | Mapping gate: owner confirms; saved mappings reused | Re-map, re-load, regenerate; lesson + test |
| Wrong calculations | Bad management decisions | Reconciliation deltas, PVM not summing | Deterministic tools + reconciliation gates + audit recompute | Gate already blocks release; fix, add regression test |
| Over-trusting AI | Silent quality decay | Owner stops reading evidence sections | Provenance tags on every number; monthly evidence drill (trace 2 random numbers) | Re-audit recent reports |
| Messy Excel formats | Rejects spike or wrong parses | Reject % rising; new source system | Profile-before-map gate; canonical parser; nasty-data tests | Quarantine + owner review of samples |
| Duplicate memory | Vault becomes noise | Same topic in 3 notes | Admission rules; duplicate check; weekly curation | Merge notes, mark superseded |
| Skill bloat | Routing confusion, maintenance drag | >25 active skills; skills with 0 runs in 90 days | ≥2-lesson evidence to create; cap with archive-one rule | Archive unused skills (keep in git) |
| Tool failure | Runs blocked | Same failure_mode recurring in logs | failure_modes documented; loud errors with plain guidance | Fallback per manifest or human path |
| Slow performance | Owner stops using it | Runs >30 min for routine work | Existing engines are fast; avoid full-file loads (Golden Rule) | Profile the slow step; move work into DuckDB |
| User confusion | Abandonment | Owner asks "where is X?" twice | Fixed locations; 3-line footers; README drill | Simplify; add a vault "how to find things" note |
| Bad reports | Lost credibility with management | Sign-off hesitation; corrections after delivery | Golden-report tests; report gate; owner sign-off | Correct + evidence report showing exactly what changed |
| Unapproved file changes | Data loss, trust loss | Any write outside runs//exports/ in logs | Read-only manifest flags; sources never edited; registered copies | Restore from original (never touched) + backup |
| Sensitive data leakage | Serious business harm | Ledger entry missing for an external call | One exit door (exports/), tier check before model choice, ledger CI check | Incident note; rotate anything exposed; tighten gate |
| Overengineering | Months with no value | Building Phase-5 items in Phase 1 | Roadmap discipline; "does it help the first useful version?" test | Freeze features; ship the current phase |
| No adoption | Everything above is moot | Owner reverts to manual Excel work | MVP targets a real monthly pain (the close); wins in days | Cut scope to the one report that matters most |

# 29. Evaluation Scorecard

Monthly, from the DB — no self-grading essays:

| Metric | Source | Target trend |
|---|---|---|
| Task completion rate | runs: done / started | >90% |
| Token cost per routine run | logs/model_calls.csv per run type | Falling month-over-month for repeat runs |
| Time per monthly close | run timestamps | Falling, then stable |
| Report accuracy | corrections-after-signoff count | → 0 |
| Validation pass rate (first try) | validation_results | Rising (skills learning) |
| Memory usefulness | notes referenced by later runs / total notes | >30% referenced within 90 days |
| Skill reuse | runs per skill | Top skills weekly; zero-use skills flagged |
| Owner understanding | monthly drill: trace a number, find an approval | Pass in <5 min |
| Failure recurrence | same lesson category repeating after a fix | → 0 (a repeat after fix = regression alarm) |
| Data safety | external sends without ledger entry | Always 0 (hard fail) |

# 30. Final MVP Recommendation

**Build in the next days, in this order (tickets 1–11):**

One project folder (the existing `G:\AI` extended per §7) · one control surface (Claude Code
chat — already in place) · **five skills** (excel-intake, column-profile-and-map,
load-to-database, reconcile-and-validate, management-report — mostly wrapping tested
engines) · **one SQLite DB** (`registry/foreman.db`, 8 MVP tables) · **one vault**
(`vault/` in Obsidian with index + 5 seed notes) · **one report template**
(MANAGEMENT_REPORT.md) · **one validation log** (validation_results table + gate messages) ·
**one lesson workflow** (LESSON.md after every run, weekly 15-min curation) · **one evidence
ledger** (evidence_items + fingerprints).

**The MVP is done when:** you drop one real factory export into `datasets/inbox/`, say what
you want, confirm a one-screen contract, and receive a signed management report where every
number traces to a fingerprinted file — with the run, gates, evidence, and one lesson all
recorded. That is achievable within days because the engines already exist and are tested;
what's being built is the governance shell around them.

# 31. Final Architect Review

Six perspectives were applied; conclusions only:

- **Product architect:** Practical — the largest de-risking move is reusing Factory Brain's
  engines; new build is thin (DB, contracts, vault, 5 skill docs). Complexity budget respected:
  16 tables *defined*, 8 *built*; 17 folders but 6 matter in month one.
- **Data engineer:** Token savings are structural, not aspirational: saved mappings, contract
  templates, and vault rules mean repeat runs re-explain nothing; cost log makes the claim
  measurable. Biggest technical risk (Excel chaos) is fronted by the profile-before-map gate
  and the already-hardened parser.
- **Factory finance expert:** Reconciliation-before-reporting and refuse-CLAIMED-numbers are
  the two rules that make this usable with a real CFO. The reject-acceptance flow (step 6 of
  §22) matches how closes actually go.
- **Non-programmer advocate:** Two windows (chat + Obsidian), four approval types, fixed
  locations, 3-line footers — operable. Watch item: mapping confirmation wording; iterate it
  in Phase 1 with the real user.
- **Security/privacy reviewer:** Tier-before-model ordering, one exit door (exports/), ledger
  CI check, and untouched originals close the main leak paths. Residual risk: owner pasting
  raw data into chat manually — mitigated by habit + README warning, not technically closable.
- **QA reviewer:** Every layer has a named validation method; skills ship with tests; the
  lesson→test rule (§18 Q8) turns corrections into permanent regression protection. Verdict:
  the system prevents skill/code drift better than the original idea did.

**Net verdict:** buildable by a non-programmer directing AI agents, useful within days on the
first real export, expandable without redesign, and honest about its two hard dependencies —
the owner's weekly curation habit, and the discipline to not build Phase 5 before Phase 1.
