"""Sales reporting for management.

ZSD_COCKPIT  incoming orders, backlog, delivered-not-billed, revenue, discount rate,
             gross margin, OTIF, quotation hit rate, returns rate, credit-blocked value,
             DSO, top customers / materials, plan vs actual (KE11)
MCTA / MCTC  SIS customer / material analysis (incoming orders, sales, credit memos,
             returns, margin)
ZSLM         service level: OTIF, fill rate (confirmed on requested date), lead time
F.31 / FD33  credit overview: limit, exposure parts, utilisation, oldest overdue item
VA25 / pipeline  quotations with probability and expiry
"""
import datetime

from mm.db import rows
from mm.util import rdiv

from .order import exposure, delivered_qty, billed_qty
from mm import util as mmclock  # noqa: E402
from mm.util import parse_date  # noqa: E402


def _sales(conn, d1, d2, by):
    """Billing per key (kunnr / matnr): revenue, deductions, cost, margin, returns."""
    key = "b.kunnr" if by == "kunnr" else "i.matnr"
    out = {}
    for r in conn.execute(
            "SELECT %s k, b.fkart, b.cancelled, i.fkimg, i.gross, i.disc, i.freight, i.cogs, b.netwr FROM billing b "
            "JOIN billing_item i USING (vbeln) WHERE b.fkdat BETWEEN ? AND ?" % key, (d1, d2)):
        if r["cancelled"] or not r["k"]:
            continue
        fk = r["fkart"] or "F2"
        d = out.setdefault(r["k"], dict(key=r["k"], qty=0, revenue=0, deductions=0, net=0, cost=0, returns=0,
                                        credits=0, invoices=0))
        sign = -1 if fk in ("G2", "RE") else 1
        net = r["gross"] - r["disc"] + (r["freight"] or 0)
        if fk == "RE":
            d["returns"] += net
        elif fk == "G2":
            d["credits"] += net
        d["qty"] += sign * r["fkimg"] if fk in ("F2", "RE") else 0
        d["revenue"] += sign * (r["gross"] + (r["freight"] or 0))
        d["deductions"] += sign * r["disc"]
        d["net"] += sign * net
        d["cost"] += sign * (r["cogs"] or 0) if fk in ("F2", "RE") else 0
        d["invoices"] += 1 if fk == "F2" else 0
    for d in out.values():
        d["margin"] = d["net"] - d["cost"]
        d["margin_pct"] = round(100.0 * d["margin"] / d["net"], 1) if d["net"] else 0
    return out


def sis(conn, d1, d2, by="kunnr"):
    s = _sales(conn, d1, d2, by)
    col = "k.kunnr" if by == "kunnr" else "p.matnr"
    for r in conn.execute("SELECT %s k, SUM(p.netwr) v, SUM(p.kwmeng) q FROM sd_vbak k JOIN sd_vbap p USING (vbeln) "
                          "WHERE k.vbtyp='C' AND k.audat BETWEEN ? AND ? AND COALESCE(p.abgru,'')='' GROUP BY %s"
                          % (col, col), (d1, d2)):
        d = s.setdefault(r["k"], dict(key=r["k"], qty=0, revenue=0, deductions=0, net=0, cost=0, returns=0,
                                      credits=0, invoices=0, margin=0, margin_pct=0))
        d["order_value"] = r["v"]
        d["order_qty"] = r["q"]
    names = {r[0]: r[1] for r in conn.execute("SELECT kunnr, name FROM customer")} if by == "kunnr" else \
        {r[0]: r[1] for r in conn.execute("SELECT matnr, maktx FROM material")}
    out = sorted(s.values(), key=lambda x: -x["net"])
    for d in out:
        d["name"] = names.get(d["key"], "")
        d.setdefault("order_value", 0)
    return out


