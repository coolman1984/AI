"""ZIMPORT - data import for go-live (LSMW-like).

A file is read for one object - a CSV file (UTF-8, comma or semicolon, Arabic text
allowed) or a sheet of the Excel workbook (.xlsx) - or the whole Excel workbook at once:
its sheets are loaded in the order of OBJECTS (plants before materials, vendors before
info records and purchase orders ...). Every line goes through the normal engine function
(all checks, number ranges, change documents - no direct SQL). "Simulate" runs everything
and rolls back; "Post" keeps the good lines. Each line runs in its own savepoint, so one
bad line does not stop the file; the log shows sheet, line, status and message.

verify() compares a file with what is in the system field by field (after the upload,
to prove that the data in MM Core is the data of the file) and gives control totals.

Nested views use dotted column names: plant.werks, plant.price, sloc.lgort (material);
sales.vkorg, sales.vtweg (customer / material). Open items, G/L balances and stock are
posted against the data takeover account 399999, which must be zero when the load is
complete (shown by takeover_balance()). Purchase orders: one line per item, the lines of
one order share the legacy order number (po_no); vendors can be given with their legacy
number (altkn) in every later sheet.
"""
import csv
import io

from mm.db import transaction
from mm.util import MMError

TAKEOVER = "399999"
DATE_COLS = {"budat", "bldat", "bedat", "eindt", "aktiv", "takeover"}
PAD = {"werks": 4, "plant.werks": 4, "lgort": 4, "sloc.lgort": 4, "ktokk": 4, "ekgrp": 3, "plant.ekgrp": 3,
       "spart": 2, "zterm": 4, "kosar": 0}


class _Rollback(Exception):
    pass


def _clean(row):
    """trim values, Excel dates -> YYYY-MM-DD, codes that lost their leading zeros in Excel (1 -> 0001)"""
    from mm.xlsx import excel_date
    out = {}
    for k, v in row.items():
        if k is None or isinstance(v, list):      # extra separators at the end of a CSV line
            continue
        k = k.strip()
        v = ("" if v is None else str(v)).strip()
        if not k or v == "":
            continue
        if k in DATE_COLS:
            v = excel_date(v)
        n = PAD.get(k)
        if n and v.isdigit() and len(v) < n:
            v = v.zfill(n)
        out[k] = v
    return out


def _nest(row):
    """plant.x / sloc.x / sales.x columns -> nested single-entry lists."""
    data, plant, sloc, sales = {}, {}, {}, {}
    for k, v in _clean(row).items():
        if k.startswith("plant."):
            plant[k[6:]] = v
        elif k.startswith("sloc."):
            sloc[k[5:]] = v
        elif k.startswith("sales."):
            sales[k[6:]] = v
        else:
            data[k] = v
    if sloc:
        plant["slocs"] = [sloc]
    if plant:
        data["plants"] = [plant]
    if sales:
        data["sales"] = [sales]
    return data


def vendor_no(conn, v):
    """vendor number in MM Core, or the legacy vendor number (altkn) of the old system"""
    v = (v or "").strip().upper()
    if not v:
        raise MMError("Enter the vendor (number in MM Core or the old vendor number)", "ZI", "010")
    if conn.execute("SELECT 1 FROM vendor WHERE lifnr=?", (v,)).fetchone():
        return v
    r = conn.execute("SELECT lifnr FROM vendor WHERE UPPER(altkn)=?", (v,)).fetchall()
    if len(r) == 1:
        return r[0]["lifnr"]
    if len(r) > 1:
        raise MMError("Old vendor number %s belongs to %d vendors - give the MM Core number" % (v, len(r)), "ZI", "011")
    raise MMError("Vendor %s does not exist (neither MM Core number nor old vendor number) - load the vendors "
                  "first" % v, "ZI", "012")


# ---------------------------------------------------------------------- objects
def _plant(conn, d, user):
    from mm.master import create_plant
    create_plant(conn, d.get("werks"), (d.get("name") or "").strip(), d.get("city") or "")
    return d.get("werks")


