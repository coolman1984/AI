import importlib.util

import pytest
import yaml

from engines.brain.orchestrator import run_pipeline
from serving.card import render_text
from serving.open_design import export_report, render_dashboard_html
from shared.contracts.models import EvidenceRef, NumberFact


def _ctx():
    out = run_pipeline(
        "data/sample/finance_actuals.csv",
        "data/sample/finance_budget.csv",
        yaml.safe_load(open("config.yaml")),
        approver="analyst_mohamed",
        budget_pdf="data/sample/budget_approval_2026.pdf",
        standards_csv="data/sample/finance_standards.csv",
    )
    return out["ctx"]


def test_dashboard_html_has_chart_numbers_signoff_and_citation():
    html = render_dashboard_html(_ctx())
    assert "<svg" in html                         # variance bridge chart
    assert "Material cost" in html                # headline
    assert "signed off by analyst_mohamed" in html
    assert "budget_approval_2026.pdf" in html     # PDF citation
    assert "Confidence" in html
    assert "Price effect" in html
    assert "Volume effect" in html
    assert "Mix effect" in html


def test_export_writes_html_and_pptx(tmp_path):
    paths = export_report(_ctx(), out_dir=str(tmp_path))
    assert paths["html"] and open(paths["html"]).read().startswith("<!doctype html>")
    if importlib.util.find_spec("pptx"):
        assert paths["pptx"] and paths["pptx"].endswith(".pptx")
        assert (tmp_path / "card.pptx").stat().st_size > 0
    else:  # pragma: no cover
        pytest.skip("python-pptx not installed")


def test_render_text_shows_audited_and_claimed_tags():
    ctx = _ctx()
    claim_fact = NumberFact(
        "Deck claim",
        42.0,
        EvidenceRef(
            source="claim:deck_page_3",
            locator="page=3",
            method="quoted figure",
            value=42.0,
        ),
    )
    ctx["card"].key_numbers.append(claim_fact)

    rendered = render_text(ctx["card"])
    assert "AUDITED-FROM-QUERY" in rendered
    assert "CLAIMED-FROM-DECK" in rendered


def test_render_dashboard_html_fails_closed_on_unknown_provenance():
    ctx = _ctx()
    ctx["card"].key_numbers[0] = NumberFact(
        "Mystery number",
        1.0,
        EvidenceRef(
            source="mystery:source",
            locator="x",
            method="unknown",
            value=1.0,
        ),
    )

    with pytest.raises(ValueError, match="Unknown evidence source prefix"):
        render_dashboard_html(ctx)
