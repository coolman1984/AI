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
from engines.docs.extract import extract_document, extract_document_hard_layout
from engines.docs.glossary import FactoryGlossary
from engines.docs.image_profile import profile_deck_images
from engines.docs.search import search_documents
from engines.docs.summarize import summarize_document
from engines.docs.translation_check import check_translation_terms
from engines.docs.workflow_record import extract_workflow_record
from engines.brain.comparison import compare_factories, compare_public_ir_quarters
from engines.brain.contradictions import find_contradictions
from engines.brain.edges import EdgeStore
from engines.brain.idea_synthesis import suggest_ideas
from engines.brain.ontology import OntologyStore
from engines.brain.open_questions import OpenQuestionsStore
from engines.brain.registry import DocumentRegistry
from engines.brain.search import search_knowledge
from engines.brain.workflow_diff import diff_workflow_versions
from engines.brain.workflow_family import WorkflowFamilyStore
from engines.data.ingest import get_connection, ingest_spreadsheet, init_ingestion_schema
from engines.email.extract import ingest_email
from engines.learning.outcomes import OutcomeStore
from engines.wiki.artifacts import write_knowledge_artifact
from eval.runner import run_golden_eval
from gov.access import can_call_tool
from ops.alerts import AlertStore
from ops.backup import list_backups, restore_backup, run_backup
from ops.session_state import update_restart_notes, write_session_state
from engines.learning.feedback import record_output_feedback
from serving.decision_brief import build_decision_brief, build_hq_deck_brief
from serving.meeting_pack import build_meeting_pack
from serving.open_design import export_executive_output
from serving.report_article import build_report_article
from serving.signoff import sign_off_output


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


def tool_extract_document_hard_layout(path: str, cfg: dict | None = None):
    doc = extract_document_hard_layout(path, cfg or {"tools": {"hard_layout": True}})
    return {
        "doc_id": doc.doc_id,
        "source_filename": doc.source_filename,
        "source_format": doc.source_format,
        "pages": [
            {"page_no": page.page_no, "text": page.text, "needs_review": page.needs_review}
            for page in doc.pages
        ],
        "warnings": doc.warnings,
    }


def tool_ingest_email(path: str, cfg: dict, metadata: dict | None = None):
    return ingest_email(path, cfg, metadata).to_dict()


def tool_ingest_spreadsheet(
    path: str,
    table: str,
    *,
    on_duplicates: str = "flag",
    infer_types: bool = False,
):
    con = get_connection()
    init_ingestion_schema(con)
    return ingest_spreadsheet(
        con,
        table,
        path,
        on_duplicates=on_duplicates,
        infer_types=infer_types,
    )


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


def tool_build_decision_brief(
    question: str,
    evidence_items: list[dict],
    options: list[dict] | None = None,
    risks: list[dict] | None = None,
    recommendation: dict | None = None,
    signoff_line: str = "Pending owner sign-off",
):
    return build_decision_brief(
        question=question,
        evidence_items=evidence_items,
        options=options,
        risks=risks,
        recommendation=recommendation,
        signoff_line=signoff_line,
    ).to_dict()


def tool_build_meeting_pack(
    topic: str,
    period: str,
    audited_numbers: list[dict] | None = None,
    registry_path: str = ".brain/document_registry.json",
    families_path: str = ".brain/workflow_families.json",
    claims_path: str = ".brain/claims.json",
    questions_path: str = ".brain/open_questions.json",
    signoff_line: str = "Pending owner sign-off",
):
    return build_meeting_pack(
        topic=topic,
        period=period,
        audited_numbers=audited_numbers,
        registry_path=registry_path,
        families_path=families_path,
        claims_path=claims_path,
        questions_path=questions_path,
        signoff_line=signoff_line,
    ).to_dict()


def tool_build_report_article(
    output_type: str,
    topic: str,
    numeric_evidence: list[dict] | None = None,
    registry_path: str = ".brain/document_registry.json",
    families_path: str = ".brain/workflow_families.json",
    claims_path: str = ".brain/claims.json",
    questions_path: str = ".brain/open_questions.json",
    signoff_line: str = "Pending owner sign-off",
):
    return build_report_article(
        output_type=output_type,
        topic=topic,
        numeric_evidence=numeric_evidence,
        registry_path=registry_path,
        families_path=families_path,
        claims_path=claims_path,
        questions_path=questions_path,
        signoff_line=signoff_line,
    ).to_dict()


