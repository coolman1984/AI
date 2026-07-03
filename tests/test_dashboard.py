"""Tests for dashboard builder (Phase 5)."""

import os


def test_build_dashboard_missing_report():
    """Building a dashboard from a non-existent report should fail."""
    from tools.build_dashboard import build_dashboard
    result = build_dashboard(report_path="/nonexistent/report.md")
    assert result["status"] == "failed"


def test_build_dashboard_from_fixture(tmp_path):
    """Building a dashboard from a fixture report should produce HTML."""
    import tools.build_dashboard as bd
    from tools.build_dashboard import build_dashboard

    # Create a fixture report
    report_path = tmp_path / "2026-06_test_report.md"
    report_path.write_text("""# Management Report

## BLUF
Total validated: 1,234,567.89

## Key Numbers
| Metric | Value | Provenance |
|---|---|---|
| Total Amount | 1,234,567.89 | AUDITED |
| Row Count | 42,000 | AUDITED |
""")

    original_dashboards = bd._DASHBOARDS_DIR
    bd._DASHBOARDS_DIR = tmp_path / "dashboards"

    try:
        result = build_dashboard(report_path=str(report_path), period="2026-06")
        assert result["status"] == "done"
        assert result["metrics_count"] >= 2
        assert os.path.isfile(result["dashboard_path"])

        # Read back and check content
        html = open(result["dashboard_path"]).read()
        assert "1,234,567.89" in html
        assert "AUDITED" in html
    finally:
        bd._DASHBOARDS_DIR = original_dashboards
