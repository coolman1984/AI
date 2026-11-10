"""JSON API for sales & distribution (SD)."""
import calendar
import datetime
import json

from mm.db import rows
from mm.util import MMError, amt_out, qty_out, parse_qty
from sd import billing, config as C, delivery, order, pricing, reports, service

from .server import db, route
from mm import util as mmclock  # noqa: E402
from mm.util import parse_int  # noqa: E402

AMT = {"netwr", "mwsbk", "netpr", "mwsbp", "wavwr", "kzwi1", "kzwi2", "freight", "kwert", "value", "gross",
       "disc", "net", "cogs", "revenue", "deductions", "cost", "margin", "returns", "credits", "order_value",
       "incoming", "backlog", "delivered_not_billed", "pipeline", "samples", "credit_blocked", "klimk",
       "open_items", "open_orders", "exposure", "overdue", "weighted", "plan", "actual", "total", "budget",
       "used", "price", "tax", "rfwrt"}
QTY = {"kwmeng", "bmeng", "wmeng", "lfimg", "pikmg", "fkimg", "delivered", "billed", "confirmed", "qty", "due",
       "missing", "on_time", "order_qty", "rfmng", "menge"}


def out(o):
    if isinstance(o, list):
        return [out(x) for x in o]
    if isinstance(o, dict):
        r = {}
        for k, v in o.items():
            if isinstance(v, (dict, list)):
                r[k] = out(v)
            elif isinstance(v, int) and not isinstance(v, bool):
                r[k] = amt_out(v) if k in AMT else qty_out(v) if k in QTY else v
            else:
                r[k] = v
        return r
    return o


def _conds(cs):
    for c in cs:
        c["kbetr_txt"] = ("%.2f %%" % (c["kbetr"] / 100.0)) if c["krech"] == "A" else "%.2f EGP" % (c["kbetr"] / 100.0)
    return cs


def _month():
    t = mmclock.today()
    return "%04d-%02d-01" % (t.year, t.month), t.isoformat()


@route("GET", "/api/sd/meta")
def sd_meta(req, q):
    c = db()
    d1, d2 = _month()
    return {
        "doc_types": C.DOC_TYPES, "item_cats": C.ITEM_CATS, "sched": C.SCHED_CATS, "copy": C.COPY_CONTROL,
        "delivery_types": C.DELIVERY_TYPES, "billing_types": C.BILLING_TYPES, "reasons": C.ORDER_REASONS,
        "rejections": C.REJECTION_REASONS, "blocks": C.BLOCKS, "cond_types": C.COND_TYPES,
        "access": C.ACCESS_TABLES, "procs": C.PRICING_PROCS, "proc_det": C.PRICING_DETERMINATION,
        "revenue": [dict(ktgrd=k[0], ktgrm=k[1], hkont=v) for k, v in C.REVENUE_ACCOUNTS.items()],
        "credit": C.CREDIT, "risk": C.RISK_CATEGORIES, "vbtyp": C.VBTYP, "freight": C.FREIGHT_INCOTERMS,
        "warranty": C.WARRANTY_MONTHS, "serialized": C.SERIALIZED, "period": {"d1": d1, "d2": d2},
        "customers": rows(c.execute("SELECT c.kunnr, c.name, c.city, c.klimk, GROUP_CONCAT(v.vtweg) areas FROM "
                                    "customer c LEFT JOIN md_knvv v USING (kunnr) GROUP BY c.kunnr ORDER BY c.kunnr")),
        "materials": rows(c.execute("SELECT DISTINCT m.matnr, m.maktx, m.meins FROM material m JOIN md_mvke v "
                                    "USING (matnr) ORDER BY m.matnr")),
    }


# ====================================================================== orders
@route("POST", "/api/sd/order")
def sd_order_create(req, q):
    r = order.create(db(), req.body, req.user)
    t = C.DOC_TYPES.get((req.body.get("auart") or "OR").upper(), {}).get("text", "Document")
    m = "%s %s has been saved" % (t, r["vbeln"])
    if r.get("delivery"):
        m += " - delivery %s created" % r["delivery"]
    if r["messages"]:
        m += " · " + " · ".join(r["messages"])
    return dict(r, message=m, type="W" if r["messages"] else "S")


@route("GET", "/api/sd/order/(?P<v>[0-9]+)")
def sd_order(req, q, v):
    d = order.detail(db(), v)
    for p in d["items"]:
        _conds(p["conditions"])
    return out(d)


