"""JSON API for master data (material, customer, vendor, CIN, Exim, governance)."""
from md import changes, checks, config as C, material as mat, partner as bp, reports
from mm.db import rows
from mm.util import MMError, amt_out, qty_out

from .server import db, route

AMT = {"verpr", "stprs", "salk3", "price", "zplp1", "bwprh", "bwph1", "kbetr", "klimk",
       "minbw", "open_balance", "balance", "sales_volume", "po_volume", "value", "netwr",
       "netpr", "dead_value", "held", "exposure", "ce_total", "old_price", "new_price", "dmbtr", "amount"}
QTY = {"ce_losgr", "minbe", "eisbe", "mabst", "bstfe", "losgr", "lbkum", "stock", "aumng", "lhmg1",
       "brgew", "ntgew", "volum", "menge", "wemng", "open", "qty"}
PCT = {"uebto", "untto", "duty", "gst"}


def out(o):
    """Convert internal integers (cents / milli / basis points) for the UI."""
    if isinstance(o, list):
        return [out(x) for x in o]
    if isinstance(o, dict):
        r = {}
        for k, v in o.items():
            if isinstance(v, (dict, list)):
                r[k] = out(v)
            elif isinstance(v, int) and not isinstance(v, bool):
                r[k] = amt_out(v) if k in AMT else qty_out(v) if k in QTY else \
                    v / 100.0 if k in PCT else v
            else:
                r[k] = v
        return r
    return o


@route("GET", "/api/md/meta")
def md_meta(req, q):
    c = db()
    from pur.config import PURCH_GROUPS
    from fi.config import PAYMENT_TERMS, CURRENCIES
    return {
        "types": {k: dict(v, bklas=v["bklas"]) for k, v in C.MATERIAL_TYPE_ATTR.items()},
        "views": C.VIEWS, "view_order": C.VIEW_ORDER, "valclasses": C.VALUATION_CLASSES,
        "sectors": C.INDUSTRY_SECTORS, "groups": C.MATERIAL_GROUPS, "divisions": C.DIVISIONS,
        "itemcat": C.ITEM_CAT_GROUPS, "status": {k: list(v) for k, v in C.MATERIAL_STATUS.items()},
        "sales_status": {k: v[0] for k, v in C.SALES_STATUS.items()},
        "mrp_ctrl": C.MRP_CONTROLLERS, "proc_types": C.PROCUREMENT_TYPES,
        "avail": C.AVAIL_CHECK, "storage": C.STORAGE_COND, "prctr": C.PROFIT_CENTERS,
        "variance": C.VARIANCE_KEYS, "qm": C.QM_CONTROL, "units": C.UNITS_EXT,
        "sorgs": C.SALES_ORGS, "channels": C.DISTR_CHANNELS, "ktgrm": C.ACCT_ASSIGN_MAT,
        "ktgrd": C.ACCT_ASSIGN_CUST, "taxcl": C.TAX_CLASS, "shipping": C.SHIPPING_COND,
        "incoterms": C.INCOTERMS, "pricing": C.PRICING_PROC, "pricegroups": C.PRICE_GROUPS,
        "districts": C.SALES_DISTRICTS, "custgroups": C.CUSTOMER_GROUPS,
        "dunning": C.DUNNING_PROC, "paymeth": C.PAYMENT_METHODS, "partners": C.PARTNER_FUNCTIONS,
        "cust_groups": C.CUST_GROUPS, "vend_groups": C.VEND_GROUPS,
        "sens_vendor": C.SENSITIVE_VENDOR, "sens_customer": C.SENSITIVE_CUSTOMER,
        "chapters": {k: list(v) for k, v in C.CHAPTER_IDS.items()}, "cin_mtypes": C.CIN_MAT_TYPES,
        "cin_vtypes": C.CIN_VENDOR_TYPES, "ssi": C.SSI_STATUS, "br_usage": C.BR_USAGE,
        "br_origin": C.BR_ORIGIN, "exim": C.EXIM_CONTROL, "countries": C.COUNTRIES,
        "purch_groups": PURCH_GROUPS, "terms": {k: v[0] for k, v in PAYMENT_TERMS.items()},
        "currencies": CURRENCIES,
        "recon": rows(c.execute("SELECT hkont, txt, recon FROM gl_account WHERE recon IN "
                                "('D','K') ORDER BY hkont")),
        "plants": rows(c.execute("SELECT werks, name FROM plant ORDER BY werks")),
        "slocs": rows(c.execute("SELECT werks, lgort, name FROM sloc ORDER BY werks, lgort")),
        "materials": rows(c.execute("SELECT matnr, maktx, mtart FROM material ORDER BY matnr")),
        "customers": rows(c.execute("SELECT kunnr, name, ktokd FROM customer ORDER BY kunnr")),
        "vendors": rows(c.execute("SELECT lifnr, name, ktokk, land FROM vendor ORDER BY lifnr")),
    }


