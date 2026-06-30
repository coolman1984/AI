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
| E10 | 2026-06-30 | Real artifacts generated | files | out/card.html, out/card.pptx | open files | High |
