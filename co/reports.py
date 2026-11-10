"""CO reports.

S_ALR_87013611  cost centers: actual / plan / variance (by cost element)
S_ALR_87013625  cost centers: actual / target / variance (operating rate)
KSB1 / KSBP     cost center actual / plan line items
KOB1            order line items
KKBC_ORD        order analysis: plan / target / actual / variances
KSBT            activity prices and activity quantities
KE30            profitability report (contribution margin P&L), plan vs actual
KE24            CO-PA line items
ZCO_RECON       FI P&L <-> CO-PA operating result reconciliation
"""
from mm.config import GL_ACCOUNTS
from mm.db import rows
from mm.util import amt_out, qty_out, rdiv

from .config import (CC_CATEGORIES, CE_CATEGORIES, PNL_ROWS, VALUE_FIELDS,
                     VRGNG, VV_KEYS)
from .core import ks, orn
from .fi import fi_pnl


def _a(c):
    return amt_out(c or 0)


def _pct(a, b):
    return round(a / b * 100, 1) if b else None


# ------------------------------------------------------------ hierarchy
def hierarchy(conn):
    groups = rows(conn.execute("SELECT * FROM cc_group ORDER BY khinr"))
    ccs = rows(conn.execute("SELECT * FROM cost_center ORDER BY kostl"))
    return {"groups": groups, "cost_centers": ccs}


def expand_group(conn, khinr):
    out, todo = [], [khinr]
    while todo:
        g = todo.pop()
        out += [r["kostl"] for r in conn.execute("SELECT kostl FROM cost_center WHERE "
                                                 "khinr=?", (g,))]
        todo += [r["khinr"] for r in conn.execute("SELECT khinr FROM cc_group WHERE "
                                                  "parent=?", (g,))]
    return sorted(out)


def _cc_list(conn, kostl="", khinr=""):
    if khinr:
        return expand_group(conn, khinr)
    if kostl:
        return [k.strip() for k in kostl.split(",") if k.strip()]
    return [r["kostl"] for r in conn.execute("SELECT kostl FROM cost_center ORDER BY kostl")]


# ------------------------------------------------------------ S_ALR_87013611
def cc_plan_actual(conn, gjahr, pfrom, pto, kostl="", khinr=""):
    ccs = _cc_list(conn, kostl, khinr)
    objs = [ks(k) for k in ccs]
    if not objs:
        return {"rows": [], "cost_centers": []}
    q = ("SELECT i.kstar, e.ktext, e.katyp, i.wrttp, SUM(i.wtg) AS w FROM co_item i "
         "JOIN cost_element e ON e.kstar=i.kstar WHERE i.gjahr=? AND i.perio BETWEEN ? "
         "AND ? AND i.objnr IN (%s) GROUP BY i.kstar, i.wrttp" % ",".join("?" * len(objs)))
    data = {}
    for r in conn.execute(q, [gjahr, pfrom, pto] + objs):
        d = data.setdefault(r["kstar"], dict(kstar=r["kstar"], ktext=r["ktext"],
                                             katyp=r["katyp"], actual=0, plan=0, commitment=0))
        d["actual" if r["wrttp"] == "04" else "plan"] += r["w"]
    texts = {r["kstar"]: r for r in conn.execute("SELECT kstar, ktext, katyp FROM cost_element")}
    for c in commitments(conn, objs, gjahr, pfrom, pto):
        t = texts.get(c["kstar"]) or {"ktext": c["kstar"], "katyp": 1}
        d = data.setdefault(c["kstar"], dict(kstar=c["kstar"], ktext=t["ktext"], katyp=t["katyp"],
                                             actual=0, plan=0, commitment=0))
        d["commitment"] += c["amount"]
    out = []
    for d in sorted(data.values(), key=lambda x: (x["katyp"] not in (1,), x["kstar"])):
        d["section"] = "Primary costs" if d["katyp"] == 1 else \
            "Secondary costs / credits"
        d["variance"] = d["actual"] - d["plan"]
        d["var_pct"] = _pct(d["variance"], d["plan"])
        d["assigned"] = d["actual"] + d["commitment"]           # actual + committed
        d["available"] = d["plan"] - d["assigned"]
        for k in ("actual", "plan", "variance", "commitment", "assigned", "available"):
            d[k] = _a(d[k])
        d["katyp_text"] = CE_CATEGORIES.get(d["katyp"], "")
        out.append(d)
    names = {r["kostl"]: r for r in conn.execute("SELECT * FROM cost_center")}
    return {"rows": out, "cost_centers": [dict(kostl=k, name=names[k]["name"],
                                               kosar=names[k]["kosar"]) for k in ccs]}


