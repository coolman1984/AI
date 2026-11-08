"""JSON API for production planning (PP)."""
import calendar
import datetime

from mm.db import rows
from mm.util import MMError, amt_out, qty_out
from pp import config as C, master, order, planning, reports, service, subcon

from .server import db, route

QTY = {"gamng", "wemng", "igmng", "iasmg", "mgvrg", "lmnga", "xmnga", "bdmng", "enmng", "open",
       "stock", "gsmng", "plnmg", "consumed", "menge", "required", "at_vendor", "to_provide",
       "po_qty", "qty", "avail", "atp", "committed", "receipts", "short", "sales", "production",
       "opening", "vgw", "vgw_setup", "ism", "req", "kapaz", "avail_day", "basis", "eisbe",
       "minbe", "mabst", "requirements", "final", "yield_qty", "scrap_qty", "hours", "bstmi",
       "bstma", "ext_received", "ce_losgr", "mad", "ss", "rop", "safety_stock", "reorder_point",
       "final_avail", "lot", "losgr"}
AMT = {"preis", "plan", "target", "actual", "variance", "wip", "previous", "delta", "dmbtr",
       "price", "total", "qty_var", "price_var", "res_var", "rem_var", "subcon_value", "value",
       "fee", "netpr", "wert"}


def out(o):
    if isinstance(o, list):
        return [out(x) for x in o]
    if isinstance(o, dict):
        r = {}
        for k, v in o.items():
            if isinstance(v, (dict, list)):
                r[k] = out(v)
            elif isinstance(v, int) and not isinstance(v, bool):
                r[k] = qty_out(v) if k in QTY else amt_out(v) if k in AMT else \
                    v / 100.0 if k == "ausch" else v
            else:
                r[k] = v
        return r
    return o


def _month():
    s = db().execute("SELECT value FROM settings WHERE key='pp_sample'").fetchone()
    t = datetime.date.today()
    y, m = (int(s["value"][:4]), int(s["value"][5:7])) if s else (t.year, t.month)
    return y, m


@route("GET", "/api/pp/meta")
def pp_meta(req, q):
    c = db()
    y, m = _month()
    return {
        "order_types": C.ORDER_TYPES, "control_keys": C.CONTROL_KEYS, "status": C.STATUS,
        "mrp_types": C.MRP_TYPES, "strategies": C.STRATEGIES, "lot_sizes": C.LOT_SIZES,
        "special": C.SPECIAL_PROC, "exceptions": C.EXCEPTIONS, "models": C.FORECAST_MODELS,
        "service": sorted(C.SERVICE_Z), "workdays": C.WORKDAYS,
        "sample": {"y": y, "m": m, "d1": "%04d-%02d-01" % (y, m),
                   "d2": "%04d-%02d-%02d" % (y, m, calendar.monthrange(y, m)[1])},
        "work_centers": out(master.work_centers(c)),
        "materials": rows(c.execute("SELECT m.matnr, m.maktx, m.mtart, m.meins, p.dismm, p.beskz, "
                                    "p.sobsl, p.strgr, p.dispo FROM material m JOIN material_plant p "
                                    "ON p.matnr=m.matnr WHERE p.werks='1000' ORDER BY m.matnr")),
        "groups": rows(c.execute("SELECT DISTINCT prgrp, ktext FROM pp_sop_group")),
        "cost_centers": rows(c.execute("SELECT kostl, name FROM cost_center ORDER BY kostl")),
        "activities": rows(c.execute("SELECT lstar, ktext FROM activity_type ORDER BY lstar")),
        "vendors": rows(c.execute("SELECT lifnr, name FROM vendor ORDER BY lifnr")),
        "slocs": rows(c.execute("SELECT werks, lgort, name, bin_managed FROM sloc WHERE werks='1000'")),
    }


# ====================================================================== master data
@route("GET", "/api/pp/bom/(?P<m>[^/]+)")
def pp_bom(req, q, m):
    c = db()
    return out({"items": master.bom(c, m, q.get("werks") or "1000"),
                "explosion": master.explode(c, m.upper(), q.get("werks") or "1000", q.get("qty") or "1"),
                "where_used": master.where_used(c, m)})


