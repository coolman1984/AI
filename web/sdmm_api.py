"""JSON API of the detailed Sales and Warehouse functions: rebate agreements (ZREB01 / ZREB02 /
ZREB_ACR / ZREB03), quotation follow-up (ZSD_QFU), sales configuration and month-end
(ZSD_CONF / ZSD_CLOSE), stock aging (ZMM_AGING), ABC analysis (ZMM_ABC), range of coverage
(ZMM_COVER), warehouse configuration and month-end (ZMM_CONF / ZMM_CLOSE)."""
from mm import analysis
from mm.util import amt_out, qty_out, require
from sd import closing as sdc
from sd import rebate

from .fi_api import _yp
from .server import db, route


def _conv(rows, amts=(), qtys=()):
    for r in rows:
        for k in amts:
            if isinstance(r.get(k), int):
                r[k] = amt_out(r[k])
        for k in qtys:
            if isinstance(r.get(k), int):
                r[k] = qty_out(r[k])
    return rows


def _reb(s):
    _conv([s], ("basis", "earned", "accrued", "settled", "to_accrue"))
    s["rate"] = s["rate"] / 100.0
    for t in s["scale"]:
        t["target"], t["rate"] = amt_out(t["target"]), t["rate"] / 100.0
    if s["next"]:
        s["next"] = dict(target=amt_out(s["next"]["target"]), rate=s["next"]["rate"] / 100.0,
                         missing=amt_out(s["next"]["missing"]))
    return s


# ------------------------------------------------------------------ rebates
@route("GET", "/api/sd/rebate")
def sd_rebates(req, q):
    return {"rows": [_reb(s) for s in rebate.agreements(db(), q.get("kunnr") or None, q.get("upto") or None)],
            "status": rebate.STATUS}


@route("POST", "/api/sd/rebate/(?P<act>create|accrue|test|settle)")
def sd_rebate_act(req, q, act):
    b = req.body
    c = db()
    if act == "create":
        return rebate.create(c, b, req.user)
    if act == "settle":
        require(b, "knuma", "budat")
        r = rebate.settle(c, b["knuma"], b["budat"], req.user)
        r["earned"] = amt_out(r["earned"])
        return r
    require(b, "budat")
    r = rebate.accrue(c, b["budat"], req.user, b.get("knuma") or None, test=act == "test")
    _conv(r["rows"], ("basis", "earned", "amount"))
    r["total"] = amt_out(r["total"])
    return r


# ------------------------------------------------------------------ sales follow-up
@route("GET", "/api/sd/quotations")
def sd_quotations(req, q):
    r = sdc.quotations(db(), q.get("key_date") or None)
    _conv(r["rows"], ("netwr", "ordered"))
    _conv([r], ("total", "won"))
    return r


@route("GET", "/api/sd/config")
def sd_config(req, q):
    return sdc.config(db())


@route("GET", "/api/sd/close_mgmt")
def sd_close_mgmt(req, q):
    y, p = _yp(q)
    return sdc.status(db(), y, p)


# ------------------------------------------------------------------ warehouse
@route("GET", "/api/wm/config")
def wm_config(req, q):
    return analysis.config(db())


@route("GET", "/api/wm/close_mgmt")
def wm_close_mgmt(req, q):
    y, p = _yp(q)
    return analysis.status(db(), y, p)


@route("GET", "/api/wm/aging")
def wm_aging(req, q):
    r = analysis.aging(db(), q.get("key_date") or None, q.get("werks") or None)
    keys = ("value", "d30", "d90", "d180", "d365", "old")
    _conv(r["rows"], keys, ("qty",))
    _conv([r["total"]], keys)
    return r


@route("GET", "/api/wm/abc")
def wm_abc(req, q):
    c = db()
    r = analysis.abc(c, analysis.check_werks(c, q.get("werks") or "1000"), q.get("key_date") or None)
    _conv(r["rows"], ("value",), ("qty",))
    for v in r["summary"].values():
        v["value"] = amt_out(v["value"])
    r["total"] = amt_out(r["total"])
    return r


@route("POST", "/api/wm/abc/save")
def wm_abc_save(req, q):
    c = db()
    b = req.body
    return analysis.save_abc(c, analysis.check_werks(c, b.get("werks") or "1000"), b.get("key_date") or None, req.user)


@route("GET", "/api/wm/coverage")
def wm_coverage(req, q):
    c = db()
    r = analysis.coverage(c, analysis.check_werks(c, q.get("werks") or "1000"), q.get("key_date") or None,
                          q.get("days") or 90)
    _conv(r["rows"], ("value",), ("stock", "used"))
    for x in r["rows"]:
        x["per_day"] = round(x["per_day"] / 1000.0, 3)
    return r