def tool_sign_off_output(
    output: dict,
    output_type: str,
    approver: str,
    audit_state: dict,
    note: str = "",
):
    return sign_off_output(
        output,
        output_type=output_type,
        approver=approver,
        audit_state=audit_state,
        note=note,
    )


def tool_export_executive_output(
    output: dict,
    output_type: str,
    out_dir: str = "out",
):
    return export_executive_output(output, output_type, out_dir=out_dir)


def tool_record_output_feedback(
    output_id: str,
    output_type: str,
    verdict: str,
    note: str = "",
    correction: dict | None = None,
    citation: dict | None = None,
    store_path: str = ".brain/output_feedback.json",
):
    return record_output_feedback(
        output_id=output_id,
        output_type=output_type,
        verdict=verdict,
        note=note,
        correction=correction,
        citation=citation,
        store_path=store_path,
    )


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


def tool_register_document(
    source_path: str,
    source_hash: str,
    tier: int,
    ingest_run_id: str,
    status: str = "registered",
    family_id: str | None = None,
    version_label: str | None = None,
    registry_path: str = ".brain/document_registry.json",
):
    return DocumentRegistry(path=registry_path).register_document(
        source_path=source_path,
        source_hash=source_hash,
        tier=tier,
        ingest_run_id=ingest_run_id,
        status=status,
        family_id=family_id,
        version_label=version_label,
    )


def tool_get_document_registry(
    registry_path: str = ".brain/document_registry.json",
    family_id: str | None = None,
    status: str | None = None,
    tier: int | None = None,
):
    registry = DocumentRegistry(path=registry_path)
    if family_id is None and status is None and tier is None:
        return registry.all()
    return registry.query(family_id=family_id, status=status, tier=tier)


def tool_register_workflow_version(
    family_id: str,
    family_name: str,
    version_label: str,
    source_hash: str,
    source_path: str,
    valid_from: str,
    ingest_run_id: str,
    valid_to: str | None = None,
    workflow_record: dict | None = None,
    tier: int = 2,
    registry_path: str = ".brain/document_registry.json",
    families_path: str = ".brain/workflow_families.json",
):
    store = WorkflowFamilyStore(
        path=families_path,
        registry=DocumentRegistry(path=registry_path),
    )
    return store.register_workflow_version(
        family_id=family_id,
        family_name=family_name,
        version_label=version_label,
        source_hash=source_hash,
        source_path=source_path,
        valid_from=valid_from,
        valid_to=valid_to,
        ingest_run_id=ingest_run_id,
        workflow_record=workflow_record,
        tier=tier,
    )


def tool_diff_workflow_versions(
    family_id: str,
    old_version_id: str,
    new_version_id: str,
    families_path: str = ".brain/workflow_families.json",
    registry_path: str = ".brain/document_registry.json",
):
    return diff_workflow_versions(
        family_id=family_id,
        old_version_id=old_version_id,
        new_version_id=new_version_id,
        families_path=families_path,
        registry_path=registry_path,
    )


def tool_list_open_questions(
    store_path: str = ".brain/open_questions.json",
    status: str | None = None,
    owner: str | None = None,
    workflow_ref: str | None = None,
    include_resolved: bool = True,
):
    return OpenQuestionsStore(path=store_path).list_questions(
        status=status,
        owner=owner,
        workflow_ref=workflow_ref,
        include_resolved=include_resolved,
    )


def tool_resolve_open_question(
    question_id: str,
    resolver: str,
    resolved_by_what: dict,
    store_path: str = ".brain/open_questions.json",
):
    return OpenQuestionsStore(path=store_path).resolve_question(
        question_id,
        resolver=resolver,
        resolved_by_what=resolved_by_what,
    )


def tool_link_decision_outcome(
    workflow_ref: str,
    decision_id: int | str,
    summary: str,
    outcome: str,
    evidence: list[dict] | None = None,
    outcomes_path: str = ".brain/decision_outcomes.json",
    questions_path: str | None = None,
    question_id: str | None = None,
):
    linked = OutcomeStore(path=outcomes_path).link_decision_outcome(
        workflow_ref=workflow_ref,
        decision_id=decision_id,
        summary=summary,
        outcome=outcome,
        evidence=evidence,
    )
    if questions_path and question_id:
        OpenQuestionsStore(path=questions_path).link_decision_outcome(
            question_id,
            linked["id"],
        )
    return linked


def tool_write_knowledge_artifact(
    record: dict,
    record_type: str,
    base_dir: str = "knowledge",
):
    return write_knowledge_artifact(
        record=record,
        record_type=record_type,
        base_dir=base_dir,
    )


