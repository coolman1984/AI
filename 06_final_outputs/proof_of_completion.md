# Proof of Completion — v1 Pilot

Scope proven: Stages 0–7 (v1 pilot). This is NOT the whole product (production-hardening and
heavy-backend activation remain — see task_queue.md). What is proven, with evidence:

| Acceptance criterion | Proof | Evidence ID |
|---|---|---|
| Pipeline runs end-to-end | `python run_demo.py` completes | E3 |
| Numbers calculated, reconcile to the cent | variance total == 100.0 | E4 |
| Every card number cited; uncited refused | card.validate() raises without evidence | E5 |
| Independent audit catches wrong numbers | tampered total → passed=False | E5 |
| Human sign-off gates release; low quality → question | demo MCQ + sign-off | E6 |
| Documents cited; scanned recovered via OCR | Tesseract conf 0.95 on scanned PDF | E7 |
| Memory: change over time | Frame +100(05) → +550(06) | E8 |
| 2nd dept by config; role-scoped; cross-links | CEO sees both; analyst scoped out | E9 |
| Quality + lint gates | 26 tests pass; ruff clean | E1, E2 |
| Visual artifacts produced | out/card.html, out/card.pptx | E10 |

Evaluator verdict (evaluation_report.md): all rubric scores ≥ 0.85 → PASS for v1 pilot scope.
Reproduce: `pip install -r requirements.txt && pytest -q && python run_demo.py`.
