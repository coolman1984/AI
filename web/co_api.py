"""JSON API for the CO module (registered on the main server's router)."""
import datetime

from co import (actual, copa, costing, master, period_end, planning, reports)
from co.config import (CC_CATEGORIES, CE_CATEGORIES, CHARACTERISTICS,
                       CUSTOMER_GROUPS, KOKRS, KOKRS_NAME, ORDER_STATUS, ORDER_TYPES,
                       PNL_ROWS, REGIONS, VALUE_FIELDS, VRGNG, BUKRS, ERKRS,
                       COST_COMPONENTS)
from co.core import reverse_co_doc
from co.fi import fi_pnl, post_gl_document
from mm.config import GL_ACCOUNTS
from mm.db import rows, transaction
from mm.util import MMError, amt_out, qty_out

from .server import db, route
from mm import util as mmclock  # noqa: E402


def _yp(q):
    s = db().execute("SELECT value FROM settings WHERE key='co_sample'").fetchone()
    if s:
        dy, dp = int(s["value"][:4]), int(s["value"][5:7])
    else:
        t = mmclock.today()
        dy, dp = t.year, t.month
    return int(q.get("gjahr") or dy), int(q.get("perio") or dp)


# ====================================================================== meta
@route("GET", "/api/co/meta")
def co_meta(req, q):
    c = db()
    y, p = _yp({})
    return {
        "kokrs": KOKRS, "kokrs_name": KOKRS_NAME, "bukrs": BUKRS, "erkrs": ERKRS,
        "sample": {"gjahr": y, "perio": p},
        "cost_elements": rows(c.execute("SELECT * FROM cost_element ORDER BY kstar")),
        "cost_centers": rows(c.execute("SELECT * FROM cost_center ORDER BY kostl")),
        "groups": rows(c.execute("SELECT * FROM cc_group ORDER BY khinr")),
        "activity_types": rows(c.execute("SELECT * FROM activity_type ORDER BY lstar")),
        "skf": rows(c.execute("SELECT * FROM stat_kf ORDER BY stagr")),
        "orders": rows(c.execute("SELECT aufnr, auart, ktext, stat, matnr FROM orders "
                                 "ORDER BY aufnr DESC")),
        "customers": rows(c.execute("SELECT * FROM customer ORDER BY kunnr")),
        "cycles": master.get_cycles(c),
        "work_centers": rows(c.execute("SELECT * FROM work_center ORDER BY arbpl")),
        "ce_categories": CE_CATEGORIES, "cc_categories": CC_CATEGORIES,
        "order_types": ORDER_TYPES, "order_status": ORDER_STATUS, "vrgng": VRGNG,
        "value_fields": VALUE_FIELDS, "pnl_rows": PNL_ROWS,
        "characteristics": CHARACTERISTICS, "regions": REGIONS,
        "customer_groups": CUSTOMER_GROUPS, "cost_components": COST_COMPONENTS,
        "gl_accounts": GL_ACCOUNTS,
        "costing_sheet": rows(c.execute("SELECT * FROM costing_sheet ORDER BY zeile")),
        "default_aa": rows(c.execute("SELECT * FROM default_aa")),
    }


# ====================================================================== master data
@route("POST", "/api/co/costelement")
def co_ka01(req, q):
    b = req.body
    master.create_cost_element(db(), b.get("kstar"), b.get("ktext") or "", b.get("katyp"))
    return {"message": "Cost element %s created" % b.get("kstar")}


@route("POST", "/api/co/costcenter")
def co_ks01(req, q):
    from mm import master as mmm
    b = req.body
    mmm.create_cost_center(db(), b.get("kostl"), b.get("name"), b.get("kosar"),
                           b.get("khinr"), b.get("verak"))
    return {"message": "Cost center %s created" % (b.get("kostl") or "").upper()}


@route("POST", "/api/co/costcenter/change")
def co_ks02(req, q):
    b = req.body
    master.change_cost_center(db(), b.get("kostl"), b.get("name"), b.get("kosar"),
                              b.get("khinr"), b.get("verak"))
    return {"message": "Cost center %s changed" % b.get("kostl")}


@route("POST", "/api/co/group")
def co_ksh1(req, q):
    b = req.body
    master.create_cc_group(db(), b.get("khinr"), b.get("ktext") or "", b.get("parent"))
    return {"message": "Hierarchy node %s saved" % b.get("khinr")}


