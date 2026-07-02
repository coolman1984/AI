"""MCP tool surface (MASTER_PLAN Part D).

Exposes the pipeline as named tools any agent (Hermes/Codex/Claude) can call. If the `mcp`
SDK is installed it can be served over MCP; without it, `dispatch()` provides the same
callable surface so the system works today. The audit/sign-off tools gate release.
"""
from __future__ import annotations

from pathlib import Path

from engines.audit.audit import approve_report
from engines.audit.brief_audit import MappingExtractor, audit_brief_claims
from engines.brain.orchestrator import run_pipeline
from engines.docs import report_reader as report_reader_module
from engines.docs.extract import extract_document
from engines.docs.glossary import FactoryGlossary
from engines.docs.image_profile import profile_deck_images
from engines.docs.search import search_documents
from engines.docs.summarize import summarize_document
from engines.docs.translation_check import check_translation_terms
from engines.docs.workflow_record import extract_workflow_record
from engines.email.extract import ingest_email
from serving.decision_brief import build_hq_deck_brief


def tool_run_finance_card(actuals_csv, budget_csv, cfg, approver=None, budget_pdf=None, standards_csv=None):
    return run_pipeline(
        actuals_csv,
        budget_csv,
        cfg,
        approver=approver,
        budget_pdf=budget_pdf,
        standards_csv=standards_csv,
    )


def tool_approve_report(audit_result, approver: str, note: str = ""):
    return approve_report(audit_result, approver, note)


def tool_search_documents(paths: list[str], query: str, cfg: dict, top_k: int = 3):
    docs = [extract_document(p, cfg) for p in paths]
    return search_documents(docs, query, top_k)


def tool_ingest_deck(path: str, cfg: dict):
    return extract_document(path, cfg)


def tool_ingest_email(path: str, cfg: dict, metadata: dict | None = None):
    return ingest_email(path, cfg, metadata).to_dict()


def tool_profile_deck_images(path: str, cfg: dict):
    return profile_deck_images(path, cfg).to_dict()


def tool_summarize_document(path: str, cfg: dict):
    return summarize_document(
        path,
        llm=report_reader_module.OpencodeLLM(),
        cfg=cfg,
        source_path=str(Path(path).resolve()),
    )


def tool_extract_workflow_record(payload: dict, stamp: dict | None = None):
    return extract_workflow_record(payload, stamp=stamp).to_dict()


def tool_check_translation_terms(
    payload: dict,
    glossary_payload: dict,
    critical_terms: list[str] | None = None,
    back_translations: dict[str, str] | None = None,
):
    record = extract_workflow_record(payload)
    glossary = FactoryGlossary.from_dict(glossary_payload)
    result = check_translation_terms(
        record,
        glossary,
        critical_terms=critical_terms,
        back_translations=back_translations,
    )
    return {
        "glossary_match_ratio": result.glossary_match_ratio,
        "review_flags": [flag.__dict__ for flag in result.review_flags],
        "blocked": result.blocked,
        "checked_terms": result.checked_terms,
    }


def tool_audit_brief_claims(
    claims: list[dict],
    citations: dict[str, str],
    second_extractions: dict[str, str],
    cfg: dict | None = None,
):
    audit = audit_brief_claims(
        claims,
        citations,
        MappingExtractor(second_extractions),
        cfg=cfg,
    )
    return {
        "passed": audit.passed,
        "needs_human": audit.needs_human,
        "certainty": audit.certainty,
        "issues": audit.issues,
        "questions": audit.questions,
        "recomputed": audit.recomputed,
    }


def tool_build_hq_deck_brief(
    payload: dict,
    stamp: dict,
    glossary_payload: dict,
    citations: dict[str, str],
    second_extractions: dict[str, str],
    coverage_report: dict,
    critical_terms: list[str] | None = None,
    back_translations: dict[str, str] | None = None,
    audit_cfg: dict | None = None,
):
    return build_hq_deck_brief(
        payload,
        stamp=stamp,
        glossary_payload=glossary_payload,
        citations=citations,
        second_extractions=second_extractions,
        coverage_report=coverage_report,
        critical_terms=critical_terms,
        back_translations=back_translations,
        audit_cfg=audit_cfg,
    ).to_dict()


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


def tool_explain_variance(actuals_csv, standards_csv, cfg, lens=None):
    from engines.data.drivers import run_variance_decomposition
    return run_variance_decomposition(actuals_csv, standards_csv, cfg, lens)


TOOLS = {
    "run_finance_card": tool_run_finance_card,   # ingest..card..audit (the trust loop)
    "approve_report": tool_approve_report,        # accountable human sign-off (Part O.6)
    "search_documents": tool_search_documents,    # cite PDFs/Word/PPT as evidence (Stage 4)
    "ingest_email": tool_ingest_email,            # email body + attachment intake
    "ingest_deck": tool_ingest_deck,              # deck/PPTX extraction into Document evidence shape
    "profile_deck_images": tool_profile_deck_images,  # image-only share and OCR readiness
    "summarize_document": tool_summarize_document,  # chunked document summary + coverage report
    "extract_workflow_record": tool_extract_workflow_record,  # validate structured deck understanding
    "check_translation_terms": tool_check_translation_terms,  # glossary match and term disagreement checks
    "audit_brief_claims": tool_audit_brief_claims,  # independent non-numeric brief audit
    "build_hq_deck_brief": tool_build_hq_deck_brief,  # first Tier 2 deck brief gate
    "what_changed": tool_what_changed,            # temporal memory: change over time (Stage 5)
    "related": tool_related,                      # knowledge memory: relationships (Stage 5)
    "run_department": tool_run_department,        # any department via its lens (Stage 7)
    "factory_brief": tool_factory_brief,          # cross-department CEO/CFO brief, role-scoped
    "explain_variance": tool_explain_variance,    # price/volume/mix decomposition (T8)
}


def dispatch(tool: str, **kwargs):
    if tool not in TOOLS:
        raise KeyError(f"unknown tool '{tool}'. Available: {list(TOOLS)}")
    return TOOLS[tool](**kwargs)