def tool_compare_public_ir_quarters(
    period_a: str,
    period_b: str,
    record_a: dict,
    record_b: dict,
):
    return compare_public_ir_quarters(
        period_a=period_a,
        period_b=period_b,
        record_a=record_a,
        record_b=record_b,
    )


def tool_find_contradictions(
    claims_path: str = ".brain/claims.json",
    families_path: str = ".brain/workflow_families.json",
    registry_path: str = ".brain/document_registry.json",
):
    return find_contradictions(
        claims_path=claims_path,
        families_path=families_path,
        registry_path=registry_path,
    )


def tool_search_knowledge(
    query: str,
    registry_path: str = ".brain/document_registry.json",
    families_path: str = ".brain/workflow_families.json",
    claims_path: str = ".brain/claims.json",
    questions_path: str = ".brain/open_questions.json",
    include_contradictions: bool = True,
    max_results: int = 20,
):
    return search_knowledge(
        query,
        registry_path=registry_path,
        families_path=families_path,
        claims_path=claims_path,
        questions_path=questions_path,
        include_contradictions=include_contradictions,
        max_results=max_results,
    )


def tool_run_golden_eval(base_dir: str | None = None):
    return run_golden_eval(base_dir=base_dir)


def tool_resolve_entity(
    alias: str,
    ontology_path: str = ".brain/ontology.json",
):
    return OntologyStore(path=ontology_path).resolve_entity(alias)


def tool_link_workflow_edge(
    source_id: str,
    target_id: str,
    edge_type: str,
    citation: str = "",
    metadata: dict | None = None,
    edges_path: str = ".brain/edges.json",
):
    return EdgeStore(path=edges_path).link_workflow_edge(
        source_id=source_id,
        target_id=target_id,
        edge_type=edge_type,
        citation=citation,
        metadata=metadata,
    )


def tool_compare_factories(
    factory_a: str,
    factory_b: str,
    record_a: dict | None = None,
    record_b: dict | None = None,
):
    return compare_factories(
        factory_a=factory_a,
        factory_b=factory_b,
        record_a=record_a,
        record_b=record_b,
    )


def tool_suggest_ideas(
    topic: str,
    input_records: list[dict],
    contradictions: list[dict] | None = None,
    signed_off: bool = False,
):
    return suggest_ideas(
        topic=topic,
        input_records=input_records,
        contradictions=contradictions,
        signed_off=signed_off,
    )


def tool_run_backup(
    repo_root: str = ".",
    backup_dir: str = ".brain/backups",
):
    return run_backup(repo_root=repo_root, backup_dir=backup_dir)


def tool_restore_backup(
    backup_path: str,
    target_dir: str,
):
    return restore_backup(backup_path=backup_path, target_dir=target_dir)


def tool_list_ingestion_alerts(
    alerts_path: str = ".brain/ingestion_alerts.json",
    alert_type: str | None = None,
    include_resolved: bool = False,
):
    return AlertStore(path=alerts_path).list_alerts(
        alert_type=alert_type,
        include_resolved=include_resolved,
    )


def tool_write_session_state(
    current_phase: str,
    next_action: str,
    blockers: list[str] | None = None,
    evidence_pointers: list[str] | None = None,
    notes: str = "",
    output_path: str = "00_control/session_state.md",
    update_restart: bool = True,
    restart_notes_path: str = "00_control/restart_notes.md",
):
    summary = write_session_state(
        current_phase=current_phase,
        next_action=next_action,
        blockers=blockers,
        evidence_pointers=evidence_pointers,
        notes=notes,
        output_path=output_path,
    )
    if update_restart:
        update_restart_notes(summary, restart_notes_path=restart_notes_path)
    return summary


TOOL_SCOPES = {
    "run_finance_card": "finance:*",
    "approve_report": "finance:*",
    "explain_variance": "finance:*",
    "run_department": "factory:*",
    "factory_brief": "factory:*",
    "compare_factories": "factory:*",
    "run_golden_eval": "eval:*",
    "run_backup": "ops:*",
    "restore_backup": "ops:*",
    "list_ingestion_alerts": "ops:*",
    "write_session_state": "ops:*",
}