# ------------------------------------------------------------ commitments (KSB2 / KOB2)
def commitments(conn, objnr=None, gjahr=None, pfrom=1, pto=12):
    """Open purchase requisitions and purchase orders with account assignment K / F:
    money already committed to a cost center / order but not yet posted as cost.
    Derived from the documents (always consistent): a PO item is reduced by its goods
    receipts (or invoices, whichever is higher), completed / deleted items are gone."""
    from mm.util import value_of
    out = []
    for r in conn.execute("SELECT * FROM po_item WHERE knttp IN ('K','F') AND COALESCE(loekz,0)=0 AND "
                          "elikz=0 AND menge > MAX(wemng, remng)"):
        open_q = r["menge"] - max(r["wemng"], r["remng"])
        obj = ks(r["kostl"]) if r["knttp"] == "K" else orn(r["aufnr"])
        out.append(dict(objnr=obj, kstar=r["sakto"] or "400000", refbt="PO", refbn=r["ebeln"],
                        refbz=r["ebelp"], date=r["eindt"], text=r["txz01"], qty=open_q,
                        amount=value_of(open_q, r["netpr"], r["peinh"])))
    for r in conn.execute("SELECT * FROM pr_item WHERE knttp IN ('K','F') AND ebeln IS NULL AND "
                          "statu IN ('N','B')"):
        obj = ks(r["kostl"]) if r["knttp"] == "K" else orn(r["aufnr"])
        out.append(dict(objnr=obj, kstar=r["sakto"] or "400000", refbt="PR", refbn=r["banfn"],
                        refbz=r["bnfpo"], date=r["lfdat"], text=r["txz01"], qty=r["menge"],
                        amount=value_of(r["menge"], r["preis"], r["peinh"] or 1)))
    if objnr:
        out = [o for o in out if o["objnr"] in (objnr if isinstance(objnr, (list, tuple, set)) else [objnr])]
    if gjahr:
        lo, hi = "%04d-%02d-01" % (gjahr, pfrom), "%04d-%02d-31" % (gjahr, pto)
        out = [o for o in out if not o["date"] or lo <= o["date"] <= hi]
    return out


# ------------------------------------------------------------ S_ALR_87013625
def cc_target_actual(conn, gjahr, perio, kostl):
    o = ks(kostl)
    acts = conn.execute("SELECT * FROM cc_activity WHERE gjahr=? AND perio=? AND "
                        "kostl=?", (gjahr, perio, kostl)).fetchall()
    act_rows, rates = [], []
    for a in acts:
        aq = -conn.execute("SELECT COALESCE(SUM(qty),0) FROM co_item WHERE objnr=? AND "
                           "wrttp='04' AND gjahr=? AND perio=? AND lstar=? AND qty<0",
                           (o, gjahr, perio, a["lstar"])).fetchone()[0]
        rate = aq / a["plan_qty"] if a["plan_qty"] else 0
        rates.append(rate)
        act_rows.append(dict(lstar=a["lstar"], plan_qty=qty_out(a["plan_qty"]),
                             actual_qty=qty_out(aq), capacity=qty_out(a["capacity"]),
                             rate=round(rate * 100, 1),
                             price_fix=_a(a["price_fix"]), price_var=_a(a["price_var"])))
    rate = sum(rates) / len(rates) if rates else 1.0
    out = []
    for r in conn.execute(
            "SELECT i.kstar, e.ktext, e.katyp, SUM(CASE WHEN wrttp='01' THEN wtg ELSE 0 "
            "END) AS plan, SUM(CASE WHEN wrttp='01' THEN wkf ELSE 0 END) AS pfix, "
            "SUM(CASE WHEN wrttp='04' THEN wtg ELSE 0 END) AS act FROM co_item i JOIN "
            "cost_element e ON e.kstar=i.kstar WHERE objnr=? AND gjahr=? AND perio=? "
            "GROUP BY i.kstar ORDER BY i.kstar", (o, gjahr, perio)):
        pvar = r["plan"] - r["pfix"]
        if r["katyp"] == 43 and r["plan"] < 0:      # activity credit: fully variable
            target = round(r["plan"] * rate)
        else:
            target = r["pfix"] + round(pvar * rate)
        out.append(dict(kstar=r["kstar"], ktext=r["ktext"], plan=_a(r["plan"]),
                        plan_fix=_a(r["pfix"]), plan_var=_a(pvar), target=_a(target),
                        actual=_a(r["act"]), tgt_var=_a(r["act"] - target),
                        var_pct=_pct(r["act"] - target, target)))
    return {"kostl": kostl, "rate": round(rate * 100, 1), "activities": act_rows,
            "rows": out}


