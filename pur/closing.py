"""1-1 ZPUR_CONF purchasing configuration (display) and 1-5 ZPUR_CLOSE purchasing month-end:
the open work of the purchasing department in the order it should be done."""
from mm import util as clock


def config(conn):
    from fi.ap import TOLERANCE
    from . import config as c
    from .importfile import COST_TYPES
    groups = dict(c.PURCH_GROUPS)
    groups.update({r["ekgrp"]: r["text"] for r in conn.execute("SELECT * FROM pur_ekgrp")})
    return {
        "ekorg": c.EKORG, "ekorg_text": c.EKORG_TEXT,
        "groups": [dict(ekgrp=k, text=v) for k, v in sorted(groups.items())],
        "doc_types": [dict(obj=o, typ=k, text=v) for o, d in (("Purchase order", c.PO_TYPES),
                                                              ("Requisition", c.PR_TYPES),
                                                              ("Contract", c.CONTRACT_TYPES),
                                                              ("RFQ", c.RFQ_TYPES)) for k, v in d.items()],
        "acct_assign": [dict(knttp=k or "(blank)", text=v) for k, v in c.ACCT_ASSIGN.items()],
        "conditions": [dict(kschl=k, text=v[0], calc=v[1]) for k, v in c.CONDITIONS.items()],
        "release": [dict(obj="Requisition", code=k, text=t, limit=v / 100.0) for k, t, v in c.PR_RELEASE] +
                   [dict(obj="Purchase order", code=k, text=t, limit=v / 100.0) for k, t, v in c.PO_RELEASE],
        "quotation_rule": {"limit": c.QUOTATION_LIMIT / 100.0, "quotations": c.QUOTATION_MIN},
        "tolerance": {"price_abs": TOLERANCE["PP"]["abs"] / 100.0, "price_pct": TOLERANCE["PP"]["pct"] / 100.0},
        "vendor_eval": [dict(key=k, text=t, weight=w) for k, t, w in c.VENDOR_EVAL],
        "import_costs": [dict(typ=k, text=v) for k, v in COST_TYPES.items()],
        "accounts": [dict(use=u, hkont=h) for u, h in (
            ("GR/IR clearing", "191100"), ("Planned freight clearing", c.FREIGHT_CLEARING),
            ("Import costs clearing", "193500"), ("LC margin deposits", "116000"),
            ("Price differences", "231500"))],
    }


def status(conn, gjahr, perio):
    from fi.ap import blocked_invoices
    from mm import periods
    from . import followup
    import calendar
    end = "%04d-%02d-%02d" % (gjahr, perio, calendar.monthrange(gjahr, perio)[1])
    one = lambda sql, *a: conn.execute(sql, a).fetchone()[0]          # noqa: E731
    pr_open = one("SELECT COUNT(DISTINCT banfn) FROM pr_item WHERE statu='N' AND (ebeln IS NULL OR ebeln='')")
    pr_block = one("SELECT COUNT(DISTINCT banfn) FROM pr_item WHERE statu='B'")
    po_block = one("SELECT COUNT(*) FROM po_header WHERE frgke='B'")
    late = followup.overdue(conn, min(end, clock.today().isoformat()))   # key date: period end or today
    late_due = [r for r in late if r["due"]]
    ses = one("SELECT COUNT(*) FROM svc_entry WHERE status='P'")
    imp = one("SELECT COUNT(DISTINCT impno) FROM imp_cost WHERE land_belnr IS NULL")
    grni = one("SELECT COUNT(*) FROM po_item WHERE COALESCE(loekz,0)=0 AND wemng > COALESCE(remng,0)")
    blocked = len(blocked_invoices(conn))
    cur = periods.current(conn) or {}
    mm_ok = (cur.get("gjahr"), cur.get("perio")) != (gjahr, perio) and \
        (cur.get("gjahr", 0), cur.get("perio", 0)) > (gjahr, perio)
    steps = [
        ("Requisitions waiting for release", "ME55", pr_block, "%d requisition(s) blocked"),
        ("Released requisitions not yet ordered", "ME57", pr_open, "%d requisition(s) to convert"),
        ("Purchase orders waiting for release", "ME28", po_block, "%d PO(s) blocked"),
        ("Delivery reminders to vendors", "ME91F", len(late_due), "%d late item(s) need a reminder"),
        ("Service entry sheets to accept", "ML81N", ses, "%d sheet(s) waiting"),
        ("Import costs to land", "ZIMP_LAND", imp, "%d import file(s) with costs not landed"),
        ("Goods received, not invoiced", "ME2M", grni, "%d PO item(s) - chase the vendor invoice"),
        ("Blocked invoices (price variance)", "MRBR", blocked, "%d invoice(s) blocked for payment"),
    ]
    out = []
    for n, (step, tcode, cnt, txt) in enumerate(steps, start=1):
        out.append(dict(no=n, step=step, tcode=tcode, count=cnt, info=txt % cnt, status="done" if not cnt else "open"))
    out.append(dict(no=len(out) + 1, step="Materials period (MMPV)", tcode="MMPV", count=0,
                    info=("current MM period %02d/%s" % (cur["perio"], cur["gjahr"])) if cur else "period control not used",
                    status="n/a" if not cur else "done" if mm_ok else "open"))
    done = sum(1 for s in out if s["status"] == "done")
    return {"gjahr": gjahr, "perio": perio, "steps": out, "done": done,
            "needed": sum(1 for s in out if s["status"] != "n/a")}