TOOLS = {
    "run_finance_card": tool_run_finance_card,   # ingest..card..audit (the trust loop)
    "approve_report": tool_approve_report,        # accountable human sign-off (Part O.6)
    "search_documents": tool_search_documents,    # cite PDFs/Word/PPT as evidence (Stage 4)
    "ingest_email": tool_ingest_email,            # email body + attachment intake
    "ingest_spreadsheet": tool_ingest_spreadsheet,  # CSV/Excel tracked ingestion spine
    "ingest_deck": tool_ingest_deck,              # deck/PPTX extraction into Document evidence shape
    "extract_document_hard_layout": tool_extract_document_hard_layout,  # Docling hard-layout opt-in path
    "profile_deck_images": tool_profile_deck_images,  # image-only share and OCR readiness
    "summarize_document": tool_summarize_document,  # chunked document summary + coverage report
    "extract_workflow_record": tool_extract_workflow_record,  # validate structured deck understanding
    "check_translation_terms": tool_check_translation_terms,  # glossary match and term disagreement checks
    "audit_brief_claims": tool_audit_brief_claims,  # independent non-numeric brief audit
    "build_hq_deck_brief": tool_build_hq_deck_brief,  # first Tier 2 deck brief gate
    "build_decision_brief": tool_build_decision_brief,  # executive decision brief (D.1)
    "build_meeting_pack": tool_build_meeting_pack,  # CFO/CEO meeting pack (D.2)
    "build_report_article": tool_build_report_article,  # management report/article (D.3)
    "sign_off_output": tool_sign_off_output,  # executive output sign-off (D.4)
    "export_executive_output": tool_export_executive_output,  # render executive outputs (D.5)
    "record_output_feedback": tool_record_output_feedback,  # owner feedback loop (D.6)
    "what_changed": tool_what_changed,            # temporal memory: change over time (Stage 5)
    "related": tool_related,                      # knowledge memory: relationships (Stage 5)
    "run_department": tool_run_department,        # any department via its lens (Stage 7)
    "factory_brief": tool_factory_brief,          # cross-department CEO/CFO brief, role-scoped
    "explain_variance": tool_explain_variance,    # price/volume/mix decomposition (T8)
    "register_document": tool_register_document,  # document registry ingest map (C.1)
    "get_document_registry": tool_get_document_registry,  # query ingested document registry (C.1)
    "register_workflow_version": tool_register_workflow_version,  # workflow family version (C.2)
    "diff_workflow_versions": tool_diff_workflow_versions,  # cited workflow version diff (C.3)
    "list_open_questions": tool_list_open_questions,  # query open questions (C.4)
    "resolve_open_question": tool_resolve_open_question,  # resolve open question with evidence (C.4)
    "link_decision_outcome": tool_link_decision_outcome,  # link workflow to decision outcome (C.4)
    "write_knowledge_artifact": tool_write_knowledge_artifact,  # durable markdown artifact (C.5)
    "compare_public_ir_quarters": tool_compare_public_ir_quarters,  # public IR period comparison (C.6)
    "find_contradictions": tool_find_contradictions,  # surface claim/workflow conflicts (C.7)
    "search_knowledge": tool_search_knowledge,  # knowledge search across brain stores (C.8)
    "run_golden_eval": tool_run_golden_eval,  # golden regression gate (F.1)
    "resolve_entity": tool_resolve_entity,  # ontology alias resolution (F.5)
    "link_workflow_edge": tool_link_workflow_edge,  # typed workflow edges (F.5)
    "compare_factories": tool_compare_factories,  # factory comparison availability gate (F.6)
    "suggest_ideas": tool_suggest_ideas,  # labeled AI-SUGGESTED IDEA synthesis (F.7)
    "run_backup": tool_run_backup,  # backup brain stores and artifacts (F.8)
    "restore_backup": tool_restore_backup,  # restore backup drill (F.8)
    "list_ingestion_alerts": tool_list_ingestion_alerts,  # query ingestion alerts (F.8)
    "write_session_state": tool_write_session_state,  # session resume snapshot (F.9)
}


def dispatch(
    tool: str,
    *,
    caller_role: str | None = None,
    caller_cfg: dict | None = None,
    **kwargs,
):
    if tool not in TOOLS:
        raise KeyError(f"unknown tool '{tool}'. Available: {list(TOOLS)}")
    if caller_role is not None and caller_cfg is not None:
        scope = TOOL_SCOPES.get(tool, "general")
        if not can_call_tool(caller_role, scope, caller_cfg):
            raise PermissionError(
                f"role '{caller_role}' cannot call tool '{tool}' (scope '{scope}')"
            )
    return TOOLS[tool](**kwargs)