def _sloc(conn, d, user):
    from mm.master import create_sloc
    create_sloc(conn, d.get("werks"), d.get("lgort"), (d.get("name") or "").strip(),
                (d.get("bin_managed") or "").upper() in ("X", "1", "Y", "YES", "TRUE", "نعم"))
    return "%s/%s" % (d.get("werks"), d.get("lgort"))


def _matgroup(conn, d, user):
    from md.material import save_material_group
    return save_material_group(conn, d.get("matkl"), d.get("text"))


def _purchgroup(conn, d, user):
    from md.material import save_purch_group
    return save_purch_group(conn, d.get("ekgrp"), d.get("text"))


def _gl(conn, d, user):
    from fi.gl import save_gl_account
    save_gl_account(conn, d.get("hkont"), d.get("txt"), (d.get("typ") or "PL").upper(), d.get("fsv") or "",
                    d.get("recon") or "", int(d.get("oi") or 0), d.get("tax") or "")
    return d.get("hkont")


def _costcenter(conn, d, user):
    from mm.master import create_cost_center
    create_cost_center(conn, (d.get("kostl") or "").upper(), d.get("name"), d.get("kosar") or "",
                       d.get("khinr") or "", d.get("verak") or "")
    return d.get("kostl")


def _material(conn, d, user):
    from md.material import create_material
    return create_material(conn, d, user, tcode="ZIMPORT")


def _vendor(conn, d, user):
    from md.partner import create_vendor
    if d.get("altkn") and conn.execute("SELECT lifnr FROM vendor WHERE UPPER(altkn)=?",
                                       (d["altkn"].upper(),)).fetchone():
        raise MMError("A vendor with the old number %s is already loaded" % d["altkn"], "ZI", "013")
    if not d.get("akont"):                               # reconciliation account by country
        d["akont"] = "160000" if (d.get("land") or "EG").upper() == "EG" else "161000"
    return create_vendor(conn, d, user, tcode="ZIMPORT")["lifnr"]


def _customer(conn, d, user):
    from md.partner import create_customer
    return create_customer(conn, d, user, tcode="ZIMPORT")["kunnr"]


def _inforec(conn, d, user):
    from pur.sourcing import save_info_record
    return save_info_record(conn, vendor_no(conn, d.get("lifnr")), d.get("matnr") or "", d.get("price"),
                            int(d.get("peinh") or 1), d.get("rabatt") or 0, d.get("frb") or "0",
                            int(d.get("aplfz") or 7), d.get("norbm") or "0", d.get("idnlf") or "",
                            werks=d.get("werks") or "1000")


def _po(conn, rows, user):
    """open purchase order of the old system: one row per item (open quantity), same po_no"""
    from pur import po
    h = rows[0]
    legacy = (h.get("po_no") or "").strip()
    if not legacy:
        raise MMError("Enter the old purchase order number (po_no)", "ZI", "020")
    if conn.execute("SELECT ebeln FROM po_header WHERE ihrez=?", (legacy,)).fetchone():
        raise MMError("Old purchase order %s is already loaded" % legacy, "ZI", "021")
    for r in rows[1:]:
        for f in ("lifnr", "bedat"):
            if r.get(f) and r.get(f) != h.get(f):
                raise MMError("All lines of purchase order %s must have the same %s" % (legacy, f), "ZI", "022")
    items = []
    for r in rows:
        it = {k: r[k] for k in ("matnr", "werks", "lgort", "menge", "netpr", "peinh", "eindt", "txz01", "matkl",
                                "meins", "knttp", "kostl", "sakto", "rabatt") if r.get(k)}
        items.append(it)
    ebeln = po.create_po(conn, {"lifnr": vendor_no(conn, h.get("lifnr")), "bedat": h.get("bedat"),
                                "ekgrp": h.get("ekgrp") or "001", "waers": h.get("waers"), "zterm": h.get("zterm"),
                                "ihrez": legacy, "items": items,
                                "rfq_reason": "Data takeover - old purchase order %s" % legacy}, user)
    po.release_all(conn, ebeln, user)                    # approved in the old system
    return ebeln