def service_level(conn, d1, d2):
    """OTIF per delivery item vs the requested date and quantity of the order."""
    lines = []
    for l in conn.execute("SELECT l.*, h.wadat_ist, h.vbeln dl, k.vdatu, k.kunnr, k.audat, p.kwmeng, c.name FROM "
                          "sd_lips l JOIN sd_likp h USING (vbeln) JOIN sd_vbak k ON k.vbeln=l.vgbel JOIN sd_vbap p ON "
                          "p.vbeln=l.vgbel AND p.posnr=l.vgpos JOIN customer c ON c.kunnr=k.kunnr WHERE h.lfart='LF' "
                          "AND h.wbstk='C' AND h.wadat_ist BETWEEN ? AND ?", (d1, d2)):
        first = conn.execute("SELECT MIN(h.wadat_ist) FROM sd_lips x JOIN sd_likp h USING (vbeln) WHERE x.vgbel=? AND "
                             "x.vgpos=?", (l["vgbel"], l["vgpos"])).fetchone()[0]
        on_time = l["wadat_ist"] <= l["vdatu"]
        in_full = delivered_qty(conn, l["vgbel"], l["vgpos"]) >= l["kwmeng"] and first == l["wadat_ist"]
        lt = (datetime.date.fromisoformat(l["wadat_ist"]) - datetime.date.fromisoformat(l["audat"])).days
        lines.append(dict(delivery=l["dl"], order=l["vgbel"], kunnr=l["kunnr"], name=l["name"], matnr=l["matnr"],
                          qty=l["lfimg"], requested=l["vdatu"], shipped=l["wadat_ist"], on_time=on_time,
                          in_full=in_full, otif=on_time and in_full, lead_days=lt))
    fill = []
    for p in conn.execute("SELECT p.vbeln, p.posnr, p.kwmeng, k.vdatu FROM sd_vbap p JOIN sd_vbak k USING (vbeln) "
                          "WHERE k.vbtyp='C' AND k.audat BETWEEN ? AND ? AND p.pstyv='TAN' AND "
                          "COALESCE(p.abgru,'')=''", (d1, d2)):
        c = conn.execute("SELECT COALESCE(SUM(bmeng),0) FROM sd_vbep WHERE vbeln=? AND posnr=? AND edatu<=?",
                         (p["vbeln"], p["posnr"], p["vdatu"])).fetchone()[0]
        fill.append(min(1.0, c / p["kwmeng"]) if p["kwmeng"] else 1)
    n = len(lines)
    return dict(lines=lines,
                otif=round(100.0 * sum(1 for l in lines if l["otif"]) / n, 1) if n else None,
                on_time=round(100.0 * sum(1 for l in lines if l["on_time"]) / n, 1) if n else None,
                in_full=round(100.0 * sum(1 for l in lines if l["in_full"]) / n, 1) if n else None,
                fill_rate=round(100.0 * sum(fill) / len(fill), 1) if fill else None,
                lead_time=round(sum(l["lead_days"] for l in lines) / n, 1) if n else None)


def credit_overview(conn):
    out = []
    today = mmclock.today().isoformat()
    for c in conn.execute("SELECT * FROM customer WHERE COALESCE(ktokd,'0001') IN ('0001','0003') ORDER BY kunnr"):
        e = exposure(conn, c["kunnr"])
        od = conn.execute("SELECT MIN(netdt), COALESCE(SUM(CASE WHEN netdt<? THEN dmbtr ELSE 0 END),0) FROM "
                          "acc_doc_item WHERE koart='D' AND kunnr=? AND augbl IS NULL AND shkzg='S'",
                          (today, c["kunnr"])).fetchone()
        days = (datetime.date.fromisoformat(today) - datetime.date.fromisoformat(od[0])).days if od[0] and \
            od[0] < today else 0
        since = (datetime.date.fromisoformat(today) - datetime.timedelta(days=90)).isoformat()
        sales90 = conn.execute("SELECT COALESCE(SUM(netwr),0) FROM billing WHERE kunnr=? AND cancelled=0 AND "
                               "fkdat>=?", (c["kunnr"], since)).fetchone()[0]
        dso = round(e["open_items"] / (sales90 * 1.14 / 90.0), 1) if sales90 > 0 else None
        out.append(dict(kunnr=c["kunnr"], name=c["name"], klimk=c["klimk"] or 0, open_items=e["open_items"],
                        open_orders=e["open_orders"], exposure=e["total"],
                        utilization=round(100.0 * e["total"] / c["klimk"], 1) if c["klimk"] else None,
                        overdue=od[1], overdue_days=days, dso=dso,
                        blocked=conn.execute("SELECT COUNT(*) FROM sd_vbak WHERE kunnr=? AND cmgst='B'",
                                             (c["kunnr"],)).fetchone()[0],
                        risk="003" if days > 60 or (c["klimk"] and e["total"] > c["klimk"]) else
                        "002" if days > 0 else "001"))
    return out