@route("POST", "/api/pp/bom")
def pp_bom_save(req, q):
    b = req.body
    master.save_bom(db(), b.get("matnr"), b.get("werks") or "1000", b.get("basis") or "1",
                    b.get("items") or [], req.user, b.get("tcode") or "CS01")
    return {"message": "BOM for material %s saved" % (b.get("matnr") or "").upper()}


@route("GET", "/api/pp/wc")
def pp_wc(req, q):
    return out(master.work_centers(db()))


@route("POST", "/api/pp/wc")
def pp_wc_save(req, q):
    master.save_work_center(db(), req.body, req.user, req.body.get("tcode") or "CR01")
    return {"message": "Work center %s saved" % (req.body.get("arbpl") or "").upper()}


@route("GET", "/api/pp/routing/(?P<m>[^/]+)")
def pp_routing(req, q, m):
    c = db()
    return out({"ops": master.routing(c, m, q.get("werks") or "1000"),
                "versions": rows(c.execute("SELECT * FROM pp_prodver WHERE matnr=?", (m.upper(),))),
                "check": master.check_version(c, m.upper(), q.get("werks") or "1000")})


@route("POST", "/api/pp/routing")
def pp_routing_save(req, q):
    b = req.body
    master.save_routing(db(), b.get("matnr"), b.get("werks") or "1000", b.get("basis") or "1",
                        b.get("ops") or [], req.user, b.get("tcode") or "CA01")
    return {"message": "Routing for material %s saved" % (b.get("matnr") or "").upper()}


@route("GET", "/api/pp/versions")
def pp_versions(req, q):
    c = db()
    out_ = rows(c.execute("SELECT v.*, m.maktx FROM pp_prodver v JOIN material m USING (matnr) "
                          "ORDER BY matnr, verid"))
    for v in out_:
        v["check"] = ", ".join(master.check_version(c, v["matnr"], v["werks"])) or "OK"
    return out(out_)


@route("POST", "/api/pp/version")
def pp_version_save(req, q):
    b = req.body
    master.save_version(db(), b.get("matnr") or "", b.get("werks") or "1000", b.get("verid") or "0001",
                        b.get("text") or "", b.get("adatu"), b.get("bdatu"), b.get("bstmi") or "0",
                        b.get("bstma") or "0", bool(b.get("lock")), req.user)
    return {"message": "Production version saved (consistency check OK)"}


@route("GET", "/api/pp/capacity")
def pp_capacity(req, q):
    y, m = _month()
    d1 = q.get("d1") or "%04d-%02d-01" % (y, m)
    d2 = q.get("d2") or (datetime.date.fromisoformat(d1) + datetime.timedelta(days=41)).isoformat()
    return out(master.capacity(db(), d1, d2, q.get("arbpl") or None))


# ====================================================================== SOP / PIR
@route("GET", "/api/pp/sop/(?P<g>[^/]+)")
def pp_sop(req, q, g):
    c = db()
    plan = planning.sop_get(c, g)
    for p in plan:
        p["opening"] = 0
    return out({"group": planning.group(c, g), "plan": plan})


@route("POST", "/api/pp/sop/(?P<act>group|plan|transfer)")
def pp_sop_post(req, q, act):
    b = req.body
    c = db()
    if act == "group":
        planning.save_group(c, b.get("prgrp") or "", b.get("ktext") or "", b.get("members") or [], req.user)
        return {"message": "Product group saved"}
    if act == "plan":
        r = planning.sop_plan(c, b.get("prgrp") or "", b.get("months") or [], int(b.get("days") or 10),
                              req.user)
        return out({"plan": r, "message": "Rough-cut plan saved"})
    r = planning.transfer_to_demand(c, b.get("prgrp") or "", req.user)
    return out({"pirs": r, "message": "%d planned independent requirements transferred" % len(r)})


@route("GET", "/api/pp/pir")
def pp_pir(req, q):
    return out(planning.pirs(db(), q.get("matnr") or None))


@route("POST", "/api/pp/pir")
def pp_pir_save(req, q):
    b = req.body
    for it in b.get("items") or [b]:
        planning.save_pir(db(), it.get("matnr") or b.get("matnr") or "", "1000", it.get("month"),
                          str(it.get("qty") or "0"), req.user)
    return {"message": "Planned independent requirements saved"}


