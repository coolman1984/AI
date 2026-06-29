# serving — manager card + output/design

**Does:** `card.py` builds the one-A4 card (BLUF, ≤5 cited numbers, confidence) and refuses
any number without evidence. `open_design.py` renders it (built-in HTML now; nexu-io
Open Design plugs in for dashboards/PDF/PPTX).
**Public interface:** `card.make_manager_card`, `card.compute_data_quality`,
`card.render_text`, `open_design.get_renderer`.
**Invariants:** output-only — never computes or invents a number; renders only an audited,
signed-off card.
**Tests:** `pytest tests/test_card_and_audit.py`
