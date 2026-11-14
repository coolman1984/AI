"""JSON API of the detailed Accounting functions: cheques (ZCHQ_IN / ZCHQ_OUT / ZCHQ), petty
cash journal (FBCJ), recurring entries (FBD1 / FBD3 / F.14), parked documents (FV50 /
FBV0 / FBV3), statement of account (F.27) and FI closing management (ZFI_CLOSE)."""
from fi import cashbook, cheque, closing, parked, recurring, reports
from mm.util import amt_out, require

from .server import db, route
from .fi_api import _yp


def _amt(rows, keys):
    for r in rows:
        for k in keys:
            if k in r and isinstance(r[k], int):
                r[k] = amt_out(r[k])
    return rows


# ------------------------------------------------------------------ cheques
@route("GET", "/api/fi/cheques")
def fi_cheques(req, q):
    c = db()
    s = cheque.summary(c)
    for v in s.values():
        v["amount"] = amt_out(v["amount"])
    return {"rows": _amt(cheque.register(c, q.get("dir") or None, q.get("status") or None), ("amount",)),
            "summary": s, "status": cheque.STATUS}


@route("POST", "/api/fi/cheque/(?P<act>in|out|collect|bounce)")
def fi_cheque_act(req, q, act):
    b = req.body
    c = db()
    if act == "in":
        r = cheque.receive(c, b, req.user)
    elif act == "out":
        r = cheque.issue(c, b, req.user)
    elif act == "collect":
        require(b, "id", "budat")
        return cheque.collect(c, b["id"], b["budat"], req.user)
    else:
        require(b, "id", "budat")
        return cheque.bounce(c, b["id"], b["budat"], req.user, b.get("reason") or "")
    r["amount"] = amt_out(r["amount"])
    return r


# ------------------------------------------------------------------ petty cash
@route("GET", "/api/fi/cashbook")
def fi_cashbook(req, q):
    y, p = _yp(q)
    d1 = q.get("d1") or "%04d-%02d-01" % (y, p)
    d2 = q.get("d2") or "%04d-12-31" % y
    bk = cashbook.book(db(), d1, d2)
    _amt(bk["lines"], ("receipt", "payment", "balance"))
    for k in ("opening", "closing", "receipts", "payments"):
        bk[k] = amt_out(bk[k])
    bk["types"] = cashbook.TYPES
    return bk


@route("POST", "/api/fi/cashbook/post")
def fi_cashbook_post(req, q):
    r = cashbook.post(db(), req.body, req.user)
    r["balance"] = amt_out(r["balance"])
    return r


# ------------------------------------------------------------------ recurring entries
@route("GET", "/api/fi/recurring")
def fi_recurring(req, q):
    c = db()
    return {"docs": _amt(recurring.documents(c), ("amount",)), "runs": recurring.runs(c)}


@route("POST", "/api/fi/recurring/save")
def fi_recurring_save(req, q):
    rid = recurring.save(db(), req.body, req.user)
    return {"id": rid, "message": "Recurring document %s saved" % rid}


@route("POST", "/api/fi/recurring/(?P<act>run|test)")
def fi_recurring_run(req, q, act):
    b = req.body
    require(b, "gjahr", "perio")
    return recurring.run(db(), b["gjahr"], b["perio"], req.user, test=act == "test")


# ------------------------------------------------------------------ parked documents
@route("GET", "/api/fi/parked")
def fi_parked(req, q):
    return {"rows": _amt(parked.listing(db(), q.get("status") or None), ("amount",))}


@route("POST", "/api/fi/parked/(?P<act>park|post|delete)")
def fi_parked_act(req, q, act):
    b = req.body
    c = db()
    if act == "park":
        pid = parked.park(c, b, req.user)
        return {"id": pid, "message": "Document parked as %s - a second person posts it (FBV0)" % pid}
    require(b, "id")
    return parked.post(c, b["id"], req.user) if act == "post" else parked.delete(c, b["id"], req.user)


# ------------------------------------------------------------------ F.27, ZFI_CLOSE
@route("GET", "/api/fi/statement")
def fi_statement(req, q):
    require(q, "partner", "d1", "d2")
    s = reports.statement(db(), q.get("koart") or "D", q["partner"], q["d1"], q["d2"])
    _amt(s["lines"], ("debit", "credit", "balance"))
    for k in ("opening", "closing", "debit", "credit"):
        s[k] = amt_out(s[k])
    return s


@route("GET", "/api/fi/close_mgmt")
def fi_close_mgmt(req, q):
    y, p = _yp(q)
    return closing.status(db(), y, p)
