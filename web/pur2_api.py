"""JSON API of the detailed Purchasing functions: import file / letter of credit and landed
cost (ZIMP01, ZLC01, ZIMP_COST, ZIMP_LAND, ZLC_REL, ZIMP03), service entry sheets (ML81N),
delivery reminders (ME91F), price history (ZPUR_PRICE), configuration (ZPUR_CONF) and the
purchasing month-end (ZPUR_CLOSE)."""
from mm.util import amt_out, qty_out, require
from pur import closing, followup, importfile, service

from .fi_api import _yp
from .server import db, route


def _amt(rows, keys):
    for r in rows:
        for k in keys:
            if k in r and isinstance(r[k], int):
                r[k] = amt_out(r[k])
    return rows


def _qty(rows, keys):
    for r in rows:
        for k in keys:
            if k in r and isinstance(r[k], int):
                r[k] = qty_out(r[k])
    return rows


# ------------------------------------------------------------------ import / LC
@route("GET", "/api/pur/import")
def pur_import(req, q):
    c = db()
    rows = _amt(importfile.files(c, q.get("status") or None),
                ("lc_amount", "margin", "costs", "landed", "goods_received"))
    for r in rows:
        r["margin_pct"] = r["margin_pct"] / 100.0
    return {"rows": rows, "cost_types": importfile.COST_TYPES, "status": importfile.STATUS}


@route("GET", "/api/pur/import/costs")
def pur_import_costs(req, q):
    require(q, "impno")
    return {"rows": _amt(importfile.costs(db(), q["impno"]), ("amount",))}


@route("POST", "/api/pur/import/(?P<act>create|lc|cost|land|test|release)")
def pur_import_act(req, q, act):
    b = req.body
    c = db()
    if act == "create":
        return importfile.create(c, b, req.user)
    require(b, "impno")
    if act == "lc":
        r = importfile.open_lc(c, b["impno"], b, req.user)
        r["margin"] = amt_out(r["margin"])
        return r
    if act == "cost":
        return importfile.add_cost(c, b["impno"], b, req.user)
    if act == "release":
        return importfile.release_margin(c, b["impno"], b, req.user)
    r = importfile.land(c, b["impno"], b, req.user, test=act == "test")
    r["total"] = amt_out(r["total"])
    _amt(r["items"], ("goods", "share", "to_stock", "to_prd"))
    _qty(r["items"], ("qty",))
    return r


# ------------------------------------------------------------------ service entry sheets
@route("GET", "/api/pur/ses")
def pur_ses(req, q):
    c = db()
    return {"sheets": _qty(_amt(service.sheets(c, q.get("status") or None), ("amount",)), ("menge",)),
            "items": _qty(_amt(service.service_items(c, q.get("ebeln") or None), ("value", "netpr")),
                          ("menge", "wemng", "open")),
            "status": service.STATUS}


@route("POST", "/api/pur/ses/(?P<act>create|accept|reject)")
def pur_ses_act(req, q, act):
    b = req.body
    c = db()
    if act == "create":
        r = service.create(c, b, req.user)
        r["amount"] = amt_out(r["amount"])
        return r
    require(b, "lblni")
    if act == "accept":
        return service.accept(c, b["lblni"], req.user, b.get("budat"))
    return service.reject(c, b["lblni"], req.user, b.get("reason") or "")


# ------------------------------------------------------------------ follow-up
@route("GET", "/api/pur/reminders")
def pur_reminders(req, q):
    rows = followup.overdue(db(), q.get("key_date") or None, q.get("lifnr") or None)
    return {"rows": _qty(_amt(rows, ("open_value", "netpr")), ("menge", "wemng", "open")),
            "levels": followup.LEVEL_TEXT}


@route("POST", "/api/pur/reminders/send")
def pur_reminders_send(req, q):
    b = req.body
    r = followup.send(db(), b.get("items") or [], req.user, b.get("key_date") or None)
    for v in r["letters"]:
        _qty(v["items"], ("open",))
    return r


@route("GET", "/api/pur/price_history")
def pur_price_history(req, q):
    require(q, "matnr")
    r = followup.price_history(db(), q["matnr"], q.get("lifnr") or None)
    _qty(r["rows"], ("menge",))
    for i in r["info_records"]:
        i["brutto"], i["frb"], i["rabatt"] = amt_out(i["brutto"]), amt_out(i["frb"]), i["rabatt"] / 100.0
    return r


# ------------------------------------------------------------------ configuration / closing
@route("GET", "/api/pur/config")
def pur_config(req, q):
    return closing.config(db())


@route("GET", "/api/pur/close_mgmt")
def pur_close_mgmt(req, q):
    y, p = _yp(q)
    return closing.status(db(), y, p)
