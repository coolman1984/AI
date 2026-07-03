# Validation Plan
- Unit + integration tests (pytest, 26 passing) mirror each module.
- Real OCR tests exercise Tesseract; memory/factory tests prove change-tracking + access.
- The audit layer is runtime validation: independent recompute + conservation + evidence.
- Gate: ruff clean + pytest green before any commit. CI runs both on push.
