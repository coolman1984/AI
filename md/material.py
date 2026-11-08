"""Material master (MARA/MARC/MARD/MBEW/MVKE/MARM/MLGN + Exim, CIN, Brazil).

MM01   create / extend material (views selected per material type, OMS2)
MM02   change material (with change documents; price control, valuation class
       and base unit only while no stock exists, prices only via MR21)
MM03   display material (all views)
MM06   flag for deletion (X-plant or plant level)
MMSC   enter storage locations (MARD)
MM50   extendable materials (views missing per plant / sales area)
MM60   materials list
ZEXIM  foreign trade data / legal control (commodity code, origin, licenses)
J1ID   CIN: material & chapter ID combination (HSN / GST)
ZMM02_BR  Brazil: NCM code, material usage, material origin
"""
import re

from mm.config import ACCOUNT_DETERMINATION
from mm.db import next_number, rows, transaction
from mm.util import MMError, now_ts, parse_amount, parse_qty, parse_date

from . import changes as cd
from .config import (MATERIAL_TYPE_ATTR, VALUATION_CLASSES, INDUSTRY_SECTORS,
                     MATERIAL_GROUPS, UNITS_EXT, MATERIAL_STATUS, SALES_ORGS,
                     DISTR_CHANNELS, ACCT_ASSIGN_MAT, TAX_CLASS, ITEM_CAT_GROUPS,
                     MRP_CONTROLLERS, PROCUREMENT_TYPES, PROFIT_CENTERS, VIEWS,
                     VIEW_ORDER, CHAPTER_IDS, CIN_MAT_TYPES, BR_USAGE, BR_ORIGIN,
                     EXIM_CONTROL, COUNTRIES, SALES_STATUS, DIVISIONS)

MARA_FIELDS = ["maktx", "matkl", "spart", "mtpos_mara", "brgew", "ntgew", "gewei", "volum",
               "voleh", "ean11", "bismt", "mstae", "prdha", "raube", "tempb", "mhdhb",
               "mhdrz", "mbrsh"]
MARC_FIELDS = ["ekgrp", "plifz", "webaz", "insmk", "uebto", "untto", "kordb", "mmsta",
               "dismm", "dispo", "minbe", "eisbe", "mabst", "bstfe", "disls", "beskz",
               "dzeit", "mtvfp", "lgfsb", "lgpro", "prctr", "ncost", "losgr", "awsls",
               "qmatv", "ssqss"]
QTY_FIELDS = {"minbe", "eisbe", "mabst", "bstfe", "losgr", "brgew", "ntgew", "volum", "aumng"}
PCT_FIELDS = {"uebto", "untto"}               # stored in basis points
INT_FIELDS = {"plifz", "webaz", "dzeit", "mhdhb", "mhdrz", "insmk", "kordb", "ncost", "qmatv"}
MVKE_FIELDS = ["dwerk", "ktgrm", "mtpos", "aumng", "vmsta", "kondm", "versg", "taxm1", "kbetr"]


def _req(v, what):
    if v in (None, ""):
        raise MMError("Fill in all required entry fields (%s)" % what, "00", "055")
    return v


def _conv(f, v):
    if v in (None, ""):
        return 0 if (f in QTY_FIELDS or f in PCT_FIELDS or f in INT_FIELDS) else ""
    if f in QTY_FIELDS:
        return parse_qty(v, allow_zero=True)
    if f in PCT_FIELDS:
        x = int(round(float(v) * 100))
        if not 0 <= x <= 10000:
            raise MMError("Tolerance must be between 0 and 100 %", "M3", "330")
        return x
    if f in INT_FIELDS:
        if isinstance(v, bool):
            return 1 if v else 0
        if str(v).upper() in ("X", "TRUE"):
            return 1
        return int(v)
    if f == "kbetr":
        return parse_amount(v, allow_zero=True)
    return str(v).strip().upper() if f not in ("maktx", "bismt", "prdha", "lgpbe") else str(v).strip()


def attr(mtart):
    a = MATERIAL_TYPE_ATTR.get((mtart or "").upper())
    if not a:
        raise MMError("Material type %s does not exist (OMS2)" % mtart, "M3", "302")
    return a


def _check_view(mtart, view):
    if view not in attr(mtart)["views"]:
        raise MMError("View '%s' cannot be maintained for material type %s (OMS2)"
                      % (VIEWS[view], mtart), "M3", "803")


def _sort_views(s):
    return "".join(v for v in VIEW_ORDER if v in set(s))


# ================================================================== validation
def _basic(conn, d, mtart):
    out = {}
    for f in MARA_FIELDS:
        if f in d:
            out[f] = _conv(f, d[f])
    if "matkl" in out and out["matkl"] and out["matkl"] not in MATERIAL_GROUPS:
        raise MMError("Material group %s does not exist (OMSF)" % out["matkl"], "M3", "309")
    if out.get("mbrsh") and out["mbrsh"] not in INDUSTRY_SECTORS:
        raise MMError("Industry sector %s does not exist (OMS3)" % out["mbrsh"], "M3", "308")
    if out.get("mstae") and out["mstae"] not in MATERIAL_STATUS:
        raise MMError("Material status %s does not exist (OMS4)" % out["mstae"], "M3", "310")
    if out.get("spart") and out["spart"] not in DIVISIONS:
        raise MMError("Division %s does not exist" % out["spart"], "M3", "311")
    if out.get("mtpos_mara") and out["mtpos_mara"] not in ITEM_CAT_GROUPS:
        raise MMError("Item category group %s does not exist" % out["mtpos_mara"])
    if out.get("ntgew") and out.get("brgew") and out["ntgew"] > out["brgew"]:
        raise MMError("The net weight cannot be greater than the gross weight", "M3", "205")
    if out.get("ean11") and not re.fullmatch(r"\d{8}|\d{13}", out["ean11"]):
        raise MMError("EAN/UPC %s: enter 8 or 13 digits (check digit)" % out["ean11"], "M3", "348")
    if out.get("ean11") and not _ean_ok(out["ean11"]):
        raise MMError("EAN %s has an incorrect check digit" % out["ean11"], "M3", "349")
    return out


