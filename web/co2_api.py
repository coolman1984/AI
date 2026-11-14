"""JSON API of the detailed Controlling functions: closing management and period lock
(1-5 ZCO_CLOSE, OKP1), budget and availability control (2-x ZBUD...), sales adjustment
(3-1 KE21N), accruals (5-x ZACR...), plan copy (KP97), simulation (E-1 ZCO_SIM) and the
basic configuration display (1-1 ZCO_CONF)."""
from co import accrual, budget, closing, copa, planning, simulation
from mm.util import amt_out, require

from .server import db, route
from .co_api import _yp

BUD_AMT = ("orig", "supp", "ret", "budget", "released", "actual", "commitment", "available", "amount")


def _amt(rows, keys):
    for r in rows:
        for k in keys:
            if k in r and isinstance(r[k], int):
                r[k] = amt_out(r[k])
    return rows


# ------------------------------------------------------------------ 1-1 configuration (display)
@route("GET", "/api/co/config")
def co_config(req, q):
    from co import config as C
    from co.schema import CO_NUMBER_RANGES
    c = db()
    return {"kokrs": C.KOKRS, "kokrs_name": C.KOKRS_NAME, "bukrs": C.BUKRS, "erkrs": C.ERKRS,
            "currency": "EGP", "fiscal_variant": "K4 - calendar year, 12 periods + 4 special periods",
            "versions": [{"version": "0", "text": "Plan / actual (version 0)", "plan": "PLAN", "actual": "ACT"}],
            "ce_categories": [{"katyp": k, "text": v} for k, v in C.CE_CATEGORIES.items()],
            "cc_categories": [{"kosar": k, "text": v} for k, v in C.CC_CATEGORIES.items()],
            "vrgng": [{"vrgng": k, "text": v} for k, v in C.VRGNG.items()],
            "order_types": [{"auart": k, "text": v} for k, v in C.ORDER_TYPES.items()],
            "cost_components": [{"comp": k, "text": v} for k, v in C.COST_COMPONENTS.items()],
            "value_fields": [{"vv": k, "text": v} for k, v in C.VALUE_FIELDS],
            "characteristics": [{"char": k, "text": v} for k, v in C.CHARACTERISTICS.items()],
            "number_ranges": [{"object": k, "start": v} for k, v in CO_NUMBER_RANGES.items()],
            "counts": {t: c.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
                       for t in ("cost_center", "cost_element", "activity_type", "orders", "cycle")},
            "budget_profile": budget.profile(c)}


# ------------------------------------------------------------------ 1-5 closing management, OKP1
@route("GET", "/api/co/close_mgmt")
def co_closing(req, q):
    y, p = _yp(q)
    out = closing.status(db(), y, p)
    out["locks"] = closing.locks(db(), y)
    return out


@route("POST", "/api/co/period_lock")
def co_period_lock(req, q):
    b = req.body
    require(b, "gjahr", "perio")
    return closing.lock(db(), b["gjahr"], b["perio"], b.get("lock", True) not in (False, "0", 0), req.user)


# ------------------------------------------------------------------ 2-x budget
@route("GET", "/api/co/budget")
def co_budget(req, q):
    y, _ = _yp(q)
    c = db()
    return {"gjahr": y, "profile": budget.profile(c), "rows": _amt(budget.report(c, y), BUD_AMT),
            "log": _amt(budget.log(c, q.get("objnr") or None, y), BUD_AMT)}


@route("POST", "/api/co/budget/profile")
def co_budget_profile(req, q):
    b = req.body
    return budget.set_profile(db(), b.get("warn_pct"), b.get("err_pct"), b.get("check_po", True), req.user)


@route("POST", "/api/co/budget/post")
def co_budget_post(req, q):
    b = req.body
    require(b, "objnr", "gjahr", "typ", "amount")
    return budget.post(db(), b["objnr"], b["gjahr"], b["typ"], b["amount"], req.user, b.get("text") or "")


# ------------------------------------------------------------------ 3-1 KE21N
@route("POST", "/api/co/ke21n")
def co_ke21n(req, q):
    belnr = copa.manual_line(db(), req.body, req.user)
    return {"belnr": belnr, "message": "CO-PA line item %s posted (record type B)" % belnr}


# ------------------------------------------------------------------ 5-x accruals
@route("GET", "/api/co/accruals")
def co_accruals(req, q):
    y, p = _yp(q)
    c = db()
    return {"gjahr": y, "perio": p, "rules": _amt(accrual.report(c, y), ("annual", "accrued", "rest")),
            "runs": _amt(accrual.runs(c, y), ("amount",))}


@route("POST", "/api/co/accrual/rule")
def co_accrual_rule(req, q):
    rid = accrual.save_rule(db(), req.body, req.user)
    return {"id": rid, "message": "Accrual rule %s saved" % rid}


@route("POST", "/api/co/accrual/(?P<act>run|test|reverse)")
def co_accrual_act(req, q, act):
    b = req.body
    require(b, "gjahr", "perio")
    if act == "reverse":
        return accrual.reverse(db(), b["gjahr"], b["perio"], req.user)
    r = accrual.run(db(), b["gjahr"], b["perio"], req.user, test=act == "test")
    _amt(r["docs"], ("amount",))
    r["total"] = amt_out(r["total"])
    return r


# ------------------------------------------------------------------ KP97, E-1
@route("POST", "/api/co/kp97")
def co_kp97(req, q):
    b = req.body
    require(b, "from_year", "to_year")
    n = planning.copy_plan(db(), b["from_year"], b["to_year"], b.get("pct") or "0", req.user)
    return {"lines": n, "message": "%d plan lines copied from %s to %s (%s %%)" % (n, b["from_year"], b["to_year"],
                                                                                   b.get("pct") or "0")}


@route("GET", "/api/co/simulation")
def co_simulation(req, q):
    y, _ = _yp(q)
    return simulation.run(db(), dict(q, gjahr=q.get("gjahr") or y))
