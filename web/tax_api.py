"""JSON API of the Egyptian taxes module (ZTAX_*)."""
import base64

from mm.util import amt_out, require
from tax import audit, eta, returns, rules

from .server import db, route

CENTS = {"base", "tax", "payable", "input_at_risk", "amount", "gross", "si_ee", "si_er", "taxable", "martyrs", "profit",
         "turnover", "limit", "upto", "books", "invoices", "einvoices", "vat_base", "diff_books", "diff_einv",
         "diff_vat", "netwr", "mwsbk", "net", "total", "vat", "sales", "threshold"}


def _c(x):
    """cents -> currency for the known amount fields, recursively"""
    if isinstance(x, list):
        return [_c(i) for i in x]
    if isinstance(x, dict):
        return {k: (amt_out(v) if k in CENTS and isinstance(v, int) and not isinstance(v, bool) else _c(v))
                for k, v in x.items()}
    return x


def _yp(q):
    from mm import util as clock
    from mm.util import parse_int
    t = clock.today()
    return (parse_int(q.get("gjahr") or t.year, "year", 2000, 2100),
            parse_int(q.get("perio") or t.month, "month", 1, 12))


# ------------------------------------------------------------------ law register
@route("GET", "/api/tax/law")
def tax_law(req, q):
    c = db()
    day = q.get("day") or None
    return {"rows": rules.register(c, day, q.get("area") or None), "areas": rules.AREAS,
            "payroll": rules.payroll_check(c, day), "wht": rules.wht_check(c, day)}


@route("GET", "/api/tax/law/history")
def tax_law_history(req, q):
    require(q, "key")
    return {"rows": rules.history(db(), q["key"].upper())}


@route("POST", "/api/tax/law/(?P<act>version|verify|apply_payroll|apply_wht)")
def tax_law_act(req, q, act):
    b = req.body
    c = db()
    if act == "version":
        return rules.new_version(c, b, req.user)
    if act == "verify":
        require(b, "id")
        return rules.set_verified(c, b["id"], req.user)
    require(b, "day")
    return rules.apply_payroll(c, b["day"], req.user) if act == "apply_payroll" else rules.apply_wht(c, b["day"], req.user)


# ------------------------------------------------------------------ returns and calendar
@route("GET", "/api/tax/vat")
def tax_vat(req, q):
    y, p = _yp(q)
    return _c(returns.vat_return(db(), y, p))


@route("GET", "/api/tax/f41")
def tax_f41(req, q):
    y, p = _yp(q)
    return _c(returns.form41(db(), y, q.get("q") or (p + 2) // 3))


@route("GET", "/api/tax/sal")
def tax_sal(req, q):
    y, p = _yp(q)
    return _c(returns.salary_return(db(), y, p))


@route("GET", "/api/tax/cit")
def tax_cit(req, q):
    return _c(returns.cit_estimate(db(), _yp(q)[0]))


@route("GET", "/api/tax/simp")
def tax_simp(req, q):
    require(q, "turnover")
    return _c(returns.simplified(db(), q["turnover"], q.get("day") or None))


@route("GET", "/api/tax/cal")
def tax_cal(req, q):
    return _c(returns.calendar_year(db(), _yp(q)[0]))


@route("POST", "/api/tax/mark")
def tax_mark(req, q):
    return returns.mark(db(), req.body, req.user)


# ------------------------------------------------------------------ e-invoice
@route("GET", "/api/tax/einv")
def tax_einv(req, q):
    return _c(eta.outbound(db(), q.get("d1") or None, q.get("d2") or None, q.get("status") or None))


@route("GET", "/api/tax/einv/settings")
def tax_einv_settings(req, q):
    return eta.settings(db())


@route("POST", "/api/tax/einv/(?P<act>settings|generate|export|record|results|cancel|submit)")
def tax_einv_act(req, q, act):
    b = req.body
    c = db()
    if act == "settings":
        return eta.save_settings(c, b, req.user)
    if act in ("generate", "export", "submit"):
        v = b.get("vbelns") or []
        if not v:
            from mm.util import MMError
            raise MMError("Select the invoices", "TX", "935")
        return eta.generate(c, v, req.user) if act == "generate" else eta.export(c, v) if act == "export" else \
            eta.submit_api(c, v, req.user)
    if act == "record":
        require(b, "vbeln")
        return eta.record(c, b["vbeln"], b, req.user)
    if act == "results":
        require(b, "text")
        return eta.import_results(c, b["text"], req.user)
    require(b, "vbeln")
    return eta.request_cancel(c, b["vbeln"], b.get("reason") or "", req.user)


@route("GET", "/api/tax/ein")
def tax_ein(req, q):
    return _c(eta.received(db(), q.get("d1") or None, q.get("d2") or None))


@route("POST", "/api/tax/ein/import")
def tax_ein_import(req, q):
    require(req.body, "text")
    return eta.import_received(db(), req.body["text"], req.user)


# ------------------------------------------------------------------ audit
@route("GET", "/api/tax/audit")
def tax_audit(req, q):
    return _c(audit.checklist(db(), _yp(q)[0]))


@route("GET", "/api/tax/revrec")
def tax_revrec(req, q):
    return _c(audit.revenue_reconciliation(db(), _yp(q)[0]))


@route("GET", "/api/tax/auditfile")
def tax_auditfile(req, q):
    y = _yp(q)[0]
    return {"name": "NERP_Tax_Audit_File_%d.xlsx" % y, "xlsx": base64.b64encode(audit.audit_file(db(), y)).decode("ascii")}


@route("GET", "/api/tax/close")
def tax_close(req, q):
    y, p = _yp(q)
    return _c(audit.close_status(db(), y, p))
