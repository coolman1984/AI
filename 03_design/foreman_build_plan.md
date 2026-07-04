---
status: ACTIVE-PLAN
owner: owner
date: 2026-07-03
---

# FOREMAN — Build Plan (code-writer execution order)

*Companion to [skill_os_blueprint.md](skill_os_blueprint.md). The blueprint is the WHY and
the design; this file is the HOW and the ORDER. A code-writer agent should execute steps
top-to-bottom. Each step is self-contained: it names the exact files, the existing engine to
reuse, the behavior to implement, the test to write, and the command that proves it done.*

Source of truth for design decisions stays in the blueprint. If this plan and the blueprint
disagree, the blueprint wins — flag it, don't guess.

---

## How to work this plan (read once, obey every step)

**Conventions**
- Work one step at a time, in order. Do not start a step until the previous step's test is green.
- New FOREMAN folders/files live alongside the existing repo (see blueprint §7). **Never edit
  the existing `engines/`, `serving/`, `gov/`, `shared/` code** except where a step explicitly says so.
- New skill folders go under `skills/` using the blueprint §10 template. The existing
  `.claude/skills/*/*.md` files are the canonical agent-facing skill library — they are
  governed by `tests/test_skill_contracts.py` and must keep passing. FOREMAN skills are
  a separate executable set under `skills/` with their own linter.
- Every tool the plan references already exists in `engines/`. The plan mostly *wraps* them;
  it rarely writes new computation. If you find yourself writing math, stop — a tool already does it.

**Guardrails (non-negotiable, from AGENTS.md)**
- Source files in `datasets/inbox/` are read-only. Register (copy + fingerprint) before touching.
- Numbers come only from tools, never invented. Nothing vanishes silently — rejects go to a file.
- Commit only when the full suite is green. One branch `main`. Commit only when the owner asks.

**Verify commands (run after every step)**
```bash
python -m pytest -q          # full suite must stay green (285 passing at plan start)
ruff check .                 # style must pass
python -m pytest tests/<the-new-test-for-this-step>.py -q   # the step's own test
```

**Definition of done for a step:** its named test is green AND the full suite is still green
AND `ruff` is clean. Not before.

---

# PHASE 0 — Trustworthy skeleton

**Goal:** the folders, database, schemas, templates, and registries exist and are machine-checked.
No business logic yet. **Done when** a fake run can be written end-to-end into the DB by hand and
the registry/schema linters pass.

### Step 0.1 — Create the folder tree
- **Create:** the FOREMAN folders from blueprint §7 that don't yet exist:
  `skills/`, `tools/`, `runs/`, `reports/`, `vault/`, `lessons/`, `schemas/`, `templates/`,
  `dashboards/`, `datasets/inbox/`, `datasets/registered/`, `logs/`, `approvals/pending/`,
  `approvals/decided/`, `registry/`, `evidence/`, `exports/`, `config/` (config.yaml already exists at root — leave it).
- Each folder gets a `.gitkeep` and a one-line `README.md` stating what it holds (from §7).
- Add `datasets/registered/`, `runs/`, `reports/`, `logs/`, `exports/`, `evidence/`,
  `approvals/`, `registry/*.db` to `.gitignore` (they hold run data / possibly sensitive copies).
- **Acceptance:** all folders exist; git ignores the data folders; `vault/`, `skills/`,
  `templates/`, `schemas/`, `registry/*.yaml` are tracked.
- **Test:** `tests/test_foreman_skeleton.py::test_folders_exist` — asserts each expected folder present.
- **DoD:** test green.

### Step 0.2 — SQLite schema + init tool
- **Create:** `tools/foreman_db.py` with `init_db(path="registry/foreman.db") -> sqlite3.Connection`.
- Implement **only the 8 MVP tables** from blueprint §8 (marked [MVP]): `runs`, `run_steps`,
  `evidence_items`, `validation_results`, `reports`, `lessons`, `approvals`, `file_fingerprints`.
  Use the key fields listed in §8. `init_db` must be **idempotent** (`CREATE TABLE IF NOT EXISTS`).