# ====================================================================== MRP
@route("POST", "/api/pp/mrp")
def pp_mrp(req, q):
    b = req.body
    r = planning.mrp_run(db(), req.user, (b.get("matnr") or "").upper() or None,
                         single_level=bool(b.get("single")), today=b.get("today") or None)
    r["reorder_point"] = len(r["reorder_point"])
    return dict(r, message="MRP run %s: %d materials, %d planned orders, %d requisitions, %d "
                "exception messages" % (r["run"], r["materials"], r["planned_orders"],
                                        r["requisitions"], r["exceptions"]))


@route("GET", "/api/pp/md04/(?P<m>[^/]+)")
def pp_md04(req, q, m):
    return out(planning.stock_requirements(db(), m, q.get("werks") or "1000"))


@route("GET", "/api/pp/mrplist")
def pp_mrplist(req, q):
    return out(planning.mrp_list(db(), "1000", q.get("dispo") or None))


@route("GET", "/api/pp/mrpmsg")
def pp_mrpmsg(req, q):
    c = db()
    run = c.execute("SELECT * FROM pp_mrp_run ORDER BY id DESC LIMIT 1").fetchone()
    return {"run": dict(run) if run else None,
            "messages": rows(c.execute("SELECT m.*, x.maktx FROM pp_mrp_msg m JOIN material x USING "
                                       "(matnr) WHERE run=? ORDER BY ausk, matnr",
                                       (run["id"] if run else 0,)))}


@route("GET", "/api/pp/plaf")
def pp_plaf(req, q):
    return out(planning.planned_orders(db(), q.get("matnr") or None, q.get("all") != "1"))


@route("POST", "/api/pp/plaf")
def pp_plaf_save(req, q):
    p = planning.save_planned_order(db(), req.body, req.user)
    return {"plnum": p, "message": "Planned order %s saved (firmed)" % p}


@route("POST", "/api/pp/plaf/delete")
def pp_plaf_delete(req, q):
    planning.delete_planned_order(db(), req.body.get("plnum"))
    return {"message": "Planned order %s deleted" % req.body.get("plnum")}


@route("POST", "/api/pp/convert")
def pp_convert(req, q):
    b = req.body
    res = []
    for p in b.get("plnums") or [b.get("plnum")]:
        res.append(dict(planning.convert(db(), p, req.user, bool(b.get("release")), today=b.get("today")),
                        plnum=p))
    return {"results": res, "message": "; ".join("%s -> %s %s" % (r["plnum"], "production order"
                                                                  if r["type"] == "ORDER" else
                                                                  "subcontracting PO", r["number"])
                                                 for r in res)}


@route("GET", "/api/pp/pegging/(?P<m>[^/]+)")
def pp_pegging(req, q, m):
    return out(planning.pegging(db(), m))


# ====================================================================== orders
@route("POST", "/api/pp/order")
def pp_order_create(req, q):
    a = order.create(db(), req.body, req.user)
    return {"aufnr": a, "message": "Production order %s saved" % a}


@route("GET", "/api/pp/order/(?P<a>[0-9]+)")
def pp_order(req, q, a):
    return out(order.detail(db(), a))


@route("POST", "/api/pp/order/(?P<a>[0-9]+)/(?P<act>release|change|teco)")
def pp_order_act(req, q, a, act):
    c = db()
    if act == "release":
        r = order.release(c, a, req.user, req.body.get("budat"))
        msg = "Order %s released" % a
        if r["missing"]:
            msg += " - MISSING PARTS: %s" % ", ".join(x["matnr"] for x in r["missing"])
        if r["prs"]:
            msg += " - external processing requisition(s) %s" % ", ".join(r["prs"])
        return out(dict(r, message=msg, type="W" if r["missing"] else "S"))
    if act == "change":
        order.change(c, a, req.body, req.user)
        return {"message": "Order %s changed and rescheduled" % a}
    order.teco(c, a, req.user)
    return {"message": "Order %s technically completed (TECO)" % a}


@route("POST", "/api/pp/release")
def pp_release_coll(req, q):
    out_ = []
    for a in req.body.get("aufnrs") or []:
        try:
            r = order.release(db(), a, req.user, req.body.get("budat"))
            out_.append(dict(aufnr=a, ok=True, missing=len(r["missing"])))
        except MMError as e:
            out_.append(dict(aufnr=a, ok=False, text=str(e)))
    return {"results": out_, "message": "%d of %d orders released" % (
        sum(1 for r in out_ if r["ok"]), len(out_))}