# ------------------------------------------------------------ line items
def line_items(conn, wrttp="04", gjahr=None, pfrom=1, pto=12, objnr_prefix="KS",
               obj="", kstar="", vrgng=""):
    sql = ("SELECT i.*, e.ktext, d.bltxt, d.usnam, d.refbn, d.stflg FROM co_item i "
           "JOIN cost_element e ON e.kstar=i.kstar JOIN co_doc d ON d.belnr=i.belnr "
           "WHERE i.wrttp=? AND i.gjahr=? AND i.perio BETWEEN ? AND ? AND i.objnr LIKE ?")
    args = [wrttp, gjahr, pfrom, pto, objnr_prefix + "%"]
    if obj:
        objs = [objnr_prefix + x.strip() for x in obj.split(",") if x.strip()]
        sql += " AND i.objnr IN (%s)" % ",".join("?" * len(objs))
        args += objs
    if kstar:
        sql += " AND i.kstar=?"
        args.append(kstar)
    if vrgng:
        sql += " AND i.vrgng=?"
        args.append(vrgng)
    out = []
    for r in conn.execute(sql + " ORDER BY i.budat DESC, i.belnr DESC, i.buzei LIMIT 5000",
                          args):
        d = dict(r)
        d["object"] = r["objnr"][2:]
        d["wtg"] = _a(r["wtg"])
        d["wkf"] = _a(r["wkf"])
        d["wkv"] = round(d["wtg"] - d["wkf"], 2)
        d["qty"] = qty_out(r["qty"])
        d["vrgng_text"] = VRGNG.get(r["vrgng"], r["vrgng"])
        out.append(d)
    return out


# ------------------------------------------------------------ orders
def order_list(conn):
    out = rows(conn.execute("SELECT * FROM orders ORDER BY aufnr DESC"))
    for o in out:
        bal = conn.execute("SELECT COALESCE(SUM(CASE WHEN vrgng<>'KOAO' AND wtg>0 THEN wtg "
                           "ELSE 0 END),0) AS deb, COALESCE(SUM(wtg),0) AS bal FROM "
                           "co_item WHERE objnr=? AND wrttp='04'", (orn(o["aufnr"]),)
                           ).fetchone()
        o["debits"] = _a(bal["deb"])
        o["balance"] = _a(bal["bal"])
        o["gamng"] = qty_out(o["gamng"])
        o["wemng"] = qty_out(o["wemng"])
    return out