def _ean_ok(e):
    digits = [int(x) for x in e]
    body, chk = digits[:-1], digits[-1]
    w = [3, 1] if len(e) == 13 else [3, 1]
    s = sum(d * w[(len(body) - 1 - i) % 2] for i, d in enumerate(body))
    return (10 - s % 10) % 10 == chk


def _plant(conn, p, mtart, new=True):
    werks = _req((p.get("werks") or "").upper(), "plant")
    if not conn.execute("SELECT 1 FROM plant WHERE werks=?", (werks,)).fetchone():
        raise MMError("Plant %s does not exist" % werks, "M3", "312")
    out = {"werks": werks}
    for f in MARC_FIELDS:
        if f in p:
            out[f] = _conv(f, p[f])
    if out.get("mmsta") and out["mmsta"] not in MATERIAL_STATUS:
        raise MMError("Plant-specific status %s does not exist (OMS4)" % out["mmsta"], "M3", "310")
    if out.get("dispo") and out["dispo"] not in MRP_CONTROLLERS:
        raise MMError("MRP controller %s does not exist in plant %s" % (out["dispo"], werks),
                      "M3", "320")
    if out.get("beskz") and out["beskz"] not in PROCUREMENT_TYPES:
        raise MMError("Procurement type %s not allowed" % out["beskz"], "M3", "321")
    if out.get("beskz") == "E" and "A" not in attr(mtart)["views"] and new:
        raise MMError("Material type %s cannot be produced in-house" % mtart, "M3", "322")
    if out.get("dismm") == "VB" and not out.get("minbe") and new:
        raise MMError("MRP type VB (reorder point) needs a reorder point", "M3", "323")
    if out.get("dismm") and out["dismm"] not in ("VB", "ND", "PD", "V1", "VV"):
        raise MMError("MRP type %s does not exist" % out["dismm"], "M3", "324")
    if out.get("disls") and out["disls"] not in ("EX", "FX", "HB", "WB", "MB"):
        raise MMError("Lot size %s does not exist" % out["disls"], "M3", "325")
    if out.get("disls") == "FX" and new and not out.get("bstfe"):
        raise MMError("Lot size FX needs a fixed lot size", "M3", "326")
    if out.get("disls") == "HB" and new and out.get("mabst", 0) and \
            out["mabst"] < out.get("minbe", 0):
        raise MMError("Maximum stock level is lower than the reorder point", "M3", "327")
    if out.get("eisbe") and out.get("minbe") and out["eisbe"] > out["minbe"] and new:
        raise MMError("Safety stock is greater than the reorder point", "M3", "328")
    if out.get("prctr") and out["prctr"] not in PROFIT_CENTERS:
        raise MMError("Profit center %s does not exist" % out["prctr"], "KM", "001")
    for f in ("lgfsb", "lgpro"):
        if out.get(f) and not conn.execute("SELECT 1 FROM sloc WHERE werks=? AND lgort=?",
                                           (werks, out[f])).fetchone():
            raise MMError("Storage location %s does not exist in plant %s" % (out[f], werks),
                          "M3", "313")
    if out.get("ekgrp"):
        from pur.config import PURCH_GROUPS
        if out["ekgrp"] not in PURCH_GROUPS:
            raise MMError("Purchasing group %s does not exist" % out["ekgrp"], "M3", "314")
    return out


def _valuation(p, mtart, a):
    vprsv = (p.get("vprsv") or a["vprsv"]).upper()
    if vprsv not in ("V", "S"):
        raise MMError("Price control must be V (moving average) or S (standard)", "M3", "306")
    if a["fixed"] and vprsv != a["vprsv"]:
        raise MMError("Price control %s is mandatory for material type %s (OMS2)"
                      % (a["vprsv"], mtart), "M3", "331")
    price = parse_amount(p.get("price") or "0", allow_zero=True)
    if vprsv == "S" and price == 0:
        raise MMError("Enter a standard price for price control S", "M3", "307")
    peinh = int(p.get("peinh") or 1)
    if peinh <= 0:
        raise MMError("Price unit must be greater than zero", "M3", "332")
    return vprsv, price, peinh


def _sales(conn, s, mtart, meins):
    _check_view(mtart, "V")
    vkorg = _req((s.get("vkorg") or "1000").upper(), "sales org.")
    vtweg = _req((s.get("vtweg") or "").upper(), "distribution channel")
    if vkorg not in SALES_ORGS:
        raise MMError("Sales organization %s does not exist" % vkorg, "M3", "340")
    if vtweg not in DISTR_CHANNELS:
        raise MMError("Distribution channel %s is not defined for sales org. %s"
                      % (vtweg, vkorg), "M3", "341")
    out = {"vkorg": vkorg, "vtweg": vtweg}
    for f in MVKE_FIELDS:
        if f in s:
            out[f] = _conv(f, s[f])
    out.setdefault("dwerk", "1000")
    out.setdefault("ktgrm", "01")
    out.setdefault("taxm1", "1")
    out.setdefault("mtpos", "NORM")
    if not conn.execute("SELECT 1 FROM plant WHERE werks=?", (out["dwerk"],)).fetchone():
        raise MMError("Delivering plant %s does not exist" % out["dwerk"], "M3", "342")
    if out["ktgrm"] and out["ktgrm"] not in ACCT_ASSIGN_MAT:
        raise MMError("Account assignment group %s does not exist" % out["ktgrm"], "M3", "343")
    if out["taxm1"] not in TAX_CLASS:
        raise MMError("Tax classification %s not allowed" % out["taxm1"], "M3", "344")
    if out.get("vmsta") and out["vmsta"] not in SALES_STATUS:
        raise MMError("Distribution-chain status %s does not exist" % out["vmsta"], "M3", "345")
    return out


