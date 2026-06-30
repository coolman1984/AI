"""Stage 7: second department by config, role-scoped access, cross-department brain."""
import shutil

import yaml

from engines.brain.factory import cross_department_entities, factory_brief, run_department
from gov.access import can_access
from shared.lenses import load_lens


def _cfg():
    return yaml.safe_load(open("config.yaml"))


def test_planning_runs_on_same_engine_via_config_only():
    # Planning is a different lens (output vs plan), NOT new engine code.
    lens = load_lens("planning")
    assert lens["metric"] == "output_plan_variance" and lens["value_col"] == "output"
    out = run_department(
        "planning", "data/sample/planning_actuals.csv", "data/sample/planning_plan.csv",
        _cfg(), approver="planner", period="2026-05",
    )
    assert out["bridge"].reconciles()
    assert out["scope"] == "planning"
    assert "Output" in out["card"].headline and "plan" in out["card"].headline.lower()
    # clean still defends: a blank-key total row + a duplicate are rejected
    reasons = sorted(r.reason for r in out["rejects"])
    assert "total_or_missing_key" in reasons and "duplicate" in reasons


def test_access_control_scopes():
    cfg = _cfg()
    assert can_access("ceo", "planning", cfg) is True
    assert can_access("cfo", "finance:costing", cfg) is True
    assert can_access("analyst", "planning", cfg) is False     # finance analyst can't see planning
    assert can_access("planner", "finance:costing", cfg) is False


def test_factory_brief_is_role_scoped_and_finds_cross_links():
    shutil.rmtree(".brain", ignore_errors=True)
    cfg = _cfg()
    fin = run_department("finance", "data/sample/finance_actuals.csv",
                         "data/sample/finance_budget.csv", cfg, approver="cfo")
    plan = run_department("planning", "data/sample/planning_actuals.csv",
                          "data/sample/planning_plan.csv", cfg, approver="planner")
    results = {"finance": fin, "planning": plan}

    ceo = factory_brief(results, "ceo", cfg)
    assert len(ceo["visible"]) == 2 and ceo["hidden"] == []

    analyst = factory_brief(results, "analyst", cfg)
    assert [v["department"] for v in analyst["visible"]] == ["Finance / Cost Control"]
    assert "Planning" in analyst["hidden"]

    # CEO sees cross-department entities (same sub_assembly tracked in both depts)
    links = cross_department_entities("ceo", cfg)
    entities = {link["entity"] for link in links}
    assert {"Frame", "Panel", "Board"} <= entities
    # the finance analyst, scoped to one department, sees no cross-department links
    assert cross_department_entities("analyst", cfg) == []