def order_analysis(conn, aufnr):
    o = conn.execute("SELECT o.*, m.maktx, m.meins FROM orders o LEFT JOIN material m "
                     "ON m.matnr=o.matnr WHERE aufnr=?", (aufnr,)).fetchone()
    if not o:
        from mm.util import MMError
        raise MMError("Order %s does not exist" % aufnr, "KO", "001")
    out = dict(o)
    lines = {}
    est = None
    if o["estimate_id"]:
        est = conn.execute("SELECT * FROM cost_estimate WHERE id=?",
                           (o["estimate_id"],)).fetchone()
        for i in conn.execute("SELECT * FROM cost_estimate_item WHERE id=?", (est["id"],)):
            key = i["ressource"].split("/")[1] if i["typ"] == "E" else \
                (i["kstar"] if i["typ"] == "G" else i["ressource"])
            d = lines.setdefault((i["kstar"], key), dict(kstar=i["kstar"], res=key,
                                                         text=i["ktext"], plan=0,
                                                         target=0, actual=0,
                                                         plan_qty=0, act_qty=0))
            d["plan"] += rdiv(i["wert"] * o["gamng"], est["losgr"])
            d["target"] += rdiv(i["wert"] * o["wemng"], est["losgr"])
            d["plan_qty"] += rdiv(i["menge"] * o["gamng"], est["losgr"])
    for a in conn.execute("SELECT kstar, matnr, lstar, vrgng, SUM(wtg) AS w, SUM(qty) AS q "
                          "FROM co_item WHERE objnr=? AND wrttp='04' GROUP BY kstar, "
                          "matnr, lstar, vrgng", (orn(aufnr),)):
        key = "SETTLEMENT" if a["vrgng"] == "KOAO" else \
            (a["matnr"] if a["kstar"] != "895000" else "OUTPUT") or a["lstar"] or a["kstar"]
        d = lines.setdefault((a["kstar"], key), dict(kstar=a["kstar"], res=key,
                                                     text="", plan=0, target=0, actual=0,
                                                     plan_qty=0, act_qty=0))
        d["actual"] += a["w"]
        d["act_qty"] += a["q"]
    if est:
        d = lines.setdefault(("895000", "OUTPUT"), dict(
            kstar="895000", res="OUTPUT", text="", plan=0, target=0, actual=0,
            plan_qty=0, act_qty=0))
        d["plan"] = -sum(x["plan"] for k, x in lines.items() if k[1] not in
                         ("OUTPUT", "SETTLEMENT"))
        d["target"] = -sum(x["target"] for k, x in lines.items() if k[1] not in
                           ("OUTPUT", "SETTLEMENT"))
    ces = {r["kstar"]: r["ktext"] for r in conn.execute("SELECT * FROM cost_element")}
    res = []
    for d in sorted(lines.values(), key=lambda x: (x["res"] in ("OUTPUT", "SETTLEMENT"),
                                                   x["kstar"], x["res"])):
        d["text"] = d["text"] or ces.get(d["kstar"], "")
        d["ce_text"] = ces.get(d["kstar"], "")
        d["variance"] = d["actual"] - d["target"]
        for k in ("plan", "target", "actual", "variance"):
            d[k] = _a(d[k])
        d["plan_qty"] = qty_out(d["plan_qty"])
        d["act_qty"] = qty_out(d["act_qty"])
        res.append(d)
    out["lines"] = res
    out["variances"] = rows(conn.execute("SELECT * FROM order_variance WHERE aufnr=? "
                                         "ORDER BY gjahr DESC, perio DESC, kstar",
                                         (aufnr,)))
    for v in out["variances"]:
        for k in ("target", "actual", "price_var", "qty_var", "res_var", "rem_var"):
            v[k] = _a(v[k])
    out["rules"] = rows(conn.execute("SELECT * FROM settle_rule WHERE aufnr=?", (aufnr,)))
    out["gamng"] = qty_out(o["gamng"])
    out["wemng"] = qty_out(o["wemng"])
    out["confirmations"] = rows(conn.execute("SELECT * FROM confirmation WHERE aufnr=? "
                                             "ORDER BY rueck", (aufnr,)))
    for c in out["confirmations"]:
        c["lmnga"] = qty_out(c["lmnga"])
        c["ism"] = qty_out(c["ism"])
    return out