- Add a `schema_version` PRAGMA/meta row so later phases can migrate safely.
- **Acceptance:** calling `init_db` twice on the same file does not error and does not duplicate tables.
- **Test:** `tests/test_foreman_db.py` — tables exist after init; second init is a no-op; can
  insert+read one `runs` row and one linked `run_steps` row.
- **DoD:** test green.

### Step 0.3 — JSON schemas + registry linter
- **Create:** `schemas/run_contract.schema.json`, `schemas/skill.schema.json`,
  `schemas/tool.schema.json` from blueprint §9/§11/§12 field lists (JSON Schema draft-2020-12,
  `required` on the mandatory fields; enums for `domain`, `risk_level`, `read_only_or_write`;
  semver pattern for `version`).
- **Create:** `tools/registry_lint.py` with `lint() -> list[str]` (returns human-readable
  problems, empty = clean). It validates `registry/skills.yaml` and `registry/tools.yaml`
  against the schemas AND checks cross-references: every `allowed_tools` id exists in
  `tools.yaml`; no two skills share a trigger; every tool `engine_path` is importable.
- **Acceptance:** a deliberately broken fixture registry produces a specific, plain-English error.
- **Test:** `tests/test_registry_lint.py` — clean registry → no errors; broken fixture → the
  expected error string.
- **DoD:** test green.

### Step 0.4 — Templates pack
- **Create:** `templates/SKILL.md` (blueprint §10 verbatim), `templates/RUN_CONTRACT.md` (§12),
  `templates/MANAGEMENT_REPORT.md` (§26 outline), `templates/LESSON.md` (§18's 11 questions as
  headings, each marked "n/a is an acceptable answer").
- **Acceptance:** each template contains its required section headings.
- **Test:** `tests/test_templates_present.py` — each template file exists and contains its
  mandatory headings (Purpose/Workflow/Validation for SKILL.md; Definition of done for RUN_CONTRACT.md; etc.).
- **DoD:** test green.

### Step 0.5 — Tool manifest of existing engines
- **Create:** `registry/tools.yaml` with passports (blueprint §11 schema) for the ~10 engines
  the MVP uses. Minimum set with accurate `engine_path`:
  - `T-FP-001` fingerprint → `tools/fingerprint.py::fingerprint_file` (built in Step 1.1)
  - `T-ING-001` ingest → `engines/data/ingest.py::ingest_spreadsheet`
  - `T-PROF-001` type inference → `engines/data/types.py::infer_column_types`
  - `T-CLEAN-ACT` → `engines/data/clean.py::clean_actuals`
  - `T-CLEAN-STD` → `engines/data/clean.py::clean_standards`
  - `T-PVM-001` → `engines/data/variance.py::price_volume_mix`
  - `T-DRV-001` → `engines/data/drivers.py::run_variance_decomposition`
  - `T-AUDIT-001` → `engines/audit/audit.py::audit_card`
  - `T-CARD-001` → `engines/serving/card.py::make_manager_card` (path: `serving/card.py`)
  - `T-DOC-001` → `engines/docs/extract.py::extract_document`
- Mark `read_only_or_write` accurately (ingest/clean WRITE to DuckDB staging only; card/audit read).
- **Acceptance:** `registry_lint()` passes; every `engine_path` imports without error.
- **Test:** covered by `tests/test_registry_lint.py` (extend to import-check each engine_path).
- **DoD:** test green.

### Step 0.6 — Skills registry stub + FOREMAN skill linter
- **Create:** `registry/skills.yaml` with the 5 MVP skill entries (blueprint §9 schema),
  `status: proposed` for now (they become `active` as each is built in Phase 1–2).
- **Create:** `tools/skill_lint.py` — for each `skills/<name>/SKILL.md`, assert it has the §10
  sections and that every tool it names is in `tools.yaml`. This is SEPARATE from the existing
  `tests/test_skill_contracts.py` (which governs `.claude/skills/*/` — do not modify that).
- **Test:** `tests/test_foreman_skill_lint.py` — passes on a valid seed skill folder, fails on
  a skill referencing an unknown tool.
- **DoD:** test green. **Phase 0 done when all of 0.1–0.6 are green and the full suite is green.**

---

# PHASE 1 — Excel-to-database MVP