def _vendor_oi(conn, d, user):
    from fi.ap import vendor_invoice
    return vendor_invoice(conn, {"lifnr": vendor_no(conn, d.get("lifnr")), "budat": d.get("budat"),
                                 "bldat": d.get("bldat"), "xblnr": d.get("xblnr"), "bktxt": "Data takeover",
                                 "zterm": d.get("zterm")},
                          [{"hkont": TAKEOVER, "amount": d.get("amount"), "sgtxt": d.get("text") or "Open item"}],
                          user, credit_memo=(d.get("credit") or "").upper() in ("X", "1", "Y"))


def _customer_oi(conn, d, user):
    from fi.ar import customer_invoice
    return customer_invoice(conn, {"kunnr": d.get("kunnr"), "budat": d.get("budat"), "bldat": d.get("bldat"),
                                   "xblnr": d.get("xblnr"), "bktxt": "Data takeover", "zterm": d.get("zterm")},
                            [{"hkont": TAKEOVER, "amount": d.get("amount"), "sgtxt": d.get("text") or "Open item"}],
                            user, credit_memo=(d.get("credit") or "").upper() in ("X", "1", "Y"))


def _gl_balance(conn, d, user):
    from fi.gl import general_posting
    amt = str(d.get("amount") or "").replace(",", "")
    neg = amt.startswith("-")
    amt = amt.lstrip("-")
    acc, off = ("50", "40") if neg else ("40", "50")
    return general_posting(conn, {"budat": d.get("budat"), "blart": "SA", "bktxt": "Data takeover"},
                           [{"bschl": acc, "account": d.get("hkont"), "amount": amt, "kostl": d.get("kostl")},
                            {"bschl": off, "account": TAKEOVER, "amount": amt}], user)


def _stock(conn, d, user):
    from mm.posting import post_goods_movement
    r = post_goods_movement(conn, {"budat": d.get("budat"), "bktxt": "Data takeover"},
                            [{"bwart": "561", "matnr": d.get("matnr"), "werks": d.get("werks") or "1000",
                              "lgort": d.get("lgort"), "lgpla": d.get("lgpla") or "", "qty": d.get("qty"),
                              "amount": d.get("value"), "insmk": d.get("insmk") or "U"}], user, tcode="ZIMPORT")
    return r["mblnr"]


def _asset(conn, d, user):
    from fi.aa import create_asset, legacy_transfer
    from mm.util import parse_amount, parse_date
    a = create_asset(conn, d.get("anlkl"), d.get("txt"), d.get("kostl"),
                     int(d["ndjar"]) if d.get("ndjar") else None, d.get("invnr") or "", user)
    anln1 = a["anln1"] if isinstance(a, dict) else a
    legacy_transfer(conn, anln1, parse_date(d.get("aktiv")), parse_amount(d.get("apc")),
                    parse_amount(d.get("accdep"), allow_zero=True), parse_date(d.get("takeover")))
    return anln1


