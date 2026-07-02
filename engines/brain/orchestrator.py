"""Orchestrator — the Hermes role (MASTER_PLAN B / K.1 layer 7).

Connects the tools and makes them work together for one finance question, in order:
  ingest (DuckDB) -> clean (Polars) -> governed variance -> manager card
  -> INDEPENDENT audit -> (human sign-off) -> memory (knowledge + temporal) -> render.
The trust wall holds throughout: numbers only ever come from the data engine.
"""
from __future__ import annotations

import polars as pl

from engines.audit.audit import approve_report, audit_card
from engines.brain.memory import get_knowledge_memory, get_temporal_memory
from engines.data.clean import clean_actuals
from engines.data.drivers import run_variance_decomposition
from engines.data.ingest import get_connection, ingest_csv
from engines.data.variance import category_variance
from engines.docs.extract import extract_document
from engines.docs.search import search_documents
from engines.learning.learning import LearningStore
from serving.card import compute_data_quality, make_manager_card, render_text
from serving.open_design import render_dashboard_html
from shared.lenses import FINANCE


def run_pipeline(
    actuals_csv: str,
    budget_csv: str,
    cfg: dict,
    approver: str | None = None,
    budget_pdf: str | None = None,
    standards_csv: str | None = None,
    period: str = "2026-05",
    lens: dict | None = None,
) -> dict:
    audit_cfg = cfg.get("audit", {})
    tool_cfg = cfg.get("tools", {})
    lens = lens or FINANCE
    grain, key_col = lens["grain"], lens["key_col"]
    value_col, baseline_col = lens["value_col"], lens["baseline_col"]

    # 1) INGEST (DuckDB, text-first) — lens decides which columns matter
    con = get_connection()
    rows_in = ingest_csv(con, "raw_actuals", actuals_csv)
    ingest_csv(con, "raw_budget", budget_csv)
    budget = con.execute(f"SELECT {grain}, {baseline_col} FROM raw_budget").pl()

    # 2) CLEAN (Polars; total-row + duplicate + locale defenses)
    clean, rejects, log = clean_actuals(con, "raw_actuals", key_col=key_col, amount_col=value_col)

    # 3) GOVERNED METRIC -> VARIANCE (same engine, lens-driven)
    bridge = category_variance(
        clean, budget, grain=grain, value_col=value_col,
        baseline_col=baseline_col, metric=lens["metric"],
    )

    decomposition = None
    if standards_csv:
        decomposition = run_variance_decomposition(actuals_csv, standards_csv, cfg, lens=lens)["decomposition"]

    # 4) MANAGER CARD (one-A4, every number cited) — lens wording
    dq = compute_data_quality(rows_in, rejects, bridge.total_actual, audit_cfg)
    card = make_manager_card(bridge, dq, lens=lens, decomposition=decomposition)

    # 4b) DOCUMENT EVIDENCE (Stage 4): extract + cite the approved-budget PDF if provided.
    # Documents are evidence, not numbers — this attaches a citation, it does not change a figure.
    document_evidence = None
    budget_doc = None
    if budget_pdf:
        budget_doc = extract_document(budget_pdf, cfg)
        passages = search_documents([budget_doc], "approved budget", top_k=1)
        if passages:
            document_evidence = passages[0].evidence
            card.evidence.append(document_evidence)
        if budget_doc.needs_review:
            card.risks.append("Budget approval document needs human review (low-confidence OCR).")

    # 5) INDEPENDENT AUDIT (four-eyes) — recompute via the lens columns
    audit = audit_card(
        card, bridge, decomposition, clean, budget, rows_in, len(rejects), audit_cfg,
        value_col=value_col, baseline_col=baseline_col,
    )

    # 6) HUMAN SIGN-OFF (accountable; required when audit needs a human)
    signoff = None
    if approver and (audit.needs_human or audit.passed):
        signoff = approve_report(audit, approver)

    # 7) MEMORY — relations (Cognee role) + history (Graphiti role), namespaced by department
    km = get_knowledge_memory(tool_cfg.get("knowledge_memory", "local_json"))
    tm = get_temporal_memory(tool_cfg.get("temporal_memory", "local_json"))
    for p in bridge.parts:
        km.add_relation(p.dim_value, "tracked_in", lens["name"], lens["scope"])
        km.add_relation(p.dim_value, "has_variance", f"{p.variance:+.2f}", p.evidence.method)
        tm.record_fact(p.dim_value, lens["metric"], f"{p.variance:+.2f}", period)

    # 8) RENDER (Open Design role) — visual output of an audited, signed card
    released = bool(signoff and signoff.approved)
    ctx = {
        "card": card, "bridge": bridge, "decomposition": decomposition, "audit": audit, "signoff": signoff,
        "released": released, "document_evidence": document_evidence, "period": period,
        "lens": lens, "scope": lens["scope"],
    }
    html = render_dashboard_html(ctx)  # export to file/PPTX via serving.open_design.export_report

    # 9) REMEMBER the decision (episodic memory — improves over time, Part P)
    decision = None
    if signoff:
        store = LearningStore()
        decision = store.record_decision(
            summary=card.headline,
            variance=bridge.total_variance,
            approver=signoff.approver,
            approved=signoff.approved,
            certainty=audit.certainty["overall"],
            status="released" if released else "blocked",
        )

    return {
        "rows_in": rows_in,
        "rejects": rejects,
        "log": log,
        "bridge": bridge,
        "decomposition": decomposition,
        "card": card,
        "card_text": render_text(card),
        "audit": audit,
        "signoff": signoff,
        "released": released,
        "decision": decision,
        "document_evidence": document_evidence,
        "budget_doc": budget_doc,
        "scope": lens["scope"],
        "ctx": ctx,
        "html": html,
    }


def _empty(_: pl.DataFrame | None = None) -> None:  # keep pl import meaningful
    return None