@route("POST", "/api/co/activitytype")
def co_kl01(req, q):
    b = req.body
    master.create_activity_type(db(), b.get("lstar"), b.get("ktext") or "",
                                b.get("meinh") or "H", b.get("kstar"), b.get("ccomp") or 30)
    return {"message": "Activity type %s created" % b.get("lstar")}


@route("POST", "/api/co/skf")
def co_kk01(req, q):
    b = req.body
    master.create_skf(db(), b.get("stagr"), b.get("ktext") or "", b.get("meinh") or "",
                      bool(b.get("fixed")))
    return {"message": "Statistical key figure %s created" % b.get("stagr")}


@route("POST", "/api/co/order")
def co_ko01(req, q):
    a = master.create_order(db(), req.body, req.user)
    return {"aufnr": a, "message": "Order %s saved" % a}


@route("POST", "/api/co/order/status")
def co_order_status(req, q):
    b = req.body
    s = master.set_order_status(db(), b.get("aufnr"), b.get("action"))
    return {"message": "Order %s: status %s" % (b.get("aufnr"), s)}


@route("POST", "/api/co/order/rule")
def co_ko02(req, q):
    b = req.body
    master.change_settlement_rule(db(), b.get("aufnr"), b.get("rules") or [])
    return {"message": "Settlement rule of order %s saved" % b.get("aufnr")}


@route("POST", "/api/co/customer")
def co_xd01(req, q):
    b = req.body
    master.create_customer(db(), b.get("kunnr") or "", b.get("name") or "",
                           b.get("city") or "", b.get("region") or "",
                           b.get("kdgrp") or "", b.get("vtweg") or "10")
    return {"message": "Customer %s created" % b.get("kunnr")}


@route("POST", "/api/co/cycle")
def co_cycle_save(req, q):
    b = req.body
    master.save_cycle(db(), b.get("cycle"), b.get("ktext") or "", b.get("typ"),
                      b.get("seq") or 50, b.get("segments") or [])
    return {"message": "Cycle %s saved" % b.get("cycle")}


@route("GET", "/api/co/hierarchy")
def co_hier(req, q):
    return reports.hierarchy(db())


@route("GET", "/api/co/bom/(?P<matnr>[^/]+)")
def co_bom(req, q, matnr):
    c = db()
    b = rows(c.execute("SELECT b.*, m.maktx, m.meins FROM bom b JOIN material m ON "
                       "m.matnr=b.idnrk WHERE b.matnr=? ORDER BY posnr", (matnr.upper(),)))
    for x in b:
        x["menge"] = qty_out(x["menge"])
        x["basis"] = qty_out(x["basis"])
    r = rows(c.execute("SELECT r.*, w.ktext AS wtext, w.kostl, w.lstar FROM routing r "
                       "JOIN work_center w ON w.arbpl=r.arbpl WHERE matnr=? ORDER BY "
                       "vornr", (matnr.upper(),)))
    for x in r:
        x["vgw"] = qty_out(x["vgw"])
        x["basis"] = qty_out(x["basis"])
    return {"bom": b, "routing": r}


# ====================================================================== planning
@route("POST", "/api/co/plan/costs")
def co_kp06(req, q):
    b = req.body
    planning.plan_costs(db(), b.get("gjahr"), b.get("pfrom"), b.get("pto"),
                        (b.get("kostl") or "").upper(), b.get("kstar"), b.get("fix"),
                        b.get("var"), b.get("lstar") or "", bool(b.get("distribute")),
                        req.user)
    return {"message": "Plan saved for %s / %s" % (b.get("kostl"), b.get("kstar"))}


@route("GET", "/api/co/plan/costs")
def co_kp06_get(req, q):
    y, p = _yp(q)
    c = db()
    out = []
    for r in c.execute("SELECT i.kstar, e.ktext, i.lstar, i.vrgng, SUM(wtg) AS w, "
                       "SUM(wkf) AS f FROM co_item i JOIN cost_element e ON "
                       "e.kstar=i.kstar WHERE wrttp='01' AND gjahr=? AND perio=? AND "
                       "objnr=? GROUP BY i.kstar, i.lstar, i.vrgng ORDER BY i.vrgng, "
                       "i.kstar", (y, p, "KS" + (q.get("kostl") or "").upper())):
        out.append(dict(kstar=r["kstar"], ktext=r["ktext"], lstar=r["lstar"] or "",
                        vrgng=r["vrgng"], vrgng_text=VRGNG.get(r["vrgng"], ""),
                        total=amt_out(r["w"]), fix=amt_out(r["f"]),
                        var=amt_out(r["w"] - r["f"])))
    return out


