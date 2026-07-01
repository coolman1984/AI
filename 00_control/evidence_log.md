# Evidence Log

| ID | Date | Claim | Evidence type | Location | Verification | Confidence |
|----|------|-------|---------------|----------|--------------|-----------|
| E1 | 2026-06-30 | All tests pass | test run | `pytest -q` → 26 passed | re-run | High |
| E2 | 2026-06-30 | Lint clean | tool output | `ruff check .` → All checks passed | re-run | High |
| E3 | 2026-06-30 | Full pipeline runs end-to-end | demo output | `python run_demo.py` | re-run | High |
| E4 | 2026-06-30 | Variance reconciles to the cent | test | test_data_pipeline (total_variance==100.0) | re-run | High |
| E5 | 2026-06-30 | Audit catches a tampered total | test | test_card_and_audit (passed=False on mismatch) | re-run | High |
| E6 | 2026-06-30 | Low quality → human question, sign-off gates release | test+demo | test_card_and_audit; demo MCQ | re-run | High |
| E7 | 2026-06-30 | Real OCR recovers a scanned PDF | demo+test | Tesseract conf 0.95; test_ocr_cascade | re-run | High |
| E8 | 2026-06-30 | Temporal change detected | demo+test | Frame +100(05)→+550(06); test_memory | re-run | High |
| E9 | 2026-06-30 | 2nd dept by config; access-scoped; cross-links | demo+test | test_factory; demo CEO/analyst | re-run | High |
| E10 | 2026-06-30 | Real artifacts generated | files | `out/card.html, out/card.pptx` | open files | High |
| E11 | 2026-06-30 | Variance decomposition reconciles (price+volume+mix==total) | test+demo | `test_drivers`; demo -50=+50-99-1 | re-run | High |
| E12 | 2026-07-01 | Local development clone and lightweight loop bridge are ready | git+files | `git status -sb`; `git remote -v`; `.agent-loop/*`; updated `00_control/*` | re-run | High |
| E13 | 2026-07-01 | Next-phase plan is grounded in the live repo and verified baseline | tests+files | `.venv`; `pytest -q` => `28 passed, 1 skipped`; `03_design/implementation_plan.md`; updated control files | re-run | High |
| E14 | 2026-07-01 | The manager outputs now surface price/volume/mix safely and clearly | tests+demo+files | targeted pytest `8 passed, 1 skipped`; full pytest `29 passed, 1 skipped`; `run_demo.py`; `out/card.html` | re-run | High |
| E15 | 2026-07-01 | The first real workflow is now formally locked in governance files | reviewed files | `00_control/mission.md`; `00_control/open_questions.md`; `00_control/success_contract.md`; `00_control/task_queue.md`; worker draft + review in `/tmp/p2_*` | re-read | High |
| E16 | 2026-07-01 | The project now treats extraction/storage/query/calculation as the explicit engineering backbone under the locked workflow | reviewed files + tests | `00_control/mission.md`; `00_control/task_queue.md`; `03_design/implementation_plan.md`; `05_validation/issue_tracker.md`; `03_design/unified-ingestion-spine.md`; worker draft + review in `/tmp/ingestion_focus_*`; `pytest -q` => `29 passed, 1 skipped` | re-read + re-run | High |
| E17 | 2026-07-01 | Unified ingestion storage contract is now real in code, not just design | tests+files | `engines/data/ingest.py`; `tests/test_ingestion_spine.py`; targeted pytest `10 passed`; broader data pytest `13 passed`; full pytest `39 passed, 1 skipped` | re-read + re-run | High |
| E18 | 2026-07-01 | The CSV path now uses the storage contract through a reusable tracked wrapper, starting IS2 for real | tests+files | `engines/data/ingest.py`; `tests/test_ingestion_spine.py`; targeted pytest `13 passed`; broader data pytest `16 passed`; full pytest `42 passed, 1 skipped` | re-read + re-run | High |
