# serving — manager card + output/design

**Does:** `card.py` builds the one-A4 card (BLUF, ≤5 cited numbers, confidence) and refuses
any number without evidence. When variance decomposition is available, the card also carries a
structured `driver_split` (price / volume / mix) without breaking the one-A4 budget.
`open_design.py` renders it visually: a real HTML dashboard (inline SVG variance-bridge chart)
plus a real PPTX deck (python-pptx); nexu-io **Open Design** plugs in via `OpenDesignRenderer`
for branded dashboards/PDF.

**Public interface:** `card.make_manager_card(bridge, data_quality, lens=None, decomposition=None)`,
`card.compute_data_quality`, `card.render_text`, `open_design.render_dashboard_html`,
`open_design.export_report`.

**Invariants:** output-only — never computes or invents a number; renders only an audited,
signed-off card. If `driver_split` is shown, it must carry evidence and match an audited
decomposition; management-facing "why" numbers do not bypass the main trust gate.

**Tests:** `pytest tests/test_card_and_audit.py tests/test_serving.py`