def _exim(e, mtart):
    _check_view(mtart, "X")
    stawn = (e.get("stawn") or "").strip()
    if stawn and not re.fullmatch(r"\d{4}\.\d{2}(\.\d{2})?", stawn):
        raise MMError("Commodity code %s: format NNNN.NN[.NN] (HS)" % stawn, "EXIM", "010")
    herkl = (e.get("herkl") or "").upper()
    if herkl and herkl not in COUNTRIES:
        raise MMError("Country of origin %s does not exist" % herkl, "EXIM", "011")
    for f in ("impctl", "expctl"):
        if (e.get(f) or "") not in EXIM_CONTROL:
            raise MMError("Legal control %s not allowed" % e.get(f), "EXIM", "012")
    if (e.get("impctl") or "") == "L" and e.get("lic_no") and not e.get("lic_valid"):
        raise MMError("Enter the validity date of license %s" % e["lic_no"], "EXIM", "013")
    return dict(stawn=stawn, herkl=herkl, herkr=(e.get("herkr") or "").upper(),
                impctl=e.get("impctl") or "", expctl=e.get("expctl") or "",
                lic_no=(e.get("lic_no") or "").strip(),
                lic_valid=parse_date(e["lic_valid"]) if e.get("lic_valid") else "",
                duty=int(round(float(e.get("duty") or 0) * 100)),
                prefz=(e.get("prefz") or "").upper())


# ================================================================== MM01
def create_material(conn, data, user, tcode="MM01"):
    mtart = (data.get("mtart") or "").upper()
    a = attr(mtart)
    maktx = (data.get("maktx") or "").strip()
    if not maktx:
        raise MMError("Enter a material description", "M3", "301")
    meins = (data.get("meins") or "").upper()
    if meins not in UNITS_EXT:
        raise MMError("Unit of measure %s is not defined (CUNI)" % meins, "M3", "303")
    basic = _basic(conn, dict(data, mbrsh=data.get("mbrsh") or "M"), mtart)
    _req(basic.get("matkl"), "material group")
    bklas = (data.get("bklas") or a["bklas"][0]).upper()
    if bklas not in a["bklas"]:
        raise MMError("Valuation class %s is not allowed for material type %s (OMSK, "
                      "account category reference %s)" % (bklas, mtart, a["ref"]), "M3", "333")
    if ("BSX", bklas) not in ACCOUNT_DETERMINATION:
        raise MMError("No stock account for valuation class %s (OBYC BSX)" % bklas, "M8", "147")
    plants = data.get("plants") or []
    if not plants:
        raise MMError("Maintain at least one plant (plant views)", "M3", "304")
    with transaction(conn):
        matnr = (data.get("matnr") or "").strip().upper()
        if not matnr:
            matnr = str(next_number(conn, "MATNR"))
        elif not a["ext"]:
            raise MMError("Material type %s uses internal number assignment" % mtart,
                          "M3", "315")
        if len(matnr) > 18 or not re.fullmatch(r"[A-Z0-9\-_/.]+", matnr):
            raise MMError("Material number %s: max. 18 characters A-Z 0-9 - _ / ." % matnr,
                          "M3", "316")
        if conn.execute("SELECT 1 FROM material WHERE matnr=?", (matnr,)).fetchone():
            raise MMError("Material %s already exists" % matnr, "M3", "305")
        if basic.get("ean11") and conn.execute("SELECT matnr FROM material WHERE ean11=?",
                                               (basic["ean11"],)).fetchone():
            raise MMError("EAN %s is already assigned to another material" % basic["ean11"],
                          "M3", "350")
        cols = dict(basic, matnr=matnr, maktx=maktx, mtart=mtart, meins=meins, bklas=bklas,
                    ersda=now_ts()[:10], ernam=user, laeda=now_ts()[:10], aenam=user)
        conn.execute("INSERT INTO material (%s) VALUES (%s)" % (",".join(cols),
                     ",".join("?" * len(cols))), list(cols.values()))
        cd.log(conn, "MATERIAL", matnr, tcode, user,
               [("MARA", matnr, "maktx", "", maktx), ("MARA", matnr, "mtart", "", mtart)], "I")
        _extend(conn, matnr, mtart, meins, data, user, tcode, creating=True)
    return matnr


def extend_material(conn, matnr, data, user, tcode="MM01"):
    """MM01 with an existing material: new plants, sales areas, storage
    locations, units, warehouse / foreign trade data."""
    with transaction(conn):
        m = _get(conn, matnr)
        _extend(conn, m["matnr"], m["mtart"], m["meins"], data, user, tcode)
    return m["matnr"]


