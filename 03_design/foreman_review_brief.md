# FOREMAN Plan Review — 2026-07-03

> This report is the output of the review brief that follows it (see *Appendix — Original
> Review Brief* at the bottom of this file). Every finding cites `file:line` evidence from the
> actual repo. The review was conducted against the two plan documents
> (`03_design/skill_os_blueprint.md`, `03_design/foreman_build_plan.md`) **and** the as-built
> code, because the code turned out to exist (see B1).

---

## Verdict

**Not safe to hand to a code-writer as-is.** The plan's reuse bet is largely real and the
phase ordering is sound, but three things make a clean build impossible right now: (1) the
review brief's central premise — "FOREMAN's own code is not written yet" — is **false**; a
substantial scaffold already exists (`tools/` has 12 modules, `skills/` has 11 folders,
`registry/*.yaml`, and 6 FOREMAN test files) and the suite is **RED** (`1 failed, 367 passed,
5 skipped`); (2) the reconciliation design (§6.3) is circular-prone and the as-built
reconcile skill confirms it — this is the project's defined catastrophic failure (a wrong
number reaching the CFO); (3) the evidence-chain claim ("the agent physically has no path to
introduce a number") is overstated — `ManagerCard.validate()` only checks that evidence
strings are non-empty, not that they map to a real ledger row. Fix B1–B5 before any further
building. The part needing redesign is the **reconciliation-independence + evidence-ledger
enforcement** (§6.3 and §6.5), not the overall architecture.

---

## Blocking findings (must fix before building)

**[B1] The test suite is already red, and the plan's "285 passing / green suite" premise is
false.** — `python -m pytest -q` → `1 failed, 367 passed, 5 skipped`.
`tests/test_memory_and_lessons.py::test_capture_lesson_creates_file` fails: it asserts
`'RUN-42'` is in the lesson file but the file reads `'RUN-1'` — a run-id threading bug in
`tools/lesson_capture.py`. Separately, `foreman_build_plan.md:32` claims "285 passing at plan
start"; the real count is 367 passed + 1 failed. **Failure it causes:** the plan's own
guardrail (`foreman_build_plan.md:28,37` — "commit only when the full suite is green") is
already violated, so every subsequent "DoD: full suite green" step is unmeetable until this
is fixed, and a code-writer following the plan would believe they broke a green baseline they
never had. **Fix:** repair `tools/lesson_capture.py` so the lesson content uses the
`run_id` returned by `start_run` (the f-strings at `tools/lesson_capture.py:51,53` look
correct — investigate why `result["path"]` contained `RUN-1`; likely a stale un-cleaned file
or a `start_run` return-value mismatch), get the suite green, and correct the "285" figure in
both plan docs to the real number.

**[B2] Reconciliation is not independent — a wrong number can pass the gate (finance-critical,
§6.3).** — As built, `skills/reconcile_and_validate/run.py:56-60` computes
`actual_total = SELECT SUM(amount) FROM <clean_table>` and compares it to a caller-supplied
`control_total` float (`run.py:62-63`). Nothing verifies the `control_total` is genuinely
external (SAP total row / prior signed report / owner figure). The plan's own walkthrough
demonstrates the circular fallback it warned about: `skill_os_blueprint.md:657-658` says "gate
re-run against detail-recomputed control ✓" after accepting excluded rows — i.e. recompute the
expected total from the same detail being validated, which by construction matches and
**proves nothing**. The reconcile function has no notion of quarantined subtotals at all
(there is no `rejects` parameter, no "detail-only recomputation" branch). **Failure it
causes:** a cleaning step that silently dropped/ double-counted rows produces a clean table
whose SUM matches a recomputed-from-the-same-detail "control" — a confidently wrong number
reaches the report. This is exactly the project's catastrophic failure mode
(`AGENTS.md` Calculation-Integrity Rule; brief §9). **Fix:** require `control_total` to carry
a `source` provenance that is *not* the same clean table (SAP row, prior signed report id, or
owner-stated value with a name); reject any control total whose source is "recomputed from
clean detail"; when the SAP total includes subtotal rows, reconcile against the SAP figure
minus explicitly-listed quarantined subtotal amounts (with the reject evidence ids cited), and
emit a warning that the adjustment was applied — never silently recompute the expected from
the actual.

**[B3] The evidence chain is enforced structurally but not verified against the ledger — a
fabricated AUDITED number passes (§6.5).** — `shared/contracts/models.py:128` checks
`n.evidence.resolves()`, and `resolves()` (`models.py:20-21`) is
`bool(self.source and self.locator and self.method)` — i.e. three non-empty strings.
`NumberFact.tag` (`models.py:40-45`) stamps `AUDITED-FROM-QUERY` purely from the source
**prefix** (`duckdb:`/`polars:`). There is **no** check that an `EvidenceRef` corresponds to
a real `evidence_items` row written by a tool step in the same run. **Failure it causes:**
`blueprint §13` claims "the agent physically has no path to *introduce* a number." That is
overstated: a skill's `run.py` (written by an AI agent) can construct
`NumberFact(value, EvidenceRef(source="duckdb:reconcile", locator="x", method="SUM(amount)"))`
and it will be tagged `AUDITED` and pass `validate()`. The real protection is procedural
(skills must call allowed tools), not enforced by the type system. **Fix:** add a report-gate
check that every `NumberFact.evidence` in a rendered card resolves to an `evidence_items`
row in `foreman.db` for the current `run_id` (match on source+locator+method, or store an
`evidence_id` on the `EvidenceRef`); refuse the report if any number's evidence is not in the
ledger. This closes the gap between "a number appears" and "a tool wrote it."

**[B4] The tool manifest records the wrong path for the manager-card tool.** —
`foreman_build_plan.md:106` lists `T-CARD-001 → engines/serving/card.py::make_manager_card
(path: serving/card.py)`. The file lives at `serving/card.py:18` (def `make_manager_card`);
there is **no** `engines/serving/` directory. **Failure it causes:** Step 0.5's own acceptance
test ("every `engine_path` imports without error", `foreman_build_plan.md:110`) fails on this
entry, so a code-writer cannot get Phase 0 green. **Fix:** set the `engine_path` to
`serving/card.py::make_manager_card` in `registry/tools.yaml` and remove the contradictory
"engines/serving" text from the plan.

**[B5] In-memory DuckDB breaks the skill chain unless one connection is threaded everywhere
(§6.12).** — `engines/data/ingest.py:61-62`: `get_connection()` returns
`duckdb.connect()` — **in-memory** (the code comment admits "in-memory staging for the demo;
file-backed in production"). The as-built reconcile skill falls back to this when no
connection is passed: `skills/reconcile_and_validate/run.py:25-30` does
`if duckdb_con is None: duckdb_con = get_connection()`. **Failure it causes:** if any skill in
the SK-001→SK-005 chain calls `get_connection()` instead of receiving the shared `con`, it
gets a fresh empty database — the clean table staged by SK-001/003 does not exist, so the
reconcile SUM returns 0 or errors, silently. The plan designs skills to take a `con`
parameter (`foreman_build_plan.md:154,205`), but never states that `run_foreman.py` must
create **one** connection and thread it, nor that `get_connection()` must become file-backed
for FOREMAN. **Fix:** either (a) make `get_connection()` file-backed
(`duckdb.connect("registry/foreman.duckdb")` or a configurable path) for FOREMAN runs, or
(b) require `run_foreman.py` to hold a single `con` and pass it to every skill, and remove
the `None`-fallback in skill `run.py` files so a missing connection raises loudly instead of
silently opening an empty DB.

---

## Non-blocking findings (improve when convenient)

**[N1] Two skill systems + two linters is a drift trap (§6.6).** — Confirmed:
`tests/test_skill_contracts.py:8,26` scans only `agent_skills/*.md`, so the new `skills/`
folder won't break it. But the repo now has two skill formats (`agent_skills/*.md` governed by
`test_skill_contracts.py`, and `skills/<name>/SKILL.md` governed by `test_foreman_skill_lint.py`)
with different templates (`blueprint §10` vs the existing one). An agent will not know which
set to load. **Fix:** pick one canonical home; either migrate `agent_skills/*.md` into
`skills/` over time with a redirect note in `AGENT_SKILL_MAP.md`, or document explicitly in
`AGENTS.md` that `agent_skills/` = capability descriptions and `skills/` = executable
workflows, and have `AGENT_SKILL_MAP.md` point to both.

**[N2] `column_mappings` is a 9th MVP table the §8 list marks non-MVP (§6.2).** — Confirmed:
`skill_os_blueprint.md:254` lists `column_mappings` without an `[MVP]` marker, but
`foreman_build_plan.md:170-172` (Step 1.4) says "add this table now if not present, it's a
Phase-1 need." So Step 0.2's "8 MVP tables" is incomplete for Phase 1. The plan handles it
inline, but the §8 marking is inconsistent and invites schema churn. **Fix:** mark
`column_mappings` as `[MVP]` in §8, or move its creation into Step 0.2 explicitly.

**[N3] Cost/token metrics are aspirational during MVP (§6.9).** — `runs` has
`est_tokens`/`model_calls_count` (`skill_os_blueprint.md:243`) but nothing populates them
until Phase 6 (`foreman_build_plan.md:304`). The §29 scorecard
(`skill_os_blueprint.md:782`) lists "token cost per routine run" as an MVP-era metric. It is
not measurable before Phase 6. **Fix:** either add a minimal `logs/model_calls.csv` write in
`run_logger` now (even if values are estimates), or move those two scorecard rows to "Phase 6
metrics" so the MVP scorecard is honest.

**[N4] FOREMAN chains have no resumability story (§6.11).** — `run_logger` is genuinely new
(not a duplicate of `engines/docs/run_state.py`, which is JSON chunk-resume for LLM
ingestion, or `ops/session_state.py`, which is a markdown human-resume). But
`run_foreman.py` (Step 2.4) chains SK-001→SK-005 with no resume-on-failure design. If SK-003
fails, the owner restarts from scratch. **Fix:** record `run_steps.status` per skill and let
`run_foreman.py` skip already-completed steps on retry (the `run_steps` table already has the
fields). Non-blocking for MVP but a real operational risk once real 600k-row exports arrive.

**[N5] Privacy enforcement is procedural for prompt content; technical only at the door
(§6.4).** — `blueprint §27` says "Tier-1 factory data never reaches any cloud model." The
actual enforcement points are: the contract marks `tier1`, `gov/privacy.py`/`gov/ledger.py`
gate *external sends* through `exports/`, and the agent is *instructed* not to paste raw rows.
There is no code that intercepts what the agent puts in a cloud model's context. The plan
honestly admits this residual in `blueprint §31` ("owner pasting raw data into chat manually —
not technically closable"). **Fix:** no code change needed for MVP, but soften §27's "never
reaches" to "never sent via a tool; manual paste remains the owner's responsibility" so the
claim matches the enforcement.

**[N6] Conservation is asserted in `clean.py`, not in `ingest_spreadsheet` (§5 claim 1).** —
`engines/data/ingest.py:525-526` documents the conservation law but the `assert` lives in
`engines/data/clean.py:143`. `foreman_build_plan.md:158` says the conservation gate for SK-001
is "already asserted inside the engine; surface it as a validation_results row." SK-001 wraps
`ingest_spreadsheet`, which does **not** assert — it only records `rows_in`/`reject_count`.
**Fix:** have SK-001 compute `rows_in == kept + rejected` from the returned dict and assert it
in the skill (then write the `validation_results` row); don't claim the engine already
asserted it.

---

## Checkable-claims results (from §5)

| # | Claim | Verdict | Evidence (file:line) | Note |
|---|---|---|---|---|
| 1 | `ingest_spreadsheet(con, table, path, *, on_duplicates, infer_types)` + conservation asserted | **PARTIAL** | `engines/data/ingest.py:599-606` (signature matches verbatim); conservation **documented** at `ingest.py:525-526` but the `assert` is in `engines/data/clean.py:143`, not in ingest | Signature correct; conservation not asserted in ingest itself |
| 2 | `clean_actuals`/`clean_standards` share one `parse_amount` | **TRUE** | `engines/data/clean.py:148-156`, `165-172`; shared call at `clean.py:108` (`parsed_row[col] = parse_amount(row.get(col))`) | Both delegate to `_clean_rows` |
| 3 | `parse_amount` handles `1,234.56`, `(1,234.56)`, `1234.56-` | **TRUE** | `engines/data/clean.py:40-45` (parens + trailing minus), `49-59` (comma/dot locales), `62` (sign applied); confirmed by `tests/test_nasty_data.py:23-25` | SAP negatives handled |
| 4 | `make_manager_card` path | **TRUE** (correct path is `serving/card.py`) | `serving/card.py:18-23`; no `engines/serving/` exists | Plan's `engines/serving/card.py` is wrong → B4 |
| 5 | `audit_card` recomputes from cleaned frame, not raw staging | **TRUE** | `engines/audit/audit.py:23-34` (takes `clean_actuals: pl.DataFrame`); re-sum at `audit.py:42-43` (`con.register("clean", clean_actuals); SELECT SUM(...) FROM clean`) | Confirms §6.3: re-sum depends on the cleaning step → B2 |
| 6 | `NumberFact` requires `EvidenceRef`; card refuses non-resolving evidence | **TRUE** (but resolves() is weak) | `models.py:36` (required, no default); `models.py:128` checks `resolves()`; `resolves()` at `models.py:20-21` = three non-empty strings | No ledger existence check → B3 |
| 7 | 8 MVP tables sufficient; `column_mappings` is a 9th Phase-1 need | **TRUE** | `skill_os_blueprint.md:243-252` (8 marked `[MVP]`); `:254` `column_mappings` no marker; `foreman_build_plan.md:170-172` says add now; `run_steps` has `params_json` (`:244`) | → N2 |
| 8 | `test_skill_contracts.py` won't break on new `skills/` | **TRUE** | `tests/test_skill_contracts.py:8` (`SKILLS_DIR = Path("agent_skills")`), `:26` (`glob("*.md")`) | Hardcoded to `agent_skills/` → N1 |
| 9 | `run_logger` duplicates existing resume machinery? | **FALSE** (no duplication) | `engines/docs/run_state.py:10-13` (JSON chunk resume); `ops/session_state.py:48-80` (markdown human resume); `tools/run_logger.py:16,33` (SQLite run+step audit) | Different backends/scopes; genuinely new — but no FOREMAN chain resume → N4 |
| 10 | Full suite green at 285 passing | **FALSE** | `python -m pytest -q` → `1 failed, 367 passed, 5 skipped`; failing: `tests/test_memory_and_lessons.py::test_capture_lesson_creates_file` | → B1 |

---

## Risk-hotspot results (from §6)

| # | Hotspot | Holds / Breaks | Evidence | One-line conclusion |
|---|---|---|---|---|
| 6.1 | Reuse bet is real, no hidden engine rewrites | **Mostly holds** | Claims 1–4 verified true/partial; skills wrap, not rewrite. One caveat: `audit_card` re-sums cleaned data (claim 5) — a reuse *limitation*, not a rewrite | Reuse is honest; the audit reuse has an independence gap (B2) |
| 6.2 | MVP DB schema completeness | **Breaks (minor)** | `column_mappings` missing from 8 MVP tables (`skill_os_blueprint.md:254` vs `foreman_build_plan.md:170`) | Add `column_mappings` to MVP (N2) |
| 6.3 | Reconciliation independence | **Breaks** | `skills/reconcile_and_validate/run.py:56-63` re-sums clean table vs caller-supplied float; no external-source enforcement; §22:657-658 circular fallback | **B2 — catastrophic-failure path open** |
| 6.4 | Privacy enforcement technical vs procedural | **Procedural for prompts** | `gov/privacy.py`/`ledger.py` gate sends; no prompt-content interception; §31 admits residual | Honest but §27 overstates "never reaches" (N5) |
| 6.5 | Evidence chain enforced or aspirational | **Aspirational at the ledger layer** | `models.py:20-21,128` = non-empty strings; `tag` by prefix `models.py:40-45`; no `evidence_items` lookup | **B3 — fabricated AUDITED number passes** |
| 6.6 | Two skill systems | **Breaks (drift risk)** | `test_skill_contracts.py:8,26` (agent_skills) + new `test_foreman_skill_lint.py`; two templates | Unify or document the split (N1) |
| 6.7 | Excel reality (272 cols, merged cells, two tables/sheet) | **Partially holds** | `clean.py` handles totals/dupes/locale/negatives (claims 2–3); `ingest.py` text-first spine handles multi-sheet. **Not handled:** merged cells, formulas-as-values, two-tables-per-sheet, header-not-on-row-1 — `SK-002` notes these as edge cases but no engine support exists | Profile-before-map gate is right; nasty-sheet handling is future work, flag in SK-002 |
| 6.8 | "Useful in days" honesty | **Breaks (over-optimistic)** | ~14 steps (Phases 0–2) each = new code + test + owner confirmations; plus B1/B5 fixes and B2/B3 redesigns | Revised: 1.5–2.5 weeks (see below) |
| 6.9 | Cost/token accounting gap | **Breaks (scorecard aspirational)** | `runs.est_tokens` not populated until Phase 6 (`foreman_build_plan.md:304`); §29 lists it as MVP metric | Minimal cost log now or move metric (N3) |
| 6.10 | Contract/model coupling | **Holds** | No FOREMAN step requires changing `shared/contracts/models.py`; FOREMAN adds tables/skills, not contract fields | Good — no hidden approval gate |
| 6.11 | Orchestration duplication + resumability | **No duplication; resumability missing** | `run_logger` is new (claim 9); `run_foreman.py` has no skip-completed-steps logic | Add step-skip resume (N4) |
| 6.12 | Windows + concurrency (in-memory DuckDB) | **Breaks** | `engines/data/ingest.py:62` `duckdb.connect()` in-memory; `skills/reconcile_and_validate/run.py:27` fallback opens fresh empty DB | **B5 — chain silently broken if con not threaded** |

---

## Rubric scores (from §7)

| Dimension | Score | Justification |
|---|---|---|
| Correctness of logic (reconciliation, evidence chain, conservation) — **weighted highest** | **2** | Reconciliation circular-prone (B2), evidence chain not ledger-verified (B3), chain broken by in-memory DuckDB (B5). Blocking findings present. |
| Buildability (steps unambiguous, testable, ordered) | **3** | Steps are clear and well-ordered, but the baseline is already red (B1) and the manifest path is wrong (B4); a code-writer would stall in Phase 0. |
| Reuse honesty (claimed reuse is real) | **4** | Fact-checks confirm engines exist with claimed signatures (claims 1–4); the one reuse limitation (audit re-sums cleaned data) is a design gap, not dishonesty. |
| Safety (privacy, read-only sources, approval gates) | **2** | Privacy is procedural for prompts (N5); evidence chain not enforced (B3); reconciliation not independent (B2). A wrong number can reach the CFO. Blocking findings present. |
| Non-programmer operability | **3** | Two-window design is sound, but "days" is unrealistic (6.8) and the red suite + silent in-memory DB failures will confuse a non-coder debugging via AI agents. |
| Expandability without redesign | **4** | Phase ordering is sound; later phases don't force rework of 0–2; two skill systems (N1) is drift risk, not a redesign. |
| Drift resistance (skills vs code, docs vs reality) | **2** | Two skill systems + two linters (N1); code already exists that the plan doesn't acknowledge (B1 staleness); suite already red. Blocking finding (B1) covers the ≤2. |

---

## Honest MVP timeline estimate

**Revised estimate: 1.5 to 2.5 weeks of focused sessions, not "days."**

Reasoning:
- The plan is honest that the engines exist and are tested — that part is real and saves
  months. But "useful in days" assumes a green baseline and no design holes.
- Three blocking fixes are real engineering before any new skill can be trusted: get the
  suite green (B1), make reconciliation independent of the data it validates (B2), and verify
  evidence against the ledger (B3). These are not 1-day items; B2 and B3 touch the trust
  model the whole system is built on.
- The in-memory DuckDB issue (B5) must be resolved before the end-to-end chain
  (`run_foreman.py`) can work at all.
- Phases 0–2 are ~14 steps, each requiring new code + a new test **and** owner confirmations
  (mappings, approvals, control totals). The owner's wall-clock confirmation time — not token
  time — dominates a non-programmer workflow. One mapping-confirmation round-trip per dataset
  is easily a session by itself.
- Some code already exists but is buggy (B1) and its reconcile skill encodes the circular
  design (B2) — so "build" is partly "fix and redesign," which is slower than greenfield.
- Bottom line for the owner: plan on roughly two weeks of 1–2 hour sessions to reach the
  first signed report on a real export. The compounding value (saved mappings, lesson loop)
  the plan promises is real **after** that — month two is when it gets fast, not week one.

---

## Appendix — Original Review Brief

*The brief that specified this review is preserved below for reference.*

# FOREMAN — Review Brief (hand this to the reviewer agent)

*Prepared 2026-07-03. This document tells a reviewer AI agent exactly what to review, where the
files are, what to verify, which decisions to challenge, and what output to return. The goal is a
hard, specific review — not a rubber stamp. If the reviewer concludes "looks good" without citing
file:line evidence and engaging the risk hotspots in §6, the review has failed.*

---

## 1. How to use this brief

You (the reviewer) are reviewing a **plan**, not finished software. FOREMAN's own code is not
written yet; what exists is (a) two design documents and (b) the existing Factory Brain engines
the plan intends to reuse. Your job is to judge whether the plan is correct, buildable, safe, and
honest about its dependencies — and to catch design/logic errors **before** a code-writer starts,
because errors are cheapest to fix now.

Work in this order: read §2–§4 for scope, verify the checkable claims in §5, then spend most of
your effort challenging the risk hotspots in §6. Return your findings in the format in §8.

Ground rules:
- **Cite evidence.** Every finding names a file and line/section. "This seems risky" without a
  citation is not a finding.
- **Separate blocking from non-blocking.** A blocking issue means "a code-writer following this
  would build something wrong, unsafe, or untestable." Everything else is an improvement.
- **Do not rewrite the plan.** Report what's wrong and recommend a fix; don't author v2 yourself.
- **Read the actual code**, not just the plan's description of it. The plan claims to reuse
  specific functions — verify those functions exist with the signatures and behavior claimed.

---

## 2. What FOREMAN is (context)

FOREMAN is a proposed **governance + orchestration shell** that sits on top of the existing,
tested Factory Brain repo (`g:\AI`). It adds: run contracts, a SQLite run/evidence database, an
approval queue, an Obsidian-style vault, a lesson loop, and a small set of "skills" (written
workflows). It deliberately reuses the existing `engines/` for all data work (ingest, clean,
variance, audit, reporting). The central bet: **~60% already exists and is tested; only the
governance shell + 5 skill wrappers are new.**

**What exists today (verify this is true):** 285 passing tests, a hardened ingestion spine with
quarantine + conservation, a canonical number parser (`clean.py::parse_amount`), variance +
price/volume/mix engines, an audit layer, provenance-tagged manager cards, a claims/facts wall.
(These were hardened earlier on 2026-07-03; see `tests/test_nasty_data.py`.)

**What is proposed (the thing under review):** the two documents in §3.

---

## 3. Exact files to review

| File | What it is | Review weight |
|---|---|---|
| `03_design/skill_os_blueprint.md` | The design — 31 sections: mission, critique of the original idea, architecture, DB schema, schemas, templates, gates, reports, second brain, roadmap, risk register, MVP recommendation | **Heavy** |
| `03_design/foreman_build_plan.md` | The execution plan — phases 0–7, each a sequence of steps with files, reuse pointers, acceptance criteria, tests | **Heavy** |
| `engines/data/ingest.py` | Ingestion spine the plan wraps (`ingest_spreadsheet`) | Verify claims |
| `engines/data/clean.py` | Canonical parser + `clean_actuals`/`clean_standards` the plan wraps | Verify claims |
| `engines/data/variance.py`, `drivers.py` | Variance + PVM + `run_variance_decomposition` | Verify claims |
| `engines/audit/audit.py` | `audit_card` — the "independent" recomputation SK-004 reuses | **Scrutinize (see §6.3)** |
| `serving/card.py` | `make_manager_card` the report skill wraps | Verify path + signature |
| `shared/contracts/models.py` | `NumberFact`/`EvidenceRef`/`RejectRecord` — the evidence contracts the anti-hallucination claim rests on | **Scrutinize (see §6.10)** |
| `tests/test_nasty_data.py`, `tests/test_skill_contracts.py` | The test patterns the plan says to extend | Verify the pattern transfers |
| `config.yaml`, `AGENTS.md`, `CLAUDE.md` | Governance the plan must not contradict | Cross-check |

---

## 4. Review scope — the six lenses

Apply all six. For each, the plan must survive the question in bold.

1. **Product architect** — *Is the reuse-the-engines bet real, or does the plan quietly require
   rewriting things that already exist? Is the phase ordering correct (no step depends on a later step)?*
2. **Data engineer** — *Do the claimed function signatures, table schemas, and data flows actually
   work? Where will real 272-column / 600k-row SAP data break this?*
3. **Factory finance expert** — *Is the reconciliation logic sound enough to trust a number in
   front of a CFO? Can a wrong control total or a circular check pass a bad number?*
4. **Non-programmer advocate** — *Can the owner (guides AI agents, not a coder) actually operate
   and build this step-by-step? Is "useful in days" honest?*
5. **Security / privacy reviewer** — *Is Tier-1 factory data actually prevented from reaching cloud
   models, or only asked nicely? Where is the enforcement, technical vs procedural?*
6. **QA / validation reviewer** — *Is every step testable as written? Does each gate have a real
   pass/fail with evidence? Will skill docs and code drift?*

---

## 5. Checkable claims to verify (fact-check these against the code)

For each, confirm TRUE / FALSE / PARTIALLY with a file:line citation.

1. `engines/data/ingest.py` exposes `ingest_spreadsheet(con, table, path, *, on_duplicates, infer_types)`
   and it enforces conservation (rows_in == kept + rejected). *(build plan Step 1.3, 0.5)*
2. `engines/data/clean.py` exposes `clean_actuals(..., qty_col=..., dup_key_cols=...)` and
   `clean_standards(...)`, both routing numbers through one `parse_amount`. *(Step 1.5)*
3. `parse_amount` handles English `1,234.56`, thousands/decimal cases, and SAP negatives
   `(1,234.56)` / `1234.56-`. *(blueprint §20 SK-003, §13)*
4. `serving/card.py::make_manager_card` exists at that path (the manifest in Step 0.5 writes
   `engines/serving/card.py` in one line and `serving/card.py` in another — **which is correct?**).
5. `engines/audit/audit.py::audit_card` recomputes totals from the **already-cleaned** Polars
   frame, not from raw staging. *(critical for §6.3 — verify exactly what it re-sums)*
6. `shared/contracts/models.py` `NumberFact` requires an `EvidenceRef`, and the manager card
   refuses to render a number without resolving evidence. *(blueprint §13 anti-hallucination claim)*
7. The 8 "MVP tables" in blueprint §8 / build plan Step 0.2 are sufficient for Phases 0–2 —
   OR a 9th table (`column_mappings`) is actually required by Step 1.4. *(**suspected gap** — verify)*
8. `tests/test_skill_contracts.py` governs `agent_skills/*.md` and would NOT break when the new
   `skills/` folder is added. *(build plan "how to work" + Step 0.6)*
9. The existing repo has resumable-run / session-state machinery (`engines/docs/run_state.py`,
   `ops/session_state.py`) — does FOREMAN's `run_logger` (Step 1.2) duplicate it or reuse it? *(§6.11)*
10. The full suite is actually green at plan start (run `python -m pytest -q`; the plan claims 285 passing).

---

## 6. Risk hotspots — challenge these hard (this is where the value is)

These are the places most likely to hide a real defect. For each, the plan's current position is
stated; your job is to confirm it holds or show where it breaks.

**6.1 The reuse bet.** Plan claims new code is thin. *Challenge:* list every place a step says
"wrap" or "reuse" but would actually require modifying a tested engine (which the guardrails
forbid). If any skill can't be built without touching `engines/`, that's a blocking contradiction.

**6.2 MVP DB schema completeness.** Step 0.2 builds 8 tables; Step 1.4 persists column mappings
and Step 1.2's `log_step` needs `params_json`. *Challenge:* enumerate every field every MVP step
writes, and confirm a table+column exists for it. Flag every missing column now — schema churn
mid-build is expensive.

**6.3 Reconciliation independence (finance-critical).** SK-004 (Step 2.1) reuses the `audit_card`
recomputation pattern. But an earlier review found `audit_card` re-sums the **cleaned** frame, not
raw staging — so if cleaning dropped/double-counted rows, re-summing the cleaned data confirms the
wrong number. *Challenge:* (a) Does SK-004 reconcile against a **truly external** control total
(SAP total row / prior signed report / owner figure), or against a re-sum of the same cleaned
data? (b) The plan says "if the control total includes quarantined subtotals, reconcile against a
detail-only recomputation" — **is this circular?** If the "expected" total is recomputed from the
same detail being validated, the check proves nothing. This is the single most important thing to
get right; a bad number reaching the CFO is the project's defined catastrophic failure.

**6.4 Privacy enforcement: technical vs procedural.** §27 says "classify tier before choosing a
model" and routes Tier-1 to local tools only. *Challenge:* Is there any **code** that prevents a
raw Tier-1 row from being placed in a cloud model's context, or is it entirely convention +
the `exports/` door + the ledger? Name the actual enforcement point. If it's procedural only,
say so plainly and rate the residual leak risk (owner pasting rows into chat is unclosable — is
anything else?).

**6.5 Evidence chain — enforced or aspirational?** §13 claims "the agent physically has no path to
introduce a number." *Challenge:* trace it. `make_manager_card` receives a `VarianceBridge` that
already contains numbers computed by engines — good. But can a skill author pass a hand-built
`NumberFact` with a literal value and a fake `EvidenceRef`? Is there a check that an evidence ref
actually resolves to a real evidence_item row, or only that the field is non-empty? Locate the
weakest link between "a number appears in a report" and "a tool computed it."

**6.6 Two skill systems.** The repo has `agent_skills/*.md` (governed by `test_skill_contracts.py`,
requiring sections like "Token budget"). The plan adds `skills/<name>/SKILL.md` with a **different**
template (§10) and a **different** linter (Step 0.6). *Challenge:* Is running two skill formats +
two linters a maintenance trap? Will an agent know which set to load? Recommend whether to unify.

**6.7 Excel reality.** Gates assume profile-before-map. *Challenge:* walk a genuinely nasty case —
two tables on one sheet, header not on row 1, merged cells, hidden rows, formulas-as-values, a
272-column export — and show where the MVP skills (SK-001/002/003) silently mishandle it or block
with a confusing message. The existing engine handles totals/dupes/locale; what does it NOT handle?

**6.8 "Useful in days" honesty.** §30 promises a usable MVP in days. *Challenge:* Phases 0–2 are
~14 steps, each requiring new code + a new test, driven by a non-programmer via AI agents. Is
"days" realistic, or is it "a week or two of focused sessions"? Reviewer should give an honest
revised estimate, not flatter the plan.

**6.9 Cost/token accounting gap.** The `runs` table has `est_tokens`/`model_calls_count`, but
nothing populates them until Phase 6. *Challenge:* the §29 scorecard lists token-saving and
cost-per-run as MVP-era metrics — are they actually measurable before Phase 6, or is the scorecard
partly aspirational during MVP? Recommend either a minimal MVP cost log or moving those metrics.

**6.10 Contract/model coupling.** FOREMAN leans on `shared/contracts/models.py`. AGENTS.md says
"ask before changing a published contract." *Challenge:* do any FOREMAN steps require changing
those contracts (e.g., adding fields to `RejectRecord`, `NumberFact`)? If yes, that's an approval
gate the plan didn't call out.

**6.11 Orchestration duplication + resumability.** Step 2.4's `run_foreman.py` chains skills.
*Challenge:* the repo already has orchestration (`engines/brain/orchestrator.py`) and resumable
runs. Does FOREMAN reinvent them? What happens if a run fails at SK-003 — can it resume, or does
the owner restart from scratch? A close pack that isn't resumable is a real operational risk.

**6.12 Windows + concurrency.** SQLite `foreman.db`, DuckDB, and source files on Windows.
*Challenge:* SQLite write locking under repeated runs; DuckDB in-memory vs file-backed
(`get_connection()` currently returns in-memory — does data survive between skills in a chain?);
file locks when the source is open in Excel (Step 1.3 claims a friendly message — is it real?).
This is a concrete, likely-to-bite class of bug.

---

## 7. What "good" looks like (rubric)

Score each dimension 1–5 (1 = will fail in practice, 5 = sound), with one-line justification:

- **Correctness of logic** (reconciliation, evidence chain, conservation) — *weighted highest*
- **Buildability** (steps are unambiguous, testable, correctly ordered)
- **Reuse honesty** (claimed reuse is real; no hidden engine rewrites)
- **Safety** (privacy, read-only sources, approval gates, nothing invented)
- **Non-programmer operability**
- **Expandability without redesign** (later phases don't force reworking Phase 0–2)
- **Drift resistance** (skills vs code, docs vs reality, the two skill systems)

A dimension scoring ≤2 must produce at least one blocking finding or the score is unjustified.

---

## 8. Required output format

Return exactly this structure:

```
# FOREMAN Plan Review — <date>

## Verdict
One paragraph: is this plan safe to hand to a code-writer as-is, with fixes first, or does it
need a redesign of a specific part? Name the part.

## Blocking findings (must fix before building)
For each: [B1] <title> — file:line/section — what's wrong — concrete failure it causes — recommended fix.

## Non-blocking findings (improve when convenient)
Same format, [N1], [N2]...

## Checkable-claims results (from §5)
Table: claim # | TRUE/FALSE/PARTIAL | evidence (file:line) | note.

## Risk-hotspot results (from §6)
For each 6.1–6.12: holds / breaks — evidence — one-line conclusion.

## Rubric scores (from §7)
Table: dimension | score 1–5 | justification.

## Honest MVP timeline estimate
Your revised estimate for Phases 0–2 for a non-programmer using AI agents, with reasoning.
```

Keep prose tight. The owner is non-technical — lead each finding with a plain-English sentence of
what it means for them, then the technical detail. Do not end with "let me know if you want more."

---

## 9. Reviewer ground truth (so you can't be misled by the plan's own optimism)

- The plan was written by the same assistant that will (later) help build it. Treat its
  self-assessment in blueprint §31 as a **claim to test**, not a finding you can rely on.
- The catastrophic failure mode for this whole project is *a confident wrong number reaching an
  executive.* Weight §6.3 and §6.5 accordingly — a plausible-but-wrong reconciliation is worse
  than an honest "blocked."
- The owner has explicitly paused the multi-agent team (Phase 6). Do not recommend building it now.
- "Nothing vanishes silently" and "no number originates from generation" are non-negotiable repo
  rules (AGENTS.md). Any step that could violate either is automatically a blocking finding.
