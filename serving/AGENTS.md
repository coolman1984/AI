# serving — manager card + executive outputs + rendering

**Does:** `card.py` builds the one-A4 card (BLUF, ≤5 cited numbers, confidence) and refuses
any number without evidence. `decision_brief.py` assembles HQ deck briefs (B.9) and executive
decision briefs (D.1). `meeting_pack.py` and `report_article.py` assemble CFO/CEO packs and
cited management articles from brain stores (D.2-D.3). `signoff.py` enforces named human
sign-off on all executive output types (D.4). `open_design.py` renders finance cards and
executive outputs to HTML/PPTX through one shared rendering layer (D.5).

**Public interface:** `card.make_manager_card(...)`, `build_decision_brief(...)`,
`build_hq_deck_brief(...)`, `build_meeting_pack(...)`, `build_report_article(...)`,
`sign_off_output(...)`, `open_design.render_dashboard_html`, `open_design.export_report`,
`open_design.export_executive_output`.

**Invariants:** output-only — never computes or invents a number; unsigned outputs render as
draft/watermarked only; executive recommendations require cited evidence; sign-off cannot
self-release.

**Tests:** `pytest tests/test_card_and_audit.py tests/test_serving.py tests/test_hq_deck_brief.py tests/test_decision_brief.py tests/test_meeting_pack.py tests/test_report_article.py tests/test_executive_signoff.py tests/test_serving_outputs.py`