def _extend(conn, matnr, mtart, meins, data, user, tcode, creating=False):
    a = attr(mtart)
    views = set("K")
    log = []
    for p in data.get("plants") or []:
        pv = _plant(conn, p, mtart)
        werks = pv["werks"]
        if conn.execute("SELECT 1 FROM material_plant WHERE matnr=? AND werks=?",
                        (matnr, werks)).fetchone():
            raise MMError("Material %s already exists in plant %s" % (matnr, werks), "M3", "317")
        vprsv, price, peinh = _valuation(p, mtart, a)
        pv.setdefault("dismm", "VB" if pv.get("minbe") else "ND")
        pv.setdefault("disls", "HB" if pv["dismm"] == "VB" else "EX")
        if not pv.get("mabst") and pv["dismm"] == "VB":
            pv["mabst"] = pv.get("minbe", 0) * 3
        pv.setdefault("ekgrp", "001")
        pv.setdefault("plifz", 7)
        pv.setdefault("beskz", "F" if "E" in a["views"] else "E")
        if "G" in a["views"]:
            pv.setdefault("awsls", "000001" if pv["beskz"] in ("E", "X") else "")
        pview = set("DLB")
        if "E" in a["views"]:
            pview.add("E")
        if "G" in a["views"]:
            pview.add("G")
        if pv.get("qmatv") or pv.get("insmk"):
            if "Q" not in a["views"]:
                _check_view(mtart, "Q")
            pview.add("Q")
        if "P" in a["views"] and pv["dismm"] in ("V1",):
            pview.add("P")
        if "A" in a["views"] and pv["beskz"] in ("E", "X"):
            pview.add("A")
        pv["vpsta"] = _sort_views(pview)
        views |= pview
        pv["matnr"] = matnr
        conn.execute("INSERT INTO material_plant (%s) VALUES (%s)" % (",".join(pv),
                     ",".join("?" * len(pv))), list(pv.values()))
        zplp1 = parse_amount(p.get("zplp1") or "0", allow_zero=True)
        conn.execute("INSERT INTO valuation (matnr,bwkey,vprsv,verpr,stprs,peinh,lbkum,salk3,"
                     "zplp1,zpld1,bwprh,bwph1) VALUES (?,?,?,?,?,?,0,0,?,?,?,?)",
                     (matnr, werks, vprsv, price, price, peinh, zplp1,
                      parse_date(p["zpld1"]) if p.get("zpld1") else None,
                      parse_amount(p.get("bwprh") or "0", allow_zero=True),
                      parse_amount(p.get("bwph1") or "0", allow_zero=True)))
        conn.execute("INSERT INTO price_history (matnr,bwkey,ts,budat,ref,reason,old_price,"
                     "new_price,peinh,lbkum,salk3) VALUES (?,?,?,?,?,?,?,?,?,0,0)",
                     (matnr, werks, now_ts(), now_ts()[:10], tcode, "Material created",
                      None, price, peinh))
        for s in p.get("slocs") or []:
            _sloc_add(conn, matnr, werks, s)
        log.append(("MARC", "%s/%s" % (matnr, werks), "werks", "", werks))
    for s in data.get("slocs") or []:
        _sloc_add(conn, matnr, (s.get("werks") or "").upper(), s)
        views.add("L")
    for s in data.get("sales") or []:
        sv = _sales(conn, s, mtart, meins)
        if conn.execute("SELECT 1 FROM md_mvke WHERE matnr=? AND vkorg=? AND vtweg=?",
                        (matnr, sv["vkorg"], sv["vtweg"])).fetchone():
            raise MMError("Material %s already exists in sales org. %s / %s"
                          % (matnr, sv["vkorg"], sv["vtweg"]), "M3", "318")
        sv["matnr"] = matnr
        conn.execute("INSERT INTO md_mvke (%s) VALUES (%s)" % (",".join(sv),
                     ",".join("?" * len(sv))), list(sv.values()))
        views.add("V")
        log.append(("MVKE", "%s/%s/%s" % (matnr, sv["vkorg"], sv["vtweg"]), "vtweg", "",
                    sv["vtweg"]))
    for u in data.get("uom") or []:
        _uom(conn, matnr, meins, u)
    if data.get("whse"):
        w = data["whse"]
        _check_view(mtart, "S")
        if (w.get("ltkza") or "F") not in ("F", "L", "M") or (w.get("ltkze") or "F") not in ("F", "N", "B"):
            raise MMError("Stock removal / placement strategy indicator not allowed", "L3", "020")
        conn.execute("INSERT OR REPLACE INTO md_mlgn VALUES (?,?,?,?,?,?)",
                     (matnr, w.get("lgnum") or "100", w.get("ltkze") or "F",
                      w.get("ltkza") or "F", parse_qty(w.get("lhmg1") or "0", allow_zero=True),
                      w.get("lety1") or ""))
        views.add("S")
    if data.get("exim"):
        e = _exim(data["exim"], mtart)
        conn.execute("INSERT OR REPLACE INTO md_exim (matnr,stawn,herkl,herkr,impctl,expctl,"
                     "lic_no,lic_valid,duty,prefz) VALUES (?,?,?,?,?,?,?,?,?,?)",
                     (matnr, e["stawn"], e["herkl"], e["herkr"], e["impctl"], e["expctl"],
                      e["lic_no"], e["lic_valid"], e["duty"], e["prefz"]))
        views.add("X")
    old = conn.execute("SELECT vpsta FROM material WHERE matnr=?", (matnr,)).fetchone()["vpsta"]
    conn.execute("UPDATE material SET vpsta=?, laeda=?, aenam=? WHERE matnr=?",
                 (_sort_views(set(old or "") | views), now_ts()[:10], user, matnr))
    if log and not creating:
        cd.log(conn, "MATERIAL", matnr, tcode, user, log, "I")


