"""API of the HR module (area HR - personnel data and salaries are confidential) and
the employee self-service (/api/hrself: own leave requests only)."""
from hr import engine, payroll, reports
from hr.config import (ABSENCE_TYPES, ACTIONS, CONFIG_TEXT, EMPLOYEE_GROUPS, EMPLOYEE_SUBGROUPS, LEAVE_REASONS,
                       OVERTIME_TYPES)
from mm.util import MMError, amt_out, parse_int, qty_out, require

from web.server import db, route

MONEY = ("basic", "allow_transport", "allow_housing", "allow_other", "ins_wage")
PAY = ("basic", "allowances", "overtime", "unpaid", "gross", "ins_wage", "si_ee", "si_er", "taxable", "tax",
       "martyrs", "other", "net")


def _emp_out(e):
    for k in MONEY:
        if k in e and e[k] is not None:
            e[k] = amt_out(e[k])
    return e


def _pay_out(r):
    for k in PAY + ("gross_fc", "net_fc"):
        if k in r and r[k] is not None:
            r[k] = amt_out(r[k])
    return r


@route("GET", "/api/hr/meta")
def hr_meta(req, q):
    c = db()
    return {"absence_types": {k: v["text"] for k, v in ABSENCE_TYPES.items()}, "overtime_types": OVERTIME_TYPES,
            "groups": EMPLOYEE_GROUPS, "subgroups": EMPLOYEE_SUBGROUPS, "actions": ACTIONS, "leave_reasons": LEAVE_REASONS,
            "orgunits": [dict(r) for r in c.execute("SELECT * FROM hr_orgunit ORDER BY orgeh")],
            "positions": [dict(r) for r in c.execute("SELECT p.*, e.pernr AS holder FROM hr_position p LEFT JOIN "
                                                     "hr_employee e ON e.plans=p.plans AND e.status='A' ORDER BY plans")]}


# ------------------------------------------------------------------ employees (PA40 / PA30 / PA20)
@route("GET", "/api/hr/employees")
def hr_employees(req, q):
    st = q.get("status", "A")
    return [_emp_out(e) for e in engine.employees(db(), None if st == "all" else st, q.get("orgeh") or None,
                                                  q.get("text") or None)]


@route("GET", "/api/hr/employee/(?P<pernr>[0-9]+)")
def hr_employee(req, q, pernr):
    return _emp_out(engine.employee(db(), pernr))


@route("POST", "/api/hr/hire")
def hr_hire(req, q):
    n = engine.hire(db(), req.body, req.user)
    return {"pernr": n, "message": "Employee %s hired" % n}


@route("POST", "/api/hr/employee/(?P<pernr>[0-9]+)/change")
def hr_change(req, q, pernr):
    ch = engine.change(db(), pernr, req.body, req.user, req.body.get("massn") or "02")
    return {"changed": ch, "message": ("Data of %s saved (%s)" % (pernr, ", ".join(ch))) if ch else "No changes"}


@route("POST", "/api/hr/employee/(?P<pernr>[0-9]+)/leave")
def hr_terminate(req, q, pernr):
    require(req.body, "leave_date", "reason")
    engine.terminate(db(), pernr, req.body["leave_date"], req.body["reason"], req.user)
    return {"message": "Leaving of %s saved - the position is vacant" % pernr}


# ------------------------------------------------------------------ organization (PPOME)
@route("GET", "/api/hr/org")
def hr_org(req, q):
    return engine.org_structure(db())


@route("POST", "/api/hr/orgunit")
def hr_orgunit(req, q):
    b = req.body
    engine.save_orgunit(db(), b.get("orgeh"), b.get("text"), b.get("parent") or "", b.get("kostl") or "",
                        b.get("manager") or "")
    return {"message": "Organizational unit %s saved" % b.get("orgeh")}


@route("POST", "/api/hr/position")
def hr_position(req, q):
    b = req.body
    engine.save_position(db(), b.get("plans"), b.get("text"), b.get("orgeh"), b.get("kostl") or "", b.get("persk") or "S")
    return {"message": "Position %s saved" % b.get("plans")}


# ------------------------------------------------------------------ time (PA61 / PT50)
@route("GET", "/api/hr/absences")
def hr_absences(req, q):
    return engine.absences(db(), q.get("pernr") or None, q.get("status") or None, q.get("year") or None)


@route("POST", "/api/hr/absence")
def hr_absence(req, q):
    b = req.body
    require(b, "pernr", "awart", "begda")
    n = engine.request_absence(db(), b["pernr"], b["awart"], b["begda"], b.get("endda"), req.user, b.get("reason"),
                               approve=False)
    return {"id": n, "message": "Absence %s saved - waiting for approval (ZINBOX)" % n}


@route("POST", "/api/hr/absence/decide")
def hr_absence_decide(req, q):
    n = parse_int(req.body.get("id"), "request")
    engine.decide_absence(db(), n, bool(req.body.get("approve")), req.user)
    return {"message": "Leave request %s %s" % (n, "approved" if req.body.get("approve") else "rejected")}


@route("POST", "/api/hr/absence/cancel")
def hr_absence_cancel(req, q):
    n = parse_int(req.body.get("id"), "absence")
    engine.cancel_absence(db(), n, req.user)
    return {"message": "Absence %s cancelled" % n}


@route("GET", "/api/hr/quota/(?P<pernr>[0-9]+)")
def hr_quota(req, q, pernr):
    return engine.quota(db(), pernr, q.get("year") or None)


