"""API of the go-live functions: physical inventory (MI01..MI07, MICN), MM periods
(MMPV / MMRV) and MB5B, print forms, data import (ZIMPORT), withholding tax,
manual clearing (F-44 / F-32 / F-03) and down payments (F-47 .. F-39)."""
from fi import clearing, wht
from mm import dataimport, forms, inventory, periods
from mm.util import MMError, amt_out, parse_int, qty_out, require

from web.server import db, route


def _keys(items):
    out = []
    for k in items or []:
        if isinstance(k, dict):
            k = (k.get("belnr"), k.get("gjahr"), k.get("buzei"))
        if not k or len(k) != 3:
            raise MMError("Select open items (document / year / line)", "F5", "260")
        out.append((str(k[0]), parse_int(k[1], "year"), parse_int(k[2], "line")))
    return out


# ------------------------------------------------------------------ physical inventory
def _inv_out(d):
    for i in d.get("items", []):
        i["buchm_o"], i["diff_o"] = qty_out(i["buchm"]), qty_out(i["diff_qty"])
        i["menge_o"] = qty_out(i["menge"]) if i["menge"] is not None else None
        if "diff_value" in i:
            i["diff_value_o"] = amt_out(i["diff_value"])
    if "total" in d:
        d["total_o"] = amt_out(d["total"])
    return d


@route("POST", "/api/mi/create")
def mi_create(req, q):
    b = req.body
    require(b, "werks", "lgort")
    mats = b.get("matnrs") or []
    if isinstance(mats, str):
        mats = [m for m in mats.replace(",", " ").split() if m]
    n = inventory.create(db(), b["werks"], b["lgort"], mats, b.get("date"), req.user, b.get("freeze", True) is not False)
    return {"iblnr": n, "message": "Physical inventory document %s created" % n}


@route("GET", "/api/mi/docs")
def mi_docs(req, q):
    return inventory.documents(db(), q.get("werks") or None, q.get("status") or None)


@route("GET", "/api/mi/doc/(?P<iblnr>[0-9]+)")
def mi_doc(req, q, iblnr):
    c = db()
    if q.get("diff"):
        th = parse_int(q.get("threshold"), "threshold", 0, default=0) * 100
        return _inv_out(inventory.differences(c, iblnr, th or None))
    return _inv_out(inventory.display(c, iblnr))


@route("POST", "/api/mi/count")
def mi_count(req, q):
    require(req.body, "iblnr")
    left = inventory.count(db(), req.body["iblnr"], req.body.get("items") or [], req.user, req.body.get("date"))
    return {"message": "Count entered" + (" - %d item(s) still to count" % left if left else " - document counted")}


@route("POST", "/api/mi/recount")
def mi_recount(req, q):
    require(req.body, "iblnr")
    n = inventory.recount(db(), req.body["iblnr"], req.body.get("zeilis") or [], req.user)
    return {"iblnr": n, "message": "Recount document %s created" % n}


@route("POST", "/api/mi/post")
def mi_post(req, q):
    require(req.body, "iblnr")
    return inventory.post(db(), req.body["iblnr"], req.body.get("budat"), req.user, req.body.get("reason") or "")


@route("POST", "/api/mi/delete")
def mi_delete(req, q):
    require(req.body, "iblnr")
    inventory.delete(db(), req.body["iblnr"], req.user)
    return {"message": "Document %s deleted - posting block removed" % req.body["iblnr"]}


@route("GET", "/api/mi/cycle")
def mi_cycle(req, q):
    out = inventory.cycle_proposal(db(), q.get("werks") or "1000")
    for r in out:
        r["qty"] = qty_out(r["qty"])
    return out


# ------------------------------------------------------------------ MM periods, MB5B
@route("GET", "/api/mmpv")
def mmpv_get(req, q):
    c = db()
    return {"current": periods.current(c), "history": periods.history(c)[:200]}