@route("POST", "/api/co/plan/activity")
def co_kp26(req, q):
    b = req.body
    planning.plan_activity(db(), b.get("gjahr"), b.get("pfrom"), b.get("pto"),
                           (b.get("kostl") or "").upper(), (b.get("lstar") or "").upper(),
                           b.get("qty"), b.get("capacity"), b.get("price_fix"),
                           b.get("price_var"))
    return {"message": "Activity plan saved"}


@route("POST", "/api/co/plan/skf")
def co_kp46(req, q):
    b = req.body
    planning.plan_skf(db(), b.get("gjahr"), b.get("pfrom"), b.get("pto"),
                      (b.get("kostl") or "").upper(), (b.get("stagr") or "").upper(),
                      b.get("value"), "04" if b.get("actual") else "01")
    return {"message": "Statistical key figure saved"}


@route("GET", "/api/co/skf")
def co_skf_values(req, q):
    y, p = _yp(q)
    out = rows(db().execute("SELECT * FROM skf_value WHERE gjahr=? AND perio=? ORDER BY "
                            "stagr, wrttp, kostl", (y, p)))
    for r in out:
        r["value"] = qty_out(r["value"])
    return out


@route("POST", "/api/co/plan/input")
def co_kp06_input(req, q):
    b = req.body
    planning.plan_activity_input(db(), b.get("gjahr"), b.get("pfrom"), b.get("pto"),
                                 (b.get("kostl") or "").upper(),
                                 (b.get("skostl") or "").upper(),
                                 (b.get("lstar") or "").upper(), b.get("qty"))
    return {"message": "Activity input saved"}


@route("POST", "/api/co/kspi")
def co_kspi(req, q):
    b = req.body
    y, p = int(b.get("gjahr")), int(b.get("perio"))
    res = planning.kspi(db(), y, p, req.user)
    for r in res:
        r["plan_qty"] = qty_out(r["plan_qty"])
        r["capacity"] = qty_out(r["capacity"])
        r["price_fix"] = amt_out(r["price_fix"])
        r["price_var"] = amt_out(r["price_var"])
    return {"prices": res, "message": "Plan price calculation executed for %s/%s" % (p, y)}


# ====================================================================== costing
@route("POST", "/api/co/ck11n")
def co_ck11n(req, q):
    b = req.body
    eid = costing.cost_estimate(db(), b.get("matnr", ""), b.get("werks") or "1000",
                                b.get("kadky") or mmclock.today().isoformat(),
                                b.get("losgr") or "100", req.user)
    return {"id": eid, "message": "Cost estimate %s saved (status KA - costed)" % eid}


@route("POST", "/api/co/ck24")
def co_ck24(req, q):
    b = req.body
    r = costing.mark_release(db(), int(b.get("id")), b.get("budat"), req.user)
    return {"message": "Cost estimate released - new standard price %.2f" %
            (r["new_price"] / 100.0)}


@route("GET", "/api/co/estimate")
def co_ck13n(req, q):
    if q.get("id"):
        return costing.get_estimate(db(), int(q["id"]))
    return costing.get_estimate(db(), None, (q.get("matnr") or "").upper(),
                                q.get("werks") or "1000")


@route("GET", "/api/co/estimates")
def co_estimates(req, q):
    out = rows(db().execute("SELECT e.*, m.maktx FROM cost_estimate e JOIN material m ON "
                            "m.matnr=e.matnr ORDER BY id DESC"))
    for r in out:
        r["unit_cost"] = amt_out(costing.unit_cost(r))
        r["total"] = amt_out(r["total"])
        r["fixed"] = amt_out(r["fixed"])
        r["losgr"] = qty_out(r["losgr"])
    return out


# ====================================================================== actual
@route("POST", "/api/co/fb50")
def co_fb50(req, q):
    b = req.body
    return post_gl_document(db(), b.get("header") or {}, b.get("lines") or [], req.user)