# order of loading = order of this list: (object, text, function, columns, Excel sheet, group column)
OBJECTS = [
    ("PLANT", "Plants", _plant, "werks,name,city", "01 Plants", None),
    ("SLOC", "Storage locations", _sloc, "werks,lgort,name,bin_managed", "02 Storage locations", None),
    ("MATGROUP", "Material groups", _matgroup, "matkl,text", "03 Material groups", None),
    ("PURCHGROUP", "Purchasing groups (buyers)", _purchgroup, "ekgrp,text", "04 Purchasing groups", None),
    ("GL", "G/L accounts", _gl, "hkont,txt,typ,fsv,recon,oi,tax", "G/L accounts", None),
    ("COSTCENTER", "Cost centers", _costcenter, "kostl,name,kosar,khinr,verak", "Cost centers", None),
    ("VENDOR", "Vendors (with bank data)", _vendor,
     "altkn,ktokk,name,name2,street,pstlz,city,land,telf1,email,stcd1,bankn,bankl,iban,swift,akont,zterm,zwels,"
     "waers,ekgrp,plifz,verkf,minbw,lifnr,stceg,ekorg", "05 Vendors", None),
    ("MATERIAL", "Materials (basic + one plant / storage location / sales view)", _material,
     "matnr,mtart,maktx,meins,matkl,bismt,spart,plant.werks,plant.vprsv,plant.price,plant.peinh,plant.ekgrp,"
     "plant.plifz,plant.dismm,plant.minbe,plant.mabst,plant.eisbe,sloc.lgort,sales.vkorg,sales.vtweg,sales.kbetr",
     "06 Materials", None),
    ("CUSTOMER", "Customers (with credit limit, one sales area)", _customer,
     "kunnr,ktokd,name,street,pstlz,city,land,stcd1,akont,zterm,klimk,sales.vkorg,sales.vtweg,sales.spart,"
     "sales.kdgrp", "Customers", None),
    ("INFOREC", "Purchasing info records (vendor prices)", _inforec, "lifnr,matnr,werks,price,peinh,rabatt,aplfz,idnlf",
     "07 Info records", None),
    ("PO", "Open purchase orders (one line per item)", _po,
     "po_no,lifnr,bedat,ekgrp,waers,matnr,werks,lgort,menge,netpr,peinh,eindt,txz01,matkl,meins,knttp,kostl",
     "08 Open purchase orders", "po_no"),
    ("VENDOR_OI", "Open vendor items (against 399999)", _vendor_oi, "lifnr,budat,bldat,xblnr,amount,zterm,credit,text",
     "Open vendor items", None),
    ("CUSTOMER_OI", "Open customer items (against 399999)", _customer_oi,
     "kunnr,budat,bldat,xblnr,amount,zterm,credit,text", "Open customer items", None),
    ("GL_BALANCE", "G/L balances (against 399999; minus = credit)", _gl_balance, "hkont,amount,kostl,budat",
     "G/L balances", None),
    ("STOCK", "Stock per bin with value (561)", _stock, "matnr,werks,lgort,lgpla,qty,value,insmk,budat", "Stock", None),
    ("ASSET", "Fixed assets with accumulated depreciation (AS91)", _asset,
     "anlkl,txt,kostl,ndjar,invnr,aktiv,apc,accdep,takeover", "Fixed assets", None),
]
_BY = {o[0]: o for o in OBJECTS}
_BY_SHEET = {o[4].lower(): o for o in OBJECTS}


def objects():
    return [dict(obj=o[0], text=o[1], columns=o[3], sheet=o[4], order=n) for n, o in enumerate(OBJECTS, start=1)]


def _obj(obj):
    o = _BY.get((obj or "").upper())
    if not o:
        raise MMError("Import object %s does not exist" % obj, "ZI", "001")
    return o


def template(obj):
    return _obj(obj)[3] + "\n"


def parse(text):
    """CSV text -> [(line, row dict)] (line 1 = header)"""
    text = (text or "").lstrip("﻿")
    if not text.strip():
        raise MMError("The file is empty", "ZI", "002")
    first = text.splitlines()[0]
    sep = ";" if first.count(";") > first.count(",") else ","
    return [(n, r) for n, r in enumerate(csv.DictReader(io.StringIO(text), delimiter=sep), start=2)]


def sheet_rows(rows, obj):
    """rows of an Excel sheet -> [(Excel line, row dict)]: the header is the row with the
    technical column names (e.g. lifnr, name ...); the label / rule rows above it and
    empty rows are ignored."""
    cols = set(_obj(obj)[3].split(","))
    head_at = None
    for i, r in enumerate(rows[:15]):
        keys = [str(c).strip() for c in r]
        if sum(1 for k in keys if k in cols) >= min(2, len(cols)):
            head_at = i
            break
    if head_at is None:
        raise MMError("Sheet for %s: the row with the column names (%s ...) is missing" % (
            _obj(obj)[1], ", ".join(_obj(obj)[3].split(",")[:4])), "ZI", "004")
    head = [str(c).strip() for c in rows[head_at]]
    out = []
    for i in range(head_at + 1, len(rows)):
        r = rows[i]
        cells = [str(c).strip() for c in r if str(c).strip()]
        if not cells or all(c.startswith("ℹ") for c in cells):       # empty line / rule line of the template
            continue
        out.append((i + 1, {head[j]: r[j] for j in range(min(len(head), len(r))) if head[j]}))
    return out


