"""Tests for MCP access control at dispatch (F.2)."""

from __future__ import annotations

import yaml
import pytest

from mcp_server.server import TOOLS, dispatch, tool_run_finance_card


def _cfg():
    return yaml.safe_load(open("config.yaml"))


def test_unauthorized_role_cannot_call_scoped_finance_tool():
    with pytest.raises(PermissionError, match="cannot call tool"):
        dispatch(
            "run_finance_card",
            caller_role="planner",
            caller_cfg=_cfg(),
            actuals_csv="a",
            budget_csv="b",
            cfg={"roles": {}},
        )


def test_unauthorized_role_cannot_call_scoped_factory_tool():
    with pytest.raises(PermissionError, match="cannot call tool"):
        dispatch(
            "factory_brief",
            caller_role="analyst",
            caller_cfg=_cfg(),
            results={},
            role="analyst",
            cfg=_cfg(),
        )


def test_authorized_wildcard_role_can_call_allowed_tool():
    out = dispatch("run_golden_eval", caller_role="ceo", caller_cfg=_cfg())
    assert out["passed"] is True
    assert callable(tool_run_finance_card)


def test_unknown_tool_raises_unknown_tool_error_not_access_leak():
    with pytest.raises(KeyError, match="unknown tool"):
        dispatch("nonexistent_tool_xyz", caller_role="ceo", caller_cfg=_cfg())


def test_dispatch_without_role_skips_access_check_for_backward_compat():
    out = dispatch("run_golden_eval")
    assert "passed" in out


def test_all_scoped_tools_have_scope_mapping():
    from mcp_server.server import TOOL_SCOPES

    for tool_name in TOOL_SCOPES:
        assert tool_name in TOOLS