@route("POST", "/api/co/kb11n")
def co_kb11n(req, q):
    b = req.body
    belnr = actual.repost(db(), b.get("budat"), b.get("sender") or {},
                          b.get("receiver") or {}, b.get("kstar"), b.get("amount"),
                          b.get("text") or "", req.user)
    return {"belnr": belnr, "message": "Document %s posted" % belnr}


@route("POST", "/api/co/kb21n")
def co_kb21n(req, q):
    b = req.body
    belnr = actual.allocate_activity(db(), b.get("budat"), (b.get("skostl") or "").upper(),
                                     (b.get("lstar") or "").upper(), b.get("qty"),
                                     b.get("receiver") or {}, b.get("text") or "",
                                     req.user)
    return {"belnr": belnr, "message": "Document %s posted" % belnr}


@route("POST", "/api/co/co11n")
def co_co11n(req, q):
    b = req.body
    belnr = actual.confirm(db(), b.get("aufnr"), b.get("vornr"), b.get("yield") or "0",
                           b.get("qty"), b.get("budat"), req.user)
    return {"belnr": belnr, "message": "Confirmation saved (CO document %s)" % belnr}


@route("POST", "/api/co/kb31n")
def co_kb31n(req, q):
    b = req.body
    y, p = actual.post_skf(db(), b.get("budat"), (b.get("kostl") or "").upper(),
                           (b.get("stagr") or "").upper(), b.get("value"))
    return {"message": "Statistical key figure posted for period %s/%s" % (p, y)}


@route("POST", "/api/co/reverse")
def co_reverse(req, q):
    with transaction(db()):
        new = reverse_co_doc(db(), req.body.get("belnr"), req.user)
    return {"belnr": new, "message": "Reversal document %s posted" % new}


@route("GET", "/api/co/doc/(?P<belnr>[0-9]+)")
def co_doc(req, q, belnr):
    c = db()
    h = c.execute("SELECT * FROM co_doc WHERE belnr=?", (belnr,)).fetchone()
    if not h:
        raise MMError("CO document %s does not exist" % belnr, "KI", "060")
    d = dict(h)
    d["vrgng_text"] = VRGNG.get(h["vrgng"], "")
    d["items"] = rows(c.execute("SELECT i.*, e.ktext FROM co_item i JOIN cost_element e "
                                "ON e.kstar=i.kstar WHERE belnr=? ORDER BY buzei", (belnr,)))
    for i in d["items"]:
        i["wtg"] = amt_out(i["wtg"])
        i["wkf"] = amt_out(i["wkf"])
        i["qty"] = qty_out(i["qty"])
        i["object"] = i["objnr"][2:]
        i["otype"] = "Cost center" if i["objnr"].startswith("KS") else "Order"
    return d


# ====================================================================== period end
@route("POST", "/api/co/cycle/run")
def co_cycle_run(req, q):
    b = req.body
    r = period_end.run_cycle(db(), b.get("cycle"), b.get("gjahr"), b.get("perio"),
                             b.get("wrttp") or "04", bool(b.get("test")), req.user)
    for line in r["lines"]:
        line["amount"] = amt_out(line["amount"])
    r["message"] = "Test run: %d lines, nothing posted" % len(r["lines"])
    if not r["test"]:
        r["message"] = "Cycle %s executed: %d sender/receiver lines, documents %s" % (
            b.get("cycle"), len(r["lines"]), ", ".join(r["docs"]) or "-")
    return r


@route("POST", "/api/co/cycle/reverse")
def co_cycle_rev(req, q):
    period_end.reverse_run(db(), int(req.body.get("run_id")), req.user)
    return {"message": "Run %s reversed" % req.body.get("run_id")}


@route("GET", "/api/co/cycle/runs")
def co_cycle_runs(req, q):
    return rows(db().execute("SELECT * FROM cycle_run ORDER BY run_id DESC LIMIT 200"))


@route("POST", "/api/co/kgi2")
def co_kgi2(req, q):
    b = req.body
    out = period_end.overhead(db(), b.get("gjahr"), b.get("perio"), b.get("aufnr") or None,
                              bool(b.get("test")), req.user)
    for r in out:
        r["base"] = amt_out(r["base"])
        r["amount"] = amt_out(r["amount"])
    return {"lines": out, "message": ("Test run - " if b.get("test") else "") +
            "Overhead calculated for %d order/row(s)" % len(out)}


