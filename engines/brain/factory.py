"""The factory brain (MASTER_PLAN B.4) — federation over department lenses.

Runs each department on the SAME engines (only the lens config differs), then assembles a
CEO/CFO brief filtered by role-scoped access, and surfaces entities that appear across
departments (a real cross-department connection via the knowledge memory).
"""
from __future__ import annotations

from engines.brain.memory import get_knowledge_memory
from engines.brain.orchestrator import run_pipeline
from gov.access import can_access
from shared.lenses import load_lens


def run_department(lens_name: str, actuals_csv: str, baseline_csv: str, cfg: dict,
                   approver: str | None = None, period: str = "2026-05") -> dict:
    """A department is a lens — no new engine code, just config (Stage 7)."""
    return run_pipeline(actuals_csv, baseline_csv, cfg, approver=approver,
                        period=period, lens=load_lens(lens_name))


def factory_brief(results: dict[str, dict], role: str, cfg: dict) -> dict:
    """One CEO/CFO brief across departments, scoped to what the role may see (G.1)."""
    visible, hidden = [], []
    for out in results.values():
        lens = out["ctx"]["lens"]
        if can_access(role, out["scope"], cfg):
            visible.append({
                "department": lens["name"],
                "headline": out["card"].headline,
                "released": out["released"],
            })
        else:
            hidden.append(lens["name"])
    return {"role": role, "visible": visible, "hidden": hidden}


def cross_department_entities(role: str, cfg: dict, backend: str = "local_json") -> list[dict]:
    """Entities tracked in >1 department the role can see — the cross-department links."""
    km = get_knowledge_memory(backend)
    by_entity: dict[str, list[tuple[str, str]]] = {}
    for r in km.all():
        if r["p"] == "tracked_in":
            by_entity.setdefault(r["s"], []).append((r["o"], r["evidence"]))  # (dept name, scope)
    out = []
    for entity, depts in by_entity.items():
        names = sorted({name for name, scope in depts if can_access(role, scope, cfg)})
        if len(names) > 1:
            out.append({"entity": entity, "departments": names})
    return out
