"""Procurement reporting.

ME2L / ME2N / ME2K / ME2M  purchasing documents with "still to be delivered"
                           and "still to be invoiced" (ME80FN view)
ME65                       vendor evaluation: price, on-time delivery,
                           quantity reliability, quality (returns)
ZPUR_COCKPIT               spend analysis (ABC), open commitments, overdue
                           deliveries, release backlog, cycle time, savings,
                           contract coverage, invoice price variance
"""
import datetime

from mm.util import amt_out, qty_out, rdiv, value_of

from .config import PURCH_GROUPS, VENDOR_EVAL


def _a(c):
    return amt_out(c or 0)


def po_lines(conn, lifnr="", matnr="", ekgrp="", knttp=None, open_only=False, d1=None,
             d2=None):
    sql = ("SELECT h.*, v.name AS vname, i.*, m.maktx FROM po_header h JOIN po_item i ON "
           "i.ebeln=h.ebeln JOIN vendor v ON v.lifnr=h.lifnr LEFT JOIN material m ON "
           "m.matnr=i.matnr WHERE i.loekz=0")
    args = []
    for col, val in (("h.lifnr", lifnr), ("i.matnr", matnr), ("h.ekgrp", ekgrp)):
        if val:
            sql += " AND %s=?" % col
            args.append(val)
    if knttp is not None and knttp != "*":
        sql += " AND COALESCE(i.knttp,'')=?"
        args.append(knttp)
    if d1:
        sql += " AND h.bedat>=?"
        args.append(d1)
    if d2:
        sql += " AND h.bedat<=?"
        args.append(d2)
    today = datetime.date.today().isoformat()
    out = []
    for r in conn.execute(sql + " ORDER BY h.ebeln DESC, i.ebelp", args):
        d = dict(r)
        open_q = 0 if r["elikz"] else max(r["menge"] - r["wemng"], 0)
        d["net_value"] = _a(value_of(r["menge"], r["netpr"], r["peinh"]) + (r["frb"] or 0))
        d["to_deliver_qty"] = qty_out(open_q)
        d["to_deliver_val"] = _a(value_of(open_q, r["netpr"], r["peinh"]))
        to_inv = r["wemng"] - r["remng"]
        d["to_invoice_qty"] = qty_out(to_inv)
        d["to_invoice_val"] = _a(value_of(to_inv, r["netpr"], r["peinh"]))
        d["overdue"] = bool(open_q and r["eindt"] and r["eindt"] < today)
        d["release"] = {"B": "Blocked", "R": "Released", "": "Not required"}.get(
            r["frgke"] or "", r["frgke"])
        d["text"] = r["maktx"] or r["txz01"]
        for k in ("menge", "wemng", "remng"):
            d[k] = qty_out(r[k])
        d["netpr"] = _a(r["netpr"])
        d["brtwr"] = _a(r["brtwr"])
        d["frb"] = _a(r["frb"])
        d["rabatt"] = (r["rabatt"] or 0) / 100.0
        if open_only and not open_q and not to_inv:
            continue
        out.append(d)
    return out


def _clamp(x):
    return max(1, min(100, round(x)))