# ====================================================================== material
@route("GET", "/api/md/material/(?P<matnr>[^/]+)")
def md_material(req, q, matnr):
    c = db()
    m = mat.get_material(c, matnr)
    k = m["matnr"]
    for p in m["plants"]:
        ce = p.pop("cost_estimate", None)
        if ce:
            p["ce_total"], p["ce_status"], p["ce_date"], p["ce_losgr"] = (
                ce["total"], ce["status"], ce["kadky"], ce["losgr"])
    if q.get("full"):
        m["changes"] = changes.changes(c, "MATERIAL", k)[:100]
        m["open_po"] = rows(c.execute(
            "SELECT h.ebeln, i.ebelp, h.lifnr, v.name, i.werks, i.menge, i.wemng, "
            "i.menge-i.wemng AS open, i.netpr, i.eindt FROM po_item i JOIN po_header h USING "
            "(ebeln) LEFT JOIN vendor v ON v.lifnr=h.lifnr WHERE i.matnr=? AND i.elikz=0 AND "
            "i.wemng<i.menge AND COALESCE(i.loekz,0)=0 ORDER BY h.ebeln", (k,)))
        m["movements"] = rows(c.execute(
            "SELECT substr(h.budat,1,7) AS month, SUM(CASE WHEN i.shkzg='S' THEN i.menge ELSE 0 END) "
            "AS rec, SUM(CASE WHEN i.shkzg='H' THEN i.menge ELSE 0 END) AS iss, "
            "SUM(CASE WHEN i.bwart IN ('201','261','601') THEN i.menge ELSE 0 END) AS cons "
            "FROM mat_doc_item i JOIN mat_doc h ON h.mblnr=i.mblnr AND h.mjahr=i.mjahr WHERE "
            "i.matnr=? GROUP BY month ORDER BY month", (k,)))
        for r in m["movements"]:
            for f in ("rec", "iss", "cons"):
                r[f] = qty_out(r[f] or 0)
        m["prices"] = rows(c.execute("SELECT bwkey, budat, ref, reason, old_price, new_price, "
                                     "peinh FROM price_history WHERE matnr=? ORDER BY id DESC "
                                     "LIMIT 30", (k,)))
        m["sales_docs"] = rows(c.execute(
            "SELECT b.vbeln, b.fkdat, b.kunnr, i.fkimg AS qty, i.net AS value FROM billing_item i "
            "JOIN billing b USING (vbeln) WHERE i.matnr=? AND b.cancelled=0 ORDER BY b.vbeln DESC "
            "LIMIT 20", (k,)))
        for r in m["sales_docs"]:
            r["qty"] = qty_out(r["qty"])
        from mm.config import gl_for
        m["accounts"] = []
        for key, txt in (("BSX", "Stock account"), ("WRX", "GR/IR clearing"),
                         ("PRD", "Price differences"), ("VBR", "Consumption"),
                         ("VAX", "Cost of goods sold"), ("UMB", "Revaluation gain/loss")):
            try:
                m["accounts"].append(dict(key=key, text=txt, hkont=gl_for(key, m["bklas"])))
            except MMError:
                pass
    return out(m)


@route("POST", "/api/md/material")
def md_material_create(req, q):
    b = req.body
    c = db()
    if b.get("matnr") and c.execute("SELECT 1 FROM material WHERE matnr=?",
                                     (b["matnr"].strip().upper(),)).fetchone():
        k = mat.extend_material(c, b["matnr"], b, req.user)
        return {"matnr": k, "message": "Material %s extended" % k}
    k = mat.create_material(c, b, req.user)
    return {"matnr": k, "message": "Material %s created" % k}


@route("POST", "/api/md/material/(?P<matnr>[^/]+)/change")
def md_material_change(req, q, matnr):
    r = mat.change_material(db(), matnr, req.body, req.user, req.body.get("tcode") or "MM02")
    return dict(r, message="Material %s changed (%d field%s)" % (
        r["matnr"], r["changed"], "" if r["changed"] == 1 else "s") if r["changed"]
        else "No data was changed")