@route("POST", "/api/sd/order/(?P<v>[0-9]+)/(?P<act>change|release|reschedule)")
def sd_order_act(req, q, v, act):
    c = db()
    if act == "change":
        order.change(c, v, req.body, req.user)
        k = c.execute("SELECT cmgst FROM sd_vbak WHERE vbeln=?", (v,)).fetchone()
        if k and k["cmgst"] == "B":
            return {"type": "W", "message": "Document %s has been saved - blocked for credit (VKM1)" % v}
        return {"message": "Document %s has been saved" % v}
    if act == "release":
        order.release_credit(c, v, req.user)
        return {"message": "Document %s released (credit)" % v}
    order.reschedule(c, v, req.body.get("today"))
    return {"message": "Document %s rescheduled (availability check repeated)" % v}


@route("GET", "/api/sd/orders")
def sd_orders(req, q):
    return out(order.va05(db(), q.get("auart", ""), q.get("kunnr", ""), q.get("matnr", ""), q.get("d1", ""),
                          q.get("d2", ""), q.get("open") == "1"))


@route("GET", "/api/sd/(?P<what>backorders|blocked|incomplete)")
def sd_lists(req, q, what):
    c = db()
    return out(order.backorders(c) if what == "backorders" else order.blocked(c) if what == "blocked"
               else order.incomplete_docs(c))


@route("GET", "/api/sd/price")
def sd_price(req, q):
    c = db()
    k = (q.get("kunnr") or "").upper()
    cust = c.execute("SELECT * FROM customer WHERE kunnr=?", (k,)).fetchone()
    if not cust:
        raise MMError("Customer %s does not exist" % k, "V1", "002")
    r = pricing.price_item(c, cust, order.area_of(c, k), (q.get("matnr") or "").upper(),
                           parse_qty(q.get("qty") or "1"), q.get("date") or mmclock.today().isoformat(),
                           manual_disc=q.get("disc") or None, inco1=(order.area_of(c, k) or {}).get("inco1"))
    for cc in r["conds"]:
        cc["text"] = C.COND_TYPES.get(cc["kschl"], {}).get("text", "")
    _conds(r["conds"])
    return out(r)


@route("GET", "/api/sd/conditions")
def sd_conditions(req, q):
    r = pricing.pricing_report(db(), q.get("kschl") or None, q.get("date") or None)
    for x in r:
        x["rate"] = ("%.2f %%" % (x["kbetr"] / 100.0)) if x["konwa"] == "%" else "%.2f" % (x["kbetr"] / 100.0)
        x["scales_txt"] = "; ".join("from %g: %.2f" % (s[0] / 1000.0, s[1] / 100.0) for s in x["scales"])
    return r


@route("POST", "/api/sd/condition")
def sd_condition_save(req, q):
    b = req.body
    n = pricing.save_condition(db(), b.get("kschl") or "", b.get("kotab") or "", b, req.user)
    return {"knumh": n, "message": "Condition record %s saved" % n}


@route("POST", "/api/sd/condition/delete")
def sd_condition_del(req, q):
    return pricing.delete_condition(db(), parse_int(req.body.get("knumh"), "condition record"), req.user)


# ====================================================================== shipping
@route("GET", "/api/sd/duelist")
def sd_due(req, q):
    return out(delivery.due_list(db(), q.get("until") or mmclock.today().isoformat()))


@route("POST", "/api/sd/delivery")
def sd_delivery_create(req, q):
    b = req.body
    r = delivery.create(db(), b.get("vbeln"), req.user, b.get("lfdat"), b.get("items"))
    return dict(r, message="Delivery %s has been saved (%d items)" % (r["vbeln"], r["items"]))


@route("GET", "/api/sd/delivery/(?P<v>[0-9]+)")
def sd_delivery(req, q, v):
    return out(delivery.detail(db(), v))


@route("POST", "/api/sd/delivery/(?P<v>[0-9]+)/(?P<act>pick|gi|reverse|delete|change)")
def sd_delivery_act(req, q, v, act):
    c = db()
    if act == "delete":
        return delivery.delete(c, v, req.user)
    if act == "change":
        return delivery.change(c, v, req.body.get("items") or {}, req.user)
    if act == "pick":
        delivery.pick(c, v, req.body.get("items"))
        return {"message": "Delivery %s picked" % v}
    if act == "gi":
        r = delivery.post_gi(c, v, req.user, req.body.get("budat"))
        return dict(r, message="Goods movement posted for delivery %s - material document %s" % (v, r["mblnr"]))
    delivery.reverse_gi(c, v, req.user, req.body.get("budat"))
    return {"message": "Goods issue for delivery %s reversed" % v}