@route("POST", "/api/co/kks2")
def co_kks2(req, q):
    b = req.body
    out = period_end.variances(db(), b.get("gjahr"), b.get("perio"),
                               b.get("aufnr") or None, req.user)
    for r in out:
        for k in ("target", "actual", "variance", "price_var", "qty_var", "res_var",
                  "rem_var"):
            r[k] = amt_out(r[k])
        r["wemng"] = qty_out(r["wemng"])
    return {"lines": out, "message": "Variances calculated for %d order(s)" % len(out)}


@route("POST", "/api/co/ko88")
def co_ko88(req, q):
    b = req.body
    out = period_end.settle(db(), b.get("gjahr"), b.get("perio"), b.get("aufnr") or None,
                            bool(b.get("test")), req.user)
    for r in out:
        r["amount"] = amt_out(r["amount"])
    return {"lines": out, "message": ("Test run - " if b.get("test") else "") +
            "Settlement: %d line(s)" % len(out)}


@route("GET", "/api/co/closing")
def co_closing(req, q):
    """Status of each closing step for the period (closing cockpit)."""
    y, p = _yp(q)
    c = db()

    def cnt(sql, *a):
        return c.execute(sql, a).fetchone()[0]
    runs = {r["cycle"]: dict(r) for r in c.execute(
        "SELECT * FROM cycle_run WHERE gjahr=? AND perio=? AND wrttp='04' AND reversed=0 "
        "ORDER BY run_id", (y, p))}
    open_cc = cnt("SELECT COUNT(*) FROM (SELECT objnr FROM co_item WHERE wrttp='04' AND "
                  "gjahr=? AND perio=? AND objnr LIKE 'KS%' GROUP BY objnr HAVING "
                  "SUM(wtg)<>0)", y, p)
    open_or = cnt("SELECT COUNT(*) FROM (SELECT objnr FROM co_item WHERE wrttp='04' AND "
                  "gjahr=? AND perio<=? AND objnr LIKE 'OR%' GROUP BY objnr HAVING "
                  "SUM(wtg)<>0)", y, p)
    return {
        "gjahr": y, "perio": p,
        "plan_prices": cnt("SELECT COUNT(*) FROM cc_activity WHERE gjahr=? AND perio=? "
                           "AND price_fix+price_var>0", y, p),
        "estimates": cnt("SELECT COUNT(*) FROM cost_estimate WHERE status='FR'"),
        "copa_plan": cnt("SELECT COUNT(*) FROM copa_item WHERE plikz=1 AND gjahr=? AND "
                         "perio=?", y, p),
        "billing": cnt("SELECT COUNT(*) FROM copa_item WHERE plikz=0 AND vrgar='F' AND "
                       "gjahr=? AND perio=?", y, p),
        "confirmations": cnt("SELECT COUNT(*) FROM confirmation WHERE substr(budat,1,7)=?",
                             "%04d-%02d" % (y, p)),
        "runs": runs,
        "kgi2": cnt("SELECT COUNT(*) FROM co_doc WHERE vrgng='KZPI' AND gjahr=? AND perio=? "
                    "AND stflg=0", y, p),
        "kks2": cnt("SELECT COUNT(DISTINCT aufnr) FROM order_variance WHERE gjahr=? AND "
                    "perio=?", y, p),
        "ko88": cnt("SELECT COUNT(*) FROM co_doc WHERE vrgng='KOAO' AND gjahr=? AND "
                    "perio=? AND stflg=0", y, p),
        "open_cc": open_cc, "open_orders": open_or,
        "recon_ok": reports.reconcile(c, y, p, p)["ok"],
    }


# ====================================================================== CO-PA
@route("POST", "/api/co/vf01")
def co_vf01(req, q):
    return copa.create_billing(db(), req.body, req.user)


