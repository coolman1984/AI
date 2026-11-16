"""JSON API of the detailed HR functions: loans and salary advances (ZHR_LOAN), one-time payments
and penalties (ZHR_ADDPAY), follow-up events (ZHR_EVENTS), leave balances (ZHR_LEAVEBAL),
payroll cost per cost center (ZHR_COST) and the HR month-end (ZHR_CLOSE)."""
from hr import extras
from hr.config import ADDPAY_TYPES, LOAN_TYPES
from mm.util import amt_out, require

from .fi_api import _yp
from .server import db, route


def _conv(rows, keys):
    for r in rows:
        for k in keys:
            if isinstance(r.get(k), int):
                r[k] = amt_out(r[k])
    return rows


@route("GET", "/api/hr/loans")
def hr_loans(req, q):
    return {"rows": _conv(extras.loans(db(), q.get("pernr") or None, q.get("status") or None),
                          ("amount", "installment", "repaid", "balance")), "types": LOAN_TYPES}


@route("POST", "/api/hr/loan")
def hr_loan_create(req, q):
    return extras.create_loan(db(), req.body, req.user)


@route("GET", "/api/hr/addpay")
def hr_addpay(req, q):
    y, p = _yp(q)
    rows = _conv(extras.payments(db(), y, p), ("amount",))
    for r in rows:
        r["days"] = r["days"] / 100.0
    return {"rows": rows, "types": {k: v["text"] for k, v in ADDPAY_TYPES.items()}}


@route("POST", "/api/hr/addpay/(?P<act>add|delete)")
def hr_addpay_act(req, q, act):
    b = req.body
    if act == "delete":
        require(b, "id")
        return extras.delete_payment(db(), b["id"], req.user)
    return extras.add_payment(db(), b, req.user)


@route("GET", "/api/hr/events")
def hr_events(req, q):
    return extras.events(db(), q.get("key_date") or None, q.get("days") or 60)


@route("GET", "/api/hr/leavebal")
def hr_leavebal(req, q):
    return extras.leave_balances(db(), q.get("year") or None)


@route("GET", "/api/hr/cost")
def hr_cost(req, q):
    r = extras.cost(db(), q.get("year") or None)
    _conv(r["rows"], ["total"] + ["m%02d" % m for m in range(1, 13)])
    r["total"] = amt_out(r["total"])
    return r


@route("GET", "/api/hr/close_mgmt")
def hr_close_mgmt(req, q):
    y, p = _yp(q)
    return extras.status(db(), y, p)
