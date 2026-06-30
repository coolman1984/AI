"""End-to-end demo: connect the tools and make them work together on sample finance data.

Run:  python run_demo.py
Shows: ingest -> clean (rejects) -> governed variance -> manager card -> INDEPENDENT
audit -> deep question -> human sign-off -> render.
"""
from __future__ import annotations

import shutil

import yaml

from engines.brain.memory import get_knowledge_memory, get_temporal_memory
from engines.brain.orchestrator import run_pipeline


def main() -> None:
    shutil.rmtree(".brain", ignore_errors=True)  # fresh memory for a deterministic demo
    cfg = yaml.safe_load(open("config.yaml"))
    out = run_pipeline(
        "data/sample/finance_actuals.csv",
        "data/sample/finance_budget.csv",
        cfg,
        approver="analyst_mohamed",
        budget_pdf="data/sample/budget_approval_2026.pdf",
        period="2026-05",
    )

    print(out["card_text"])
    de = out["document_evidence"]
    if de:
        print(f"DOCUMENT EVIDENCE: cited {de.source} ({de.locator}) via {de.method}")
    if out["budget_doc"] and out["budget_doc"].warnings:
        print("DOC WARNINGS: " + "; ".join(out["budget_doc"].warnings))
    print()
    print()
    print("REJECTS (nothing vanishes silently):")
    for r in out["rejects"]:
        print(f"  - row {r.row_id}: {r.reason}")
    print()
    a = out["audit"]
    print("AUDIT (independent four-eyes re-run):")
    print(f"  recomputed variance = {a.recomputed['variance']:+,.2f}  "
          f"(matches card: {a.passed})")
    print(f"  certainty = {a.certainty}")
    print(f"  needs_human = {a.needs_human}")
    for q in a.questions:
        print(f"  QUESTION: {q['question']}")
        for opt in q["options"]:
            print(f"      {opt}")
    s = out["signoff"]
    print()
    print(f"SIGN-OFF: approved={s.approved} by {s.approver} — {s.note}")
    print(f"RELEASED TO MANAGER: {out['released']}")

    # --- OCR cascade demo: a scanned (image-only) PDF forces fallback to OCR ---
    from engines.docs.extract import extract_document
    print()
    print("OCR CASCADE on a scanned (image-only) PDF:")
    scanned = extract_document("data/sample/budget_approval_scanned.pdf", cfg)
    p = scanned.pages[0]
    print(f"  born-digital failed -> OCR engine used: {p.ocr_engine}, "
          f"confidence={p.ocr_confidence:.2f}, needs_review={p.needs_review}")
    print(f"  recovered text: {scanned.full_text[:70]!r}")

    # --- temporal memory: run a second period and detect what changed ---
    run_pipeline(
        "data/sample/finance_actuals_2026_06.csv",
        "data/sample/finance_budget.csv",
        cfg,
        approver="analyst_mohamed",
        period="2026-06",
    )
    print()
    print("KNOWLEDGE MEMORY (relations for Frame):")
    for r in get_knowledge_memory("local_json").relations_for("Frame"):
        print(f"  Frame --{r['p']}--> {r['o']}")
    print("TEMPORAL MEMORY (what changed for Frame across periods):")
    for c in get_temporal_memory("local_json").changes("Frame", "material_cost_variance"):
        print(f"  {c['from_period']} {c['from_value']} -> {c['to_period']} {c['to_value']}")

    # --- visual output: export the audited, signed card to HTML + PPTX ---
    from serving.open_design import export_report
    paths = export_report(out["ctx"], out_dir="out")
    print()
    print(f"VISUAL OUTPUT: dashboard -> {paths['html']}   deck -> {paths['pptx']}")


if __name__ == "__main__":
    main()