@route("POST", "/api/md/material/(?P<matnr>[^/]+)/delete")
def md_material_delete(req, q, matnr):
    b = req.body
    r = mat.flag_deletion(db(), matnr, req.user, b.get("werks") or None, bool(b.get("flag", True)))
    return dict(r, message="Deletion flag %s for material %s%s" % (
        "set" if b.get("flag", True) else "removed", r["matnr"],
        " plant " + b["werks"] if b.get("werks") else " (all plants)"))


@route("POST", "/api/md/material/(?P<matnr>[^/]+)/cin")
def md_material_cin(req, q, matnr):
    b = req.body
    mat.save_cin_material(db(), matnr, b.get("werks") or "1000", b.get("chapid"),
                          (b.get("mtype") or "").upper(), req.user, b.get("subcon"))
    return {"message": "Material/chapter ID combination saved"}


@route("POST", "/api/md/material/(?P<matnr>[^/]+)/brazil")
def md_material_br(req, q, matnr):
    b = req.body
    mat.save_br_material(db(), matnr, b.get("werks") or "1000", b.get("steuc"), b.get("mtuse"),
                         b.get("mtorg"), req.user, b.get("cfop_cat") or "")
    return {"message": "Brazilian tax data saved"}


@route("GET", "/api/md/mm60")
def md_mm60(req, q):
    return out(mat.mm60(db(), q.get("mtart", ""), q.get("matkl", ""), q.get("werks", ""),
                        q.get("q", "")))


@route("GET", "/api/md/mm50")
def md_mm50(req, q):
    return mat.mm50(db())


@route("GET", "/api/md/exim")
def md_exim(req, q):
    return out(rows(db().execute(
        "SELECT m.matnr, m.maktx, m.mtart, e.stawn, e.herkl, e.herkr, e.impctl, e.expctl, "
        "e.lic_no, e.lic_valid, e.duty, e.prefz FROM material m LEFT JOIN md_exim e ON "
        "e.matnr=m.matnr ORDER BY m.matnr")))


@route("GET", "/api/md/changes")
def md_changes(req, q):
    return changes.changes(db(), q.get("obj") or None, (q.get("id") or "").upper() or None,
                           q.get("d1") or None, q.get("d2") or None, q.get("user") or None)


# ====================================================================== partners
@route("GET", "/api/md/customers")
def md_customers(req, q):
    return out(bp.customers(db(), q.get("ktokd", ""), q.get("land", ""),
                            q.get("blocked") == "1"))


@route("GET", "/api/md/customer/(?P<kunnr>[^/]+)")
def md_customer(req, q, kunnr):
    c = bp.get_customer(db(), kunnr)
    c["changes"] = changes.changes(db(), "DEBI", c["kunnr"])[:60]
    from fi.ar import credit_exposure
    c["exposure"] = credit_exposure(db(), c["kunnr"])
    return out(c)


@route("POST", "/api/md/customer")
def md_customer_create(req, q):
    tc = req.body.get("tcode") or "XD01"
    r = bp.create_customer(db(), req.body, req.user, tc)
    return dict(r, message="Customer %s has been created for company code 1000%s" % (
        r["kunnr"], " / sales area" if req.body.get("sales") else ""))


@route("POST", "/api/md/customer/(?P<kunnr>[^/]+)/(?P<act>change|block|delete|group|cin)")
def md_customer_act(req, q, kunnr, act):
    b, c, u = req.body, db(), req.user
    if act == "change":
        r = bp.change_customer(c, kunnr, b, u, b.get("tcode") or "XD02")
        m = "Changes have been made" if r["changed"] else "No data was changed"
        if r["sensitive"]:
            m += " - sensitive fields changed, confirmation required (FD08)"
        return dict(r, message=m)
    if act == "block":
        bp.block_customer(c, kunnr, u, b.get("sperr"), b.get("aufsd"), b.get("lifsd"),
                          b.get("faksd"))
        return {"message": "Blocking data saved for customer %s" % kunnr.upper()}
    if act == "delete":
        r = bp.flag_customer(c, kunnr, u, bool(b.get("flag", True)))
        return out(dict(r, message="Deletion flag saved for customer %s" % kunnr.upper()))
    if act == "group":
        bp.change_customer_group(c, kunnr, b.get("ktokd") or "", u)
        return {"message": "Account group changed"}
    bp.save_cin_customer(c, kunnr, b, u)
    return {"message": "Customer excise / GST details saved"}