@route("GET", "/api/hr/quotas")
def hr_quotas(req, q):
    c = db()
    out = []
    for e in engine.employees(c):
        out.append(dict(engine.quota(c, e["pernr"], q.get("year") or None), pernr=e["pernr"], name=e["name"],
                        org_text=e["org_text"]))
    return out


@route("GET", "/api/hr/overtime")
def hr_overtime(req, q):
    out = engine.overtime(db(), q.get("pernr") or None, q.get("month") or None)
    for r in out:
        r["hours"] = qty_out(r["hours"])
    return out


@route("POST", "/api/hr/overtime")
def hr_overtime_add(req, q):
    b = req.body
    require(b, "pernr", "datum", "ottype", "hours")
    n = engine.add_overtime(db(), b["pernr"], b["datum"], b["ottype"], b["hours"], req.user)
    return {"id": n, "message": "Overtime saved"}


# ------------------------------------------------------------------ payroll
def _yp(b):
    return (parse_int(b.get("gjahr"), "year", 2000, 2100), parse_int(b.get("perio"), "period", 1, 12))


@route("GET", "/api/hr/payroll")
def hr_payroll(req, q):
    c = db()
    out = {"runs": payroll.runs(c)}
    if q.get("gjahr") and q.get("perio"):
        y, p = _yp(q)
        out["status"] = payroll.status(c, y, p)
        out["results"] = [_pay_out(r) for r in payroll.results(c, y, p, q.get("pernr") or None)]
        tot = {}
        for r in payroll.results(c, y, p):
            for k in PAY:
                tot[k] = tot.get(k, 0) + (r[k] or 0)
        out["totals"] = _pay_out(tot)
    return out


@route("POST", "/api/hr/payroll/(?P<act>run|simulate|post|reverse|pay)")
def hr_payroll_act(req, q, act):
    c = db()
    y, p = _yp(req.body)
    if act in ("run", "simulate"):
        r = payroll.run(c, y, p, req.user, simulate=act == "simulate")
        return {"status": r["status"], "results": [_pay_out(dict(x)) for x in r["results"]], "totals": _pay_out(r["totals"]),
                "message": "Payroll %04d/%02d %s for %d employees - net pay %s EGP"
                           % (y, p, "simulated" if act == "simulate" else "released", len(r["results"]),
                              amt_out(r["totals"]["net"]))}
    if act == "post":
        return payroll.post(c, y, p, req.user)
    if act == "reverse":
        return payroll.reverse_posting(c, y, p, req.user)
    r = payroll.pay(c, y, p, req.user, req.body.get("budat"))
    r["transfers"] = [dict(t, amount=amt_out(t["amount"]), local=amt_out(t["local"])) for t in r["transfers"]]
    return r


# ------------------------------------------------------------------ reports, customizing
@route("GET", "/api/hr/cockpit")
def hr_cockpit(req, q):
    d = reports.cockpit(db(), q.get("currency") or None)
    d["headcount"]["monthly_cost"] = amt_out(d["headcount"]["monthly_cost"])
    for t in d["trend"]:
        for k in ("gross", "si_er", "net", "tax", "overtime"):
            t[k] = amt_out(t[k] or 0)
    if d["last"]:
        d["last"] = d["trend"][-1]
    return d


@route("GET", "/api/hr/config")
def hr_config(req, q):
    c = db()
    return [dict(key=k, value=engine.cfg(c, k), text=t) for k, t in CONFIG_TEXT.items()]


@route("POST", "/api/hr/config")
def hr_config_save(req, q):
    engine.save_config(db(), req.body.get("values") or {}, req.user)
    return {"message": "HR customizing saved"}


# ------------------------------------------------------------------ self-service (own data only)
def _me(req):
    e = db().execute("SELECT pernr FROM hr_employee WHERE bname=? AND status='A'", (req.user,)).fetchone()
    if not e:
        raise MMError("Your user %s is not linked to an employee (PA30 field 'user')" % req.user, "PG", "080")
    return e[0]


@route("GET", "/api/hrself")
def hrself(req, q):
    c = db()
    p = _me(req)
    e = engine.employee(c, p)
    slips = [dict(gjahr=r["gjahr"], perio=r["perio"], net=amt_out(r["net"]))
             for r in c.execute("SELECT r.gjahr, r.perio, r.net FROM hr_payroll r JOIN hr_payroll_run u USING (gjahr, perio) "
                                "WHERE r.pernr=? AND u.status IN ('POST','PAID') ORDER BY r.gjahr DESC, r.perio DESC",
                                (p,))]
    return {"pernr": p, "name": e["name"], "org_text": e["org_text"], "position_text": e["position_text"],
            "quota": e["quota"], "absences": engine.absences(c, p), "payslips": slips}


@route("POST", "/api/hrself/leave")
def hrself_leave(req, q):
    b = req.body
    require(b, "awart", "begda")
    n = engine.request_absence(db(), _me(req), b["awart"], b["begda"], b.get("endda"), req.user, b.get("reason"))
    return {"id": n, "message": "Leave request %s sent to HR for approval" % n}


@route("GET", "/api/hrself/payslip")
def hrself_payslip(req, q):
    from mm import forms
    y, p = _yp(q)
    return {"html": forms.render(db(), "PAYSLIP", "%04d-%02d-%s" % (y, p, _me(req)))}