def vendor_evaluation(conn, d1=None, d2=None):
    d1 = d1 or "2000-01-01"
    d2 = d2 or "9999-12-31"
    items = conn.execute("SELECT h.lifnr, h.bedat, i.* FROM po_header h JOIN po_item i ON "
                         "i.ebeln=h.ebeln WHERE i.loekz=0 AND i.matnr IS NOT NULL AND "
                         "h.bedat BETWEEN ? AND ?", (d1, d2)).fetchall()
    avg = {}
    for i in items:
        a = avg.setdefault(i["matnr"], [0, 0])
        a[0] += i["netpr"] / i["peinh"] * i["menge"]
        a[1] += i["menge"]
    avg = {k: v[0] / v[1] for k, v in avg.items() if v[1]}
    res = {}
    for i in items:
        r = res.setdefault(i["lifnr"], dict(lifnr=i["lifnr"], price=[], ontime=[],
                                            quantity=[], quality=[0, 0], spend=0, items=0,
                                            late_days=[]))
        r["items"] += 1
        r["spend"] += value_of(i["menge"], i["netpr"], i["peinh"])
        ratio = (i["netpr"] / i["peinh"]) / avg[i["matnr"]] if avg.get(i["matnr"]) else 1
        r["price"].append((_clamp(100 - (ratio - 1) * 300), i["menge"]))
        if i["wemng"]:
            dev = abs(i["wemng"] - i["menge"]) / i["menge"]
            if i["elikz"] or i["wemng"] >= i["menge"]:
                r["quantity"].append((_clamp(100 - dev * 200), i["menge"]))
        for g in conn.execute("SELECT h.budat, d.menge, d.bwart FROM mat_doc_item d JOIN "
                              "mat_doc h ON h.mblnr=d.mblnr AND h.mjahr=d.mjahr WHERE "
                              "d.ebeln=? AND d.ebelp=? AND d.bwart IN ('101','122') AND "
                              "d.canceled=0", (i["ebeln"], i["ebelp"])):
            if g["bwart"] == "122":
                r["quality"][1] += g["menge"]
                continue
            r["quality"][0] += g["menge"]
            if i["eindt"]:
                late = (datetime.date.fromisoformat(g["budat"]) -
                        datetime.date.fromisoformat(i["eindt"])).days
                r["late_days"].append(late)
                r["ontime"].append((_clamp(100 - max(late, 0) * 12), g["menge"]))
    out = []
    names = {v["lifnr"]: v["name"] for v in conn.execute("SELECT lifnr, name FROM vendor")}

    def wavg(lst):
        w = sum(q for _, q in lst)
        return round(sum(s * q for s, q in lst) / w) if w else None
    for r in res.values():
        rec, ret = r["quality"]
        scores = {"price": wavg(r["price"]), "ontime": wavg(r["ontime"]),
                  "quantity": wavg(r["quantity"]),
                  "quality": _clamp(100 - ret / rec * 100 * 5) if rec else None}
        tw = sum(w for k, _, w in VENDOR_EVAL if scores[k] is not None)
        total = round(sum(scores[k] * w for k, _, w in VENDOR_EVAL if scores[k] is not None)
                      / tw) if tw else None
        n_gr = len(r["late_days"])
        out.append(dict(lifnr=r["lifnr"], name=names.get(r["lifnr"], ""), items=r["items"],
                        spend=_a(r["spend"]), total=total, **scores,
                        ontime_pct=round(sum(1 for d in r["late_days"] if d <= 0) / n_gr * 100,
                                         1) if n_gr else None,
                        avg_late=round(sum(max(d, 0) for d in r["late_days"]) / n_gr, 1)
                        if n_gr else None,
                        return_pct=round(ret / rec * 100, 2) if rec else 0,
                        grade="A" if (total or 0) >= 85 else "B" if (total or 0) >= 70 else "C"))
    return sorted(out, key=lambda x: -(x["total"] or 0))