**Goal:** skills SK-001, SK-002, SK-003 are real. **Done when** a real factory export loads
into the analytical store with quarantine and an owner-confirmed column mapping, every step
recorded in `foreman.db`.

### Step 1.1 — Fingerprint + register tool
- **Create:** `tools/fingerprint.py::fingerprint_file(path) -> dict` returning
  `{sha256, size_bytes, original_path}`; and `register_file(path, db) -> dict` that copies the
  file to `datasets/registered/<sha8>_<name>` (never moves/edits the original) and writes a
  `file_fingerprints` row. Re-registering the same bytes returns the existing row (dedup on sha256).
- **Acceptance:** same file registered twice → one fingerprint row, same registered path;
  the original in `inbox/` is byte-identical before and after.
- **Test:** `tests/test_fingerprint.py`.
- **DoD:** test green.

### Step 1.2 — Run logger (shared plumbing for all skills)
- **Create:** `tools/run_logger.py` with a small API: `start_run(db, contract) -> run_id`,
  `log_step(db, run_id, seq, tool_id, params, status, output_path) -> step_id`,
  `log_evidence(db, run_id, step_id, source_fingerprint, locator, method, value_or_summary)`,
  `log_validation(db, run_id, gate_name, rule_ref, passed, expected, actual, message)`,
  `finish_run(db, run_id, status, outcome_summary, model_calls_count=0, est_tokens=0)`.
- These write the §8 tables. Every subsequent skill uses this — no skill writes SQL directly.
- **Acceptance:** a scripted run produces one `runs` row + N `run_steps` + evidence + validation rows.
- **Test:** `tests/test_run_logging.py`.
- **DoD:** test green.

### Step 1.3 — SK-001 excel-intake
- **Create:** `skills/excel-intake/SKILL.md` (from §10 template, content from blueprint §20 SK-001)
  and `skills/excel-intake/run.py::run_excel_intake(inbox_path, db, con) -> dict`.
- **Behavior:** register+fingerprint (Step 1.1) → `ingest_spreadsheet` (T-ING-001, `on_duplicates=flag`)
  → write evidence (fingerprint, sheet list, rows_in/kept/rejected) via run_logger → return summary.
- **Reuse:** `engines/data/ingest.py::ingest_spreadsheet`. Do NOT reimplement ingestion.
- **Gates:** fingerprint gate (file registered), conservation gate (rows_in == kept + rejected —
  already asserted inside the engine; surface it as a `validation_results` row).
- **Edge cases to handle explicitly:** file locked/open in Excel → catch and return a plain
  "close the file in Excel and retry" message (do not crash); multi-sheet workbook; empty sheet.
- **Test:** `tests/test_skill_excel_intake.py` — fixture workbook containing one total row, one
  duplicate, one junk amount → exactly those quarantined; conservation holds; evidence + run
  rows written; registry entry flips to usable. Set SK-001 `status: active` in `skills.yaml`.
- **DoD:** test green; full suite green.

### Step 1.4 — SK-002 column-profile-and-map
- **Create:** `skills/column-profile-and-map/SKILL.md` + `run.py::run_profile_and_map(table, db, con, prior_mapping=None) -> dict`.
- **Behavior:** profile each column (dtype via `infer_column_types`, null %, sample values,
  suspected key) → propose canonical mapping → if a `column_mappings`-style prior exists for a
  similar dataset, pre-fill from it → return proposal for owner confirmation. On confirmation,
  persist the mapping (blueprint §8 `column_mappings` — add this table now if not present, it's
  a Phase-1 need) and write a vault mapping note stub.
- **Reuse:** `engines/data/types.py::infer_column_types`.
- **Gate:** column-mapping gate — every required canonical column mapped, no source column mapped
  twice; mapping is not "confirmed" until an owner confirmation is recorded.
- **Edge cases:** 272-column SAP export → profile in batches, propose only the columns the target
  lens needs; duplicate header names; header not on row 1.
- **Test:** `tests/test_skill_column_map.py` — fixture with renamed columns + a saved prior
  mapping → proposal matches the prior. Set SK-002 `status: active`.
- **DoD:** test green; full suite green.