@route("GET", "/api/sd/deliveries")
def sd_deliveries(req, q):
    return out(delivery.monitor(db(), q.get("status") or ""))


# ====================================================================== billing
@route("GET", "/api/sd/billdue")
def sd_billdue(req, q):
    return out(billing.due_list(db(), q.get("until") or None))


@route("POST", "/api/sd/billing")
def sd_billing_create(req, q):
    r = billing.create(db(), req.body.get("ref"), req.user, req.body.get("fkdat"))
    return out(r)


@route("GET", "/api/sd/billing/(?P<v>[0-9]+)")
def sd_billing(req, q, v):
    d = billing.document(db(), v)
    if d.get("einv") and d["einv"].get("payload"):
        d["einv"]["payload"] = json.loads(d["einv"]["payload"])
    return out(d)


@route("POST", "/api/sd/billing/(?P<v>[0-9]+)/(?P<act>cancel|einv)")
def sd_billing_act(req, q, v, act):
    if act == "cancel":
        return billing.cancel(db(), v, req.user, req.body.get("budat"))
    r = billing.einvoice(db(), v, req.user)
    return dict(r, message="E-invoice %s: %s%s" % (v, r["status"], (" - " + "; ".join(r["errors"]))
                                                    if r["errors"] else ""))


@route("GET", "/api/sd/billings")
def sd_billings(req, q):
    return out(billing.vf05(db(), q.get("d1", ""), q.get("d2", ""), q.get("kunnr", ""), q.get("fkart", "")))


@route("GET", "/api/sd/einv")
def sd_einv(req, q):
    c = db()
    r = rows(c.execute("SELECT b.vbeln, b.fkdat, b.fkart, b.kunnr, c.name, b.netwr, b.mwsbk, e.uuid, e.status, e.ts "
                       "FROM billing b JOIN customer c ON c.kunnr=b.kunnr LEFT JOIN sd_einv e USING (vbeln) WHERE "
                       "b.fkart IN ('F2','G2','L2','RE','ZSRV') AND b.cancelled=0 ORDER BY b.vbeln DESC"))
    return out(r)


# ====================================================================== returns
@route("GET", "/api/sd/returns")
def sd_returns(req, q):
    c = db()
    orders_ = rows(c.execute("SELECT k.*, c.name FROM sd_vbak k JOIN customer c USING (kunnr) WHERE k.auart='RE' "
                             "ORDER BY vbeln DESC"))
    for o in orders_:
        o["reason"] = C.ORDER_REASONS.get(o["augru"] or "", "")
        o["delivery"] = c.execute("SELECT vbeln FROM sd_likp WHERE vgbel=?", (o["vbeln"],)).fetchone()
        o["delivery"] = o["delivery"][0] if o["delivery"] else None
        o["credit"] = c.execute("SELECT vbeln FROM billing WHERE aubel=? AND fkart='RE'", (o["vbeln"],)).fetchone()
        o["credit"] = o["credit"][0] if o["credit"] else None
    stock = rows(c.execute("SELECT q.matnr, m.maktx, q.lgort, q.lgpla, SUM(q.qty) qty FROM quant q JOIN material m "
                           "USING (matnr) WHERE q.insmk='B' AND q.werks='1000' GROUP BY q.matnr, q.lgort, q.lgpla"))
    return out({"orders": orders_, "blocked": stock})


@route("POST", "/api/sd/retdecision")
def sd_retdecision(req, q):
    b = req.body
    from mm.posting import post_goods_movement
    if b.get("decision") not in ("343", "551"):
        raise MMError("Decision must be 343 (back to stock) or 551 (scrap)", "QA", "001")
    line = {"bwart": b["decision"], "matnr": b.get("matnr"), "werks": "1000", "lgort": b.get("lgort"),
            "lgpla": b.get("lgpla") or "", "qty": b.get("qty"), "insmk": "B"}
    if b["decision"] == "551":
        line["kostl"] = b.get("kostl") or "4300"
    r = post_goods_movement(db(), {"budat": b.get("budat"), "bktxt": "Returns decision"}, [line], req.user)
    return dict(r, message="Material document %s posted (%s)" % (r["mblnr"], "back to unrestricted stock"
                                                                  if b["decision"] == "343" else "scrapped"))