def workbook_sheets(data):
    """Excel workbook bytes -> [(object, sheet name, rows)] in the loading order"""
    from mm.xlsx import XlsxError, read
    try:
        book = read(data)
    except XlsxError as e:
        raise MMError(str(e), "ZI", "005")
    found = []
    for name, rows in book.items():
        o = _BY_SHEET.get(name.strip().lower())
        if o:
            found.append((o, name, rows))
    if not found:
        raise MMError("No MM Core sheet found in the workbook (e.g. '05 Vendors') - use the template of ZIMPORT",
                      "ZI", "006")
    order = {o[0]: n for n, o in enumerate(OBJECTS)}
    found.sort(key=lambda x: order[x[0][0]])
    return [(o[0], name, rows) for o, name, rows in found]


def _load(conn, o, items, user, log, sheet=""):
    """items: [(line, row dict)]; one savepoint per line (per order for grouped objects)"""
    if o[5]:                                              # grouped: one document per key (purchase orders)
        groups, order = {}, []
        for line, row in items:
            r = _clean(row)
            k = r.get(o[5]) or "?%d" % line
            if k not in groups:
                groups[k] = []
                order.append(k)
            groups[k].append((line, r))
        units = [([ln for ln, _ in groups[k]], [r for _, r in groups[k]]) for k in order]
    else:
        units = [([line], row) for line, row in items]
    for lines, payload in units:
        ref = lines[0] if len(lines) == 1 else "%s-%s" % (lines[0], lines[-1])
        try:
            with transaction(conn):
                key = o[2](conn, payload if o[5] else _nest(payload), user)
            log.append(dict(sheet=sheet, line=ref, status="S", key=str(key or ""), message="OK"))
        except MMError as e:
            log.append(dict(sheet=sheet, line=ref, status="E", key="", message="%s (%s %s)" % (e.msg, e.msg_class,
                                                                                                e.msg_no)))
        except (ValueError, KeyError, TypeError) as e:
            log.append(dict(sheet=sheet, line=ref, status="E", key="", message="Wrong value: %s" % e))


def _result(log, simulate, text):
    ok = sum(1 for x in log if x["status"] == "S")
    return {"log": log, "ok": ok, "errors": len(log) - ok, "simulated": simulate,
            "message": "%s: %d lines OK, %d with errors%s" % (text, ok, len(log) - ok,
                                                              " (simulation - nothing saved)" if simulate else "")}


def run(conn, obj, text, user, simulate=True):
    """one object from CSV text. Returns {log: [{line, status, key, message}], ok, errors}."""
    o = _obj(obj)
    data = parse(text)
    if len(data) > 5000:
        raise MMError("At most 5000 lines per file", "ZI", "003")
    log = []
    try:
        with transaction(conn):
            _load(conn, o, data, user, log)
            if simulate:
                raise _Rollback()
    except _Rollback:
        pass
    return _result(log, simulate, o[1])


def run_xlsx(conn, data, user, simulate=True, only=None):
    """the Excel workbook: every MM Core sheet in the loading order (or only one object).
    Simulation runs the sheets one after the other in one transaction (later sheets see
    the plants / vendors / materials of earlier sheets) and then rolls everything back."""
    sheets = workbook_sheets(data)
    if only:
        sheets = [s for s in sheets if s[0] == only.upper()]
        if not sheets:
            raise MMError("The workbook has no sheet '%s'" % _obj(only)[4], "ZI", "007")
    log, done = [], []
    total = 0
    try:
        with transaction(conn):
            for obj, name, rows in sheets:
                items = sheet_rows(rows, obj)
                total += len(items)
                if total > 20000:
                    raise MMError("At most 20000 lines per workbook", "ZI", "003")
                if items:
                    _load(conn, _BY[obj], items, user, log, name)
                    done.append(name)
            if simulate:
                raise _Rollback()
    except _Rollback:
        pass
    r = _result(log, simulate, "Workbook (%s)" % ", ".join(done) if done else "Workbook (no lines)")
    r["sheets"] = [dict(sheet=s, ok=sum(1 for x in log if x["sheet"] == s and x["status"] == "S"),
                        errors=sum(1 for x in log if x["sheet"] == s and x["status"] == "E")) for s in done]
    return r


