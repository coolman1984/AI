"""JSON API of the production status board (ZPP_BOARD), the daily line plan (ZPP_LINEPLAN)
and the downtime log (ZPP_LOSS)."""
from mm.util import qty_out
from pp import board

from .server import db, route

Q = ("plan", "target", "prod", "diff", "scrap", "loss_units", "uph_target", "uph_result")


def _q(d, keys):
    for k in keys:
        if isinstance(d.get(k), int):
            d[k] = qty_out(d[k])
    return d


@route("GET", "/api/pp/board")
def pp_board(req, q):
    b = board.board(db(), q.get("datum") or None)
    for g in b["groups"]:
        for r in g["lines"]:
            _q(r, Q)
        _q(g["total"], Q)
    if b["total"]:
        _q(b["total"], Q)
    for s in b["shipping"]:
        _q(s, ("ordered", "delivery", "shipped", "open"))
    for s in b["shortages"]:
        _q(s, ("required", "stock", "short"))
    for s in b["quality"]["lines"]:
        _q(s, ("today", "d1", "week"))
    _q(b["quality"], ("blocked_stock",))
    return b


@route("GET", "/api/pp/lineplan")
def pp_lineplan(req, q):
    rows = board.plans(db(), q.get("datum"))
    for r in rows:
        _q(r, ("plan", "uph"))
    return {"rows": rows}


@route("POST", "/api/pp/lineplan/(?P<act>save|copy)")
def pp_lineplan_act(req, q, act):
    b = req.body
    if act == "copy":
        return board.copy_plans(db(), b.get("src"), b.get("dst"), req.user)
    return board.save_plan(db(), b, req.user)


@route("GET", "/api/pp/loss")
def pp_loss(req, q):
    return {"rows": board.losses(db(), q.get("datum")), "reasons": board.LOSS_REASONS}


@route("POST", "/api/pp/loss")
def pp_loss_add(req, q):
    return board.add_loss(db(), req.body, req.user)