def _sloc_add(conn, matnr, werks, s):
    lgort = _req((s.get("lgort") or "").upper(), "storage location")
    if not conn.execute("SELECT 1 FROM material_plant WHERE matnr=? AND werks=?",
                        (matnr, werks)).fetchone():
        raise MMError("Material %s is not maintained in plant %s" % (matnr, werks), "M3", "319")
    if not conn.execute("SELECT 1 FROM sloc WHERE werks=? AND lgort=?",
                        (werks, lgort)).fetchone():
        raise MMError("Storage location %s does not exist in plant %s" % (lgort, werks),
                      "M3", "313")
    if conn.execute("SELECT auto FROM md_mard WHERE matnr=? AND werks=? AND lgort=?",
                    (matnr, werks, lgort)).fetchone():
        conn.execute("UPDATE md_mard SET lgpbe=? WHERE matnr=? AND werks=? AND lgort=?",
                     ((s.get("lgpbe") or "").strip().upper(), matnr, werks, lgort))
        return
    conn.execute("INSERT INTO md_mard (matnr,werks,lgort,lgpbe,auto,ersda) VALUES "
                 "(?,?,?,?,0,?)", (matnr, werks, lgort, (s.get("lgpbe") or "").strip().upper(),
                                   now_ts()[:10]))


def _uom(conn, matnr, meins, u):
    meinh = (u.get("meinh") or "").upper()
    if meinh not in UNITS_EXT:
        raise MMError("Unit of measure %s is not defined (CUNI)" % meinh, "M3", "303")
    if meinh == meins:
        raise MMError("The alternative unit must differ from the base unit", "M3", "334")
    umrez, umren = int(u.get("umrez") or 0), int(u.get("umren") or 1)
    if umrez <= 0 or umren <= 0:
        raise MMError("Enter a conversion factor greater than zero", "M3", "335")
    conn.execute("INSERT OR REPLACE INTO md_marm VALUES (?,?,?,?,?)",
                 (matnr, meinh, umrez, umren, u.get("ean11") or ""))


def convert(conn, matnr, qty_milli, from_unit):
    """Alternative unit -> base unit (MARM): qty * umrez / umren."""
    m = conn.execute("SELECT meins FROM material WHERE matnr=?", (matnr,)).fetchone()
    if not m or from_unit == m["meins"]:
        return qty_milli
    u = conn.execute("SELECT * FROM md_marm WHERE matnr=? AND meinh=?",
                     (matnr, from_unit)).fetchone()
    if not u:
        raise MMError("No conversion factor for unit %s of material %s" % (from_unit, matnr),
                      "M3", "336")
    return qty_milli * u["umrez"] // u["umren"]


# ================================================================== MM02
def change_material(conn, matnr, data, user, tcode="MM02"):
    with transaction(conn):
        m = _get(conn, matnr)
        matnr, mtart = m["matnr"], m["mtart"]
        a = attr(mtart)
        log = []
        basic = _basic(conn, {k: v for k, v in data.items() if k in MARA_FIELDS}, mtart)
        if "maktx" in basic and not basic["maktx"]:
            raise MMError("Enter a material description", "M3", "301")
        stock = conn.execute("SELECT COALESCE(SUM(lbkum),0) FROM valuation WHERE matnr=?",
                             (matnr,)).fetchone()[0]
        if data.get("meins") and data["meins"].upper() != m["meins"]:
            if stock or conn.execute("SELECT 1 FROM mat_doc_item WHERE matnr=? LIMIT 1",
                                     (matnr,)).fetchone():
                raise MMError("Base unit of measure cannot be changed: stock or documents "
                              "exist", "M3", "337")
            basic["meins"] = data["meins"].upper()
        if data.get("bklas") and data["bklas"] != m["bklas"]:
            if data["bklas"] not in a["bklas"]:
                raise MMError("Valuation class %s is not allowed for material type %s (OMSK)"
                              % (data["bklas"], mtart), "M3", "333")
            if stock:
                raise MMError("Valuation class cannot be changed: stock exists (post the "
                              "stock out, change, post it back)", "M3", "095")
            basic["bklas"] = data["bklas"]
        for f, o, n in cd.diff(m, basic, list(basic)):
            log.append(("MARA", matnr, f, o, n))
        if basic:
            basic.update(laeda=now_ts()[:10], aenam=user)
            conn.execute("UPDATE material SET %s WHERE matnr=?" % ",".join(
                "%s=?" % k for k in basic), list(basic.values()) + [matnr])
        for p in data.get("plants") or []:
            pv = _plant(conn, p, mtart, new=False)
            werks = pv.pop("werks")
            old = conn.execute("SELECT * FROM material_plant WHERE matnr=? AND werks=?",
                               (matnr, werks)).fetchone()
            if not old:
                raise MMError("Material %s is not maintained in plant %s (extend with MM01)"
                              % (matnr, werks), "M3", "319")
            if pv.get("qmatv") or pv.get("insmk"):
                _check_view(mtart, "Q")
            chg = cd.diff(old, pv, list(pv))
            if chg:
                conn.execute("UPDATE material_plant SET %s WHERE matnr=? AND werks=?" % ",".join(
                    "%s=?" % f for f, _, _ in chg), [n for _, _, n in chg] + [matnr, werks])
                log += [("MARC", "%s/%s" % (matnr, werks), f, o, n) for f, o, n in chg]
            v = conn.execute("SELECT * FROM valuation WHERE matnr=? AND bwkey=?",
                             (matnr, werks)).fetchone()
            if p.get("vprsv") and p["vprsv"].upper() != v["vprsv"]:
                nv = p["vprsv"].upper()
                if nv not in ("V", "S") or (a["fixed"] and nv != a["vprsv"]):
                    raise MMError("Price control %s is not allowed for material type %s"
                                  % (nv, mtart), "M3", "331")
                if v["lbkum"]:
                    raise MMError("Price control cannot be changed: plant %s has stock "
                                  "(%s)" % (werks, v["lbkum"] / 1000.0), "M3", "160")
                conn.execute("UPDATE valuation SET vprsv=? WHERE matnr=? AND bwkey=?",
                             (nv, matnr, werks))
                log.append(("MBEW", "%s/%s" % (matnr, werks), "vprsv", v["vprsv"], nv))
            for f in ("price", "verpr", "stprs"):
                if p.get(f) not in (None, "") and parse_amount(p[f], allow_zero=True) != \
                        (v["stprs"] if v["vprsv"] == "S" else v["verpr"]):
                    raise MMError("Prices cannot be changed in MM02 - use MR21 (price change "
                                  "with revaluation)", "M3", "161")
            vals = {}
            if p.get("zplp1") not in (None, ""):
                vals["zplp1"] = parse_amount(p["zplp1"], allow_zero=True)
            if p.get("zpld1"):
                vals["zpld1"] = parse_date(p["zpld1"])
            for f in ("bwprh", "bwph1"):
                if p.get(f) not in (None, ""):
                    vals[f] = parse_amount(p[f], allow_zero=True)
            chg = cd.diff(v, vals, list(vals))
            if chg:
                conn.execute("UPDATE valuation SET %s WHERE matnr=? AND bwkey=?" % ",".join(
                    "%s=?" % f for f, _, _ in chg), [n for _, _, n in chg] + [matnr, werks])
                log += [("MBEW", "%s/%s" % (matnr, werks), f, o, n) for f, o, n in chg]
            for s in p.get("slocs") or []:
                _sloc_add(conn, matnr, werks, s)
        for s in data.get("sales") or []:
            sv = _sales(conn, s, mtart, m["meins"])
            key = (matnr, sv.pop("vkorg"), sv.pop("vtweg"))
            old = conn.execute("SELECT * FROM md_mvke WHERE matnr=? AND vkorg=? AND vtweg=?",
                               key).fetchone()
            if not old:
                raise MMError("Material %s is not defined for sales org. %s / %s (extend with "
                              "MM01)" % (matnr, key[1], key[2]), "M3", "318")
            chg = cd.diff(old, sv, [f for f in MVKE_FIELDS if f in s])
            if chg:
                conn.execute("UPDATE md_mvke SET %s WHERE matnr=? AND vkorg=? AND vtweg=?"
                             % ",".join("%s=?" % f for f, _, _ in chg),
                             [n for _, _, n in chg] + list(key))
                log += [("MVKE", "/".join(key), f, o, n) for f, o, n in chg]
        for u in data.get("uom") or []:
            _uom(conn, matnr, m["meins"], u)
        if data.get("exim"):
            e = _exim(data["exim"], mtart)
            old = conn.execute("SELECT * FROM md_exim WHERE matnr=?", (matnr,)).fetchone()
            if old:
                log += [("EXIM", matnr, f, o, n) for f, o, n in cd.diff(old, e, list(e))]
            conn.execute("INSERT OR REPLACE INTO md_exim (matnr,stawn,herkl,herkr,impctl,"
                         "expctl,lic_no,lic_valid,duty,prefz) VALUES (?,?,?,?,?,?,?,?,?,?)",
                         (matnr, e["stawn"], e["herkl"], e["herkr"], e["impctl"],
                          e["expctl"], e["lic_no"], e["lic_valid"], e["duty"], e["prefz"]))
            if "X" not in (m["vpsta"] or ""):
                conn.execute("UPDATE material SET vpsta=? WHERE matnr=?",
                             (_sort_views(set(m["vpsta"] or "") | {"X"}), matnr))
        nr = cd.log(conn, "MATERIAL", matnr, tcode, user, log)
    return {"matnr": matnr, "changenr": nr, "changed": len(log)}


