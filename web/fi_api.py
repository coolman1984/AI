"""JSON API for the FI module (registered on the main server's router)."""
import datetime

from fi import aa, ap, ar, gl, reports
from fi.config import (ASSET_CLASSES, ASSET_TRANS, BUKRS, BUTXT, CURRENCIES, DEP_KEYS,
                       DOC_TYPES, DUNNING, FSV_NODES, HOUSE_BANKS, KTOPL, NUMBER_RANGES,
                       PAYMENT_TERMS, POSTING_KEYS, TAX_CODES)
from mm.db import rows
from mm.util import (MMError, amt_out, parse_int, parse_key, parse_period, parse_year,
                     qty_out)

from .server import db, route
from mm import util as mmclock  # noqa: E402


def _yp(q):
    s = db().execute("SELECT value FROM settings WHERE key='co_sample'").fetchone()
    t = mmclock.today()
    dy, dp = (int(s["value"][:4]), int(s["value"][5:7])) if s else (t.year, t.month)
    return parse_year(q.get("gjahr"), dy), parse_period(q.get("perio"), dp)


def _cents(d, keys):
    for k in keys:
        if d.get(k) is not None and isinstance(d.get(k), int):
            d[k] = amt_out(d[k])
    return d


# ====================================================================== meta
@route("GET", "/api/fi/meta")
def fi_meta(req, q):
    c = db()
    y, p = _yp({})
    vend = rows(c.execute("SELECT * FROM vendor ORDER BY lifnr"))
    cust = rows(c.execute("SELECT * FROM customer ORDER BY kunnr"))
    for x in cust:
        x["klimk"] = amt_out(x["klimk"] or 0)
    num = {r["object"][3:]: r["current"] for r in c.execute(
        "SELECT * FROM number_range WHERE object LIKE 'FI_%'")}
    return {
        "bukrs": BUKRS, "butxt": BUTXT, "ktopl": KTOPL, "sample": {"gjahr": y, "perio": p},
        "gl": rows(c.execute("SELECT * FROM gl_account ORDER BY hkont")),
        "fsv": [dict(node=n, text=t, parent=par, side=s) for n, t, par, s in FSV_NODES],
        "doc_types": [dict(blart=k, text=v[0], nr=v[1], koart=v[2]) for k, v in
                      DOC_TYPES.items()],
        "number_ranges": [dict(nr=k, start=v, current=num.get(k)) for k, v in
                          NUMBER_RANGES.items()],
        "posting_keys": [dict(bschl=k, text=v[0], koart=v[1], shkzg=v[2]) for k, v in
                         POSTING_KEYS.items()],
        "tax": [dict(mwskz=k, text=v[0], pct=v[1] / 100.0, typ=v[2], hkont=v[3])
                for k, v in TAX_CODES.items()],
        "terms": [dict(zterm=k, text=v[0], disc_days=v[1], disc_pct=v[2] / 100.0,
                       net_days=v[3]) for k, v in PAYMENT_TERMS.items()],
        "banks": [dict(hbkid=a, hktid=b, text=t, hkont=g, waers=w,
                       balance=amt_out(reports.gl_balance(c, g, "9999-12-31")))
                  for a, b, t, g, w in HOUSE_BANKS],
        "asset_classes": [dict(anlkl=k, text=v[0], apc=v[1], accdep=v[2], afasl=v[3],
                               ndjar=v[4], numbers=v[5]) for k, v in ASSET_CLASSES.items()],
        "dep_keys": DEP_KEYS, "asset_trans": ASSET_TRANS, "currencies": CURRENCIES,
        "dunning": {"procedure": DUNNING["procedure"], "interval": DUNNING["interval_days"],
                    "grace": DUNNING["grace_days"],
                    "levels": [dict(level=k, text=v[0], charges=amt_out(v[1]))
                               for k, v in DUNNING["levels"].items()]},
        "vendors": vend, "customers": cust,
        "assets": rows(c.execute("SELECT * FROM asset ORDER BY anln1")),
        "rates": rows(c.execute("SELECT waers, gdatu, ukurs/100000.0 AS ukurs FROM "
                                "exch_rate ORDER BY waers, gdatu DESC")),
        "period": dict(c.execute("SELECT * FROM posting_period WHERE id=1").fetchone()
                       or {}),
        "today_open": __import__("fi.document", fromlist=["x"]).period_open(c, mmclock.today().isoformat()),
        "carry_forward_missing": reports.retained_earnings(c, y)[1],
        "blocked_invoices": len(ap.blocked_invoices(c)),
    }


