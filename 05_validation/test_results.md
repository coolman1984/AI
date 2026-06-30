# Test Results

Command: `pytest -q`   Result: **26 passed**   Lint: `ruff check .` → All checks passed.
Date: 2026-06-30. Reproduce: `pip install -r requirements.txt && pytest -q`.

| Suite | Covers |
|---|---|
| test_data_pipeline | ingest, clean (total/dupe/junk + conservation), variance reconciles |
| test_card_and_audit | card refuses uncited numbers; audit recompute; tamper caught; sign-off gate |
| test_documents | real PDF extraction; cited search; poor-text → review |
| test_ocr_cascade | **real Tesseract** read; cascade path; scanned PDF → OCR end-to-end |
| test_learning | decision memory + outcome tracking; untrusted-skill quarantine |
| test_memory | knowledge relations query; temporal change detection |
| test_serving | dashboard HTML (SVG, citation, sign-off); HTML+PPTX export |
| test_factory | planning by config; access scopes; role-scoped brief; cross-department links |
| test_orchestrator | end-to-end pipeline; MCP dispatch |
