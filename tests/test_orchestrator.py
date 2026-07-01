import yaml

from engines.brain.orchestrator import run_pipeline
from mcp_server.server import dispatch


def _cfg():
    return yaml.safe_load(open("config.yaml"))


def test_end_to_end_pipeline_releases_after_signoff():
    out = run_pipeline(
        "data/sample/finance_actuals.csv",
        "data/sample/finance_budget.csv",
        _cfg(),
        approver="analyst_mohamed",
        standards_csv="data/sample/finance_standards.csv",
    )
    assert out["audit"].passed is True
    assert out["released"] is True
    assert "OVER budget" in out["card_text"] or "UNDER budget" in out["card_text"]
    assert "OPERATING VIEW (vs standard cost)" in out["card_text"]
    assert "Price effect" in out["html"]
    assert "<h1>" in out["html"] and "Material cost" in out["html"]


def test_mcp_dispatch_runs_the_tool():
    out = dispatch(
        "run_finance_card",
        actuals_csv="data/sample/finance_actuals.csv",
        budget_csv="data/sample/finance_budget.csv",
        cfg=_cfg(),
        approver="cfo",
        standards_csv="data/sample/finance_standards.csv",
    )
    assert out["bridge"].total_variance == 100.0
    assert out["card"].driver_split is not None