# ====================================================================== service / CRM
@route("GET", "/api/sd/equi")
def sd_equi(req, q):
    return out(service.equipment(db(), q.get("kunnr") or None))


@route("POST", "/api/sd/equi")
def sd_equi_save(req, q):
    e = service.create_equipment(db(), req.body, req.user)
    return {"equnr": e, "message": "Equipment %s created" % e}


@route("GET", "/api/sd/qmel")
def sd_qmel(req, q):
    return out(service.notifications(db()))


@route("POST", "/api/sd/qmel")
def sd_qmel_save(req, q):
    r = service.create_notification(db(), req.body, req.user)
    return dict(r, message="Notification %s created%s" % (r["qmnum"], " - UNDER WARRANTY" if r["warranty"] else ""))


@route("POST", "/api/sd/qmel/(?P<n>[0-9]+)/(?P<act>order|complete|dp90)")
def sd_qmel_act(req, q, n, act):
    c = db()
    if act == "order":
        a = service.create_service_order(c, n, req.body, req.user)
        return {"aufnr": a, "message": "Service order %s created and released" % a}
    if act == "complete":
        service.complete(c, n, req.user)
        return {"message": "Notification %s completed, order technically completed" % n}
    r = service.dp90(c, n, req.user, req.body.get("fkdat"))
    return out(dict(r, message="Service invoice %s created (DP90)" % r["vbeln"]))


@route("GET", "/api/sd/activity")
def sd_activity(req, q):
    return service.activities(db())


@route("POST", "/api/sd/activity")
def sd_activity_save(req, q):
    i = service.save_activity(db(), req.body, req.user)
    return {"id": i, "message": "Activity %s saved" % i}


@route("GET", "/api/sd/deal")
def sd_deal(req, q):
    return out(service.deals(db()))


@route("POST", "/api/sd/deal")
def sd_deal_save(req, q):
    k = service.save_deal(db(), req.body, req.user)
    return {"knuma": k, "message": "Sales deal %s saved with condition records ZDEA" % k}


@route("GET", "/api/sd/listing")
def sd_listing(req, q):
    return service.listings(db())


@route("POST", "/api/sd/(?P<what>listing|custmat)")
def sd_listing_save(req, q, what):
    b = req.body
    if what == "listing":
        service.save_listing(db(), b.get("kunnr") or "", b.get("matnr") or "", b.get("kind") or "B",
                             b.get("datab"), b.get("datbi"))
    else:
        service.save_custmat(db(), b.get("kunnr") or "", b.get("matnr") or "", b.get("kdmat") or "",
                             b.get("postx") or "")
    return {"message": "Saved"}


# ====================================================================== reports
@route("GET", "/api/sd/cockpit")
def sd_cockpit(req, q):
    d1, d2 = _month()
    return out(reports.cockpit(db(), q.get("d1") or d1, q.get("d2") or d2))


@route("GET", "/api/sd/sis")
def sd_sis(req, q):
    d1, d2 = _month()
    return out(reports.sis(db(), q.get("d1") or d1, q.get("d2") or d2, q.get("by") or "kunnr"))


@route("GET", "/api/sd/slm")
def sd_slm(req, q):
    d1, d2 = _month()
    return out(reports.service_level(db(), q.get("d1") or d1, q.get("d2") or d2))


@route("GET", "/api/sd/credit")
def sd_credit(req, q):
    return out(reports.credit_overview(db()))


@route("GET", "/api/sd/pipeline")
def sd_pipeline(req, q):
    return out(reports.pipeline(db()))


@route("GET", "/api/sd/samples")
def sd_samples(req, q):
    return out(rows(db().execute(
        "SELECT k.vbeln, k.kunnr, c.name, k.audat, k.augru, k.kostl, l.vbeln dl, h.wadat_ist, l.matnr, l.lfimg, l.cogs "
        "FROM sd_vbak k JOIN customer c USING (kunnr) LEFT JOIN sd_likp h ON h.vgbel=k.vbeln LEFT JOIN sd_lips l ON "
        "l.vbeln=h.vbeln WHERE k.auart IN ('FD','ZWR') ORDER BY k.vbeln DESC")))