# ====================================================================== GL / config
@route("POST", "/api/fi/fs00")
def fi_fs00(req, q):
    b = req.body
    gl.save_gl_account(db(), b.get("hkont"), b.get("txt") or "", b.get("typ") or "PL",
                       b.get("fsv") or "", b.get("recon") or "", b.get("oi") or 0,
                       b.get("tax") or "", b.get("blocked") or 0)
    return {"message": "G/L account %s saved in chart of accounts INT" % b.get("hkont")}


@route("POST", "/api/fi/ob52")
def fi_ob52(req, q):
    b = req.body
    gl.set_periods(db(), parse_year(b.get("y1")), parse_period(b.get("p1")), parse_year(b.get("y2")),
                   parse_period(b.get("p2")))
    return {"message": "Posting periods %s/%s - %s/%s are open" % (b["p1"], b["y1"],
                                                                   b["p2"], b["y2"])}


@route("POST", "/api/fi/ob08")
def fi_ob08(req, q):
    b = req.body
    gl.set_rate(db(), b.get("waers") or "USD", b.get("gdatu"), b.get("ukurs"))
    return {"message": "Exchange rate saved"}


@route("POST", "/api/fi/f02")
def fi_f02(req, q):
    b = req.body
    belnr = gl.general_posting(db(), b.get("header") or {}, b.get("lines") or [], req.user)
    return {"belnr": belnr, "gjahr": int((b.get("header") or {}).get("budat", "0000")[:4]
                                         or 0), "message": "Document %s was posted in "
                                                           "company code 1000" % belnr}


@route("POST", "/api/fi/fb08")
def fi_fb08(req, q):
    b = req.body
    new = gl.reverse(db(), parse_key(b.get("belnr"), "document"), parse_year(b.get("gjahr")), b.get("budat"),
                     b.get("reason") or "01", req.user)
    return {"belnr": new, "message": "Document %s was posted (reversal of %s)"
            % (new, b.get("belnr"))}


@route("POST", "/api/fi/fbs1")
def fi_fbs1(req, q):
    b = req.body
    belnr = gl.accrual(db(), b.get("budat"), b.get("stodt"), b.get("lines") or [],
                       b.get("text") or "Accrual", req.user)
    return {"belnr": belnr, "message": "Accrual document %s posted, reversal planned on %s"
            % (belnr, b.get("stodt"))}


@route("POST", "/api/fi/f81")
def fi_f81(req, q):
    b = req.body
    out = gl.reverse_accruals(db(), b.get("d1"), b.get("d2"), req.user)
    return {"lines": out, "message": "%d document(s) reversed" % len(out)}


@route("POST", "/api/fi/fcv")
def fi_fcv(req, q):
    b = req.body
    r = gl.fx_valuation(db(), b.get("key_date"), req.user, bool(b.get("test")))
    r["message"] = ("Test run: " if r["test"] else "Posted %s: " % (r["belnr"] or "-")) + \
        "%d item(s), valuation difference %.2f" % (len(r["lines"]), r["total"])
    return r


@route("POST", "/api/fi/f13")
def fi_f13(req, q):
    b = req.body
    r = gl.grir_clearing(db(), b.get("budat"), req.user, bool(b.get("test")))
    n = sum(1 for x in r["lines"] if x["cleared"])
    r["message"] = ("Test run: " if b.get("test") else "Clearing document %s: "
                    % r["augbl"]) + "%d PO item(s) can be cleared" % n
    return r


@route("GET", "/api/fi/vat")
def fi_vat(req, q):
    y, p = _yp(q)
    d1 = q.get("d1") or "%04d-%02d-01" % (y, p)
    d2 = q.get("d2") or reports.eop(y, p)
    r = gl.vat_report(db(), d1, d2)
    for x in r["rows"]:
        _cents(x, ("base", "tax"))
    for k in ("output", "input", "payable"):
        r[k] = amt_out(r[k])
    r["d1"], r["d2"] = d1, d2
    return r


