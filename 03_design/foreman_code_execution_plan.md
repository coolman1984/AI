# FOREMAN — Code Execution Plan (reviewed and guard-railed)

**Companion to:** `foreman_build_plan.md` (the WHAT) and `skill_os_blueprint.md` (the WHY).  
This document is the **HOW and the ORDER for writing the code**, reviewed using Tier 1/Tier 2 skills before delivery.

---

## Tier 1 and Tier 2 skills applied to this plan

| Skill | How used |
|---|---|
| `software-development-lifecycle` | Overall lifecycle framework |
| `planning-and-task-breakdown` | Task decomposition, dependency mapping, sizing |
| `code-review-and-quality` | Plan self-review across 5 axes |
| `spec-driven-development` | Phase 0 spec-first approach |
| `incremental-implementation` | One slice at a time, keep green |
| `context-engineering` | Project context anchoring |
| `action-first-operator-reporting` | Concise reporting style |

---

## GUARDRAILS (non-negotiable — read before starting any step)

### Project-level guardrails (from AGENTS.md and blueprint)

1. **Never edit existing engines.** `engines/`, `serving/`, `gov/`, `shared/`, `mcp_server/`, `ops/` are read-only. FOREMAN *wraps* them, never rewrites them.
2. **Never edit existing agent skills.** `agent_skills/*.md` stay untouched. `tests/test_skill_contracts.py` governs them and must keep passing.
3. **Numbers from tools only.** Never invent, guess, or synthesize a number. Every value must trace to a tool call.
4. **Source files are read-only.** `datasets/inbox/` files are never edited. Registration copies + fingerprints them.
5. **Full suite must stay green.** `python -m pytest -q` must pass after every step. Ruff must pass.
6. **One commit, one branch** (main). Commit only when the full suite is green and the owner asks.
7. **No data in git.** `datasets/registered/`, `runs/`, `reports/`, `logs/`, `exports/`, `evidence/`, `approvals/`, `registry/*.db` are gitignored.

### Execution guardrails (from incremental-implementation skill)

8. **One step at a time.** Do not start step N+1 until step N's test is green AND the full suite is green.
9. **Write the test first or confirm existing test covers it.** Every step has a named test.
10. **Do not scope-creep.** Touch only what the step specifies. "While I'm here" fixes are forbidden.
11. **Verify after every file write.** Read the file back to confirm it was written correctly.
12. **Do not reimplement existing code.** Before writing a new tool, check if it already exists in `engines/`.
13. **When stuck, stop and ask.** Never guess an API signature or engine path — read the source.

### Plan-review guardrails (from code-review-and-quality skill)

14. **Every task must fit ~5 files.** If a step needs more, split it further.
15. **Every acceptance criterion must be testable.** Not "works well" — "test passes".
16. **No silent failures.** Every error path produces a plain-English message.
17. **Simplicity first.** If you can do it in fewer files with less code, do that.

---

## THE PLAN

### Phase 0: Trustworthy skeleton (6 steps)

**Phase goal:** Folders, database, schemas, templates, and registries exist and are machine-checked.  
**Phase guardrail:** No business logic yet. Phase 0 is scaffold only.  
**Phase done when:** A fake run can be written end-to-end into the DB by hand and registry/schema linters pass.

---

#### Step 0.1 — Create the folder tree

