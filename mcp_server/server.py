"""MCP tool surface (MASTER_PLAN Part D).

Exposes the pipeline as named tools any agent (Hermes/Codex/Claude) can call. If the `mcp`
SDK is installed it can be served over MCP; without it, `dispatch()` provides the same
callable surface so the system works today. The audit/sign-off tools gate release.
"""
from __future__ import annotations

from engines.audit.audit import approve_report
from engines.brain.orchestrator import run_pipeline


def tool_run_finance_card(actuals_csv: str, budget_csv: str, cfg: dict, approver: str | None = None):
    return run_pipeline(actuals_csv, budget_csv, cfg, approver=approver)


def tool_approve_report(audit_result, approver: str, note: str = ""):
    return approve_report(audit_result, approver, note)


TOOLS = {
    "run_finance_card": tool_run_finance_card,   # ingest..card..audit (the trust loop)
    "approve_report": tool_approve_report,        # accountable human sign-off (Part O.6)
}


def dispatch(tool: str, **kwargs):
    if tool not in TOOLS:
        raise KeyError(f"unknown tool '{tool}'. Available: {list(TOOLS)}")
    return TOOLS[tool](**kwargs)