@route("GET", "/api/pp/coois")
def pp_coois(req, q):
    return out(order.coois(db(), q.get("auart", ""), q.get("stat", ""), q.get("matnr", ""),
                           q.get("d1", ""), q.get("d2", "")))


@route("GET", "/api/pp/atp")
def pp_atp(req, q):
    from mm.util import parse_qty
    return out(order.availability(db(), (q.get("matnr") or "").upper(), "1000",
                                  parse_qty(q.get("qty") or "1"),
                                  q.get("date") or datetime.date.today().isoformat()))


@route("GET", "/api/pp/missing")
def pp_missing(req, q):
    c = db()
    res = []
    for o in c.execute("SELECT aufnr, matnr, gstrp FROM orders WHERE stat IN ('CRTD','REL') AND "
                       "auart IN ('PP01','ZP03','ZREF','ZP07')").fetchall():
        for a in order.check_order(c, o["aufnr"]):
            a.update(aufnr=o["aufnr"], header=o["matnr"])
            res.append(a)
    return out(res)


@route("POST", "/api/pp/confirm")
def pp_confirm(req, q):
    b = req.body
    r = order.confirm(db(), b.get("aufnr"), b.get("vornr"), b.get("yield") or "0",
                      b.get("scrap") or "0", b.get("act") or None, b.get("budat"),
                      None if b.get("final") in (None, "") else bool(b.get("final")), req.user)
    m = "Confirmation %s saved: activity %.3f h" % (r["rueck"], r["activity"] / 1000.0)
    if r["backflush"]:
        m += ", %d component(s) backflushed" % r["backflush"]
    if r["auto_gr"]:
        m += ", automatic goods receipt"
    return dict(r, message=m)


@route("POST", "/api/pp/confirm/cancel")
def pp_confirm_cancel(req, q):
    order.cancel_confirmation(db(), req.body.get("rueck"), req.user, req.body.get("budat"))
    return {"message": "Confirmation %s cancelled" % req.body.get("rueck")}


@route("GET", "/api/pp/confirmations")
def pp_confirmations(req, q):
    sql = ("SELECT c.*, o.matnr FROM confirmation c JOIN orders o USING (aufnr) WHERE o.auart IN "
           "('PP01','ZP03','ZREF','ZP07')")
    args = []
    if q.get("aufnr"):
        sql += " AND c.aufnr=?"
        args.append(q["aufnr"])
    r = rows(db().execute(sql + " ORDER BY rueck DESC", args))
    for x in r:
        x["yield"] = qty_out(x.pop("lmnga") or 0)
        x["scrap"] = qty_out(x.pop("xmnga") or 0)
        x["act"] = qty_out(x.pop("ism") or 0)
    return r


@route("GET", "/api/pp/picking")
def pp_picking(req, q):
    return out(order.picking_list(db()))


@route("POST", "/api/pp/picking")
def pp_picking_post(req, q):
    r = order.post_picking(db(), req.body.get("items") or [], req.body.get("budat"), req.user)
    return dict(r, message="Material document %s posted (goods issue 261)" % r["mblnr"])


# ====================================================================== subcontracting
@route("GET", "/api/pp/subcon")
def pp_subcon(req, q):
    return out({"items": subcon.cockpit(db()), "stock": subcon.stock_list(db()),
                "pos": subcon.subcon_items(db())})


@route("POST", "/api/pp/subcon/(?P<act>provide|po)")
def pp_subcon_post(req, q, act):
    b = req.body
    if act == "provide":
        r = subcon.provide(db(), b.get("ebeln"), b.get("budat"), req.user)
        return dict(r, message="Components provided to vendor (541) - document %s" % r["mblnr"])
    e = subcon.create_po(db(), (b.get("lifnr") or "").upper(), b.get("matnr") or "", b.get("qty") or "1",
                         b.get("eindt"), req.user)
    return {"ebeln": e, "message": "Subcontracting purchase order %s created" % e}