@route("GET", "/api/md/vendors")
def md_vendors(req, q):
    return out(bp.vendors(db(), q.get("ktokk", ""), q.get("land", ""), q.get("blocked") == "1"))


@route("GET", "/api/md/vendor/(?P<lifnr>[^/]+)")
def md_vendor(req, q, lifnr):
    v = bp.get_vendor(db(), lifnr)
    v["changes"] = changes.changes(db(), "KRED", v["lifnr"])[:60]
    try:
        from pur.analytics import vendor_evaluation
        v["evaluation"] = next((e for e in vendor_evaluation(db()) if e["lifnr"] == v["lifnr"]),
                               None)
    except Exception:
        v["evaluation"] = None
    return out(v)


@route("POST", "/api/md/vendor")
def md_vendor_create(req, q):
    tc = req.body.get("tcode") or "XK01"
    r = bp.create_vendor(db(), req.body, req.user, tc)
    return dict(r, message="Vendor %s has been created for company code 1000 / purch. org. "
                "1000" % r["lifnr"])


@route("POST", "/api/md/vendor/(?P<lifnr>[^/]+)/(?P<act>change|block|delete|group|cin)")
def md_vendor_act(req, q, lifnr, act):
    b, c, u = req.body, db(), req.user
    if act == "change":
        r = bp.change_vendor(c, lifnr, b, u, b.get("tcode") or "XK02")
        m = "Changes have been made" if r["changed"] else "No data was changed"
        if r["sensitive"]:
            m += " - sensitive fields changed: payment blocked until confirmed (FK08)"
        return dict(r, message=m)
    if act == "block":
        r = bp.block_vendor(c, lifnr, u, b.get("sperr"), b.get("sperm"), b.get("zahls"))
        return out(dict(r, message="Blocking data saved for vendor %s" % lifnr.upper()))
    if act == "delete":
        r = bp.flag_vendor(c, lifnr, u, bool(b.get("flag", True)))
        return out(dict(r, message="Deletion flag saved for vendor %s" % lifnr.upper()))
    if act == "group":
        bp.change_vendor_group(c, lifnr, b.get("ktokk") or "", u)
        return {"message": "Account group changed"}
    bp.save_cin_vendor(c, lifnr, b, u)
    return {"message": "Vendor excise / GST details saved"}


@route("GET", "/api/md/sensitive")
def md_sensitive(req, q):
    return out(bp.sensitive_list(db(), q.get("koart") or None,
                                 None if q.get("status") == "all" else "P"))


@route("POST", "/api/md/sensitive/confirm")
def md_sensitive_confirm(req, q):
    b = req.body
    r = bp.confirm_sensitive(db(), b.get("koart"), (b.get("id") or "").upper(), req.user,
                             bool(b.get("reject")))
    return dict(r, message="Changes %s" % ("rejected - old values restored" if b.get("reject")
                                           else "confirmed - payment block released"))


@route("GET", "/api/md/ranges")
def md_ranges(req, q):
    return bp.number_ranges(db())


@route("GET", "/api/md/cin")
def md_cin(req, q):
    c = db()
    return out({
        "materials": rows(c.execute("SELECT x.*, m.maktx FROM md_cin_mat x JOIN material m USING "
                                    "(matnr) ORDER BY matnr")),
        "customers": rows(c.execute("SELECT x.*, c.name, c.city FROM md_cin_cust x JOIN customer c "
                                    "USING (kunnr) ORDER BY kunnr")),
        "vendors": rows(c.execute("SELECT x.*, v.name, v.city FROM md_cin_vend x JOIN vendor v "
                                  "USING (lifnr) ORDER BY lifnr")),
        "brazil": rows(c.execute("SELECT x.*, m.maktx FROM md_br_mat x JOIN material m USING "
                                 "(matnr) ORDER BY matnr")),
    })


@route("GET", "/api/md/cockpit")
def md_cockpit(req, q):
    return out(reports.cockpit(db(), int(q.get("days") or 60)))


@route("GET", "/api/md/check")
def md_check(req, q):
    """Preview of the status checks for a material (used by the screens)."""
    w = []
    res = {}
    for area in ("purch", "inv", "sales"):
        try:
            checks.material(db(), (q.get("matnr") or "").upper(), q.get("werks") or "1000",
                            area, w)
            res[area] = "OK"
        except MMError as e:
            res[area] = str(e)
    return {"result": res, "warnings": w}