### Step 1.5 — SK-003 load-to-database
- **Create:** `skills/load-to-database/SKILL.md` + `run.py::run_load_to_database(table, mapping, db, con) -> dict`.
- **Behavior:** apply confirmed mapping → `clean_actuals` (or `clean_standards` for standards
  data) with `qty_col` when present → write rejects file to `runs/<id>/rejects/` → load clean
  table into DuckDB → record counts at every stage.
- **Reuse:** `engines/data/clean.py::clean_actuals` / `clean_standards` (canonical parser, dup
  detection, qty quarantine — all already hardened 2026-07-03). Do NOT reparse numbers.
- **Gates:** numeric/date cleaning, DB loading (loaded == cleaned), duplicate (below 5% or stop
  and show samples). Reject rate over threshold → stop, surface samples, do not silently proceed.
- **Test:** extend the `tests/test_nasty_data.py` pattern into `tests/test_skill_load_db.py` —
  nasty fixture → correct quarantine, conservation, reject-rate gate fires above threshold.
  Set SK-003 `status: active`.
- **DoD:** test green; full suite green. **Phase 1 done when 1.1–1.5 green and full suite green.**

---

# PHASE 2 — Reporting and validation

**Goal:** SK-004, SK-005 real. **Done when** the owner receives a signed management report whose
every number traces to a fingerprinted source.

### Step 2.1 — SK-004 reconcile-and-validate
- **Create:** `skills/reconcile-and-validate/SKILL.md` + `run.py::run_reconcile(clean_table, control_total, db, con) -> dict`.
- **Behavior:** compute SUM(amount) via SQL → compare to control total (SAP total row / prior
  report / owner-stated figure) within 0.01 tolerance → on fail, drill down by dimension and
  surface where the delta sits → apply materiality escalation (>2% rejected value).
- **Reuse:** `engines/audit/audit.py` recomputation pattern (independent DuckDB SQL sum, the
  four-eyes engine) + SQL sums.
- **Gate:** reconciliation gate. If the control total itself includes quarantined subtotal rows,
  reconcile against a detail-only recomputation and SAY SO in the evidence.
- **Test:** `tests/test_skill_reconcile.py` — matching fixture passes; off-by-one fixture fails
  the gate WITH a by-dimension drill-down in the result. Set SK-004 `status: active`.
- **DoD:** test green; full suite green.

### Step 2.2 — SK-005 management-report
- **Create:** `skills/management-report/SKILL.md` + `run.py::run_management_report(validated_tables, lens, period, db, con) -> dict`.
- **Behavior:** run variance + PVM → build the manager card → render report to
  `reports/<date>_<type>_<topic>.md` (+ HTML) with provenance tags → require a sign-off record.
- **Reuse:** `engines/data/variance.py` / `drivers.py::run_variance_decomposition`,
  `serving/card.py::make_manager_card`, existing HTML render in `serving/open_design.py`.
- **Gate:** report-generation gate — every number carries an evidence_id and is tagged AUDITED;
  a wanted-but-unvalidated number is OMITTED with a stated reason, never rendered as CLAIMED.
  Final-delivery gate — the contract's definition-of-done checklist all checked.
- **Test:** `tests/test_skill_mgmt_report.py` — golden fixture: regenerated report's numbers
  match expected exactly; an injected CLAIMED number is refused/omitted. Set SK-005 `status: active`.
- **DoD:** test green; full suite green.

### Step 2.3 — Approval queue
- **Create:** `tools/approvals.py::request_approval(db, run_id, type, request_md) -> approval_id`
  (writes a file to `approvals/pending/` and an `approvals` row) and
  `decide_approval(db, approval_id, decision, decided_by)` (moves file to `approvals/decided/`,
  records decision). Only the four types from §19: external_send, skill_promotion, write_action,
  sensitive_memory.
- **Test:** `tests/test_approvals.py` — request creates file+row; decide moves file + records.
- **DoD:** test green.

### Step 2.4 — End-to-end MVP run
- **Create:** `tools/run_foreman.py` — a thin driver that takes an inbox file + a plain-English
  goal, drafts a run contract into `runs/<id>/contract.md`, and chains SK-001→SK-005, stopping
  at any failed gate with a plain message.