# ================================================================== MM06
def flag_deletion(conn, matnr, user, werks=None, flag=True):
    """X-plant (werks None) or plant level. Returns warnings like SAP."""
    warnings = []
    with transaction(conn):
        m = _get(conn, matnr)
        if werks:
            p = conn.execute("SELECT lvorm FROM material_plant WHERE matnr=? AND werks=?",
                             (m["matnr"], werks)).fetchone()
            if not p:
                raise MMError("Material %s is not maintained in plant %s" % (matnr, werks),
                              "M3", "319")
            conn.execute("UPDATE material_plant SET lvorm=? WHERE matnr=? AND werks=?",
                         (1 if flag else 0, m["matnr"], werks))
            cd.log(conn, "MATERIAL", m["matnr"], "MM06", user,
                   [("MARC", "%s/%s" % (m["matnr"], werks), "lvorm", p["lvorm"], 1 if flag else 0)])
            plants = [werks]
        else:
            conn.execute("UPDATE material SET lvorm=? WHERE matnr=?", (1 if flag else 0, m["matnr"]))
            cd.log(conn, "MATERIAL", m["matnr"], "MM06", user,
                   [("MARA", m["matnr"], "lvorm", m["lvorm"], 1 if flag else 0)])
            plants = [r["werks"] for r in m["plants"]]
        if flag:
            for w in plants:
                v = conn.execute("SELECT lbkum, salk3 FROM valuation WHERE matnr=? AND bwkey=?",
                                 (m["matnr"], w)).fetchone()
                if v and v["lbkum"]:
                    warnings.append("Plant %s still has stock %.3f (value %.2f) - the material "
                                    "cannot be archived until the stock is zero"
                                    % (w, v["lbkum"] / 1000.0, v["salk3"] / 100.0))
            n = conn.execute("SELECT COUNT(*) FROM po_item WHERE matnr=? AND elikz=0 AND "
                             "wemng<menge AND COALESCE(loekz,0)=0", (m["matnr"],)).fetchone()[0]
            if n:
                warnings.append("%d open purchase order item(s) exist" % n)
    return {"matnr": m["matnr"], "warnings": warnings}


# ================================================================== J1ID / Brazil
def gstin_check_char(s14):
    chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    total = 0
    for i, ch in enumerate(s14):
        p = chars.index(ch) * (1 if i % 2 == 0 else 2)
        total += p // 36 + p % 36
    return chars[(36 - total % 36) % 36]


