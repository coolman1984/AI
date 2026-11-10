"""ZIMPORT - data import for go-live (LSMW-like).

A CSV file (UTF-8, comma or semicolon, Arabic text allowed) is read for one
object; every line goes through the normal engine function (all checks, number
ranges, change documents - no direct SQL). "Simulate" runs everything and rolls
back; "Post" keeps the good lines. Each line runs in its own savepoint, so one
bad line does not stop the file; the log shows line, status and message.

Nested views use dotted column names: plant.werks, plant.price, sloc.lgort
(material); sales.vkorg, sales.vtweg (customer / material). Open items, G/L
balances and stock are posted against the data takeover account 399999, which
must be zero when the load is complete (shown by takeover_balance()).
"""
import csv
import io

from mm.db import transaction
from mm.util import MMError

TAKEOVER = "399999"


class _Rollback(Exception):
    pass


def _nest(row):
    """plant.x / sloc.x / sales.x columns -> nested single-entry lists."""
    data, plant, sloc, sales = {}, {}, {}, {}
    for k, v in row.items():
        if k is None or isinstance(v, list):      # extra separators at the end of a line
            continue
        k = k.strip()
        v = (v or "").strip()
        if not k or v == "":
            continue
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
    return create_vendor(conn, d, user, tcode="ZIMPORT")["lifnr"]


def _customer(conn, d, user):
    from md.partner import create_customer
    return create_customer(conn, d, user, tcode="ZIMPORT")["kunnr"]


def _inforec(conn, d, user):
    from pur.sourcing import save_info_record
    return save_info_record(conn, d.get("lifnr") or "", d.get("matnr") or "", d.get("price"),
                            int(d.get("peinh") or 1), d.get("rabatt") or 0, d.get("frb") or "0",
                            int(d.get("aplfz") or 7), d.get("norbm") or "0", d.get("idnlf") or "",
                            werks=d.get("werks") or "1000")


def _vendor_oi(conn, d, user):
    from fi.ap import vendor_invoice
    return vendor_invoice(conn, {"lifnr": d.get("lifnr"), "budat": d.get("budat"), "bldat": d.get("bldat"),
                                 "xblnr": d.get("xblnr"), "bktxt": "Data takeover", "zterm": d.get("zterm")},
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


# order of loading = order of this list
OBJECTS = [
    ("GL", "G/L accounts", _gl, "hkont,txt,typ,fsv,recon,oi,tax"),
    ("COSTCENTER", "Cost centers", _costcenter, "kostl,name,kosar,khinr,verak"),
    ("MATERIAL", "Materials (basic + one plant / storage location / sales view)", _material,
     "matnr,mtart,maktx,meins,matkl,spart,plant.werks,plant.vprsv,plant.price,plant.peinh,plant.dismm,"
     "plant.minbe,sloc.lgort,sales.vkorg,sales.vtweg,sales.kbetr"),
    ("VENDOR", "Vendors (with bank data)", _vendor,
     "lifnr,ktokk,name,street,pstlz,city,land,stceg,bankn,bankl,iban,akont,zterm,zwels,waers,ekorg"),
    ("CUSTOMER", "Customers (with credit limit, one sales area)", _customer,
     "kunnr,ktokd,name,street,pstlz,city,land,stcd1,akont,zterm,klimk,sales.vkorg,sales.vtweg,sales.spart,"
     "sales.kdgrp"),
    ("INFOREC", "Purchasing info records", _inforec, "lifnr,matnr,werks,price,peinh,rabatt,aplfz"),
    ("VENDOR_OI", "Open vendor items (against 399999)", _vendor_oi, "lifnr,budat,bldat,xblnr,amount,zterm,credit,text"),
    ("CUSTOMER_OI", "Open customer items (against 399999)", _customer_oi,
     "kunnr,budat,bldat,xblnr,amount,zterm,credit,text"),
    ("GL_BALANCE", "G/L balances (against 399999; minus = credit)", _gl_balance, "hkont,amount,kostl,budat"),
    ("STOCK", "Stock per bin with value (561)", _stock, "matnr,werks,lgort,lgpla,qty,value,insmk,budat"),
    ("ASSET", "Fixed assets with accumulated depreciation (AS91)", _asset,
     "anlkl,txt,kostl,ndjar,invnr,aktiv,apc,accdep,takeover"),
]
_BY = {o[0]: o for o in OBJECTS}


def objects():
    return [dict(obj=o[0], text=o[1], columns=o[3], order=n) for n, o in enumerate(OBJECTS, start=1)]


def template(obj):
    o = _BY.get((obj or "").upper())
    if not o:
        raise MMError("Import object %s does not exist" % obj, "ZI", "001")
    return o[3] + "\n"


def parse(text):
    text = (text or "").lstrip("﻿")
    if not text.strip():
        raise MMError("The file is empty", "ZI", "002")
    first = text.splitlines()[0]
    sep = ";" if first.count(";") > first.count(",") else ","
    return list(csv.DictReader(io.StringIO(text), delimiter=sep))


def run(conn, obj, text, user, simulate=True):
    """Returns {log: [{line, status, key, message}], ok, errors}."""
    o = _BY.get((obj or "").upper())
    if not o:
        raise MMError("Import object %s does not exist" % obj, "ZI", "001")
    data = parse(text)
    if len(data) > 5000:
        raise MMError("At most 5000 lines per file", "ZI", "003")
    log = []
    try:
        with transaction(conn):
            for n, row in enumerate(data, start=2):          # line 1 = header
                try:
                    with transaction(conn):                  # savepoint per line
                        key = o[2](conn, _nest(row), user)
                    log.append(dict(line=n, status="S", key=str(key or ""), message="OK"))
                except MMError as e:
                    log.append(dict(line=n, status="E", key="", message="%s (%s %s)" % (e.msg, e.msg_class, e.msg_no)))
                except (ValueError, KeyError, TypeError) as e:
                    log.append(dict(line=n, status="E", key="", message="Wrong value: %s" % e))
            if simulate:
                raise _Rollback()
    except _Rollback:
        pass
    ok = sum(1 for x in log if x["status"] == "S")
    return {"log": log, "ok": ok, "errors": len(log) - ok, "simulated": simulate,
            "message": "%s: %d lines OK, %d with errors%s" % (o[1], ok, len(log) - ok,
                                                              " (simulation - nothing saved)" if simulate else "")}


def takeover_balance(conn):
    r = conn.execute("SELECT COALESCE(SUM(CASE WHEN shkzg='S' THEN dmbtr ELSE -dmbtr END),0) FROM acc_doc_item "
                     "WHERE hkont=?", (TAKEOVER,)).fetchone()[0]
    return r