def cockpit(conn, d1, d2):
    today = datetime.date.today().isoformat()
    lines = conn.execute("SELECT h.lifnr, h.bedat, h.ekgrp, h.frgke, i.* FROM po_header h "
                         "JOIN po_item i ON i.ebeln=h.ebeln WHERE i.loekz=0").fetchall()
    names = {v["lifnr"]: v["name"] for v in conn.execute("SELECT lifnr, name FROM vendor")}
    period = [l for l in lines if d1 <= l["bedat"] <= d2]
    val = lambda l: value_of(l["menge"], l["netpr"], l["peinh"]) + (l["frb"] or 0)  # noqa
    spend = sum(val(l) for l in period)
    by_vendor, by_group, by_mat = {}, {}, {}
    for l in period:
        by_vendor[l["lifnr"]] = by_vendor.get(l["lifnr"], 0) + val(l)
        g = l["matkl"] or "-"
        by_group[g] = by_group.get(g, 0) + val(l)
        k = l["matnr"] or l["txz01"]
        by_mat[k] = by_mat.get(k, 0) + val(l)
    abc, cum = [], 0
    for v, s in sorted(by_vendor.items(), key=lambda x: -x[1]):
        cum += s
        share = cum / spend * 100 if spend else 0
        abc.append(dict(lifnr=v, name=names.get(v, ""), spend=_a(s),
                        pct=round(s / spend * 100, 1) if spend else 0,
                        cum=round(share, 1), cls="A" if share <= 80 or not abc else
                        ("B" if share <= 95 else "C")))
    open_val = sum(value_of(max(l["menge"] - l["wemng"], 0), l["netpr"], l["peinh"])
                   for l in lines if not l["elikz"])
    overdue = [l for l in lines if not l["elikz"] and l["menge"] > l["wemng"] and
               l["eindt"] and l["eindt"] < today]
    to_invoice = sum(value_of(l["wemng"] - l["remng"], l["netpr"], l["peinh"]) for l in lines)
    contract_share = sum(val(l) for l in period if l["konnr"]) / spend * 100 if spend else 0
    pr_wait = conn.execute("SELECT COUNT(DISTINCT banfn) FROM pr_item WHERE statu='B'"
                           ).fetchone()[0]
    pr_open = conn.execute("SELECT COUNT(*) FROM pr_item WHERE statu='N'").fetchone()[0]
    po_block = conn.execute("SELECT COUNT(*) FROM po_header WHERE frgke='B'").fetchone()[0]
    cyc = conn.execute("SELECT AVG(julianday(h.bedat)-julianday(p.badat)) FROM pr_item p "
                       "JOIN po_header h ON h.ebeln=p.ebeln WHERE p.statu='A' AND h.bedat "
                       "BETWEEN ? AND ?", (d1, d2)).fetchone()[0]
    sav = 0
    for s in conn.execute("SELECT DISTINCT submi FROM rfq WHERE statu='A'").fetchall():
        q = conn.execute("SELECT * FROM rfq WHERE submi=? AND netpr IS NOT NULL",
                         (s["submi"],)).fetchall()
        win = [x for x in q if x["statu"] == "A"][0]
        avgp = sum(x["netpr"] for x in q) / len(q)
        sav += value_of(win["menge"], int(avgp) - win["netpr"], win["peinh"])
    ipv = conn.execute("SELECT COALESCE(SUM(CASE WHEN i.shkzg='S' THEN i.dmbtr ELSE -i.dmbtr "
                       "END),0) FROM acc_doc_item i JOIN acc_doc h USING (belnr, gjahr) WHERE "
                       "h.tcode='MIRO' AND i.ktosl IN ('BSX','PRD','') AND i.hkont NOT IN "
                       "('154000','160000','161000','191100','193000') AND h.budat BETWEEN ? "
                       "AND ?", (d1, d2)).fetchone()[0]
    ev = vendor_evaluation(conn, d1, d2)
    monthly = {}
    for l in lines:
        monthly[l["bedat"][:7]] = monthly.get(l["bedat"][:7], 0) + val(l)
    return {
        "kpi": {"spend": _a(spend), "po_count": len({l["ebeln"] for l in period}),
                "vendors": len(by_vendor), "open_commitment": _a(open_val),
                "to_invoice": _a(to_invoice), "overdue_items": len(overdue),
                "overdue_value": _a(sum(value_of(l["menge"] - l["wemng"], l["netpr"],
                                                 l["peinh"]) for l in overdue)),
                "contract_share": round(contract_share, 1), "pr_waiting": pr_wait,
                "pr_open": pr_open, "po_blocked": po_block,
                "cycle_days": round(cyc, 1) if cyc is not None else None,
                "savings": _a(sav), "ipv": _a(ipv),
                "ontime": round(sum(e["ontime_pct"] or 0 for e in ev if e["ontime_pct"]
                                    is not None) / max(1, sum(1 for e in ev if e["ontime_pct"]
                                                              is not None)), 1)},
        "abc": abc,
        "by_group": [dict(group=k, spend=_a(v)) for k, v in sorted(by_group.items(),
                                                                    key=lambda x: -x[1])],
        "by_material": [dict(item=k, spend=_a(v)) for k, v in
                        sorted(by_mat.items(), key=lambda x: -x[1])[:10]],
        "monthly": [dict(month=k, spend=_a(v)) for k, v in sorted(monthly.items())],
        "overdue": [dict(ebeln=l["ebeln"], ebelp=l["ebelp"], lifnr=l["lifnr"],
                         name=names.get(l["lifnr"], ""), matnr=l["matnr"] or l["txz01"],
                         eindt=l["eindt"], open=qty_out(l["menge"] - l["wemng"]),
                         days=(datetime.date.fromisoformat(today) -
                               datetime.date.fromisoformat(l["eindt"])).days)
                    for l in overdue],
        "evaluation": ev, "groups": PURCH_GROUPS,
    }
