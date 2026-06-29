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
from engines.data.ingest import get_connection, ingest_csv
from engines.data.variance import material_cost_variance
from serving.card import compute_data_quality, make_manager_card, render_text
from serving.open_design import get_renderer


def run_pipeline(actuals_csv: str, budget_csv: str, cfg: dict, approver: str | None = None) -> dict:
    audit_cfg = cfg.get("audit", {})
    tool_cfg = cfg.get("tools", {})

    # 1) INGEST (DuckDB, text-first)
    con = get_connection()
    rows_in = ingest_csv(con, "raw_actuals", actuals_csv)
    ingest_csv(con, "raw_budget", budget_csv)
    budget = con.execute("SELECT sub_assembly, budget_amount FROM raw_budget").pl()

    # 2) CLEAN (Polars; total-row + duplicate + locale defenses)
    clean, rejects, log = clean_actuals(con, "raw_actuals")

    # 3) GOVERNED METRIC -> VARIANCE
    bridge = material_cost_variance(clean, budget)

    # 4) MANAGER CARD (one-A4, every number cited)
    dq = compute_data_quality(rows_in, rejects, bridge.total_actual, audit_cfg)
    card = make_manager_card(bridge, dq)

    # 5) INDEPENDENT AUDIT (four-eyes)
    audit = audit_card(card, bridge, clean, budget, rows_in, len(rejects), audit_cfg)

    # 6) HUMAN SIGN-OFF (accountable; required when audit needs a human)
    signoff = None
    if approver and (audit.needs_human or audit.passed):
        signoff = approve_report(audit, approver)

    # 7) MEMORY — relations (Cognee role) + history (Graphiti role)
    km = get_knowledge_memory(tool_cfg.get("knowledge_memory", "local_json"))
    tm = get_temporal_memory(tool_cfg.get("temporal_memory", "local_json"))
    for p in bridge.parts:
        km.add_relation(p.dim_value, "has_variance", f"{p.variance:+.2f}", p.evidence.method)
        tm.record_fact(p.dim_value, "material_cost_variance", f"{p.variance:+.2f}", "2026-05")

    # 8) RENDER (Open Design role) — only renders an audited, signed card
    released = bool(signoff and signoff.approved)
    renderer = get_renderer(tool_cfg.get("renderer", "builtin_html"))
    html = renderer.render_html(card, audited=audit.passed, signed_by=signoff.approver if signoff else None)

    return {
        "rows_in": rows_in,
        "rejects": rejects,
        "log": log,
        "bridge": bridge,
        "card": card,
        "card_text": render_text(card),
        "audit": audit,
        "signoff": signoff,
        "released": released,
        "html": html,
    }


def _empty(_: pl.DataFrame | None = None) -> None:  # keep pl import meaningful
    return None