def takeover_balance(conn):
    r = conn.execute("SELECT COALESCE(SUM(CASE WHEN shkzg='S' THEN dmbtr ELSE -dmbtr END),0) FROM acc_doc_item "
                     "WHERE hkont=?", (TAKEOVER,)).fetchone()[0]
    return r


# ---------------------------------------------------------------------- verify (file = system?)
def _amt(v):
    from mm.util import parse_amount
    try:
        return parse_amount(str(v).replace(",", ""), allow_zero=True)
    except (MMError, ValueError):
        return None


def _qty(v):
    from mm.util import parse_qty
    try:
        return parse_qty(str(v).replace(",", ""), allow_zero=True)
    except (MMError, ValueError):
        return None


def _same(kind, file_v, sys_v):
    if sys_v is None:
        return False
    if kind == "amt":
        return _amt(file_v) == sys_v
    if kind == "qty":
        return _qty(file_v) == sys_v
    if kind == "int":
        try:
            return int(float(file_v)) == int(sys_v)
        except (TypeError, ValueError):
            return False
    if kind == "flag":
        return (str(file_v).upper() in ("X", "1", "Y", "YES", "TRUE", "نعم")) == bool(sys_v)
    if kind == "pct":
        try:
            return int(round(float(file_v) * 100)) == int(sys_v)
        except (TypeError, ValueError):
            return False
    if kind == "code":
        return str(file_v).strip().upper() == str(sys_v or "").strip().upper()
    return " ".join(str(file_v).split()) == " ".join(str(sys_v or "").split())


def _fmt(kind, v):
    if v is None:
        return "(missing)"
    if kind == "amt":
        return "%.2f" % (v / 100.0)
    if kind == "qty":
        return ("%.3f" % (v / 1000.0)).rstrip("0").rstrip(".")
    if kind == "pct":
        return "%.2f" % (v / 100.0)
    return str(v)


