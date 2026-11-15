"""1-1 ZSD_CONF sales configuration (display), 1-5 ZSD_CLOSE sales month-end and
3-2 ZSD_QFU quotation follow-up (validity, days left, converted into orders)."""
import calendar
import datetime

from mm import util as clock
from mm.util import parse_date


def config(conn):
    from . import config as c
    return {
        "doc_types": [dict(auart=k, text=(v.get("text") if isinstance(v, dict) else v)) for k, v in c.DOC_TYPES.items()],
        "item_cats": [dict(pstyv=k, text=(v.get("text") if isinstance(v, dict) else v)) for k, v in c.ITEM_CATS.items()],
        "billing_types": [dict(fkart=k, text=(v.get("text") if isinstance(v, dict) else v))
                          for k, v in c.BILLING_TYPES.items()],
        "conditions": [dict(kschl=k, text=v["text"], kind=v["kind"], calc=v["calc"], access=", ".join(v["access"]))
                       for k, v in c.COND_TYPES.items()],
        "procedures": [dict(kalsm=k, text=(v.get("text") if isinstance(v, dict) else
                                           " > ".join(v) if isinstance(v, (list, tuple)) else str(v)))
                       for k, v in c.PRICING_PROCS.items()],
        "credit": dict(c.CREDIT),
        "risk": [dict(ctlpc=k, text=v) for k, v in c.RISK_CATEGORIES.items()],
        "blocks": [dict(code=k, text=v) for k, v in c.BLOCKS.items()],
        "reasons": [dict(augru=k, text=v) for k, v in c.ORDER_REASONS.items()],
        "shipping_points": [dict(vstel=k, text=v) for k, v in c.SHIPPING_POINTS.items()],
        "accounts": [dict(use=u, hkont=h) for u, h in (
            ("Sales deductions", c.DEDUCTION_ACCOUNT), ("Freight revenue", c.FREIGHT_ACCOUNT),
            ("Service revenue", c.SERVICE_ACCOUNT), ("Customer rebates", "881000"),
            ("Accrued customer rebates", "291000"))],
        "warranty_months": c.WARRANTY_MONTHS,
    }


def quotations(conn, key_date=None):
    """ZSD_QFU: quotations with validity, days left and how much became orders"""
    kd = parse_date(key_date) if key_date else clock.today().isoformat()
    out = []
    for q in conn.execute("SELECT k.*, c.name FROM sd_vbak k LEFT JOIN customer c ON c.kunnr=k.kunnr WHERE "
                          "k.vbtyp='B' ORDER BY k.audat DESC, k.vbeln DESC"):
        ordered = conn.execute("SELECT COALESCE(SUM(p.netwr),0) FROM sd_vbap p JOIN sd_vbak k ON k.vbeln=p.vbeln "
                               "WHERE k.vbtyp='C' AND p.vgbel=?", (q["vbeln"],)).fetchone()[0]
        days = (datetime.date.fromisoformat(q["bnddt"]) - datetime.date.fromisoformat(kd)).days if q["bnddt"] else None
        conv = round(ordered * 100.0 / q["netwr"], 1) if q["netwr"] else 0.0
        st = "Won" if conv >= 99.9 else "Partly won" if ordered else \
            "Expired" if days is not None and days < 0 else "Rejected" if q["gbstk"] == "C" else "Open"
        out.append(dict(vbeln=q["vbeln"], kunnr=q["kunnr"], name=q["name"] or "", audat=q["audat"], bnddt=q["bnddt"] or "",
                        days_left=days, netwr=q["netwr"], ordered=ordered, conversion=conv, status=st,
                        follow_up=st == "Open" and days is not None and days <= 7))
    tot = sum(r["netwr"] for r in out)
    won = sum(r["ordered"] for r in out)
    return {"rows": out, "total": tot, "won": won, "hit_rate": round(won * 100.0 / tot, 1) if tot else None,
            "open": sum(1 for r in out if r["status"] == "Open"), "follow_up": sum(1 for r in out if r["follow_up"])}


def status(conn, gjahr, perio):
    from . import order
    end = "%04d-%02d-%02d" % (gjahr, perio, calendar.monthrange(gjahr, perio)[1])
    kd = min(end, clock.today().isoformat())
    one = lambda sql, *a: conn.execute(sql, a).fetchone()[0]          # noqa: E731
    blocked = len(order.blocked(conn))
    incomplete = len(order.incomplete_docs(conn))
    late_orders = one("SELECT COUNT(DISTINCT e.vbeln) FROM sd_vbep e JOIN sd_vbak k ON k.vbeln=e.vbeln WHERE "
                      "k.vbtyp='C' AND k.gbstk<>'C' AND e.edatu<=? AND e.bmeng>0", kd)
    not_gi = one("SELECT COUNT(*) FROM sd_likp WHERE wbstk<>'C' AND wadat<=?", end)
    not_billed = one("SELECT COUNT(*) FROM sd_likp WHERE wbstk='C' AND fkstk<>'C' AND COALESCE(wadat_ist,wadat)<=?", end)
    no_acc = one("SELECT COUNT(*) FROM billing WHERE cancelled=0 AND (belnr IS NULL OR belnr='') AND fkdat<=?", end)
    einv = one("SELECT COUNT(*) FROM billing b LEFT JOIN sd_einv e ON e.vbeln=b.vbeln WHERE b.cancelled=0 AND "
               "b.fkdat BETWEEN ? AND ? AND (e.status IS NULL OR e.status NOT LIKE 'Submitted%')",
               "%04d-%02d-01" % (gjahr, perio), end)
    returns = one("SELECT COUNT(*) FROM sd_vbak WHERE vbtyp='H' AND gbstk<>'C'")
    rebate = one("SELECT COUNT(*) FROM sd_rebate r WHERE r.status='A' AND r.datab<=? AND NOT EXISTS (SELECT 1 FROM "
                 "sd_rebate_acr a WHERE a.knuma=r.knuma AND a.budat>=?)", end, "%04d-%02d-01" % (gjahr, perio))
    steps = [
        ("Orders on credit / delivery block", "VKM1", blocked, "%d order(s) blocked"),
        ("Incomplete sales documents", "V.02", incomplete, "%d document(s) incomplete"),
        ("Orders due, not delivered", "V.15", late_orders, "%d order(s) past the delivery date"),
        ("Deliveries without goods issue", "VL06O", not_gi, "%d delivery(ies) not shipped"),
        ("Shipped, not billed", "VF04", not_billed, "%d delivery(ies) to bill"),
        ("Invoices not posted to accounting", "VF02", no_acc, "%d invoice(s) without FI document"),
        ("E-invoices not submitted (ETA)", "ZEINV", einv, "%d invoice(s) to submit"),
        ("Open returns", "ZRET_MON", returns, "%d return order(s) open"),
        ("Rebate accrual of the month", "ZREB_ACR", rebate, "%d agreement(s) not accrued this month"),
    ]
    out = [dict(no=n, step=s, tcode=t, count=c, info=txt % c, status="done" if not c else "open")
           for n, (s, t, c, txt) in enumerate(steps, start=1)]
    done = sum(1 for s in out if s["status"] == "done")
    return {"gjahr": gjahr, "perio": perio, "steps": out, "done": done, "needed": len(out)}