def check_pan(pan):
    if not re.fullmatch(r"[A-Z]{5}\d{4}[A-Z]", pan or ""):
        raise MMError("PAN %s is not valid (format AAAAA9999A)" % pan, "J1I", "010")


def check_gstin(gstin, pan=None):
    g = (gstin or "").upper()
    if not re.fullmatch(r"\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]", g):
        raise MMError("GSTIN %s is not valid (format 99AAAAA9999A9Z9)" % gstin, "J1I", "011")
    if gstin_check_char(g[:14]) != g[14]:
        raise MMError("GSTIN %s: check character is wrong (expected %s)"
                      % (g, gstin_check_char(g[:14])), "J1I", "012")
    if pan and g[2:12] != pan:
        raise MMError("GSTIN %s does not contain the PAN %s" % (g, pan), "J1I", "013")
    return g


def save_cin_material(conn, matnr, werks, chapid, mtype, user, subcon=False):
    m = _get(conn, matnr)
    if chapid not in CHAPTER_IDS:
        raise MMError("Chapter ID %s does not exist (J1ID chapter IDs)" % chapid, "J1I", "001")
    if mtype not in CIN_MAT_TYPES:
        raise MMError("Material type for excise %s not allowed" % mtype, "J1I", "002")
    with transaction(conn):
        if not conn.execute("SELECT 1 FROM material_plant WHERE matnr=? AND werks=?",
                            (m["matnr"], werks)).fetchone():
            raise MMError("Material %s is not maintained in plant %s" % (matnr, werks), "M3", "319")
        old = conn.execute("SELECT * FROM md_cin_mat WHERE matnr=? AND werks=?",
                           (m["matnr"], werks)).fetchone()
        conn.execute("INSERT OR REPLACE INTO md_cin_mat VALUES (?,?,?,?,?,?,?)",
                     (m["matnr"], werks, chapid, mtype, chapid.replace(".", ""),
                      CHAPTER_IDS[chapid][1] * 100, 1 if subcon else 0))
        cd.log(conn, "MATERIAL", m["matnr"], "J1ID", user,
               [("J_1IMTCHID", "%s/%s" % (m["matnr"], werks), "chapid",
                 old["chapid"] if old else "", chapid)], "U" if old else "I")


def save_br_material(conn, matnr, werks, steuc, mtuse, mtorg, user, cfop_cat=""):
    m = _get(conn, matnr)
    if not re.fullmatch(r"\d{4}\.\d{2}\.\d{2}", steuc or ""):
        raise MMError("NCM code %s: format NNNN.NN.NN (8 digits)" % steuc, "J1B", "001")
    if mtuse not in BR_USAGE:
        raise MMError("Material usage %s not allowed" % mtuse, "J1B", "002")
    if mtorg not in BR_ORIGIN:
        raise MMError("Material origin %s not allowed" % mtorg, "J1B", "003")
    if mtorg in ("1", "2"):
        e = conn.execute("SELECT herkl FROM md_exim WHERE matnr=?", (m["matnr"],)).fetchone()
        if not e or not e["herkl"] or e["herkl"] == "BR":
            raise MMError("Foreign origin needs a foreign country of origin (foreign trade "
                          "view)", "J1B", "004")
    if mtuse == "3" and m["mtart"] not in ("HAWA", "FERT"):
        raise MMError("Usage 'resale' needs material type HAWA or FERT", "J1B", "005")
    with transaction(conn):
        old = conn.execute("SELECT * FROM md_br_mat WHERE matnr=? AND werks=?",
                           (m["matnr"], werks)).fetchone()
        conn.execute("INSERT OR REPLACE INTO md_br_mat VALUES (?,?,?,?,?,?)",
                     (m["matnr"], werks, steuc, mtuse, mtorg, cfop_cat))
        items = [("MARC_BR", "%s/%s" % (m["matnr"], werks), "steuc",
                  old["steuc"] if old else "", steuc)]
        if old:
            items += [("MARC_BR", "%s/%s" % (m["matnr"], werks), f, old[f], n)
                      for f, n in (("mtuse", mtuse), ("mtorg", mtorg))]
        cd.log(conn, "MATERIAL", m["matnr"], "ZMM02_BR", user, items, "U" if old else "I")


# ================================================================== MM03
def _get(conn, matnr):
    m = conn.execute("SELECT * FROM material WHERE matnr=?",
                     ((matnr or "").strip().upper(),)).fetchone()
    if not m:
        raise MMError("Material %s does not exist" % matnr, "M3", "305")
    m = dict(m)
    m["plants"] = rows(conn.execute("SELECT werks FROM material_plant WHERE matnr=?",
                                    (m["matnr"],)))
    return m