# ====================================================================== service parts
@route("POST", "/api/pp/forecast")
def pp_forecast(req, q):
    b = req.body
    if b.get("mass"):
        r = service.mass_forecast(db(), "1000", req.user, bool(b.get("apply")))
        for x in r:
            for k in ("mad", "ss", "rop"):
                if k in x:
                    x[k] = qty_out(x[k])
        return {"results": r, "message": "Mass forecast for %d materials" % len(r)}
    r = service.forecast(db(), b.get("matnr") or "", "1000", b.get("model") or "G",
                         int(b.get("hist") or 6), int(b.get("periods") or 6), float(b.get("alpha") or 0.3),
                         float(b.get("beta") or 0.2), int(b.get("service") or 95), user=req.user,
                         apply=bool(b.get("apply")))
    r["history"] = [dict(month=m, value=qty_out(v)) for m, v in r["history"]]
    r["forecast"] = [dict(month=m, value=qty_out(v)) for m, v in r["forecast"]]
    r["expost"] = [qty_out(v) for v in r["expost"]]
    for k in ("mad", "safety_stock", "reorder_point"):
        r[k] = qty_out(r[k])
    r["message"] = "Forecast %s: MAD %.3f, MAPE %.1f %%, safety stock %.3f, reorder point %.3f" % (
        r["matnr"], r["mad"], r["mape"], r["safety_stock"], r["reorder_point"])
    return r


@route("GET", "/api/pp/forecast")
def pp_forecast_list(req, q):
    c = db()
    out_ = rows(c.execute("SELECT f.*, m.maktx, m.meins, p.eisbe, p.minbe, p.dismm FROM pp_fc_param f "
                          "JOIN material m USING (matnr) JOIN material_plant p ON p.matnr=f.matnr AND "
                          "p.werks=f.werks"))
    for f in out_:
        f["mape"] = f["mape"] / 100.0
        f["tsig"] = f["tsig"] / 100.0
        f["alpha"] = f["alpha"] / 100.0
        f["values"] = [dict(month=v["month"], kind=v["kind"], value=qty_out(v["value"]))
                       for v in c.execute("SELECT * FROM pp_forecast WHERE matnr=? ORDER BY month",
                                          (f["matnr"],))]
        f["stock"] = c.execute("SELECT COALESCE(SUM(qty),0) FROM quant WHERE matnr=? AND werks='1000' "
                               "AND insmk='U'", (f["matnr"],)).fetchone()[0]
    return out(out_)


@route("GET", "/api/pp/reservations")
def pp_resv(req, q):
    return out(service.reservations(db(), q.get("all") != "1"))


@route("POST", "/api/pp/reservation")
def pp_resv_create(req, q):
    b = req.body
    r = service.create_reservation(db(), b.get("kostl"), b.get("items") or [], b.get("bdter"), req.user)
    return {"rsnum": r, "message": "Reservation %s created" % r}


@route("POST", "/api/pp/reservation/issue")
def pp_resv_issue(req, q):
    b = req.body
    r = service.issue_reservation(db(), b.get("rsnum"), b.get("budat"), req.user, b.get("items"))
    return dict(r, message="Goods issue %s posted against reservation %s" % (r["mblnr"], b.get("rsnum")))


@route("POST", "/api/pp/wip")
def pp_wip(req, q):
    b = req.body
    y, m = _month()
    r = service.wip(db(), b.get("gjahr") or y, b.get("perio") or m, req.user, bool(b.get("test")))
    return out({"orders": r, "message": "WIP %s: %d order(s), total %.2f" % (
        "test run" if b.get("test") else "posted", len(r), sum(x["wip"] for x in r) / 100.0)})


@route("GET", "/api/pp/wip")
def pp_wip_list(req, q):
    return out(rows(db().execute("SELECT w.*, o.matnr, o.stat FROM pp_wip w JOIN orders o USING (aufnr) "
                                 "ORDER BY gjahr DESC, perio DESC, aufnr")))


@route("GET", "/api/pp/cockpit")
def pp_cockpit(req, q):
    y, m = _month()
    d1 = q.get("d1") or "%04d-%02d-01" % (y, m)
    d2 = q.get("d2") or "%04d-%02d-%02d" % (y, m, calendar.monthrange(y, m)[1])
    r = reports.cockpit(db(), d1, d2)
    for f in r["forecast"]:
        f["mape"] = f["mape"] / 100.0
    return out(r)
