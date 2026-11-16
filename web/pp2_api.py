"""JSON API of the detailed Production functions: OEE (ZPP_OEE), scrap analysis (ZPP_SCRAP),
order progress (ZPP_PROGRESS), configuration (ZPP_CONF) and month-end (ZPP_CLOSE)."""
from mm.util import amt_out, qty_out
from pp import analysis

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


@route("GET", "/api/pp/config")
def pp_config(req, q):
    return analysis.config(db())


@route("GET", "/api/pp/close_mgmt")
def pp_close_mgmt(req, q):
    y, p = _yp(q)
    return analysis.status(db(), y, p)


@route("GET", "/api/pp/oee")
def pp_oee(req, q):
    r = analysis.oee(db(), q.get("d1"), q.get("d2"))
    _conv(r["rows"], (), ("good", "scrap", "ideal"))
    return r


@route("GET", "/api/pp/scrap")
def pp_scrap(req, q):
    r = analysis.scrap(db(), q.get("d1"), q.get("d2"))
    for k in ("by_reason", "by_material", "by_line"):
        _conv(r[k], ("value",), ("good", "scrap"))
    _conv([r], ("value",), ("good", "scrap"))
    return r


@route("GET", "/api/pp/progress")
def pp_progress(req, q):
    r = analysis.progress(db(), q.get("key_date") or None, q.get("all") != "1")
    _conv(r["rows"], (), ("gamng", "confirmed", "delivered"))
    return r