def pipeline(conn):
    out = rows(conn.execute("SELECT k.*, c.name FROM sd_vbak k JOIN customer c USING (kunnr) WHERE k.auart IN "
                            "('IN','QT') ORDER BY k.vbeln DESC"))
    today = mmclock.today().isoformat()
    for k in out:
        k["followed"] = conn.execute("SELECT GROUP_CONCAT(vbeln) FROM sd_vbfa WHERE vbelv=?",
                                     (k["vbeln"],)).fetchone()[0]
        k["weighted"] = rdiv(k["netwr"] * (k["prob"] or 0), 100)
        k["state"] = "Won" if k["followed"] and k["auart"] == "QT" else \
            "Expired" if k["bnddt"] and k["bnddt"] < today else "Open"
    return out


def cockpit(conn, d1, d2):
    d1, d2 = parse_date(d1), parse_date(d2)
    sl = service_level(conn, d1, d2)
    sales = _sales(conn, d1, d2, "kunnr")
    net = sum(s["net"] for s in sales.values())
    rev = sum(s["revenue"] for s in sales.values())
    ded = sum(s["deductions"] for s in sales.values())
    cost = sum(s["cost"] for s in sales.values())
    ret = sum(s["returns"] for s in sales.values())
    incoming = conn.execute("SELECT COALESCE(SUM(netwr),0), COUNT(*) FROM sd_vbak WHERE vbtyp='C' AND auart NOT IN "
                            "('FD','ZWR') AND audat BETWEEN ? AND ?", (d1, d2)).fetchone()
    backlog = 0
    dnb = 0
    for p in conn.execute("SELECT p.* FROM sd_vbap p JOIN sd_vbak k USING (vbeln) WHERE k.vbtyp='C' AND "
                          "p.pstyv='TAN' AND COALESCE(p.abgru,'')=''"):
        dq = delivered_qty(conn, p["vbeln"], p["posnr"])
        bq = billed_qty(conn, p["vbeln"], p["posnr"])
        if p["kwmeng"]:
            backlog += rdiv(p["netwr"] * max(0, p["kwmeng"] - dq), p["kwmeng"])
            dnb += rdiv(p["netwr"] * max(0, dq - bq), p["kwmeng"])
    qts = pipeline(conn)
    q_done = [q for q in qts if q["auart"] == "QT" and q["state"] != "Open"]
    blocked = conn.execute("SELECT COALESCE(SUM(netwr),0), COUNT(*) FROM sd_vbak WHERE cmgst='B'").fetchone()
    samples = conn.execute("SELECT COALESCE(SUM(l.cogs),0) FROM sd_lips l JOIN sd_likp h USING (vbeln) WHERE "
                           "l.pstyv='TANN' AND h.wbstk='C' AND h.wadat_ist BETWEEN ? AND ?", (d1, d2)).fetchone()[0]
    co = credit_overview(conn)
    top_c = sis(conn, d1, d2, "kunnr")[:8]
    top_m = sis(conn, d1, d2, "matnr")[:8]
    plan = rows(conn.execute("SELECT matnr, SUM(qty) q, SUM(qty*price/1000) v FROM copa_plan_qty WHERE "
                             "gjahr=? AND perio=? GROUP BY matnr", (int(d1[:4]), int(d1[5:7])))) \
        if conn.execute("SELECT 1 FROM sqlite_master WHERE name='copa_plan_qty'").fetchone() else []
    act = {m["key"]: m for m in top_m}
    pva = [dict(matnr=p["matnr"], plan=p["v"], actual=act.get(p["matnr"], {}).get("net", 0)) for p in plan]
    return {
        "kpi": dict(incoming=incoming[0], orders=incoming[1], backlog=backlog, delivered_not_billed=dnb,
                    revenue=net, discount_pct=round(100.0 * ded / rev, 2) if rev else 0,
                    margin=net - cost, margin_pct=round(100.0 * (net - cost) / net, 1) if net else 0,
                    otif=sl["otif"], fill_rate=sl["fill_rate"], lead_time=sl["lead_time"],
                    hit_rate=round(100.0 * sum(1 for q in q_done if q["state"] == "Won") / len(q_done), 1)
                    if q_done else None,
                    pipeline=sum(q["weighted"] for q in qts if q["state"] == "Open"),
                    returns_pct=round(100.0 * ret / net, 2) if net else 0, samples=samples,
                    credit_blocked=blocked[0], credit_blocked_n=blocked[1],
                    dso=round(sum(c["dso"] or 0 for c in co) / max(1, sum(1 for c in co if c["dso"])), 1)),
        "top_customers": top_c, "top_materials": top_m, "credit": co, "plan_vs_actual": pva,
        "service": sl,
    }