@route("POST", "/api/mmpv")
def mmpv_open(req, q):
    b = req.body
    return periods.open_next(db(), parse_int(b.get("gjahr"), "year", 2000, 2100),
                             parse_int(b.get("perio"), "period", 1, 12), req.user, b.get("prev_open", True) is not False)


@route("POST", "/api/mmrv")
def mmrv_close(req, q):
    periods.close_previous(db(), req.user)
    return {"message": "Previous MM period closed - only the current period is open"}


@route("GET", "/api/mb5b")
def mb5b(req, q):
    out = periods.stock_at(db(), q.get("werks") or "1000", q.get("date"), q.get("matnr") or None)
    for r in out:
        r["qty"], r["value"] = qty_out(r["qty"]), amt_out(r["value"])
    return out


# ------------------------------------------------------------------ forms
@route("GET", "/api/forms/(?P<form>[A-Za-z]+)/(?P<key>[^/]+)")
def form_render(req, q, form, key):
    return {"html": forms.render(db(), form, key), "outputs": forms.outputs(db(), form, key)}


@route("POST", "/api/forms/log")
def form_log(req, q):
    require(req.body, "form", "key")
    forms.log_output(db(), req.body["form"], req.body["key"], req.body.get("medium") or "PRINT", req.user)
    return {"message": "Output %s of %s %s logged" % ((req.body.get("medium") or "PRINT").lower(),
                                                     req.body["form"], req.body["key"])}


@route("GET", "/api/forms")
def form_list(req, q):
    return {"forms": forms.FORMS, "log": forms.outputs(db(), q.get("form") or None, q.get("key") or None)}


# ------------------------------------------------------------------ data import
@route("GET", "/api/import/objects")
def imp_objects(req, q):
    return {"objects": dataimport.objects(), "takeover": amt_out(dataimport.takeover_balance(db()))}


@route("GET", "/api/import/template/(?P<obj>[A-Za-z_]+)")
def imp_template(req, q, obj):
    return {"csv": dataimport.template(obj)}


@route("POST", "/api/import/run")
def imp_run(req, q):
    require(req.body, "obj", "text")
    return dataimport.run(db(), req.body["obj"], req.body["text"], req.user, req.body.get("simulate", True) is not False)


def _xlsx_body(b):
    import base64
    import binascii
    try:
        data = base64.b64decode(b.get("xlsx") or "", validate=True)
    except (binascii.Error, ValueError):
        raise MMError("The Excel file could not be read - choose it again", "ZI", "008")
    if not data:
        raise MMError("Choose the Excel file", "ZI", "002")
    if len(data) > 30 * 1024 * 1024:
        raise MMError("The Excel file is larger than 30 MB - split it", "ZI", "009")
    return data


@route("POST", "/api/import/xlsx")
def imp_xlsx(req, q):
    """the Excel workbook: all MM Core sheets in the loading order (obj = ALL) or one object"""
    b = req.body
    only = (b.get("obj") or "ALL").upper()
    return dataimport.run_xlsx(db(), _xlsx_body(b), req.user, b.get("simulate", True) is not False,
                               None if only == "ALL" else only)


@route("POST", "/api/import/verify")
def imp_verify(req, q):
    """compare the file with MM Core field by field (after the upload)"""
    b = req.body
    if b.get("xlsx"):
        only = (b.get("obj") or "ALL").upper()
        return dataimport.verify_xlsx(db(), _xlsx_body(b), None if only == "ALL" else only)
    require(b, "obj", "text")
    return dataimport.verify(db(), b["obj"], b["text"])


@route("GET", "/api/import/workbook/(?P<area>[A-Za-z]+)")
def imp_workbook(req, q, area):
    """Excel template of a business area (PUR = purchasing); example=1 with sample data"""
    import base64
    from mm import templates
    if area.upper() != "PUR":
        raise MMError("Templates exist for: PUR (purchasing)", "ZI", "030")
    ex = q.get("example") in ("1", "true", "X")
    data = templates.purchasing_workbook(example=ex)
    return {"name": "MM_Core_Purchasing_%s.xlsx" % ("EXAMPLE" if ex else "Template"),
            "xlsx": base64.b64encode(data).decode("ascii")}


