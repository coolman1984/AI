# Progress

> Historical progress log. For current architecture and next work, read
> `03_design/assistant_master_plan.md`, `03_design/phase_a_cards.md`, and
> `00_control/restart_notes.md`. Older entries keep their original task labels
> for audit history.

Date: 2026-06-30
Completed: Stages 0-7 of Factory Second Brain (foundation -> numeric trust loop -> audit +
sign-off -> decision memory -> documents + OCR cascade -> knowledge + temporal memory ->
dashboard + PPTX -> multi-department + factory brain). Adopted the Master Agent OS and
instantiated the governance file tree from real state.
Files changed: engines/*, serving/*, shared/*, mcp_server/*, gov/*, tests/*, run_demo.py,
docs (MASTER_PLAN, FACTORY_SECOND_BRAIN, BUILD, RISK_AND_GAPS_AUDIT, AGENTS, CODEX_PLAN),
governance (00_control..07_archive).
Validation performed: ruff clean; pytest 26 passed; run_demo end-to-end OK.
Evidence recorded: E1-E10.
Problems found: none open (see issue_tracker.md for by-design adapter gaps).
Next task: T8 - price/qty/mix variance decomposition.
Confidence level: High (verified by tests + demo), with honest caveats on heavy adapters.

---
Date: 2026-06-30 (T8)
Completed: T8 price/volume/mix variance decomposition (`engines/data/variance.price_volume_mix`
+ `engines/data/drivers` runner + MCP tool `explain_variance` + `finance_standards.csv`). It
explains why a cost variance moved and reconciles exactly (`price + volume + mix == total`).
Files changed: `engines/data/variance.py`, `engines/data/drivers.py`, `shared/contracts/models.py`,
`mcp_server/server.py`, `run_demo.py`, `tests/test_drivers.py`, `data/sample/finance_standards.csv`.
Validation performed: ruff clean; pytest 29 passed; demo shows -50 = +50 -99 -1.
Evidence recorded: E11.
Problems found: none.
Next task: T8b - surface the drivers on the card + dashboard.
Confidence level: High (reconciliation proven by test + demo).

---
Date: 2026-07-01
Completed: audited the architecture-vs-reality gap, verified the local baseline on `.venv`
(`pytest 28 passed, 1 skipped`), created a governed implementation plan for the next phases,
and expanded T8b into execution slices.
Files changed: `03_design/implementation_plan.md`, `00_control/task_queue.md`,
`00_control/decisions.md`, `05_validation/issue_tracker.md`.
Validation performed: `. .venv/bin/activate && pytest -q`.
Evidence recorded: E13.
Problems found: branch-policy divergence is controlled (I4); heavy infrastructure remains
intentionally blocked behind P2 gates (I1).
Next task: T8b1 - add a typed driver payload to the manager card contract.
Confidence level: High (plan grounded in current code + green tests).

---
Date: 2026-07-01 (T8b)
Completed: surfaced the price/volume/mix view in the manager card and HTML dashboard, with a
truth-preserving refinement: the driver panel is labeled explicitly as an operating view against
standard cost, so it cannot be confused with the main budget variance headline.
Files changed: `shared/contracts/models.py`, `serving/{card,open_design}.py`,
`engines/brain/orchestrator.py`, `mcp_server/server.py`, `run_demo.py`, tests, and module
`AGENTS.md` files.
Validation performed: targeted pytest => `8 passed, 1 skipped`; full pytest => `29 passed, 1 skipped`;
`python run_demo.py` confirmed the card text and visual output include the new driver view.
Evidence recorded: E14.
Problems found: none in this slice; the next bottleneck is real data, not rendering.
Next task: P2 - lock the first real finance workflow and profile one real export.
Confidence level: High (feature implemented, tested, and demoed with honest labeling).

---
Date: 2026-07-01 (P2.1)
Completed: locked the first real workflow in governance files as monthly material cost variance
review for Cost Control / Finance, and made the current non-goals explicit so the team cannot drift
into heavy infrastructure early.
Files changed: `00_control/mission.md`, `00_control/open_questions.md`,
`00_control/success_contract.md`, `00_control/task_queue.md`.
Validation performed: writer worker draft reviewed by reviewer worker; final scope trimmed to the
smallest correct slice and re-read in repo.
Evidence recorded: E15.
Problems found: no real export has landed yet, so P2.2 remains the active bottleneck.
Next task: P2.2 - receive and profile one real export.
Confidence level: High (scope locked, next move clarified).

---
Date: 2026-07-01 (IS1)
Completed: turned the unified ingestion storage contract into working code: run lifecycle tracking,
reject persistence, and a minimal DuckDB schema now exist and are verified by dedicated tests.
Files changed: `engines/data/ingest.py`, `tests/test_ingestion_spine.py`, plus governance files
reflecting the new project state.
Validation performed: new targeted pytest => `10 passed`; data-slice pytest => `13 passed`; full
pytest => `39 passed, 1 skipped`.
Evidence recorded: E17.
Problems found: the contract exists, but Excel/CSV still uses the old demo-style path and needs
IS2; P2.2 still waits on the first real export.
Next task: two-track move - P2.2 externally and IS2 internally.
Confidence level: High (contract implemented, tested, and integrated without breaking the project).

---
Date: 2026-07-01 (IS2.1)
Completed: started IS2 for real by adding a tracked CSV ingestion path on top of the new storage
contract, so callers can create, run, and finish a tracked ingest in one reusable step instead of
manual three-step chaining.
Files changed: `engines/data/ingest.py`, `tests/test_ingestion_spine.py`, and governance files
reflecting that IS2 has begun.
Validation performed: targeted pytest => `13 passed`; data-slice pytest => `16 passed`; full pytest
=> `42 passed, 1 skipped`.
Evidence recorded: E18.
Problems found: CSV is now tracked cleanly, but the path is still text-first demo ingestion and
needs the next IS2 slice for typed reusable ingestion; P2.2 still waits on the first real export.
Next task: continue IS2 internally while waiting for P2.2 externally.
Confidence level: High (IS2 has moved from plan to code without fake Excel breadth).

---
Date: 2026-07-01 (IS2.2)
Completed: closed the gap IS2.1 left open - `ingest_csv_tracked` previously always reported
`reject_count=0`; it now detects embedded total/subtotal rows and exact-duplicate rows, quarantines
them to `ingestion_rejects` with a reason, and keeps only accepted rows in the target table.
Files changed: `engines/data/ingest.py`, `tests/test_ingestion_spine.py`, `engines/data/AGENTS.md`,
`00_control/{task_queue,evidence_log,restart_notes}.md`.
Validation performed: targeted pytest `tests/test_ingestion_spine.py` => `16 passed`; full pytest
=> `42 passed, 4 skipped`; `ruff check .` => clean.
Evidence recorded: E19.
Problems found: none in this slice; multi-sheet Excel (IS2.3) and per-column type inference
(IS2.4) are still open, and P2.2 still waits on the first real export.
Next task: IS2.3 or IS2.4.
Confidence level: High (reject flow implemented test-first, conservation law asserted).

---
Date: 2026-07-01 (Ingestion focus)
Completed: translated Mohamed's new priority into project governance: extraction from Excel, PDF
tables, PowerPoint, and email into local storage with query + calculation readiness is now the
explicit engineering backbone under the locked workflow.
Files changed: `00_control/mission.md`, `00_control/task_queue.md`, `03_design/implementation_plan.md`,
`05_validation/issue_tracker.md`, `03_design/unified-ingestion-spine.md`.
Validation performed: writing worker draft reviewed by reviewer worker; schema design corrected to
avoid all-text generic columns; repo files re-read after patching; `pytest -q` => `29 passed, 1 skipped`.
Evidence recorded: E16.
Problems found: P2.2 still depends on an external real export; PowerPoint and email remain planned
but not yet implemented.
Next task: two-track move - wait for the first real export externally, and start IS1 internally.
Confidence level: High (priority clarified without fake breadth).

---
Date: 2026-07-02 (OSS-backed planning alignment)
Completed: reworked the live planning path so later phases use repo-owned wrappers around
clean-licensed OSS where the approved plan allows it, instead of assuming greenfield engine builds
across the board. The queue now matches the B-F card structure and archives the stale umbrella rows
it replaced.
Files changed: `03_design/oss_reference_evaluation.md`,
`03_design/current_implementation_plan.md`, `03_design/phase_b_to_f_cards.md`,
`00_control/task_queue.md`, `00_control/restart_notes.md`, `00_control/run_log.md`.
Validation performed: re-read the approved master plan, local OSS README/license files, the revised
B-F cards, and the rewritten task queue; checked that the next-action pointer still lands on A0.2
and that stale rows (`IS4`, `IS5`, `T9`, `T10`, `T11`) are now archived.
Evidence recorded: E21.
Problems found: this is planning/governance progress only; no product code or tests were changed in
this slice, and Phase A implementation still resumes at A0.2.
Next task: A0.2, then later-phase execution should follow the OSS-backed queue (`RapidOCR` first,
`Docling` later, stable `mcp-python-sdk` later, graph backends only behind contracts).
Confidence level: High (live planning docs and queue now tell one consistent story).

---
Date: 2026-07-02 (A0 gate green)
Completed: verified that the deterministic verifier, citation-support checks, privacy gate,
external-call ledger, LLM chokepoint, prompt-injection defense, report-reader gate wiring, and
render-time provenance tagging are all green together. The one live failure was the dashboard HTML
path not forcing provenance tags; that path now renders tags visibly and fails closed on unknown
sources.
Files changed: `serving/open_design.py`, `00_control/{task_queue,restart_notes,evidence_log}.md`.
Validation performed: targeted pytest `tests/test_verify.py` => `14 passed`; targeted pytest
`tests/test_serving.py` => `3 passed, 1 skipped`; full `pytest -q` => `106 passed, 4 skipped`;
`ruff check serving/open_design.py` => clean.
Evidence recorded: E22.
Problems found: none in the Phase A rail stack after the serving fix; the project is now ready to
start B.1 while P2.2 remains externally blocked.
Next task: B.1 - native PPTX extractor (thin deterministic path).
Confidence level: High (suite green and queue now matches the repo state).
