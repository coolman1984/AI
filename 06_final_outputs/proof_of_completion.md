# Proof Of Completion - v1 Pilot

> Historical v1 proof. Current architecture and phase order are
> `03_design/assistant_master_plan.md` and `03_design/phase_a_cards.md`.

Scope proven: Stages 0-7 (v1 pilot). This is not the whole product. What was proven,
with evidence:

| Acceptance criterion | Proof | Evidence ID |
|---|---|---|
| Pipeline runs end-to-end | `python run_demo.py` completes | E3 |
| Numbers calculated, reconcile to the cent | variance total == 100.0 | E4 |
| Every card number cited; uncited refused | card.validate() raises without evidence | E5 |
| Independent audit catches wrong numbers | tampered total -> passed=False | E5 |
| Human sign-off gates release; low quality asks a question | demo MCQ + sign-off | E6 |
| Documents cited; scanned recovered via OCR | Tesseract conf 0.95 on scanned PDF | E7 |
| Memory: change over time | Frame +100(05) -> +550(06) | E8 |
| 2nd dept by config; role-scoped; cross-links | CEO sees both; analyst scoped out | E9 |
| Quality + lint gates | tests pass; ruff clean | E1, E2 |
| Visual artifacts produced | out/card.html, out/card.pptx | E10 |

Evaluator verdict (`00_control/evaluation_report.md`): PASS for v1 pilot scope.
Reproduce: `pip install -r requirements.txt && pytest -q && python run_demo.py`.