# ------------------------------------------------------------------ withholding tax
@route("GET", "/api/fi/wht")
def fi_wht(req, q):
    c = db()
    out = {"codes": wht.codes(c)}
    if q.get("lifnr"):
        out["vendor"] = wht.vendor_codes(c, q["lifnr"].upper())
    return out


@route("POST", "/api/fi/wht/assign")
def fi_wht_assign(req, q):
    b = req.body
    require(b, "lifnr", "code")
    wht.assign(db(), b["lifnr"], b["code"], b.get("exempt_from"), b.get("exempt_to"), b.get("certificate_no"),
               bool(b.get("delete")))
    return {"message": "Withholding tax %s %s for vendor %s" % (b["code"].upper(), "removed" if b.get("delete")
                                                                else "saved", b["lifnr"].upper())}


@route("GET", "/api/fi/wht/report")
def fi_wht_report(req, q):
    out = wht.report(db(), q.get("d1") or None, q.get("d2") or None, q.get("lifnr") or None)
    for r in out:
        r["base"], r["amount"] = amt_out(r["base"]), amt_out(r["amount"])
    return out


# ------------------------------------------------------------------ manual clearing, down payments
@route("POST", "/api/fi/clear")
def fi_clear(req, q):
    b = req.body
    require(b, "koart", "partner")
    return clearing.clear_open_items(db(), b["koart"], b["partner"], _keys(b.get("items")), b.get("budat"),
                                     req.user, bool(b.get("residual")))


@route("GET", "/api/fi/openitems")
def fi_openitems(req, q):
    from fi.ap import open_items
    from fi.document import signed
    koart = (q.get("koart") or "K").upper()
    if koart not in ("K", "D", "S"):
        raise MMError("Account type must be K, D or S", "F5", "100")
    partner = (q.get("partner") or "").upper()
    if not partner:
        raise MMError("Enter the vendor, customer or G/L account", "F5", "260")
    sp = q.get("special")
    rows_ = open_items(db(), koart, None if koart == "S" else partner, hkont=partner if koart == "S" else None,
                       special=True if sp == "all" else ("A" if sp == "A" else False))
    return [dict(belnr=r["belnr"], gjahr=r["gjahr"], buzei=r["buzei"], budat=r["budat"], xblnr=r["xblnr"],
                 umskz=r["umskz"] or "", sgtxt=r["sgtxt"], amount=amt_out(signed(r)), zlspr=r["zlspr"] or "")
            for r in rows_]


@route("POST", "/api/fi/dp/request")
def fi_dp_request(req, q):
    b = req.body
    require(b, "koart", "partner", "amount")
    n = clearing.request(db(), b["koart"], b["partner"], b["amount"], b.get("due"), req.user, b.get("ebeln"),
                         b.get("text"))
    return {"id": n, "message": "Down-payment request %s saved (noted item)" % n}


@route("GET", "/api/fi/dp/requests")
def fi_dp_requests(req, q):
    out = clearing.requests(db(), (q.get("koart") or "").upper() or None, q.get("status", "O") or None)
    for r in out:
        r["amount"] = amt_out(r["amount"])
    return out


@route("POST", "/api/fi/dp/post")
def fi_dp_post(req, q):
    b = req.body
    require(b, "koart", "partner")
    return clearing.down_payment(db(), b["koart"], b["partner"], b.get("amount"), b.get("budat"), req.user,
                                 b.get("bank") or "113100", b.get("request_id") or None, b.get("text"))


@route("POST", "/api/fi/dp/clear")
def fi_dp_clear(req, q):
    b = req.body
    require(b, "koart", "partner", "dp", "invoice")
    k = _keys([b["dp"], b["invoice"]])
    return clearing.clear_down_payment(db(), b["koart"], b["partner"], k[0], k[1], b.get("budat"), req.user)