# ------------------------------------------------------------ KSBT
def activity_prices(conn, gjahr, perio):
    out = []
    for a in conn.execute("SELECT c.*, t.ktext, t.meinh, s.name FROM cc_activity c JOIN "
                          "activity_type t ON t.lstar=c.lstar JOIN cost_center s ON "
                          "s.kostl=c.kostl WHERE gjahr=? AND perio=? ORDER BY c.kostl",
                          (gjahr, perio)):
        aq = -conn.execute("SELECT COALESCE(SUM(qty),0) FROM co_item WHERE objnr=? AND "
                           "wrttp='04' AND gjahr=? AND perio=? AND lstar=? AND qty<0",
                           (ks(a["kostl"]), gjahr, perio, a["lstar"])).fetchone()[0]
        pq = a["plan_qty"]
        out.append(dict(kostl=a["kostl"], name=a["name"], lstar=a["lstar"],
                        ktext=a["ktext"], meinh=a["meinh"], plan_qty=qty_out(pq),
                        capacity=qty_out(a["capacity"]), actual_qty=qty_out(aq),
                        price_fix=_a(a["price_fix"]), price_var=_a(a["price_var"]),
                        price_tot=_a(a["price_fix"] + a["price_var"]),
                        price_ind=a["price_ind"],
                        plan_cost=_a(rdiv(pq * (a["price_fix"] + a["price_var"]), 1000)),
                        rate=round(aq / pq * 100, 1) if pq else None))
    return out


# ------------------------------------------------------------ KE30
def _scheme(vals):
    """vals: dict of value fields -> computed scheme row values"""
    out = {}
    net = vals.get("vv010", 0) - vals.get("vv020", 0)
    cm1 = net - vals.get("vv030", 0) - vals.get("vv050", 0) - vals.get("vv060", 0)
    cm2 = cm1 - vals.get("vv040", 0) - vals.get("vv051", 0) - vals.get("vv061", 0) - \
        vals.get("vv070", 0)
    cm3 = cm2 - vals.get("vv080", 0) - vals.get("vv090", 0)
    ebit = cm3 - vals.get("vv100", 0) - vals.get("vv110", 0)
    out.update(vals)
    out.update({"=NET": net, "=CM1": cm1, "=CM2": cm2, "=CM3": cm3, "=EBIT": ebit})
    return out


def copa_totals(conn, plikz, gjahr, pfrom, pto, filters=None, by=None):
    sel = ", ".join("SUM(%s) AS %s" % (k, k) for k in VV_KEYS)
    sql = ("SELECT %s%s, SUM(CASE WHEN vrgar IN ('F','0') THEN qty ELSE 0 END) AS qty "
           "FROM copa_item WHERE plikz=? AND gjahr=? AND perio BETWEEN ? AND ?"
           % ((by + ", ") if by else "", sel))
    args = [plikz, gjahr, pfrom, pto]
    for k, v in (filters or {}).items():
        if v:
            sql += " AND %s=?" % k
            args.append(v)
    if by:
        sql += " GROUP BY %s" % by
    return conn.execute(sql, args).fetchall()


def ke30(conn, gjahr, pfrom, pto, drill="", filters=None):
    """Contribution margin report: actual, plan, variance + drill-down."""
    filters = {k: v for k, v in (filters or {}).items() if v}
    act = copa_totals(conn, 0, gjahr, pfrom, pto, filters)[0]
    pln = copa_totals(conn, 1, gjahr, pfrom, pto, filters)[0]
    A = _scheme({k: act[k] or 0 for k in VV_KEYS})
    P = _scheme({k: pln[k] or 0 for k in VV_KEYS})
    cols = []
    if drill:
        for r in copa_totals(conn, 0, gjahr, pfrom, pto, filters, by=drill):
            cols.append((r[drill] or "#", _scheme({k: r[k] or 0 for k in VV_KEYS}),
                         r["qty"] or 0))
        plan_by = {r[drill] or "#": _scheme({k: r[k] or 0 for k in VV_KEYS})
                   for r in copa_totals(conn, 1, gjahr, pfrom, pto, filters, by=drill)}
        known = {c[0] for c in cols}
        for k, v in plan_by.items():
            if k not in known:
                cols.append((k, _scheme({x: 0 for x in VV_KEYS}), 0))
    out_rows = []
    for code, text, sign in PNL_ROWS:
        a, p = A[code], P[code]
        r = dict(code=code, text=text, kind=sign, actual=_a(a), plan=_a(p),
                 variance=_a(a - p), var_pct=_pct(a - p, p),
                 pct_rev=_pct(a, A["=NET"]))
        if drill:
            r["by"] = {c[0]: _a(c[1][code]) for c in cols}
            r["by_plan"] = {k: _a(v[code]) for k, v in plan_by.items()}
        out_rows.append(r)
    return {"rows": out_rows, "drill": [c[0] for c in cols], "qty_actual":
            qty_out(act["qty"] or 0), "qty_plan": qty_out(pln["qty"] or 0),
            "drill_qty": {c[0]: qty_out(c[2]) for c in cols}}


