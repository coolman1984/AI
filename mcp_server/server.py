"""MCP tool surface (MASTER_PLAN Part D).

Exposes the pipeline as named tools any agent (Hermes/Codex/Claude) can call. If the `mcp`
SDK is installed it can be served over MCP; without it, `dispatch()` provides the same
callable surface so the system works today. The audit/sign-off tools gate release.
"""
from __future__ import annotations

from engines.audit.audit import approve_report
from engines.brain.orchestrator import run_pipeline
from engines.docs.extract import extract_document
from engines.docs.search import search_documents


def tool_run_finance_card(actuals_csv, budget_csv, cfg, approver=None, budget_pdf=None):
    return run_pipeline(actuals_csv, budget_csv, cfg, approver=approver, budget_pdf=budget_pdf)


def tool_approve_report(audit_result, approver: str, note: str = ""):
    return approve_report(audit_result, approver, note)


def tool_search_documents(paths: list[str], query: str, cfg: dict, top_k: int = 3):
    docs = [extract_document(p, cfg) for p in paths]
    return search_documents(docs, query, top_k)


def tool_what_changed(entity: str, attribute: str = "material_cost_variance", backend: str = "local_json"):
    from engines.brain.memory import get_temporal_memory
    return get_temporal_memory(backend).changes(entity, attribute)


def tool_related(subject: str, backend: str = "local_json"):
    from engines.brain.memory import get_knowledge_memory
    return get_knowledge_memory(backend).relations_for(subject)


def tool_run_department(lens_name, actuals_csv, baseline_csv, cfg, approver=None, period="2026-05"):
    from engines.brain.factory import run_department
    return run_department(lens_name, actuals_csv, baseline_csv, cfg, approver, period)


def tool_factory_brief(results: dict, role: str, cfg: dict):
    from engines.brain.factory import cross_department_entities, factory_brief
    brief = factory_brief(results, role, cfg)
    brief["cross_department"] = cross_department_entities(role, cfg)
    return brief


TOOLS = {
    "run_finance_card": tool_run_finance_card,   # ingest..card..audit (the trust loop)
    "approve_report": tool_approve_report,        # accountable human sign-off (Part O.6)
    "search_documents": tool_search_documents,    # cite PDFs/Word/PPT as evidence (Stage 4)
    "what_changed": tool_what_changed,            # temporal memory: change over time (Stage 5)
    "related": tool_related,                      # knowledge memory: relationships (Stage 5)
    "run_department": tool_run_department,        # any department via its lens (Stage 7)
    "factory_brief": tool_factory_brief,          # cross-department CEO/CFO brief, role-scoped
}


def dispatch(tool: str, **kwargs):
    if tool not in TOOLS:
        raise KeyError(f"unknown tool '{tool}'. Available: {list(TOOLS)}")
    return TOOLS[tool](**kwargs)