def get_material(conn, matnr):
    m = _get(conn, matnr)
    k = m["matnr"]
    a = attr(m["mtart"])
    m["mtart_text"] = a["text"]
    m["bklas_text"] = VALUATION_CLASSES.get(m["bklas"], ("",))[0]
    m["allowed_views"] = a["views"]
    m["views"] = [{"key": v, "text": VIEWS[v], "allowed": v in a["views"],
                   "maintained": v in (m["vpsta"] or "")} for v in VIEW_ORDER]
    m["plants"] = rows(conn.execute(
        "SELECT mp.*, v.vprsv, v.verpr, v.stprs, v.peinh, v.lbkum, v.salk3, v.zplp1, v.zpld1, "
        "v.bwprh, v.bwph1, p.name AS plant_name FROM material_plant mp "
        "JOIN valuation v ON v.matnr=mp.matnr AND v.bwkey=mp.werks "
        "JOIN plant p ON p.werks=mp.werks WHERE mp.matnr=? ORDER BY mp.werks", (k,)))
    for p in m["plants"]:
        p["price"] = p["stprs"] if p["vprsv"] == "S" else p["verpr"]
        st = MATERIAL_STATUS.get(p["mmsta"] or "")
        p["mmsta_text"] = st[0] if st else ""
        ce = conn.execute("SELECT * FROM cost_estimate WHERE matnr=? AND werks=? ORDER BY "
                          "rowid DESC LIMIT 1", (k, p["werks"])).fetchone() \
            if _has(conn, "cost_estimate") else None
        p["cost_estimate"] = dict(ce) if ce else None
    m["slocs"] = rows(conn.execute(
        "SELECT d.*, s.name, COALESCE((SELECT SUM(qty) FROM quant q WHERE q.matnr=d.matnr AND "
        "q.werks=d.werks AND q.lgort=d.lgort),0) AS stock FROM md_mard d JOIN sloc s ON "
        "s.werks=d.werks AND s.lgort=d.lgort WHERE d.matnr=? ORDER BY d.werks, d.lgort", (k,)))
    m["uom"] = rows(conn.execute("SELECT * FROM md_marm WHERE matnr=? ORDER BY meinh", (k,)))
    m["sales"] = rows(conn.execute("SELECT * FROM md_mvke WHERE matnr=? ORDER BY vkorg, vtweg",
                                   (k,)))
    m["whse"] = _one(conn, "SELECT * FROM md_mlgn WHERE matnr=?", (k,))
    m["exim"] = _one(conn, "SELECT * FROM md_exim WHERE matnr=?", (k,))
    m["cin"] = rows(conn.execute("SELECT * FROM md_cin_mat WHERE matnr=?", (k,)))
    m["brazil"] = rows(conn.execute("SELECT * FROM md_br_mat WHERE matnr=?", (k,)))
    st = MATERIAL_STATUS.get(m["mstae"] or "")
    m["mstae_text"] = st[0] if st else ""
    m["stock_total"] = sum(p["lbkum"] for p in m["plants"])
    m["value_total"] = sum(p["salk3"] for p in m["plants"])
    return m


def _has(conn, table):
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE name=?", (table,)).fetchone())


def _one(conn, sql, args):
    r = conn.execute(sql, args).fetchone()
    return dict(r) if r else None


# ================================================================== lists
def mm60(conn, mtart="", matkl="", werks="", q=""):
    sql = ("SELECT m.matnr, m.maktx, m.mtart, m.matkl, m.meins, m.bklas, m.vpsta, m.mstae, "
           "m.lvorm, m.ersda, m.ernam, m.laeda, m.aenam, mp.werks, mp.mmsta, mp.lvorm AS plvorm, "
           "mp.dismm, mp.ekgrp, v.vprsv, v.verpr, v.stprs, v.peinh, v.lbkum, v.salk3 "
           "FROM material m LEFT JOIN material_plant mp ON mp.matnr=m.matnr LEFT JOIN "
           "valuation v ON v.matnr=mp.matnr AND v.bwkey=mp.werks WHERE 1=1")
    args = []
    for col, v in (("m.mtart", mtart), ("m.matkl", matkl), ("mp.werks", werks)):
        if v:
            sql += " AND %s=?" % col
            args.append(v.upper())
    if q:
        sql += " AND (m.matnr LIKE ? OR m.maktx LIKE ?)"
        args += ["%" + q + "%"] * 2
    out = rows(conn.execute(sql + " ORDER BY m.matnr, mp.werks", args))
    for r in out:
        r["price"] = r["stprs"] if r["vprsv"] == "S" else r["verpr"]
        r["deleted"] = 1 if (r["lvorm"] or r["plvorm"]) else 0
    return out


def mm50(conn):
    """Extendable materials: for every material, the plants / sales areas /
    allowed views that are still missing."""
    plants = [r["werks"] for r in conn.execute("SELECT werks FROM plant ORDER BY werks")]
    out = []
    for m in conn.execute("SELECT matnr, maktx, mtart, vpsta FROM material ORDER BY matnr"):
        a = MATERIAL_TYPE_ATTR.get(m["mtart"])
        if not a:
            continue
        have = {r["werks"] for r in conn.execute(
            "SELECT werks FROM material_plant WHERE matnr=?", (m["matnr"],))}
        for w in plants:
            if w not in have:
                out.append(dict(matnr=m["matnr"], maktx=m["maktx"], mtart=m["mtart"],
                                level="Plant", org=w, missing="Plant views (E D L B G)"))
        if "V" in a["views"]:
            sa = {r["vtweg"] for r in conn.execute(
                "SELECT vtweg FROM md_mvke WHERE matnr=? AND vkorg='1000'", (m["matnr"],))}
            for ch in DISTR_CHANNELS:
                if ch not in sa:
                    out.append(dict(matnr=m["matnr"], maktx=m["maktx"], mtart=m["mtart"],
                                    level="Sales area", org="1000/%s" % ch,
                                    missing="Sales views"))
        miss = [VIEWS[v] for v in a["views"] if v not in (m["vpsta"] or "") and v not in "CPA"]
        if miss:
            out.append(dict(matnr=m["matnr"], maktx=m["maktx"], mtart=m["mtart"],
                            level="Views", org="", missing=", ".join(miss)))
    return out


def slocs(conn, matnr):
    m = _get(conn, matnr)
    return rows(conn.execute(
        "SELECT d.*, s.name FROM md_mard d JOIN sloc s ON s.werks=d.werks AND s.lgort=d.lgort "
        "WHERE d.matnr=? ORDER BY d.werks, d.lgort", (m["matnr"],)))