def _sys_record(conn, obj, d):
    """(key text, {field: (kind, system value)}) of the record a file line describes, or (key, None)"""
    one = lambda sql, a: conn.execute(sql, a).fetchone()         # noqa: E731
    if obj == "PLANT":
        r = one("SELECT * FROM plant WHERE werks=?", (d.get("werks"),))
        return d.get("werks"), r and {"name": ("text", r["name"]), "city": ("text", r["city"])}
    if obj == "SLOC":
        r = one("SELECT * FROM sloc WHERE werks=? AND lgort=?", (d.get("werks"), d.get("lgort")))
        return "%s/%s" % (d.get("werks"), d.get("lgort")), r and {"name": ("text", r["name"]),
                                                                  "bin_managed": ("flag", r["bin_managed"])}
    if obj == "MATGROUP":
        from md.config import MATERIAL_GROUPS
        k = (d.get("matkl") or "").upper()
        return k, ({"text": ("text", MATERIAL_GROUPS[k])} if k in MATERIAL_GROUPS else None)
    if obj == "PURCHGROUP":
        from pur.config import PURCH_GROUPS
        k = d.get("ekgrp") or ""
        return k, ({"text": ("text", PURCH_GROUPS[k])} if k in PURCH_GROUPS else None)
    if obj == "VENDOR":
        if d.get("altkn"):
            r = one("SELECT * FROM vendor WHERE UPPER(altkn)=?", (d["altkn"].upper(),))
        else:
            r = one("SELECT * FROM vendor WHERE lifnr=?", ((d.get("lifnr") or "").upper(),))
        key = (r["lifnr"] if r else "?") + (" (old %s)" % d["altkn"] if d.get("altkn") else "")
        if not r:
            return key, None
        f = {k: ("text", r[k]) for k in ("name", "name2", "street", "pstlz", "city", "telf1", "email", "verkf")}
        f.update({k: ("code", r[k]) for k in ("ktokk", "land", "stcd1", "bankn", "bankl", "iban", "swift", "akont",
                                              "zterm", "zwels", "waers", "ekgrp")})
        f.update(plifz=("int", r["plifz"]), minbw=("amt", r["minbw"]))
        return key, f
    if obj == "MATERIAL":
        m = one("SELECT * FROM material WHERE matnr=?", ((d.get("matnr") or "").upper(),))
        if not m:
            return d.get("matnr"), None
        f = {"maktx": ("text", m["maktx"]), "mtart": ("code", m["mtart"]), "meins": ("code", m["meins"]),
             "matkl": ("code", m["matkl"]), "bismt": ("text", m["bismt"]), "spart": ("code", m["spart"])}
        w = d.get("plant.werks")
        if w:
            p = one("SELECT * FROM material_plant WHERE matnr=? AND werks=?", (m["matnr"], w))
            v = one("SELECT * FROM valuation WHERE matnr=? AND bwkey=?", (m["matnr"], w))
            f["plant.werks"] = ("code", w if p else None)
            if p:
                f.update({"plant.ekgrp": ("code", p["ekgrp"]), "plant.plifz": ("int", p["plifz"]),
                          "plant.dismm": ("code", p["dismm"]), "plant.minbe": ("qty", p["minbe"]),
                          "plant.mabst": ("qty", p["mabst"]), "plant.eisbe": ("qty", p["eisbe"])})
            if v:
                f.update({"plant.vprsv": ("code", v["vprsv"]),
                          "plant.price": ("amt", v["stprs"] if v["vprsv"] == "S" else v["verpr"]),
                          "plant.peinh": ("int", v["peinh"])})
            if d.get("sloc.lgort"):
                s = one("SELECT 1 FROM md_mard WHERE matnr=? AND werks=? AND lgort=?",
                        (m["matnr"], w, d["sloc.lgort"]))
                f["sloc.lgort"] = ("code", d["sloc.lgort"] if s else None)
        return m["matnr"], f
    if obj == "INFOREC":
        try:
            lifnr = vendor_no(conn, d.get("lifnr"))
        except MMError:
            return d.get("lifnr"), None
        r = one("SELECT * FROM info_record WHERE lifnr=? AND matnr=? AND werks=? AND COALESCE(loekz,0)=0",
                (lifnr, (d.get("matnr") or "").upper(), d.get("werks") or "1000"))
        key = "%s / %s" % (lifnr, d.get("matnr"))
        return key, r and {"price": ("amt", r["brutto"]), "peinh": ("int", r["peinh"]),
                           "rabatt": ("pct", r["rabatt"]), "aplfz": ("int", r["aplfz"]), "idnlf": ("text", r["idnlf"])}
    return "", None


VERIFIABLE = ("PLANT", "SLOC", "MATGROUP", "PURCHGROUP", "VENDOR", "MATERIAL", "INFOREC", "PO")
_SKIP = {"VENDOR": {"altkn", "lifnr", "ekorg", "stceg"}, "MATERIAL": {"matnr", "sales.vkorg", "sales.vtweg",
                                                                    "sales.kbetr"},
         "INFOREC": {"lifnr", "matnr", "werks"}, "PLANT": {"werks"}, "SLOC": {"werks", "lgort"},
         "MATGROUP": {"matkl"}, "PURCHGROUP": {"ekgrp"}}