@route("POST", "/api/fi/fb41")
def fi_fb41(req, q):
    b = req.body
    belnr = gl.vat_settlement(db(), b.get("d1"), b.get("d2"), b.get("budat"), req.user)
    return {"belnr": belnr, "message": "Tax payable posted: document %s" % belnr}


@route("POST", "/api/fi/ff67")
def fi_ff67(req, q):
    b = req.body
    return gl.bank_statement(db(), b.get("hbkid") or "NBE", b.get("azdat"), b.get("aznum"),
                             b.get("opening"), b.get("closing"), b.get("lines") or [],
                             req.user)


@route("GET", "/api/fi/ff67")
def fi_ff67_list(req, q):
    out = rows(db().execute("SELECT * FROM bank_statement ORDER BY id DESC"))
    for r in out:
        _cents(r, ("ssbtr", "esbtr"))
    return out


# ====================================================================== AP
@route("POST", "/api/fi/xk01")
def fi_xk01(req, q):
    from mm import master as mmm
    b = req.body
    mmm.create_vendor(db(), b.get("lifnr"), b.get("name"), b.get("city") or "",
                      b.get("akont") or "160000", b.get("zterm") or "NT30",
                      b.get("waers") or "EGP", b.get("land") or "EG", b.get("stcd1") or "",
                      b.get("bankn") or "")
    return {"message": "Vendor %s has been created for company code 1000"
            % (b.get("lifnr") or "").upper()}


@route("POST", "/api/fi/xk02")
def fi_xk02(req, q):
    """FK02 from the FI screens: same engine (change documents, dual control) as XK02."""
    from md import partner
    b = req.body
    lifnr = parse_key(b.get("lifnr"), "vendor")
    if b.get("zterm") and b["zterm"] not in PAYMENT_TERMS:
        raise MMError("Payment terms %s are not defined" % b["zterm"], "F2", "060")
    r = {}
    if b.get("zterm"):
        r = partner.change_vendor(db(), lifnr, {"zterm": b["zterm"]}, req.user, "FK02")
    if b.get("sperr") is not None:
        partner.block_vendor(db(), lifnr, req.user, sperr=b.get("sperr"))
    msg = "Changes have been made to vendor %s" % lifnr
    if r.get("sensitive"):
        msg += " - sensitive fields %s must be confirmed by a second person (FK08)" % ", ".join(r["sensitive"])
    return {"message": msg}


@route("POST", "/api/fi/fb60")
def fi_fb60(req, q):
    b = req.body
    belnr = ap.vendor_invoice(db(), b.get("header") or {}, b.get("lines") or [], req.user,
                              bool(b.get("credit_memo")))
    return {"belnr": belnr, "gjahr": int(((b.get("header") or {}).get("budat") or
                                          mmclock.today().isoformat())[:4]),
            "message": "Document %s was posted in company code 1000" % belnr}