**What to do:**
1. Create FOREMAN folders under `G:\AI\` that don't yet exist: `skills/`, `tools/`, `runs/`, `reports/`, `vault/`, `lessons/`, `schemas/`, `templates/`, `dashboards/`, `datasets/inbox/`, `datasets/registered/`, `logs/`, `approvals/pending/`, `approvals/decided/`, `registry/`, `evidence/`, `exports/`, `config/`
2. Each folder gets a `.gitkeep` and a one-line `README.md` stating what it holds
3. Add `datasets/registered/`, `runs/`, `reports/`, `logs/`, `exports/`, `evidence/`, `approvals/`, `registry/*.db` to `.gitignore`
4. Ensure `vault/`, `skills/`, `templates/`, `schemas/`, `registry/*.yaml` are tracked (not in gitignore)

**Files to create:**
- `G:\AI\skills\.gitkeep` + `skills\README.md`
- `G:\AI\tools\.gitkeep` + `tools\README.md`
- ... (all folder READMEs + gitkeeps)
- Update `G:\AI\.gitignore` to exclude the run-data folders

**What NOT to touch:**
- `engines/`, `serving/`, `gov/`, `shared/`, `mcp_server/`, `ops/`
- `agent_skills/`
- Existing `tests/`
- Existing root files (`config.yaml`, `AGENTS.md`, `CLAUDE.md`, `AGENT_CORE_CONTRACT.md`, etc.)

**Exact test:** `pytest tests/test_foreman_skeleton.py::test_folders_exist`
- Create this test FIRST (it will fail until folders exist, then pass)
- Assert each expected folder exists

**Verification:** `ruff check . && python -m pytest -q && python -m pytest tests/test_foreman_skeleton.py -q`

**Guard:** Do not delete or restructure any existing folder. FOREMAN folders are ADDITIONS only.

---

#### Step 0.2 — SQLite schema + init tool

**What to do:**
1. Create `G:\AI\tools\foreman_db.py` with `init_db(path)` that creates 8 MVP tables: `runs`, `run_steps`, `evidence_items`, `validation_results`, `reports`, `lessons`, `approvals`, `file_fingerprints`
2. Only the key fields from blueprint §8 (MVP tables only). Use `CREATE TABLE IF NOT EXISTS` for idempotency.
3. Add a `schema_version` meta row

**Files to create:**
- `G:\AI\tools\foreman_db.py` — `init_db()` function, 8 table definitions
- `G:\AI\tests\test_foreman_db.py` — test that init is idempotent, tables exist, insert+read works

**Key signature (read blueprint §8 carefully):**
```python
def init_db(path: str = "registry/foreman.db") -> sqlite3.Connection
```

**What NOT to touch:**
- Do NOT create non-MVP tables yet (skills, tools, memory_notes, skill_updates, datasets, column_mappings, business_rules, kpis)
- Do NOT modify existing `engines/` database code
- Do NOT create a DuckDB connection — the analytical store is separate

**Exact test:** `pytest tests/test_foreman_db.py -q`
- Tables exist after init
- Second init is a no-op (no error, no duplicates)
- Can insert one `runs` row and one linked `run_steps` row

**Guard:** `init_db` must be idempotent. Test this explicitly.

---

#### Step 0.3 — JSON schemas + registry linter

**What to do:**
1. Create 3 JSON schemas: `schemas/run_contract.schema.json`, `schemas/skill.schema.json`, `schemas/tool.schema.json`
2. Use JSON Schema draft-2020-12, `required` on mandatory fields, enums for `domain`/`risk_level`/`read_only_or_write`, semver pattern for `version`
3. Create `G:\AI\tools\registry_lint.py` with `lint() -> list[str]`
   - Validates `registry/skills.yaml` and `registry/tools.yaml` against schemas
   - Checks cross-references: every `allowed_tools` id exists in `tools.yaml`
   - No two skills share a trigger
   - Every tool `engine_path` is importable

**Files to create:**
- `G:\AI\schemas\run_contract.schema.json`
- `G:\AI\schemas\skill.schema.json`
- `G:\AI\schemas\tool.schema.json`
- `G:\AI\tools\registry_lint.py`
- `G:\AI\tests\test_registry_lint.py`

**Key guardrail:** Read blueprint §9 for skill schema fields, §11 for tool schema fields. Do NOT invent fields.

**What NOT to touch:**
- Do NOT create `registry/skills.yaml` and `registry/tools.yaml` yet (Steps 0.5, 0.6)
- Do NOT modify existing test structure

**Exact test:** `pytest tests/test_registry_lint.py -q`
- Clean registry fixture → no errors
- Broken fixture (unknown tool_id) → expected error string

---

#### Step 0.4 — Templates pack

**What to do:**
1. Create 4 template files from blueprint verbatim sections
2. `templates/SKILL.md` — §10 verbatim
3. `templates/RUN_CONTRACT.md` — §12 verbatim
4. `templates/MANAGEMENT_REPORT.md` — §26 outline (BLUF, 5 key numbers, drivers, risks, actions, confidence + sign-off, 3-line footer)
5. `templates/LESSON.md` — §18's 11 questions as headings, each marked "n/a is an acceptable answer"

**Files to create:**
- `G:\AI\templates\SKILL.md`
- `G:\AI\templates\RUN_CONTRACT.md`
- `G:\AI\templates\MANAGEMENT_REPORT.md`
- `G:\AI\templates\LESSON.md`
- `G:\AI\tests\test_templates_present.py`

**Guard:** Templates are MARKDOWN only. No code generation. No executable templates.

**Exact test:** `pytest tests/test_templates_present.py -q`
- Each template file exists
- Each contains its mandatory section headings

---

#### Step 0.5 — Tool manifest of existing engines

**What to do:**
1. Read existing engine signatures from `engines/` to get accurate `engine_path` values
2. Create `G:\AI\registry\tools.yaml` with ~10 tool passports in blueprint §11 schema
3. Each entry must have correct `engine_path` (read the actual module to confirm)

**Tool entries (from blueprint §11, verified against existing code):**
```
T-FP-001 fingerprint → tools/fingerprint.py::fingerprint_file (will exist after Step 1.1)
T-ING-001 ingest → engines/data/ingest.py::ingest_spreadsheet
T-PROF-001 type inference → engines/data/types.py::infer_column_types
T-CLEAN-ACT → engines/data/clean.py::clean_actuals
T-CLEAN-STD → engines/data/clean.py::clean_standards
T-PVM-001 → engines/data/variance.py::price_volume_mix
T-DRV-001 → engines/data/drivers.py::run_variance_decomposition
T-AUDIT-001 → engines/audit/audit.py::audit_card
T-CARD-001 → G:\AI\serving\card.py::make_manager_card
T-DOC-001 → engines/docs/extract.py::extract_document
```

**IMPORTANT:** Before writing each engine_path, READ the source file to confirm the function signature and module exists. Do NOT guess paths.

**Files to create:**
- `G:\AI\registry\tools.yaml`
- Extend `tests/test_registry_lint.py` to also check importability

**Guard:** Every engine_path must be verified by reading the actual source file. If a path/function doesn't exist, flag it, don't fudge it.

**Exact test:** `pytest tests/test_registry_lint.py -q` (extended to import-check)

---

#### Step 0.6 — Skills registry stub + FOREMAN skill linter

**What to do:**
1. Create `G:\AI\registry\skills.yaml` with 5 MVP skills (SK-001 through SK-005), blueprint §9 schema
2. Set all to `status: proposed` (they become `active` in Phase 1–2)
3. Create `G:\AI\tools\skill_lint.py` — for each `skills/<name>/SKILL.md`, assert §10 sections present and every named tool exists in `tools.yaml`
4. Create `G:\AI\tests\test_foreman_skill_lint.py`

**Files to create:**
- `G:\AI\registry\skills.yaml`
- `G:\AI\tools\skill_lint.py`
- `G:\AI\tests\test_foreman_skill_lint.py`

**Critical guardrail:** This linter is SEPARATE from the existing `tests/test_skill_contracts.py`. Do NOT modify that file. FOREMAN skills are a new set.

**Exact test:** `pytest tests/test_foreman_skill_lint.py -q`
- Passes on a valid seed skill folder
- Fails on a skill referencing an unknown tool

**Phase 0 complete gate:** All of 0.1–0.6 tests green + `ruff check .` + `python -m pytest -q` full suite green.

---

### Phase 1: Excel-to-database MVP (5 steps)

**Phase goal:** Skills SK-001, SK-002, SK-003 are real.  
**Phase guardrail:** The plan mostly WRAPS existing engines. If you find yourself writing math, stop — a tool already does it.  
**Phase done when:** A real factory export loads into the analytical store with quarantine and an owner-confirmed column mapping, every step recorded in `foreman.db`.

---

#### Step 1.1 — Fingerprint + register tool

**What to do:**
1. Create `G:\AI\tools\fingerprint.py`
2. `fingerprint_file(path) -> dict` returning `{sha256, size_bytes, original_path}`
3. `register_file(path, db) -> dict` that copies file to `datasets/registered/<sha8>_<name>` (never moves/edits original), writes `file_fingerprints` row
4. Re-registering same bytes → return existing row (dedup on sha256)

**Files to create:**
- `G:\AI\tools\fingerprint.py`
- `G:\AI\tests\test_fingerprint.py`

**Guard:** The original file in `inbox/` must be byte-identical before and after registration.

**Exact test:** `pytest tests/test_fingerprint.py -q`
- Same file registered twice → one fingerprint row, same registered path
- Original is untouched

---

#### Step 1.2 — Run logger (shared plumbing for all skills)

**What to do:**
1. Create `G:\AI\tools\run_logger.py`
2. API: `start_run(db, contract) -> run_id`, `log_step(...) -> step_id`, `log_evidence(...)`, `log_validation(...)`, `finish_run(...)`
3. These write the §8 tables. Every subsequent skill uses this — no skill writes SQL directly.

**Files to create:**
- `G:\AI\tools\run_logger.py`
- `G:\AI\tests\test_run_logging.py`

**Guard:** Every run must go through this logger. No direct SQL writes from skills.

**Exact test:** `pytest tests/test_run_logging.py -q`
- A scripted run produces one `runs` row + N `run_steps` + evidence + validation rows

---

#### Step 1.3 — SK-001 excel-intake

**What to do:**
1. Create `G:\AI\skills\excel-intake\SKILL.md` from §10 template, content from blueprint §20 SK-001
2. Create `G:\AI\skills\excel-intake\run.py::run_excel_intake(inbox_path, db, con) -> dict`
3. Behavior: register+fingerprint → ingest_spreadsheet → write evidence → return summary

**Reuse:** `engines/data/ingest.py::ingest_spreadsheet`. Do NOT reimplement ingestion.
**Gates:** fingerprint gate (file registered), conservation gate (rows_in == kept + rejected)
**Edge cases:** file locked/open in Excel → catch and return plain "close it" message

**Files to create:**
- `G:\AI\skills\excel-intake\SKILL.md`
- `G:\AI\skills\excel-intake\run.py`
- `G:\AI\tests\test_skill_excel_intake.py`
- Update `G:\AI\registry\skills.yaml` → set SK-001 `status: active`

**Guard:** Read `ingest_spreadsheet` signature first. Do NOT reimplement parsing.

**Exact test:** `pytest tests/test_skill_excel_intake.py -q`
- Fixture workbook: one total row, one duplicate, one junk amount → exactly those quarantined
- Conservation holds: rows_in == kept + rejected
- Evidence + run rows written to DB

---

#### Step 1.4 — SK-002 column-profile-and-map

**What to do:**
1. Create `G:\AI\skills\column-profile-and-map\SKILL.md`
2. Create `G:\AI\skills\column-profile-and-map\run.py::run_profile_and_map(table, db, con, prior_mapping=None) -> dict`

**Reuse:** `engines/data/types.py::infer_column_types`. Do NOT reimplement type inference.
**Gate:** column-mapping gate — every required canonical column mapped, no source column mapped twice
**Edge case:** 272-column SAP export → profile in batches, propose only the columns the target lens needs

**Files to create:**
- `G:\AI\skills\column-profile-and-map\SKILL.md`
- `G:\AI\skills\column-profile-and-map\run.py`
- `G:\AI\tests\test_skill_column_map.py`
- Update `G:\AI\registry\skills.yaml` → set SK-002 `status: active`

**Guard:** Mapping is not "confirmed" until owner confirmation is recorded. Do NOT auto-confirm.

**Exact test:** `pytest tests/test_skill_column_map.py -q`
- Fixture with renamed columns + a saved prior mapping → proposal matches the prior

---

#### Step 1.5 — SK-003 load-to-database

**What to do:**
1. Create `G:\AI\skills\load-to-database\SKILL.md`
2. Create `G:\AI\skills\load-to-database\run.py::run_load_to_database(table, mapping, db, con) -> dict`

**Reuse:** `engines/data/clean.py::clean_actuals` / `clean_standards` — canonical parser, dup detection, qty quarantine. Do NOT reparse numbers.
**Gates:** numeric/date cleaning, DB loading (loaded == cleaned), duplicate (below 5% or stop and show samples)

**Files to create:**
- `G:\AI\skills\load-to-database\SKILL.md`
- `G:\AI\skills\load-to-database\run.py`
- `G:\AI\tests\test_skill_load_db.py`
- Update `G:\AI\registry\skills.yaml` → set SK-003 `status: active`

**Guard:** Reject rate over threshold → stop, surface samples, do NOT silently proceed.

**Exact test:** `pytest tests/test_skill_load_db.py -q`
- Nasty fixture → correct quarantine, conservation, reject-rate gate fires above threshold

**Phase 1 complete gate:** 1.1–1.5 tests green + full suite green.

---

### Phase 2: Reporting and validation (4 steps)

**Phase goal:** SK-004, SK-005 real.  
**Phase done when:** Owner receives a signed management report whose every number traces to a fingerprinted source.

---

#### Step 2.1 — SK-004 reconcile-and-validate

**Reuse:** `engines/audit/audit.py` recomputation pattern + SQL sums. Do NOT reimplement audit logic.
**Gate:** reconciliation gate — delta > 0.01 → drill down by dimension, surface the delta location.
**Edge case:** control total includes quarantined subtotal rows → reconcile against detail-only recomputation and say so.

**Files to create:**
- `G:\AI\skills\reconcile-and-validate\SKILL.md`
- `G:\AI\skills\reconcile-and-validate\run.py`
- `G:\AI\tests\test_skill_reconcile.py`
- Update `G:\AI\registry\skills.yaml` → set SK-004 `status: active`

**Exact test:** Matching fixture passes; off-by-one fixture fails gate WITH by-dimension drill-down.

---

#### Step 2.2 — SK-005 management-report

**Reuse:** `engines/data/variance.py`, `drivers.py`, `serving/card.py::make_manager_card`, `serving/open_design.py`. Do NOT reimplement reporting.
**Gate:** report-generation gate — every number carries an evidence_id, tagged AUDITED. A wanted-but-unvalidated number is OMITTED with a stated reason, never rendered as CLAIMED.

**Files to create:**
- `G:\AI\skills\management-report\SKILL.md`
- `G:\AI\skills\management-report\run.py`
- `G:\AI\tests\test_skill_mgmt_report.py`
- Update `G:\AI\registry\skills.yaml` → set SK-005 `status: active`

**Critical guardrail:** No CLAIMED numbers in a management report. Ever. Test this explicitly.

**Exact test:** Golden fixture → regenerated report numbers match expected exactly. Injected CLAIMED number is refused/omitted.

---

#### Step 2.3 — Approval queue

**Files to create:**
- `G:\AI\tools\approvals.py` — `request_approval()` and `decide_approval()`
- `G:\AI\tests\test_approvals.py`

**Guard:** Only 4 types: external_send, skill_promotion, write_action, sensitive_memory.

**Exact test:** Request creates file+row; decide moves file + records decision.

---

#### Step 2.4 — End-to-end MVP run

**Files to create:**
- `G:\AI\tools\run_foreman.py` — thin driver that chains SK-001→SK-005
- `G:\AI\tests\test_foreman_end_to_end.py`

**Guard:** Stops at any failed gate with a plain message. Does NOT continue past a gate failure.

**Exact test:** Full chain on fixture → report whose every number resolves to an evidence_item and a fingerprint.

**Phase 2 complete gate:** 2.1–2.4 tests green + full suite green. MVP is usable.

---

### Phases 3–7: Lightweight outlines (no code yet)

**Do NOT implement Phases 3–7 until Phase 2 is complete.**

Phase 3: Second brain + lessons (vault, memory gate, lesson capture, curation helper)
Phase 4: Factory analytics modules (period-close-pack, variance-driver, inventory-exception, rework-cost, cross-period)
Phase 5: Dashboard (static HTML, checksum gate)
Phase 6: Multi-agent orchestration (ONLY when owner re-enables the team)
Phase 7: Advanced decision support

---

## Execution flow summary

```
Phase 0 ──→ Phase 1 ──→ Phase 2 ──→ (stop, MVP is done)
  │            │            │
  0.1 ─┐      1.1 ─┐      2.1 ─┐
  0.2 ─┤      1.2 ─┤      2.2 ─┤
  0.3 ─┤      1.3 ─┤      2.3 ─┤
  0.4 ─┤      1.4 ─┤      2.4 ─┤
  0.5 ─┤      1.5 ─┤          └── End-to-end test green = MVP done
  0.6 ─┤          └── Ph1 gate
       └── Ph0 gate
```

Between every step: `ruff check . && python -m pytest -q`  
After every step's test: `python -m pytest tests/<step-test>.py -q`  
Move to next step only when both pass.

---

## Mistakes to catch (from code-review self-review of this plan)

| Risk | How the plan prevents it |
|---|---|
| Editing existing engines | Guardrail 1: `engines/`, `serving/`, `gov/`, `shared/`, `mcp_server/`, `ops/` are read-only |
| Breaking existing tests | Guardrail 5: Full suite must stay green after every step |
| Reimplementing existing code | Guardrail 12: Check existing engine before writing new tool. Steps name exact functions to reuse |
| Scope creep | Guardrail 10: Each step specifies exact files. "While I'm here" forbidden |
| Skipping verification | Every step specifies the exact test command. Guardrail 8: One step at a time |
| Planning too far ahead | Phases 3–7 are outlines only. No code until Phase 2 green |
| Writing math instead of wrapping tools | Guardrail in Phase 1 header: "If you find yourself writing math, stop — a tool already does it" |
| Committing while suite is red | Guardrail 6: Commit only when full suite is green AND owner asks |
| Adding tables beyond MVP 8 | Step 0.2 explicitly lists the 8 tables. Non-MVP tables are forbidden in Phase 0 |
| Path/import mistakes | Step 0.5 explicitly says: read the source file before writing the tool manifest entry |
| Forgetting to verify file writes | Guardrail 11: After every file write, read it back |
| Touching agent_skills/ or test_skill_contracts.py | Guardrail 2 + explicit note in Step 0.6 |
| Auto-confirming column mappings | Step 1.4 guard: mapping is not confirmed until owner records it |
| Rendering unvalidated numbers in reports | Step 2.2 critical guardrail: No CLAIMED numbers. Test this explicitly |
| Continuing past a gate failure | Step 2.4 guard: stops at failed gate with plain message |

---

## Start here

Step 0.1 — Create the folder tree.
