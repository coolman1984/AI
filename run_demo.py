"""End-to-end demo: connect the tools and make them work together on sample finance data.

Run:  python run_demo.py
Shows: ingest -> clean (rejects) -> governed variance -> manager card -> INDEPENDENT
audit -> deep question -> human sign-off -> render.
"""
from __future__ import annotations

import yaml

from engines.brain.orchestrator import run_pipeline


def main() -> None:
    cfg = yaml.safe_load(open("config.yaml"))
    out = run_pipeline(
        "data/sample/finance_actuals.csv",
        "data/sample/finance_budget.csv",
        cfg,
        approver="analyst_mohamed",
    )

    print(out["card_text"])
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


if __name__ == "__main__":
    main()