@route("GET", "/api/co/billing")
def co_billing(req, q):
    out = rows(db().execute("SELECT b.*, c.name FROM billing b JOIN customer c ON "
                            "c.kunnr=b.kunnr ORDER BY vbeln DESC"))
    for r in out:
        r["netwr"] = amt_out(r["netwr"])
        r["items"] = rows(db().execute("SELECT * FROM billing_item WHERE vbeln=?",
                                       (r["vbeln"],)))
        for i in r["items"]:
            for k in ("price", "gross", "disc", "net", "cogs"):
                i[k] = amt_out(i[k])
            i["fkimg"] = qty_out(i["fkimg"])
            i["disc_pct"] = i["disc_pct"] / 100.0
    return out


@route("POST", "/api/co/ke11")
def co_ke11(req, q):
    b = req.body
    copa.plan_sales(db(), b.get("gjahr"), b.get("perio"), (b.get("kunnr") or "").upper(),
                    (b.get("matnr") or "").upper(), b.get("qty"), b.get("price"),
                    b.get("disc") or "0", user=req.user)
    return {"message": "Sales plan saved and valuated"}


@route("GET", "/api/co/ke11")
def co_ke11_get(req, q):
    y, p = _yp(q)
    out = rows(db().execute("SELECT p.*, c.name, m.maktx FROM copa_plan_qty p JOIN customer "
                            "c ON c.kunnr=p.kunnr JOIN material m ON m.matnr=p.matnr WHERE "
                            "gjahr=? AND perio=? ORDER BY kunnr, matnr", (y, p)))
    for r in out:
        r["qty"] = qty_out(r["qty"])
        r["price"] = amt_out(r["price"])
        r["disc_pct"] = r["disc_pct"] / 100.0
        r["revenue"] = round(r["qty"] * r["price"], 2)
    return out


# ====================================================================== reports
@route("GET", "/api/co/rep/cc")
def co_rep_cc(req, q):
    y = int(q.get("gjahr") or _yp(q)[0])
    return reports.cc_plan_actual(db(), y, int(q.get("pfrom") or _yp(q)[1]),
                                  int(q.get("pto") or _yp(q)[1]),
                                  (q.get("kostl") or "").upper(), q.get("khinr") or "")


@route("GET", "/api/co/rep/target")
def co_rep_target(req, q):
    y, p = _yp(q)
    return reports.cc_target_actual(db(), y, p, (q.get("kostl") or "").upper())


@route("GET", "/api/co/rep/lineitems")
def co_rep_items(req, q):
    y, p = _yp(q)
    return reports.line_items(db(), q.get("wrttp") or "04", y,
                              int(q.get("pfrom") or p), int(q.get("pto") or p),
                              q.get("otype") or "KS", (q.get("obj") or "").upper(),
                              q.get("kstar") or "", q.get("vrgng") or "")


@route("GET", "/api/co/rep/orders")
def co_rep_orders(req, q):
    return reports.order_list(db())


@route("GET", "/api/co/rep/order/(?P<aufnr>[0-9]+)")
def co_rep_order(req, q, aufnr):
    return reports.order_analysis(db(), aufnr)


@route("GET", "/api/co/rep/prices")
def co_rep_prices(req, q):
    y, p = _yp(q)
    return reports.activity_prices(db(), y, p)


@route("GET", "/api/co/rep/ke30")
def co_rep_ke30(req, q):
    y, p = _yp(q)
    filters = {k: q.get(k) for k in ("matnr", "kunnr", "region", "kdgrp", "vtweg", "matkl")}
    return reports.ke30(db(), y, int(q.get("pfrom") or p), int(q.get("pto") or p),
                        q.get("drill") or "", filters)


@route("GET", "/api/co/rep/ke24")
def co_rep_ke24(req, q):
    y, p = _yp(q)
    return reports.ke24(db(), y, int(q.get("pfrom") or p), int(q.get("pto") or p),
                        int(q.get("plikz") or 0))


@route("GET", "/api/co/rep/recon")
def co_rep_recon(req, q):
    y, p = _yp(q)
    return reports.reconcile(db(), y, int(q.get("pfrom") or p), int(q.get("pto") or p))


@route("GET", "/api/co/rep/fipnl")
def co_rep_fipnl(req, q):
    y, p = _yp(q)
    out = fi_pnl(db(), y, int(q.get("pfrom") or p), int(q.get("pto") or p))
    for r in out:
        r["balance"] = amt_out(r["balance"])
    return out


@route("GET", "/api/co/cockpit")
def co_cockpit(req, q):
    y, p = _yp(q)
    return reports.cockpit(db(), y, p)