def ke24(conn, gjahr, pfrom, pto, plikz=0):
    out = []
    for r in conn.execute("SELECT * FROM copa_item WHERE plikz=? AND gjahr=? AND perio "
                          "BETWEEN ? AND ? ORDER BY id DESC LIMIT 5000",
                          (plikz, gjahr, pfrom, pto)):
        d = dict(r)
        for k in VV_KEYS:
            d[k] = _a(r[k])
        d["qty"] = qty_out(r["qty"])
        out.append(d)
    return out


# ------------------------------------------------------------ reconciliation
def reconcile(conn, gjahr, pfrom, pto):
    """FI result = CO-PA operating result - costs still on cost centers -
    costs still on orders (WIP / unsettled) - FI-only P&L postings."""
    from .config import PRIMARY_CATS
    pnl = fi_pnl(conn, gjahr, pfrom, pto)
    fi_result = -sum(r["balance"] for r in pnl)     # revenues are credits
    ces = {r["kstar"]: r["katyp"] for r in conn.execute("SELECT * FROM cost_element")}
    fi_only = [r for r in pnl if r["hkont"] not in ces and r["hkont"] != "500000"]
    fi_only_total = -sum(r["balance"] for r in fi_only)
    cogs_fi = sum(r["balance"] for r in pnl if r["hkont"] == "500000")
    tot = copa_totals(conn, 0, gjahr, pfrom, pto)[0]
    sch = _scheme({k: tot[k] or 0 for k in VV_KEYS})
    cogs_copa = sum((tot[k] or 0) for k in ("vv030", "vv040", "vv050", "vv051", "vv060",
                                            "vv061", "vv070"))
    cc_open = conn.execute("SELECT COALESCE(SUM(wtg),0) FROM co_item WHERE wrttp='04' AND "
                           "gjahr=? AND perio BETWEEN ? AND ? AND objnr LIKE 'KS%'",
                           (gjahr, pfrom, pto)).fetchone()[0]
    ord_open = conn.execute("SELECT COALESCE(SUM(wtg),0) FROM co_item WHERE wrttp='04' AND "
                            "gjahr=? AND perio BETWEEN ? AND ? AND objnr LIKE 'OR%'",
                            (gjahr, pfrom, pto)).fetchone()[0]
    explained = sch["=EBIT"] - cc_open - ord_open + fi_only_total + (cogs_copa - cogs_fi)
    cc_detail = [dict(kostl=r["objnr"][2:], name=r["name"], balance=_a(r["b"]))
                 for r in conn.execute(
                     "SELECT i.objnr, c.name, SUM(i.wtg) AS b FROM co_item i JOIN "
                     "cost_center c ON 'KS'||c.kostl=i.objnr WHERE wrttp='04' AND gjahr=? "
                     "AND perio BETWEEN ? AND ? GROUP BY i.objnr HAVING b<>0 ORDER BY "
                     "i.objnr", (gjahr, pfrom, pto))]
    return {
        "fi_pnl": [dict(r, balance=_a(r["balance"]), co=("CE cat. %s" % ces[r["hkont"]])
                        if r["hkont"] in ces else ("COGS (CO-PA via billing)"
                                                   if r["hkont"] == "500000" else
                                                   "FI only")) for r in pnl],
        "fi_result": _a(fi_result), "copa_ebit": _a(sch["=EBIT"]),
        "cc_open": _a(cc_open), "orders_open": _a(ord_open),
        "fi_only": _a(fi_only_total), "cogs_fi": _a(cogs_fi), "cogs_copa": _a(cogs_copa),
        "explained": _a(explained), "difference": _a(fi_result - explained),
        "ok": fi_result == explained, "cc_detail": cc_detail,
        "value_fields": [dict(vv=k, text=t, value=_a(tot[k] or 0))
                         for k, t in VALUE_FIELDS],
    }