- **Acceptance:** the blueprint §22 scenario runs on a synthetic SAP-shaped fixture end-to-end:
  contract → fingerprint → profile/map → load+quarantine → reconcile → signed report → evidence
  chain complete → lesson prompt.
- **Test:** `tests/test_foreman_end_to_end.py` — the full chain on a fixture produces a report
  whose every number resolves to an evidence_item and a fingerprint.
- **DoD:** test green; full suite green. **Phase 2 done → MVP is usable.**

---

# PHASE 3 — Second brain and lessons

**Goal:** vault + lesson loop live and curated. **Done when** ~10 confirmed vault notes exist and
at least one was reused by a later run.

- **Step 3.1 — Vault seed:** `vault/index.md` + note-type templates (§16) + 5 seed notes
  (one business rule, one dataset, one column mapping, one KPI, one glossary term).
  Test: Obsidian-style link resolver — no broken `[[links]]` in seed notes.
- **Step 3.2 — Memory admission gate:** `tools/memory_gate.py` enforcing §17 (evidence required;
  duplicate-title/topic check; sensitive-data → approval). Test: duplicate note rejected;
  unevidenced note rejected; sensitive note routed to approvals.
- **Step 3.3 — Lesson capture:** after every run, write `lessons/RUN-<id>.md` from `templates/LESSON.md`;
  a run cannot be marked `done` without a lesson row (even "nothing notable"). Test: lesson gate.
- **Step 3.4 — Weekly curation helper:** `tools/curate_lessons.py` lists `raw` lessons and lets
  the owner promote/merge/reject (status recorded). Test: promotion writes a vault note + flips status.

---

# PHASE 4 — Factory analytics modules

**Goal:** expansion skills that wrap existing engines. **Done when** the monthly close runs as one
chained contract. Build in this order (each is one step, same shape as Phase 1 skills):

1. `period-close-pack` — chain intake→load→reconcile→reports for the whole close in one run.
2. `variance-driver-decomposition` — wrap `run_variance_decomposition` with narrative.
3. `inventory-exception-scan` — apply confirmed rule notes to an inventory snapshot.
4. `rework-cost-analysis` — rework qty/cost by cause + repeat offenders.
5. `cross-period-comparison` — same report logic across periods with drift detection.

Each: SKILL.md + run.py + a golden/fixture test + registry entry. Rules live as vault
business-rule notes cited by the skill (never hardcoded thresholds).

---

# PHASE 5 — Dashboard and UI

**Goal:** a single static HTML the owner opens for the month at a glance. **Done when** dashboard
values are byte-identical to the source report (checksum test).

- **Step 5.1:** `tools/build_dashboard.py` — reads an existing report's validated data (never
  recomputes) and renders static HTML into `dashboards/`. Reuse `serving/open_design.py`.
- **Step 5.2:** checksum gate — dashboard numbers == report numbers exactly. Test enforces it.
- Forbidden: a live server. Static files only.

---

# PHASE 6 — Multi-agent orchestration (only when the owner re-enables the team)

**Goal:** re-enable the CLAUDE.md write→review→gate pipeline for scale, with per-model cost logging.
**Done when** two skills run in parallel with review gates, cheaper (logged tokens) than solo.
*Currently the owner has the team paused — do not build this until told.*

- Cost log: `logs/model_calls.csv` — every model call records model, run_id, est_tokens.
- Wire writer/reviewer/gate roles per CLAUDE.md; the scorecard (§29) reads the cost log.

---

# PHASE 7 — Advanced decision support

**Goal:** evidence-backed decision briefs and cross-period intelligence.
- `decision-brief` skill wrapping `serving/decision_brief.py`.
- Contradiction surfacing on numbers (`engines/brain/contradictions.py`).
- Every projection labeled and evidence-linked; nothing ungoverned.

---

## Progress tracking

Mirror these steps into `00_control/task_queue.md` as rows (ID `FM-0.1`…`FM-7.x`) so status is
tracked with the rest of the project. A step is `Passed` only when its test is green AND the full
suite is green — same evidence rule the rest of the queue uses.

**Start here:** Phase 0, Step 0.1.
