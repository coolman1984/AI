"""Tests for Phase 7 advanced decision support."""

import pytest


def test_decision_brief_imports():
    """decision-brief should import cleanly."""
    from skills.decision_brief.run import run_decision_brief
    assert callable(run_decision_brief)


def test_decision_brief_no_data():
    """Decision brief without data should return options but note insufficient evidence."""
    from skills.decision_brief.run import run_decision_brief
    result = run_decision_brief("Test decision")
    assert result["status"] == "done"
    assert "topic" in result
    assert len(result["options"]) == 3


def test_decision_brief_with_custom_options():
    """Decision brief should accept custom options."""
    from skills.decision_brief.run import run_decision_brief
    custom = [
        {"name": "Option A", "impact": "Low risk"},
        {"name": "Option B", "impact": "High reward"},
    ]
    result = run_decision_brief("Custom decision", options=custom)
    assert len(result["options"]) == 2
    assert result["options"][0]["option"] == "Option A"


def test_decision_brief_governance_label():
    """Every projection should carry an evidence-linked label."""
    from skills.decision_brief.run import run_decision_brief
    result = run_decision_brief("Governance test")
    assert "governance" in result
    assert "evidence-linked" in result["governance"]