# ------------------------------------------------------------ cockpit
def cockpit(conn, gjahr, perio):
    k = ke30(conn, gjahr, perio, perio)
    rowmap = {r["code"]: r for r in k["rows"]}
    prods = ke30(conn, gjahr, perio, perio, drill="matnr")
    cust = ke30(conn, gjahr, perio, perio, drill="kunnr")
    ytd = ke30(conn, gjahr, 1, perio)
    ccs = []
    for c in conn.execute("SELECT * FROM cost_center ORDER BY kostl"):
        r = conn.execute(
            "SELECT SUM(CASE WHEN wrttp='04' AND vrgng IN ('COIN','KAMV','RKIV','RKIU') "
            "AND wtg>0 THEN wtg ELSE 0 END) AS act, SUM(CASE WHEN wrttp='01' AND vrgng IN "
            "('RKP1','RKP2','RKPV','RKPU') AND wtg>0 THEN wtg ELSE 0 END) AS pln FROM "
            "co_item WHERE objnr=? AND gjahr=? AND perio=?",
            (ks(c["kostl"]), gjahr, perio)).fetchone()
        ccs.append(dict(kostl=c["kostl"], name=c["name"], kosar=c["kosar"],
                        kosar_text=CC_CATEGORIES.get(c["kosar"] or "", ""),
                        actual=_a(r["act"]), plan=_a(r["pln"]),
                        variance=_a((r["act"] or 0) - (r["pln"] or 0)),
                        var_pct=_pct((r["act"] or 0) - (r["pln"] or 0), r["pln"] or 0)))
    rec = reconcile(conn, gjahr, perio, perio)
    orders = order_list(conn)
    return {"gjahr": gjahr, "perio": perio, "pnl": k["rows"], "ytd": ytd["rows"],
            "kpi": {"revenue": rowmap["vv010"]["actual"],
                    "net": rowmap["=NET"]["actual"],
                    "cm1": rowmap["=CM1"]["actual"], "cm2": rowmap["=CM2"]["actual"],
                    "ebit": rowmap["=EBIT"]["actual"],
                    "ebit_plan": rowmap["=EBIT"]["plan"],
                    "revenue_plan": rowmap["vv010"]["plan"],
                    "prod_var": rowmap["vv080"]["actual"],
                    "absorption": rowmap["vv090"]["actual"],
                    "qty": k["qty_actual"], "qty_plan": k["qty_plan"],
                    "recon_ok": rec["ok"], "open_orders": sum(1 for o in orders
                                                               if o["balance"])},
            "products": [dict(matnr=m, net=next(r for r in prods["rows"]
                                                if r["code"] == "=NET")["by"].get(m, 0),
                              cm1=next(r for r in prods["rows"]
                                       if r["code"] == "=CM1")["by"].get(m, 0),
                              ebit=next(r for r in prods["rows"]
                                        if r["code"] == "=EBIT")["by"].get(m, 0),
                              qty=prods["drill_qty"].get(m, 0))
                         for m in prods["drill"]],
            "customers": [dict(kunnr=m, net=next(r for r in cust["rows"]
                                                 if r["code"] == "=NET")["by"].get(m, 0),
                               ebit=next(r for r in cust["rows"]
                                         if r["code"] == "=EBIT")["by"].get(m, 0))
                          for m in cust["drill"]],
            "cost_centers": ccs, "recon": {k2: rec[k2] for k2 in
                                           ("fi_result", "copa_ebit", "difference", "ok")}}


def gl_text(hkont):
    return GL_ACCOUNTS.get(hkont, "")