@route("GET", "/api/fi/miro/po/(?P<ebeln>[0-9]+)")
def fi_miro_po(req, q, ebeln):
    c = db()
    h = c.execute("SELECT h.*, v.name, v.zterm FROM po_header h JOIN vendor v ON "
                  "v.lifnr=h.lifnr WHERE ebeln=?", (ebeln,)).fetchone()
    if not h:
        raise MMError("Purchase order %s does not exist" % ebeln, "M8", "001")
    items = rows(c.execute("SELECT i.*, m.maktx, m.meins FROM po_item i JOIN material m ON "
                           "m.matnr=i.matnr WHERE ebeln=? ORDER BY ebelp", (ebeln,)))
    for i in items:
        i["to_invoice"] = qty_out(i["wemng"] - i["remng"])
        i["value"] = amt_out(i["netpr"] * (i["wemng"] - i["remng"]) // (1000 * i["peinh"]))
        for k in ("menge", "wemng", "remng"):
            i[k] = qty_out(i[k])
        _cents(i, ("netpr", "reewr"))
    return {"header": dict(h), "items": items}


@route("POST", "/api/fi/miro")
def fi_miro(req, q):
    b = req.body
    credit = bool(b.get("credit"))
    subsequent = bool(b.get("subsequent"))
    if b.get("simulate"):
        s = ap.miro_simulate(db(), b.get("header") or {}, b.get("items") or [], req.user,
                             credit=credit, subsequent=subsequent)
        for l in s["lines"]:
            l["amount"] = amt_out(l["amount"])
            l["wrbtr"] = amt_out(l.get("wrbtr") or 0)
        msg = "Simulation: gross amount %.2f %s - balance OK" % (s["gross"], s["waers"])
        if s.get("blocked"):
            msg += " - will be BLOCKED for payment: " + "; ".join(s["blocked"])
        if s.get("warning"):
            msg += " - " + s["warning"]
        s["message"] = msg
        return s
    belnr = ap.miro(db(), b.get("header") or {}, b.get("items") or [], req.user,
                    credit=credit, subsequent=subsequent)
    msg = "Document no. %s created" % belnr
    if belnr.blocked:
        msg += " - blocked for payment (%s), release with MRBR" % "; ".join(belnr.blocked)
    if belnr.warning:
        msg += " - " + belnr.warning
    return {"belnr": str(belnr), "blocked": belnr.blocked, "type": "W" if belnr.blocked else "S",
            "message": msg}


@route("POST", "/api/fi/mr8m")
def fi_mr8m(req, q):
    b = req.body
    return ap.cancel_invoice(db(), parse_key(b.get("belnr"), "invoice document"),
                             parse_year(b.get("gjahr")), b.get("budat"), req.user,
                             b.get("reason") or "01")


@route("GET", "/api/fi/mrbr")
def fi_mrbr_list(req, q):
    out = ap.blocked_invoices(db())
    for r in out:
        r["wrbtr"] = amt_out(r["wrbtr"])
        r["dmbtr"] = amt_out(r["dmbtr"])
    return out


@route("POST", "/api/fi/mrbr")
def fi_mrbr(req, q):
    b = req.body
    return ap.release_blocked(db(), parse_key(b.get("belnr"), "invoice document"),
                              parse_year(b.get("gjahr")), req.user)


@route("POST", "/api/fi/fbra")
def fi_fbra(req, q):
    b = req.body
    return gl.reset_clearing(db(), parse_key(b.get("augbl"), "clearing document"),
                             parse_year(b.get("gjahr")), req.user, bool(b.get("reverse")),
                             b.get("budat") or None)


@route("GET", "/api/fi/fbra")
def fi_fbra_items(req, q):
    out = rows(db().execute("SELECT i.belnr, i.gjahr, i.buzei, i.koart, i.lifnr, i.kunnr, i.hkont, "
                            "i.shkzg, i.dmbtr, i.sgtxt, h.budat, h.tcode FROM acc_doc_item i JOIN acc_doc h "
                            "USING (belnr, gjahr) WHERE i.augbl=? ORDER BY i.belnr, i.buzei",
                            (parse_key(q.get("augbl"), "clearing document"),)))
    for r in out:
        r["amount"] = amt_out(r["dmbtr"] if r["shkzg"] == "S" else -r["dmbtr"])
    return out


@route("GET", "/api/fi/f16")
def fi_f16_status(req, q):
    from fi.reports import retained_earnings
    y = parse_year(q.get("gjahr"), mmclock.today().year)
    amount, missing = retained_earnings(db(), y)
    done = rows(db().execute("SELECT * FROM fi_carry_forward ORDER BY gjahr"))
    for r in done:
        r["amount"] = amt_out(-r["amount"])
    return {"gjahr": y, "carried": amt_out(-amount), "missing": missing, "runs": done}


@route("POST", "/api/fi/f16")
def fi_f16(req, q):
    b = req.body
    return gl.carry_forward(db(), parse_year(b.get("gjahr")), req.user, bool(b.get("test")))


@route("POST", "/api/fi/afab-reverse")
def fi_afab_reverse(req, q):
    b = req.body
    return aa.reverse_depreciation(db(), parse_year(b.get("gjahr")), parse_period(b.get("perio")),
                                   req.user)


@route("POST", "/api/fi/f110/delete")
def fi_f110_delete(req, q):
    b = req.body
    return ap.delete_proposal(db(), b.get("laufd"), parse_key(b.get("laufi"), "run identification"))


@route("POST", "/api/fi/f110/exclude")
def fi_f110_exclude(req, q):
    b = req.body
    return ap.exclude_from_proposal(db(), b.get("laufd"), parse_key(b.get("laufi"), "run identification"),
                                    parse_key(b.get("belnr"), "document"), parse_year(b.get("gjahr")),
                                    parse_int(b.get("buzei"), "line item"), b.get("exclude", True) is not False)


@route("GET", "/api/fi/openitems")
def fi_open(req, q):
    out = []
    for r in ap.open_items(db(), q.get("koart") or "K", q.get("partner") or None,
                           q.get("key_date") or None):
        d = dict(r)
        d["amount"] = amt_out(r["dmbtr"] if r["shkzg"] == "S" else -r["dmbtr"])
        d["amount_fc"] = amt_out(r["wrbtr"] if r["shkzg"] == "S" else -r["wrbtr"])
        d["disc_date"] = ap.discount_date(r)
        out.append(d)
    return out


@route("POST", "/api/fi/pay")
def fi_pay(req, q):
    b = req.body
    return ap.pay(db(), b.get("koart"), (b.get("partner") or "").upper(), b.get("budat"),
                  [tuple(x) for x in b.get("items") or []], req.user,
                  b.get("bank") or "113100", b.get("amount") or None,
                  bool(b.get("residual")), b.get("discount", True) is not False)


@route("POST", "/api/fi/f110")
def fi_f110(req, q):
    b = req.body
    r = ap.payment_run(db(), b.get("laufd"), (b.get("laufi") or "R1").upper(),
                       b.get("nextd"), req.user, bool(b.get("execute")))
    for p in r["payments"]:
        _cents(p, ("amount", "discount"))
        for i in p["items"]:
            _cents(i, ("amount", "discount"))
    for x in r.get("exceptions") or []:
        _cents(x, ("amount",))
    r["total"] = amt_out(r["total"])
    r["message"] = ("Payment run executed: %d payment document(s)" % len(r["docs"])
                    if r["executed"] else "Proposal created: %d vendor(s)" % len(r["payments"]))
    return r


@route("GET", "/api/fi/f110")
def fi_f110_runs(req, q):
    import json
    out = rows(db().execute("SELECT * FROM payrun ORDER BY laufd DESC, laufi"))
    for r in out:
        r["count"] = len(json.loads(r["proposal"] or "[]"))
        del r["proposal"]
    return out


# ====================================================================== AR
@route("POST", "/api/fi/xd01")
def fi_xd01(req, q):
    from co import master as com
    b = req.body
    com.create_customer(db(), b.get("kunnr") or "", b.get("name") or "", b.get("city") or "",
                        b.get("region") or "CAI", b.get("kdgrp") or "01",
                        b.get("vtweg") or "10", b.get("zterm") or "NT30",
                        b.get("klimk") or "0", "140000", b.get("stcd1") or "",
                        b.get("land") or "EG")
    return {"message": "Customer %s has been created" % (b.get("kunnr") or "").upper()}


@route("POST", "/api/fi/xd02")
def fi_xd02(req, q):
    """FD02 from the FI screens: same engine (change documents, dual control) as XD02."""
    from md import partner
    b = req.body
    kunnr = parse_key(b.get("kunnr"), "customer")
    if b.get("zterm") and b["zterm"] not in PAYMENT_TERMS:
        raise MMError("Payment terms %s are not defined" % b["zterm"], "F2", "060")
    data = {k: b[k] for k in ("zterm", "klimk") if b.get(k) not in (None, "")}
    r = partner.change_customer(db(), kunnr, data, req.user, "FD02") if data else {}
    msg = "Changes have been made to customer %s" % kunnr
    if r.get("sensitive"):
        msg += " - sensitive fields %s must be confirmed by a second person (FD08)" % ", ".join(r["sensitive"])
    return {"message": msg}


@route("POST", "/api/fi/fb70")
def fi_fb70(req, q):
    b = req.body
    belnr = ar.customer_invoice(db(), b.get("header") or {}, b.get("lines") or [],
                                req.user, bool(b.get("credit_memo")))
    return {"belnr": belnr, "gjahr": int(((b.get("header") or {}).get("budat") or
                                          mmclock.today().isoformat())[:4]),
            "message": "Document %s was posted in company code 1000" % belnr}


@route("POST", "/api/fi/f150")
def fi_f150(req, q):
    b = req.body
    r = ar.dunning_run(db(), b.get("ausdt"), req.user, bool(b.get("execute")))
    for L in r["letters"]:
        _cents(L, ("total", "charges"))
        for i in L["items"]:
            _cents(i, ("amount",))
    r["message"] = ("Dunning run executed: " if r["executed"] else "Dunning proposal: ") + \
        "%d customer(s)" % len(r["letters"])
    return r


@route("GET", "/api/fi/credit")
def fi_fd32(req, q):
    c = db()
    out = []
    for cu in c.execute("SELECT * FROM customer ORDER BY kunnr").fetchall():
        exp = ar.credit_exposure(c, cu["kunnr"])
        out.append(dict(kunnr=cu["kunnr"], name=cu["name"], klimk=amt_out(cu["klimk"] or 0),
                        exposure=amt_out(exp), free=amt_out((cu["klimk"] or 0) - exp),
                        used=round(exp / cu["klimk"] * 100, 1) if cu["klimk"] else None,
                        zterm=cu["zterm"]))
    return out


# ====================================================================== assets
@route("POST", "/api/fi/as01")
def fi_as01(req, q):
    b = req.body
    n = aa.create_asset(db(), b.get("anlkl"), b.get("txt"), (b.get("kostl") or "").upper(),
                        b.get("ndjar") or None, b.get("invnr") or "", req.user)
    return {"anln1": n, "message": "Asset %s 0 has been created" % n}


@route("POST", "/api/fi/acquire")
def fi_acquire(req, q):
    b = req.body
    belnr = aa.acquire(db(), b.get("anln1"), b.get("budat"), b.get("amount"), req.user,
                       (b.get("lifnr") or "").upper() or None, b.get("mwskz") or "V1",
                       b.get("bldat"), b.get("xblnr") or "", b.get("text") or "")
    return {"belnr": belnr, "message": "Asset acquisition posted: document %s" % belnr}


@route("POST", "/api/fi/afab")
def fi_afab(req, q):
    b = req.body
    r = aa.depreciation_run(db(), b.get("gjahr"), b.get("perio"), req.user,
                            bool(b.get("test")))
    for x in r["lines"]:
        _cents(x, ("planned", "posted", "amount"))
    r["total"] = amt_out(r["total"])
    r["message"] = ("Test run: " if r["test"] else "Posted document %s: " % (r["belnr"] or
                                                                            "-")) + \
        "%d asset(s), depreciation %.2f" % (len(r["lines"]), r["total"])
    return r


@route("POST", "/api/fi/retire")
def fi_retire(req, q):
    b = req.body
    r = aa.retire(db(), b.get("anln1"), b.get("budat"), req.user, b.get("revenue") or None,
                  (b.get("kunnr") or "").upper() or None, b.get("mwskz") or "A1",
                  b.get("text") or "")
    return {"belnr": r["belnr"], "message": "Retirement posted: document %s, book value "
            "%.2f, result %.2f" % (r["belnr"], r["nbv"] / 100.0, r["result"] / 100.0)}


@route("GET", "/api/fi/aw01n")
def fi_aw01n(req, q):
    y, _ = _yp(q)
    e = aa.explorer(db(), q.get("anln1"), parse_int(q.get("gjahr"), "gjahr", default=y))
    _cents(e, ("apc_start", "acquisitions", "retirements", "apc_end", "dep_start",
               "dep_year", "dep_retired", "dep_end", "planned_year", "nbv_start", "nbv_end"))
    for i in e["items"]:
        _cents(i, ("apc", "dep"))
    for p in e["periods"]:
        _cents(p, ("planned", "posted"))
    return e


@route("GET", "/api/fi/ar01")
def fi_ar01(req, q):
    return reports.asset_list(db(), q.get("upto") or None)


@route("GET", "/api/fi/assethistory")
def fi_hist(req, q):
    y, _ = _yp(q)
    out = aa.history_sheet(db(), parse_int(q.get("gjahr"), "gjahr", default=y))
    for r in out:
        _cents(r, [k for k in r if k not in ("anlkl", "txt", "count")])
    return out


# ====================================================================== reports
@route("GET", "/api/fi/fs10n")
def fi_fs10n(req, q):
    y, _ = _yp(q)
    return reports.account_balance(db(), q.get("hkont") or "113100", parse_int(q.get("gjahr"), "gjahr", default=y))


@route("GET", "/api/fi/fbl")
def fi_fbl(req, q):
    out = reports.line_items(db(), q.get("koart") or "S", (q.get("key") or "").upper(),
                             q.get("status") or "open", q.get("key_date") or None,
                             q.get("d1") or None, q.get("d2") or None)
    for r in out:
        for k in ("dmbtr", "wrbtr", "txbase"):
            r.pop(k, None)
        r["menge"] = qty_out(r["menge"]) if r.get("menge") else None
        r["zbd1p"] = (r["zbd1p"] or 0) / 100.0
    return out


@route("GET", "/api/fi/tb")
def fi_tb(req, q):
    y, p = _yp(q)
    return reports.trial_balance(db(), y, parse_int(q.get("pfrom"), "pfrom", default=1), parse_int(q.get("pto"), "pto", default=p))


@route("GET", "/api/fi/fs")
def fi_fs(req, q):
    y, p = _yp(q)
    return reports.statements(db(), y, parse_int(q.get("pfrom"), "pfrom", default=p), parse_int(q.get("pto"), "pto", default=p))


@route("GET", "/api/fi/partners")
def fi_partners(req, q):
    y, _ = _yp(q)
    return reports.partner_balances(db(), q.get("koart") or "K", y)


@route("GET", "/api/fi/aging")
def fi_aging(req, q):
    y, p = _yp(q)
    return reports.aging(db(), q.get("koart") or "D", q.get("key_date") or reports.eop(y, p))


@route("GET", "/api/fi/cash")
def fi_cash(req, q):
    y, p = _yp(q)
    return reports.cash_position(db(), q.get("key_date") or reports.eop(y, p),
                                 parse_int(q.get("weeks"), "weeks", default=8))


@route("GET", "/api/fi/cockpit")
def fi_cockpit(req, q):
    y, p = _yp(q)
    return reports.cockpit(db(), y, p)


@route("GET", "/api/fi/closing")
def fi_closing(req, q):
    """FI closing cockpit status for the period."""
    y, p = _yp(q)
    c = db()
    d1, d2 = "%04d-%02d-01" % (y, p), reports.eop(y, p)

    def cnt(where, *a):
        return c.execute("SELECT COUNT(*) FROM acc_doc WHERE budat BETWEEN ? AND ? AND "
                         + where, (d1, d2) + a).fetchone()[0]
    st = reports.statements(c, y, p, p)
    grir_open = c.execute("SELECT COUNT(DISTINCT zuonr) FROM acc_doc_item i JOIN acc_doc h "
                          "USING (belnr, gjahr) WHERE i.hkont='191100' AND i.augbl IS NULL "
                          "AND h.budat<=?", (d2,)).fetchone()[0]
    from co.reports import reconcile
    return {
        "gjahr": y, "perio": p,
        "fb60": cnt("tcode IN ('FB60','FB65')"), "miro": cnt("tcode='MIRO'"),
        "billing": cnt("blart='RV'"), "payments": cnt("blart IN ('KZ','ZP','DZ')"),
        "f110": cnt("tcode='F110'"), "afab": cnt("tcode='AFAB'"),
        "assets": cnt("tcode IN ('F-90','ABZON','ABAVN','F-92')"),
        "ff67": cnt("tcode='FF67'"), "fbs1": cnt("tcode='FBS1'"),
        "fcv": cnt("tcode='FAGL_FCV'"),
        "f13": c.execute("SELECT COUNT(*) FROM grir_run WHERE budat BETWEEN ? AND ?", (d1, d2)).fetchone()[0],
        "fb41": cnt("tcode='FB41'"),
        "f150": c.execute("SELECT COUNT(*) FROM dunning_run WHERE ausdt BETWEEN ? AND ?",
                          (d1, d2)).fetchone()[0],
        "grir_open": grir_open, "balanced": st["balanced"],
        "result": st["result"], "co_recon": reconcile(c, y, p, p)["ok"],
        "period": dict(c.execute("SELECT * FROM posting_period WHERE id=1").fetchone()
                       or {}),
        "today_open": __import__("fi.document", fromlist=["x"]).period_open(c, mmclock.today().isoformat()),
        "carry_forward_missing": reports.retained_earnings(c, y)[1],
        "blocked_invoices": len(ap.blocked_invoices(c)),
    }
