# Success Contract

1. **Mission:** see `mission.md`.
2. **Deliverables:** runnable pipeline (`run_demo.py`), engines + tests, governance files,
   architecture docs, generated artifacts (card.html, card.pptx).
3. **Acceptance criteria (v1 pilot — MET):**
   - 200MB-capable streaming ingest design; messy-data defenses (total rows, dupes, locale).
   - Governed variance that reconciles to the cent; every card number carries evidence.
   - Independent audit re-computes numbers a second way; asks the human on low certainty;
     **nothing released without a named sign-off.**
   - Documents cited; scanned docs recovered via OCR cascade; low confidence → human review.
   - Memory: decisions stored; relations queryable; change-over-time detected.
   - Second department added by config only; access role-scoped; cross-department links.
4. **Quality criteria:** every Evaluator rubric score ≥ 0.85 (see evaluation_report.md).
5. **Data requirements:** raw inputs read-only; conservation law (`rows_in == clean+rejected`).
6. **Technical constraints:** local-first/in-house; Python 3.11; one branch `main`.
7. **Formatting/naming:** modules small + single-responsibility; per-module `AGENTS.md`.
8. **Validation method:** ruff + pytest green; demo runs end-to-end.
9. **Evidence required:** test results, demo output, generated artifacts (evidence_log.md).
10. **Failure conditions:** any uncited number on a card; audit number-mismatch; a release
    without sign-off; data leaving the network. (All guarded in code.)
11. **Human approval points:** the audit sign-off gate (Part O) — mandatory before release.
12. **Final handover:** `06_final_outputs/handover_notes.md` + `proof_of_completion.md`.

**Done means:** acceptance criteria satisfied with recorded evidence, not confidence.
v1 pilot scope: **SATISFIED**. Production-hardening items remain (task_queue.md).