def _verify_po(conn, items, diffs, sheet):
    """purchase orders: header and every item (in the order of the file) against the system"""
    groups, order = {}, []
    for line, row in items:
        r = _clean(row)
        k = r.get("po_no") or "?"
        if k not in groups:
            groups[k] = []
            order.append(k)
        groups[k].append((line, r))
    found = 0
    value_file = value_sys = 0
    for k in order:
        rows = groups[k]
        h = conn.execute("SELECT * FROM po_header WHERE ihrez=?", (k,)).fetchone()
        for line, r in rows:
            if r.get("menge") and r.get("netpr"):
                try:
                    pe = max(int(float(r.get("peinh") or 1)), 1)
                except ValueError:
                    pe = 1
                value_file += (_qty(r["menge"]) or 0) * (_amt(r["netpr"]) or 0) // (1000 * pe)
        if not h:
            diffs.append(dict(sheet=sheet, line=rows[0][0], key="old PO %s" % k, field="-", file="", system="(missing)",
                              status="MISSING"))
            continue
        found += 1
        its = conn.execute("SELECT * FROM po_item WHERE ebeln=? ORDER BY ebelp", (h["ebeln"],)).fetchall()
        for it in its:
            value_sys += it["menge"] * it["netpr"] // (1000 * (it["peinh"] or 1))
        try:
            lifnr = vendor_no(conn, rows[0][1].get("lifnr"))
        except MMError:
            lifnr = None
        checks = [(rows[0][0], "lifnr", rows[0][1].get("lifnr"), lifnr == h["lifnr"], h["lifnr"]),
                  (rows[0][0], "bedat", rows[0][1].get("bedat"), rows[0][1].get("bedat") == h["bedat"], h["bedat"])]
        if len(its) != len(rows):
            checks.append((rows[0][0], "items", len(rows), False, len(its)))
        for (line, r), it in zip(rows, its):
            for f, kind in (("matnr", "code"), ("werks", "code"), ("menge", "qty"), ("netpr", "amt"),
                            ("peinh", "int"), ("eindt", "text"), ("kostl", "code")):
                if r.get(f):
                    checks.append((line, f, r[f], _same(kind, r[f], it[f]), _fmt(kind, it[f])))
        for line, f, fv, ok, sv in checks:
            diffs.append(dict(sheet=sheet, line=line, key="old PO %s = %s" % (k, h["ebeln"]), field=f, file=str(fv),
                              system=str(sv), status="OK" if ok else "DIFFERENT"))
    return dict(sheet=sheet, lines=len(items), records=len(order), found=found,
                control="Order value (open qty x price): file %.2f / MM Core %.2f" % (value_file / 100.0,
                                                                                     value_sys / 100.0),
                control_ok=value_file == value_sys)


def verify_items(conn, obj, items, sheet=""):
    """[(line, row)] of one object -> (differences, summary)"""
    obj = obj.upper()
    diffs = []
    if obj == "PO":
        return diffs, _verify_po(conn, items, diffs, sheet)
    if obj not in VERIFIABLE:
        return diffs, dict(sheet=sheet, lines=len(items), records=len(items), found=None,
                           control="(no field comparison for this object - check the balances)", control_ok=None)
    found = 0
    for line, row in items:
        d = _clean(row)
        key, sysrec = _sys_record(conn, obj, d)
        if sysrec is None:
            diffs.append(dict(sheet=sheet, line=line, key=key, field="-", file="", system="(missing)", status="MISSING"))
            continue
        found += 1
        for f, v in d.items():
            if f in _SKIP.get(obj, ()) or f not in sysrec:
                continue
            kind, sv = sysrec[f]
            ok = _same(kind, v, sv)
            fv = _amt(v) if kind == "amt" else _qty(v) if kind == "qty" else None
            diffs.append(dict(sheet=sheet, line=line, key=key, field=f, file=_fmt(kind, fv) if fv is not None else v,
                              system=_fmt(kind, sv), status="OK" if ok else "DIFFERENT"))
    return diffs, dict(sheet=sheet, lines=len(items), records=len(items), found=found,
                       control="%d of %d lines found in MM Core" % (found, len(items)), control_ok=found == len(items))


def _verify_result(diffs, summaries):
    bad = [x for x in diffs if x["status"] != "OK"]
    checked = len(diffs)
    return {"differences": bad, "checked": checked, "ok": checked - len(bad), "summary": summaries,
            "all_ok": not bad and all(s["control_ok"] is not False for s in summaries),
            "message": ("Everything in the file is in MM Core exactly as in the file (%d values compared)" % checked)
            if not bad else "%d of %d compared values are missing or different - see the list" % (len(bad), checked)}


def verify(conn, obj, text):
    diffs, s = verify_items(conn, obj, parse(text))
    return _verify_result(diffs, [s])


def verify_xlsx(conn, data, only=None):
    diffs, summaries = [], []
    for obj, name, rows in workbook_sheets(data):
        if only and obj != only.upper():
            continue
        items = sheet_rows(rows, obj)
        if not items:
            continue
        d, s = verify_items(conn, obj, items, name)
        diffs += d
        summaries.append(s)
    return _verify_result(diffs, summaries)
