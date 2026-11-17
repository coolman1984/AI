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


# ------------------------------------------------------------------ ZSD_BOARD / ZMM_BOARD
def _amt(d, keys):
    from mm.util import amt_out
    for k in keys:
        if isinstance(d.get(k), int):
            d[k] = amt_out(d[k])
    return d


@route("GET", "/api/sd/board")
def sd_board(req, q):
    from sd import board as sdb
    b = sdb.board(db(), q.get("datum") or None)
    keys = ("plan", "target", "actual", "diff", "today", "backlog")
    for g in b["groups"]:
        for r in g["lines"]:
            _amt(r, keys)
            _q(r, ("plan_qty", "qty"))
        _amt(g["total"], keys)
    if b["total"]:
        _amt(b["total"], keys)
    for c in b["customers"]:
        _amt(c, ("sales", "backlog", "receivable", "overdue"))
    for k in ("today", "week", "month", "quotations"):
        _amt(b["orders"][k], ("value",))
    _amt(b["orders"], ("backlog",))
    _amt(b["credit"], ("value",))
    _amt(b["aging"], tuple(b["aging"]))
    _amt(b["returns"]["month"], ("value",))
    _amt(b["returns"]["credit_memos"], ("value",))
    return b


@route("GET", "/api/wm/board")
def wm_board(req, q):
    from mm import board as mmb
    b = mmb.board(db(), q.get("datum") or None)
    keys = ("value", "quality", "blocked")
    for g in b["groups"]:
        for r in g["lines"]:
            _amt(r, keys)
        _amt(g["total"], keys)
    if b["total"]:
        _amt(b["total"], keys)
    _amt(b["inbound"], ("late_value",))
    for r in b["reorder"]:
        _q(r, ("stock", "reorder", "safety"))
    for r in b["slow"]:
        _q(r, ("qty",))
        _amt(r, ("value",))
    _amt(b, ("slow_value",))
    return b


# ------------------------------------------------------------------ daily meeting boards
DM = {"inhouse": "inhouse", "pending": "pending", "oqc": "oqc", "pdefect": "pdefect", "mdefect": "mdefect",
      "mloss": "mloss", "scrap": "pending_scrap"}
DM_QTY = {"plan", "today", "diff", "d1", "month", "scrap", "inhouse", "subcon", "subcon_open", "planned", "done",
          "pending", "pending_qty", "stock_qty", "qty", "ok", "rej", "week", "good", "std", "actual", "over"}
DM_AMT = {"value", "stock_value", "blocked_fg", "returns_value", "blocked_value", "usage_value", "inv_value",
          "scrap_value", "total", "scrapped_value", "0-30 days", "31-90 days", "> 90 days"}


def _dm(x, key=None):
    from mm.util import amt_out
    if isinstance(x, list):
        return [_dm(i) for i in x]
    if isinstance(x, dict):
        return {k: _dm(v, k) for k, v in x.items()}
    if isinstance(x, int) and not isinstance(x, bool):
        if key in DM_AMT:
            return amt_out(x)
        if key in DM_QTY:
            return qty_out(x)
    return x


@route("GET", "/api/pp/dm/(?P<kind>inhouse|pending|oqc|pdefect|mdefect|mloss|scrap)")
def pp_daily_meeting(req, q, kind):
    from pp import daily
    return _dm(getattr(daily, DM[kind])(db(), q.get("datum") or None))
