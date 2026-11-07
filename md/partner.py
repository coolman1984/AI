"""Customer and vendor master (business partners).

Customer: XD01/XD02/XD03 (central), FD01/FD02/FD03 (accounting), VD01/VD02/VD03
          (sales), XD04 changes, XD05 block, XD06 deletion flag, XD07 account group,
          FD08/FD09 confirm sensitive changes, S_ALR_87012179 list
Vendor:   XK01/XK02/XK03 (central), FK01..FK03 (accounting), MK01..MK03
          (purchasing), XK04, XK05, XK06, XK07, FK08/FK09, S_ALR_87012086 list
CIN:      J1ID customer / vendor excise & GST details (India)
"""
import re

from mm.db import rows, transaction
from mm.util import MMError, now_ts, parse_amount

from . import changes as cd
from .config import (CUST_GROUPS, CUST_RANGES, VEND_GROUPS, VEND_RANGES, PARTNER_FUNCTIONS,
                     SALES_ORGS, DISTR_CHANNELS, DIVISIONS, SALES_DISTRICTS, CUSTOMER_GROUPS,
                     PRICE_GROUPS, SHIPPING_COND, INCOTERMS, ACCT_ASSIGN_CUST, PRICING_PROC,
                     DUNNING_PROC, PAYMENT_METHODS, COUNTRIES, SENSITIVE_VENDOR,
                     SENSITIVE_CUSTOMER, CIN_VENDOR_TYPES, SSI_STATUS)
from .material import check_gstin, check_pan

CUST_GENERAL = ["name", "name2", "street", "pstlz", "city", "region", "land", "telf1",
                "email", "stcd1", "stceg", "bankn", "bankl"]
CUST_COMPANY = ["akont", "zterm", "klimk", "mahna", "zwels", "xzver", "busab"]
CUST_SALES = ["spart", "bzirk", "kdgrp", "konda", "kalks", "vsbed", "vwerk", "inco1",
              "inco2", "zterm", "ktgrd", "taxkd", "waers"]
VEND_GENERAL = ["name", "name2", "street", "pstlz", "city", "land", "telf1", "email",
                "stcd1", "stceg", "bankn", "bankl", "iban", "swift"]
VEND_COMPANY = ["akont", "zterm", "zwels", "reprf", "witht", "busab"]
VEND_PURCH = ["ekorg", "waers", "minbw", "webre", "verkf", "lfabc", "ekgrp", "plifz",
              "inco1", "inco2"]
BLOCKS_C = ["sperr", "aufsd", "lifsd", "faksd"]
BLOCKS_V = ["sperr", "sperm", "zahls"]


def _s(v):
    return "" if v is None else str(v).strip()


def _norm(d, fields, amounts=(), ints=()):
    out = {}
    for f in fields:
        if f in d:
            v = d[f]
            if f in amounts:
                out[f] = parse_amount(v or "0", allow_zero=True)
            elif f in ints:
                out[f] = 1 if str(v).upper() in ("1", "X", "TRUE") else 0
            elif f in ("name", "name2", "street", "city", "email", "busab", "verkf", "inco2"):
                out[f] = _s(v)
            else:
                out[f] = _s(v).upper()
    return out


def _field_status(group, vals, creating, has_sales=False):
    for f in group["req"]:
        if f == "vkorg":
            if creating and not has_sales:
                raise MMError("Fill in all required entry fields (sales area data - "
                              "account group %s)" % group["text"], "00", "055")
            continue
        if creating and not vals.get(f):
            raise MMError("Fill in all required entry fields (%s)" % f, "00", "055")
        if not creating and f in vals and not vals[f]:
            raise MMError("Field %s is a required entry field" % f, "00", "055")
    for f in group["sup"]:
        if vals.get(f):
            raise MMError("Field %s is suppressed for account group %s" % (f, group["text"]),
                          "F2", "015")


def _number(conn, table, key, given, rng):
    lo, hi, ext = rng
    if ext:
        if not given:
            raise MMError("Number range is external - enter a number (%s-%s)" % (lo, hi),
                          "F2", "009")
        if len(given) != len(lo) or not (lo <= given <= hi):
            raise MMError("Number %s is not in the external interval %s-%s" % (given, lo, hi),
                          "F2", "010")
        return given
    if given:
        raise MMError("Number range is internal - the system assigns the number", "F2", "011")
    cur = conn.execute("SELECT MAX(%s) FROM %s WHERE length(%s)=? AND %s BETWEEN ? AND ?"
                       % (key, table, key, key), (len(lo), lo, hi)).fetchone()[0]
    nxt = str(int(cur) + 1 if cur else int(lo) + 1).zfill(len(lo))
    if nxt > hi:
        raise MMError("Number range interval %s-%s is exhausted" % (lo, hi), "F2", "012")
    return nxt


def _check_common(conn, vals, koart):
    from fi.config import PAYMENT_TERMS, CURRENCIES
    if vals.get("land") and vals["land"] not in COUNTRIES:
        raise MMError("Country %s does not exist" % vals["land"], "F2", "020")
    if vals.get("zterm") and vals["zterm"] not in PAYMENT_TERMS:
        raise MMError("Payment terms %s are not defined (OBB8)" % vals["zterm"], "F2", "030")
    if vals.get("waers") and vals["waers"] not in CURRENCIES:
        raise MMError("Currency %s is not defined" % vals["waers"], "F2", "031")
    if vals.get("akont"):
        a = conn.execute("SELECT recon FROM gl_account WHERE hkont=?", (vals["akont"],)).fetchone()
        if not a or a["recon"] != koart:
            raise MMError("Account %s is not a %s reconciliation account" % (
                vals["akont"], "vendor" if koart == "K" else "customer"), "F2", "032")
    if vals.get("land") == "EG" and vals.get("stcd1") and \
            not re.fullmatch(r"\d{3}-?\d{3}-?\d{3}", vals["stcd1"]):
        raise MMError("Tax number %s: Egyptian tax registration has 9 digits (999-999-999)"
                      % vals["stcd1"], "AR", "102")
    if vals.get("email") and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", vals["email"]):
        raise MMError("E-mail address %s is not valid" % vals["email"], "AM", "201")
    if vals.get("iban"):
        vals["iban"] = vals["iban"].replace(" ", "")
        if not iban_ok(vals["iban"]):
            raise MMError("IBAN %s is not valid (check digits)" % vals["iban"], "AR", "191")
    if vals.get("swift") and not re.fullmatch(r"[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?", vals["swift"]):
        raise MMError("SWIFT/BIC %s is not valid" % vals["swift"], "AR", "190")
    if vals.get("zwels"):
        for ch in vals["zwels"]:
            if ch not in PAYMENT_METHODS:
                raise MMError("Payment method %s is not defined" % ch, "F2", "033")


def iban_ok(iban):
    s = iban.upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{10,30}", s):
        return False
    r = s[4:] + s[:4]
    num = "".join(str(int(c, 36)) for c in r)
    return int(num) % 97 == 1


def make_iban(country, bban):
    """Compute the IBAN check digits for a BBAN (used by the demo data)."""
    num = "".join(str(int(c, 36)) for c in (bban + country + "00").upper())
    return "%s%02d%s" % (country, 98 - int(num) % 97, bban)


def _duplicates(conn, table, key, vals, own=None):
    w = []
    if vals.get("stcd1"):
        for r in conn.execute("SELECT %s FROM %s WHERE REPLACE(stcd1,'-','')=? AND %s<>?"
                              % (key, table, key), (vals["stcd1"].replace("-", ""), own or "")):
            w.append("Tax number %s is already used by %s" % (vals["stcd1"], r[0]))
    if vals.get("bankn"):
        for r in conn.execute("SELECT %s FROM %s WHERE bankn=? AND %s<>?" % (key, table, key),
                              (vals["bankn"], own or "")):
            w.append("Bank account %s is already used by %s" % (vals["bankn"], r[0]))
    if vals.get("name"):
        for r in conn.execute("SELECT %s FROM %s WHERE lower(name)=lower(?) AND %s<>?"
                              % (key, table, key), (vals["name"], own or "")):
            w.append("Possible duplicate: %s has the same name" % r[0])
    return w


def _sensitive(conn, koart, objectid, nr, fields, user):
    if not fields or not nr:
        return
    p = conn.execute("SELECT id, fields FROM md_sensitive WHERE koart=? AND objectid=? AND "
                     "status='P'", (koart, objectid)).fetchone()
    if p:
        allf = sorted(set(p["fields"].split(",")) | set(fields))
        conn.execute("UPDATE md_sensitive SET fields=?, changenr=?, changed_by=?, changed_at=? "
                     "WHERE id=?", (",".join(allf), nr, user, now_ts(), p["id"]))
    else:
        conn.execute("INSERT INTO md_sensitive (koart,objectid,changenr,fields,changed_by,"
                     "changed_at) VALUES (?,?,?,?,?,?)",
                     (koart, objectid, nr, ",".join(sorted(fields)), user, now_ts()))


# ====================================================================== customer
def _sales_area(conn, s):
    vk = (s.get("vkorg") or "1000").upper()
    vt = (s.get("vtweg") or "").upper()
    sp = (s.get("spart") or "00").upper()
    if vk not in SALES_ORGS:
        raise MMError("Sales organization %s does not exist" % vk, "F2", "040")
    if vt not in DISTR_CHANNELS:
        raise MMError("Distribution channel %s does not exist" % vt, "F2", "041")
    if sp not in DIVISIONS:
        raise MMError("Division %s does not exist" % sp, "F2", "042")
    v = _norm(s, CUST_SALES)
    v.update(vkorg=vk, vtweg=vt, spart=sp)
    for f, tab, txt in (("bzirk", SALES_DISTRICTS, "Sales district"),
                        ("kdgrp", CUSTOMER_GROUPS, "Customer group"),
                        ("konda", PRICE_GROUPS, "Price group"),
                        ("kalks", PRICING_PROC, "Customer pricing procedure"),
                        ("vsbed", SHIPPING_COND, "Shipping conditions"),
                        ("inco1", INCOTERMS, "Incoterms"),
                        ("ktgrd", ACCT_ASSIGN_CUST, "Account assignment group")):
        if v.get(f) and v[f] not in tab:
            raise MMError("%s %s does not exist" % (txt, v[f]), "F2", "043")
    for f in ("kalks", "vsbed", "ktgrd", "waers", "zterm"):
        if not v.get(f):
            raise MMError("Fill in all required entry fields (sales area %s/%s: %s)"
                          % (vk, vt, f), "00", "055")
    if v.get("inco1") and v["inco1"] != "EXW" and not v.get("inco2"):
        raise MMError("Enter Incoterms part 2 (location) for %s" % v["inco1"], "F2", "044")
    if vt == "20" and v.get("taxkd") == "1":
        raise MMError("Export sales area 1000/20: tax classification must be 0 (exempt)",
                      "F2", "045")
    v.setdefault("taxkd", "0" if vt == "20" else "1")
    v.setdefault("vwerk", "1000")
    _check_common(conn, v, "D")
    return v


def create_customer(conn, data, user, tcode="XD01"):
    ktokd = (data.get("ktokd") or "0001").upper()
    g = CUST_GROUPS.get(ktokd)
    if not g:
        raise MMError("Account group %s does not exist (OBD2)" % ktokd, "F2", "004")
    vals = _norm(data, CUST_GENERAL + CUST_COMPANY, amounts=("klimk",), ints=("xzver",))
    vals.setdefault("land", "EG")
    sales = data.get("sales") or []
    if tcode in ("FD01",):
        sales = []
    _field_status(g, vals, True, has_sales=bool(sales) or tcode == "FD01")
    _check_common(conn, vals, "D")
    if vals.get("mahna") and vals["mahna"] not in DUNNING_PROC:
        raise MMError("Dunning procedure %s does not exist" % vals["mahna"], "F2", "034")
    areas = [_sales_area(conn, s) for s in sales]
    with transaction(conn):
        kunnr = _number(conn, "customer", "kunnr", _s(data.get("kunnr")).upper(),
                        CUST_RANGES[g["nr"]])
        if conn.execute("SELECT 1 FROM customer WHERE kunnr=?", (kunnr,)).fetchone():
            raise MMError("Customer %s already exists" % kunnr, "F2", "001")
        warnings = _duplicates(conn, "customer", "kunnr", vals)
        first = areas[0] if areas else {}
        cols = dict(vals, kunnr=kunnr, ktokd=ktokd, erdat=now_ts()[:10], ernam=user,
                    region=vals.get("region") or first.get("bzirk", ""),
                    kdgrp=first.get("kdgrp", ""), vtweg=first.get("vtweg", ""))
        if "akont" in g["sup"]:
            cols["akont"] = ""
        conn.execute("INSERT INTO customer (%s) VALUES (%s)" % (",".join(cols),
                     ",".join("?" * len(cols))), list(cols.values()))
        for a in areas:
            _insert_area(conn, kunnr, a, ktokd, data.get("partners") or [])
        cd.log(conn, "DEBI", kunnr, tcode, user,
               [("KNA1", kunnr, "name", "", vals.get("name")), ("KNA1", kunnr, "ktokd", "", ktokd)],
               "I")
    return {"kunnr": kunnr, "warnings": warnings}


def _insert_area(conn, kunnr, a, ktokd, partners):
    if conn.execute("SELECT 1 FROM md_knvv WHERE kunnr=? AND vkorg=? AND vtweg=? AND spart=?",
                    (kunnr, a["vkorg"], a["vtweg"], a["spart"])).fetchone():
        raise MMError("Customer %s already exists in sales area %s/%s/%s"
                      % (kunnr, a["vkorg"], a["vtweg"], a["spart"]), "F2", "002")
    cols = dict(a, kunnr=kunnr)
    for f in CUST_SALES:
        cols.setdefault(f, "")
    conn.execute("INSERT INTO md_knvv (%s) VALUES (%s)" % (",".join(cols),
                 ",".join("?" * len(cols))), list(cols.values()))
    allowed = CUST_GROUPS[ktokd]["partners"].split(",")
    pf = {p["parvw"].upper(): [] for p in partners if p.get("parvw")}
    for p in partners:
        if p.get("parvw"):
            pf[p["parvw"].upper()].append(_s(p.get("kunn2")).upper())
    for f in allowed:                       # mandatory functions default to itself
        pf.setdefault(f, [kunnr])
    for f, targets in pf.items():
        if f not in PARTNER_FUNCTIONS:
            raise MMError("Partner function %s does not exist" % f, "VP", "001")
        if f not in allowed:
            raise MMError("Partner function %s is not allowed for account group %s"
                          % (f, CUST_GROUPS[ktokd]["text"]), "VP", "002")
        for t in targets:
            t2 = t or kunnr
            if t2 != kunnr:
                tg = conn.execute("SELECT ktokd FROM customer WHERE kunnr=?", (t2,)).fetchone()
                if not tg:
                    raise MMError("Partner %s does not exist" % t2, "VP", "003")
                if f not in CUST_GROUPS[tg["ktokd"] or "0001"]["partners"].split(","):
                    raise MMError("Customer %s (account group %s) cannot be partner %s"
                                  % (t2, tg["ktokd"], PARTNER_FUNCTIONS[f]), "VP", "004")
            conn.execute("INSERT OR IGNORE INTO md_knvp VALUES (?,?,?,?,?)",
                         (kunnr, a["vkorg"], a["vtweg"], f, t2))


def change_customer(conn, kunnr, data, user, tcode="XD02"):
    with transaction(conn):
        c = _cust(conn, kunnr)
        k = c["kunnr"]
        g = CUST_GROUPS.get(c["ktokd"] or "0001")
        vals = _norm(data, CUST_GENERAL + CUST_COMPANY, amounts=("klimk",), ints=("xzver",))
        _field_status(g, vals, False)
        _check_common(conn, vals, "D")
        chg = cd.diff(c, vals, list(vals))
        log = [("KNA1" if f in CUST_GENERAL else "KNB1", k, f, o, n) for f, o, n in chg]
        if chg:
            conn.execute("UPDATE customer SET %s WHERE kunnr=?" % ",".join(
                "%s=?" % f for f, _, _ in chg), [n for _, _, n in chg] + [k])
        for s in data.get("sales") or []:
            a = _sales_area(conn, s)
            key = (k, a["vkorg"], a["vtweg"], a["spart"])
            old = conn.execute("SELECT * FROM md_knvv WHERE kunnr=? AND vkorg=? AND vtweg=? "
                               "AND spart=?", key).fetchone()
            if not old:
                _insert_area(conn, k, a, c["ktokd"] or "0001", data.get("partners") or [])
                log.append(("KNVV", "/".join(key), "vtweg", "", a["vtweg"]))
                continue
            ch2 = cd.diff(old, a, [f for f in CUST_SALES if f in s])
            if ch2:
                conn.execute("UPDATE md_knvv SET %s WHERE kunnr=? AND vkorg=? AND vtweg=? AND "
                             "spart=?" % ",".join("%s=?" % f for f, _, _ in ch2),
                             [n for _, _, n in ch2] + list(key))
                log += [("KNVV", "/".join(key), f, o, n) for f, o, n in ch2]
        nr = cd.log(conn, "DEBI", k, tcode, user, log)
        sens = [f for f, _, _ in chg if f in SENSITIVE_CUSTOMER]
        _sensitive(conn, "D", k, nr, sens, user)
        warnings = _duplicates(conn, "customer", "kunnr", {f: n for f, _, n in chg
                                                           if f in ("stcd1", "bankn")}, own=k)
    return {"kunnr": k, "changenr": nr, "changed": len(log), "sensitive": sens,
            "warnings": warnings}


def block_customer(conn, kunnr, user, sperr=None, aufsd=None, lifsd=None, faksd=None):
    """XD05: posting block (company code), order / delivery / billing block."""
    new = {f: v for f, v in (("sperr", sperr), ("aufsd", aufsd), ("lifsd", lifsd),
                             ("faksd", faksd)) if v is not None}
    if "sperr" in new:
        new["sperr"] = 1 if str(new["sperr"]).upper() in ("1", "X", "TRUE") else 0
    for f in ("aufsd", "lifsd", "faksd"):
        if f in new:
            new[f] = _s(new[f]).upper()
            if new[f] and new[f] not in ("01", "02", "08", "10"):
                raise MMError("Block reason %s does not exist (01 credit, 02 legal, 08 "
                              "overdue, 10 other)" % new[f], "F2", "050")
    with transaction(conn):
        c = _cust(conn, kunnr)
        chg = cd.diff(c, new, list(new))
        if chg:
            conn.execute("UPDATE customer SET %s WHERE kunnr=?" % ",".join(
                "%s=?" % f for f, _, _ in chg), [n for _, _, n in chg] + [c["kunnr"]])
        cd.log(conn, "DEBI", c["kunnr"], "XD05", user,
               [("KNA1", c["kunnr"], f, o, n) for f, o, n in chg])
    return {"kunnr": c["kunnr"], "changed": len(chg)}


def flag_customer(conn, kunnr, user, flag=True):
    with transaction(conn):
        c = _cust(conn, kunnr)
        conn.execute("UPDATE customer SET loevm=? WHERE kunnr=?", (1 if flag else 0, c["kunnr"]))
        cd.log(conn, "DEBI", c["kunnr"], "XD06", user,
               [("KNA1", c["kunnr"], "loevm", c["loevm"], 1 if flag else 0)])
    return _open_balance(conn, "D", c["kunnr"])


def change_customer_group(conn, kunnr, ktokd, user):
    """XD07: the number must fit the new group's interval, a ship-to cannot
    become a sold-to without company code data."""
    ktokd = ktokd.upper()
    g = CUST_GROUPS.get(ktokd)
    if not g:
        raise MMError("Account group %s does not exist (OBD2)" % ktokd, "F2", "004")
    with transaction(conn):
        c = _cust(conn, kunnr)
        lo, hi, ext = CUST_RANGES[g["nr"]]
        if not (len(c["kunnr"]) == len(lo) and lo <= c["kunnr"] <= hi):
            raise MMError("Customer %s is not in the number interval %s-%s of account group "
                          "%s" % (c["kunnr"], lo, hi, ktokd), "F2", "016")
        if "akont" in g["req"] and not c["akont"]:
            raise MMError("Account group %s needs company code data - maintain it with FD02 "
                          "first" % ktokd, "F2", "017")
        conn.execute("UPDATE customer SET ktokd=? WHERE kunnr=?", (ktokd, c["kunnr"]))
        cd.log(conn, "DEBI", c["kunnr"], "XD07", user,
               [("KNA1", c["kunnr"], "ktokd", c["ktokd"], ktokd)])


def _cust(conn, kunnr):
    c = conn.execute("SELECT * FROM customer WHERE kunnr=?", (_s(kunnr).upper(),)).fetchone()
    if not c:
        raise MMError("Customer %s does not exist" % kunnr, "F2", "102")
    return c


def get_customer(conn, kunnr):
    c = dict(_cust(conn, kunnr))
    k = c["kunnr"]
    g = CUST_GROUPS.get(c["ktokd"] or "0001", {})
    c["ktokd_text"] = g.get("text", "")
    c["sales"] = rows(conn.execute("SELECT * FROM md_knvv WHERE kunnr=? ORDER BY vkorg, vtweg",
                                   (k,)))
    c["partners"] = rows(conn.execute(
        "SELECT p.*, c.name FROM md_knvp p LEFT JOIN customer c ON c.kunnr=p.kunn2 WHERE "
        "p.kunnr=? ORDER BY p.vkorg, p.vtweg, p.parvw", (k,)))
    for p in c["partners"]:
        p["text"] = PARTNER_FUNCTIONS.get(p["parvw"], "")
    c["cin"] = _one(conn, "SELECT * FROM md_cin_cust WHERE kunnr=?", (k,))
    c["sensitive"] = rows(conn.execute("SELECT * FROM md_sensitive WHERE koart='D' AND "
                                       "objectid=? ORDER BY id DESC", (k,)))
    c.update(_open_balance(conn, "D", k))
    c["sales_volume"] = conn.execute("SELECT COALESCE(SUM(netwr),0) FROM billing WHERE kunnr=? "
                                     "AND cancelled=0", (k,)).fetchone()[0]
    c["bills"] = rows(conn.execute("SELECT vbeln, fkdat, netwr, cancelled FROM billing WHERE "
                                   "kunnr=? ORDER BY vbeln DESC LIMIT 20", (k,)))
    c["blocked"] = bool(c["sperr"] or c["aufsd"] or c["lifsd"] or c["faksd"])
    return c


def _open_balance(conn, koart, key):
    col = "kunnr" if koart == "D" else "lifnr"
    r = conn.execute("SELECT COALESCE(SUM(CASE WHEN shkzg='S' THEN dmbtr ELSE -dmbtr END),0) "
                     "AS bal, COUNT(*) AS n FROM acc_doc_item WHERE koart=? AND %s=? AND "
                     "(augbl IS NULL OR augbl='')" % col, (koart, key)).fetchone()
    t = conn.execute("SELECT COALESCE(SUM(CASE WHEN shkzg='S' THEN dmbtr ELSE -dmbtr END),0) "
                     "FROM acc_doc_item WHERE koart=? AND %s=?" % col, (koart, key)).fetchone()[0]
    return {"open_items": r["n"], "open_balance": r["bal"], "balance": t}


def customers(conn, ktokd="", land="", blocked=False):
    sql = "SELECT * FROM customer WHERE 1=1"
    args = []
    if ktokd:
        sql += " AND ktokd=?"
        args.append(ktokd)
    if land:
        sql += " AND land=?"
        args.append(land)
    out = rows(conn.execute(sql + " ORDER BY kunnr", args))
    res = []
    for c in out:
        c.update(_open_balance(conn, "D", c["kunnr"]))
        c["blocked"] = bool(c["sperr"] or c["aufsd"] or c["lifsd"] or c["faksd"])
        c["areas"] = ", ".join("%s/%s" % (r["vkorg"], r["vtweg"]) for r in conn.execute(
            "SELECT vkorg, vtweg FROM md_knvv WHERE kunnr=?", (c["kunnr"],)))
        c["group_text"] = CUST_GROUPS.get(c["ktokd"] or "0001", {}).get("text", "")
        if not blocked or c["blocked"] or c["loevm"]:
            res.append(c)
    return res


# ====================================================================== vendor
def create_vendor(conn, data, user, tcode="XK01"):
    ktokk = (data.get("ktokk") or "0001").upper()
    g = VEND_GROUPS.get(ktokk)
    if not g:
        raise MMError("Account group %s does not exist (OBD3)" % ktokk, "F2", "004")
    fields = VEND_GENERAL + (VEND_COMPANY if tcode != "MK01" else []) + \
        (VEND_PURCH if tcode != "FK01" else [])
    vals = _norm(data, fields, amounts=("minbw",), ints=("reprf", "webre"))
    vals.setdefault("land", "EG")
    vals.setdefault("waers", "EGP")
    if "plifz" in vals:
        vals["plifz"] = int(vals["plifz"] or 0)
    req = dict(g)
    if tcode == "MK01":
        req = dict(g, req=[f for f in g["req"] if f not in VEND_COMPANY and f != "bankn"])
    _field_status(req, vals, True)
    if ktokk == "0003" and vals.get("land") == "EG":
        raise MMError("Account group 0003 is for foreign vendors (country must not be EG)",
                      "F2", "018")
    if ktokk in ("0001", "0002") and vals.get("land") != "EG":
        raise MMError("Account group %s is for domestic vendors - use 0003" % ktokk, "F2", "019")
    _check_common(conn, vals, "K")
    if vals.get("ekgrp"):
        from pur.config import PURCH_GROUPS
        if vals["ekgrp"] not in PURCH_GROUPS:
            raise MMError("Purchasing group %s does not exist" % vals["ekgrp"], "F2", "035")
    with transaction(conn):
        lifnr = _number(conn, "vendor", "lifnr", _s(data.get("lifnr")).upper(),
                        VEND_RANGES[g["nr"]])
        if conn.execute("SELECT 1 FROM vendor WHERE lifnr=?", (lifnr,)).fetchone():
            raise MMError("Vendor %s already exists" % lifnr, "F2", "001")
        warnings = _duplicates(conn, "vendor", "lifnr", vals)
        cols = dict(vals, lifnr=lifnr, ktokk=ktokk, sperr=0, erdat=now_ts()[:10], ernam=user)
        if tcode == "MK01":
            cols.setdefault("akont", "160000")
            cols.setdefault("zterm", "NT30")
        conn.execute("INSERT INTO vendor (%s) VALUES (%s)" % (",".join(cols),
                     ",".join("?" * len(cols))), list(cols.values()))
        cd.log(conn, "KRED", lifnr, tcode, user,
               [("LFA1", lifnr, "name", "", vals.get("name")), ("LFA1", lifnr, "ktokk", "", ktokk)],
               "I")
    return {"lifnr": lifnr, "warnings": warnings}


def change_vendor(conn, lifnr, data, user, tcode="XK02"):
    with transaction(conn):
        v = _vend(conn, lifnr)
        k = v["lifnr"]
        g = VEND_GROUPS.get(v["ktokk"] or "0001")
        vals = _norm(data, VEND_GENERAL + VEND_COMPANY + VEND_PURCH, amounts=("minbw",),
                     ints=("reprf", "webre"))
        if "plifz" in vals:
            vals["plifz"] = int(vals["plifz"] or 0)
        _field_status(g, vals, False)
        _check_common(conn, vals, "K")
        chg = cd.diff(v, vals, list(vals))
        tab = lambda f: "LFA1" if f in VEND_GENERAL else "LFB1" if f in VEND_COMPANY else "LFM1"
        log = [(tab(f), k, f, o, n) for f, o, n in chg]
        if chg:
            conn.execute("UPDATE vendor SET %s WHERE lifnr=?" % ",".join(
                "%s=?" % f for f, _, _ in chg), [n for _, _, n in chg] + [k])
        nr = cd.log(conn, "KRED", k, tcode, user, log)
        sens = [f for f, _, _ in chg if f in SENSITIVE_VENDOR]
        _sensitive(conn, "K", k, nr, sens, user)
        warnings = _duplicates(conn, "vendor", "lifnr", {f: n for f, _, n in chg
                                                         if f in ("stcd1", "bankn")}, own=k)
    return {"lifnr": k, "changenr": nr, "changed": len(log), "sensitive": sens,
            "warnings": warnings}


def block_vendor(conn, lifnr, user, sperr=None, sperm=None, zahls=None):
    """XK05: posting block (company code), purchasing block, payment block."""
    new = {}
    for f, v in (("sperr", sperr), ("sperm", sperm)):
        if v is not None:
            new[f] = 1 if str(v).upper() in ("1", "X", "TRUE") else 0
    if zahls is not None:
        new["zahls"] = _s(zahls).upper()
        if new["zahls"] and new["zahls"] not in ("A", "R", "*"):
            raise MMError("Payment block key %s does not exist (A blocked, R invoice "
                          "verification, * skip)" % new["zahls"], "F2", "051")
    with transaction(conn):
        v = _vend(conn, lifnr)
        chg = cd.diff(v, new, list(new))
        if chg:
            conn.execute("UPDATE vendor SET %s WHERE lifnr=?" % ",".join(
                "%s=?" % f for f, _, _ in chg), [n for _, _, n in chg] + [v["lifnr"]])
        cd.log(conn, "KRED", v["lifnr"], "XK05", user,
               [("LFA1", v["lifnr"], f, o, n) for f, o, n in chg])
        open_po = conn.execute("SELECT COUNT(*) FROM po_header h JOIN po_item i USING (ebeln) "
                               "WHERE h.lifnr=? AND i.elikz=0 AND i.wemng<i.menge AND "
                               "COALESCE(i.loekz,0)=0", (v["lifnr"],)).fetchone()[0]
    out = {"lifnr": v["lifnr"], "changed": len(chg), "open_po_items": open_po}
    out.update(_open_balance(conn, "K", v["lifnr"]))
    return out


def flag_vendor(conn, lifnr, user, flag=True):
    with transaction(conn):
        v = _vend(conn, lifnr)
        conn.execute("UPDATE vendor SET loevm=? WHERE lifnr=?", (1 if flag else 0, v["lifnr"]))
        cd.log(conn, "KRED", v["lifnr"], "XK06", user,
               [("LFA1", v["lifnr"], "loevm", v["loevm"], 1 if flag else 0)])
    return _open_balance(conn, "K", v["lifnr"])


def change_vendor_group(conn, lifnr, ktokk, user):
    ktokk = ktokk.upper()
    g = VEND_GROUPS.get(ktokk)
    if not g:
        raise MMError("Account group %s does not exist (OBD3)" % ktokk, "F2", "004")
    with transaction(conn):
        v = _vend(conn, lifnr)
        lo, hi, _ = VEND_RANGES[g["nr"]]
        if not (len(v["lifnr"]) == len(lo) and lo <= v["lifnr"] <= hi):
            raise MMError("Vendor %s is not in the number interval %s-%s of account group %s"
                          % (v["lifnr"], lo, hi, ktokk), "F2", "016")
        conn.execute("UPDATE vendor SET ktokk=? WHERE lifnr=?", (ktokk, v["lifnr"]))
        cd.log(conn, "KRED", v["lifnr"], "XK07", user,
               [("LFA1", v["lifnr"], "ktokk", v["ktokk"], ktokk)])


def _vend(conn, lifnr):
    v = conn.execute("SELECT * FROM vendor WHERE lifnr=?", (_s(lifnr).upper(),)).fetchone()
    if not v:
        raise MMError("Vendor %s does not exist" % lifnr, "F2", "103")
    return v


def get_vendor(conn, lifnr):
    v = dict(_vend(conn, lifnr))
    k = v["lifnr"]
    v["ktokk_text"] = VEND_GROUPS.get(v["ktokk"] or "0001", {}).get("text", "")
    v["cin"] = _one(conn, "SELECT * FROM md_cin_vend WHERE lifnr=?", (k,))
    v["sensitive"] = rows(conn.execute("SELECT * FROM md_sensitive WHERE koart='K' AND "
                                       "objectid=? ORDER BY id DESC", (k,)))
    v.update(_open_balance(conn, "K", k))
    from md.checks import payment_exception
    v["payment_exception"] = payment_exception(conn, k)
    v["po_volume"] = conn.execute(
        "SELECT COALESCE(SUM(CAST(i.menge AS INTEGER) * i.netpr / i.peinh / 1000),0) FROM "
        "po_item i JOIN po_header h USING (ebeln) WHERE h.lifnr=? AND COALESCE(i.loekz,0)=0",
        (k,)).fetchone()[0]
    v["pos"] = rows(conn.execute(
        "SELECT h.ebeln, h.bedat, COUNT(*) AS items, h.frgke FROM po_header h JOIN po_item i "
        "USING (ebeln) WHERE h.lifnr=? GROUP BY h.ebeln ORDER BY h.ebeln DESC LIMIT 20", (k,)))
    v["info_records"] = rows(conn.execute("SELECT infnr, matnr, brutto AS netpr, peinh, aplfz FROM info_record "
                                          "WHERE lifnr=?", (k,))) \
        if conn.execute("SELECT 1 FROM sqlite_master WHERE name='info_record'").fetchone() else []
    v["blocked"] = bool(v["sperr"] or v["sperm"] or v["zahls"])
    return v


def vendors(conn, ktokk="", land="", blocked=False):
    sql = "SELECT * FROM vendor WHERE 1=1"
    args = []
    if ktokk:
        sql += " AND ktokk=?"
        args.append(ktokk)
    if land:
        sql += " AND land=?"
        args.append(land)
    from md.checks import payment_exception
    res = []
    for v in rows(conn.execute(sql + " ORDER BY lifnr", args)):
        v.update(_open_balance(conn, "K", v["lifnr"]))
        v["blocked"] = bool(v["sperr"] or v["sperm"] or v["zahls"])
        v["group_text"] = VEND_GROUPS.get(v["ktokk"] or "0001", {}).get("text", "")
        v["payment_exception"] = payment_exception(conn, v["lifnr"]) or ""
        if not blocked or v["blocked"] or v["loevm"]:
            res.append(v)
    return res


# ====================================================================== FK08 / FD08
def sensitive_list(conn, koart=None, status="P"):
    sql = "SELECT s.* FROM md_sensitive s WHERE 1=1"
    args = []
    if koart:
        sql += " AND koart=?"
        args.append(koart)
    if status:
        sql += " AND status=?"
        args.append(status)
    out = rows(conn.execute(sql + " ORDER BY id DESC", args))
    for r in out:
        t = "vendor" if r["koart"] == "K" else "customer"
        k = "lifnr" if r["koart"] == "K" else "kunnr"
        n = conn.execute("SELECT name FROM %s WHERE %s=?" % (t, k), (r["objectid"],)).fetchone()
        r["name"] = n["name"] if n else ""
        r["details"] = rows(conn.execute(
            "SELECT p.fname, p.value_old, p.value_new FROM md_cdpos p JOIN md_cdhdr h ON "
            "h.changenr=p.changenr WHERE h.objectclas=? AND h.objectid=? AND p.fname IN (%s) "
            "AND h.udate>=substr(?,1,10) ORDER BY h.changenr" % ",".join("?" * len(r["fields"].split(","))),
            ["KRED" if r["koart"] == "K" else "DEBI", r["objectid"]] + r["fields"].split(",")
            + [r["changed_at"]]))
        if r["koart"] == "K":
            r["open_balance"] = _open_balance(conn, "K", r["objectid"])["open_balance"]
    return out


def confirm_sensitive(conn, koart, objectid, user, reject=False):
    """FK08/FD08: a second person confirms (or rejects) the changes.
    Rejecting restores the old values from the change documents."""
    with transaction(conn):
        p = conn.execute("SELECT * FROM md_sensitive WHERE koart=? AND objectid=? AND "
                         "status='P'", (koart, objectid)).fetchone()
        if not p:
            raise MMError("No unconfirmed changes for %s" % objectid, "F2", "060")
        if p["changed_by"] == user:
            raise MMError("Changes cannot be confirmed by the user who made them (%s) - "
                          "dual control" % user, "F2", "061")
        if reject:
            table, key, oc = ("vendor", "lifnr", "KRED") if koart == "K" else \
                ("customer", "kunnr", "DEBI")
            first = {}
            for r in conn.execute(
                    "SELECT p.fname, p.value_old FROM md_cdpos p JOIN md_cdhdr h ON "
                    "h.changenr=p.changenr WHERE h.objectclas=? AND h.objectid=? AND "
                    "h.udate>=substr(?,1,10) ORDER BY h.changenr", (oc, objectid,
                                                                    p["changed_at"])):
                if r["fname"] in p["fields"].split(",") and r["fname"] not in first:
                    first[r["fname"]] = r["value_old"]
            for f, old in first.items():
                conn.execute("UPDATE %s SET %s=? WHERE %s=?" % (table, f, key),
                             (int(old) if f == "klimk" and old else old, objectid))
            cd.log(conn, oc, objectid, "FK08" if koart == "K" else "FD08", user,
                   [("LFA1" if koart == "K" else "KNA1", objectid, f, "rejected", v)
                    for f, v in first.items()])
        conn.execute("UPDATE md_sensitive SET status=?, confirmed_by=?, confirmed_at=? WHERE id=?",
                     ("R" if reject else "C", user, now_ts(), p["id"]))
    return {"objectid": objectid, "status": "R" if reject else "C"}


# ====================================================================== J1ID
def save_cin_customer(conn, kunnr, data, user):
    with transaction(conn):
        c = _cust(conn, kunnr)
        if c["land"] != "IN":
            raise MMError("CIN details are only for customers in India (country %s)" % c["land"],
                          "J1I", "020")
        pan = _s(data.get("pan")).upper()
        check_pan(pan)
        gstin = check_gstin(data.get("gstin"), pan)
        old = conn.execute("SELECT * FROM md_cin_cust WHERE kunnr=?", (c["kunnr"],)).fetchone()
        conn.execute("INSERT OR REPLACE INTO md_cin_cust VALUES (?,?,?,?,?,?,?)",
                     (c["kunnr"], gstin, pan, _s(data.get("excise_reg")).upper(),
                      _s(data.get("ecc_no")).upper(), _s(data.get("cst_no")).upper(),
                      1 if data.get("exempt") else 0))
        cd.log(conn, "DEBI", c["kunnr"], "J1ID", user,
               [("J_1IMOCUST", c["kunnr"], "gstin", old["gstin"] if old else "", gstin),
                ("J_1IMOCUST", c["kunnr"], "pan", old["pan"] if old else "", pan)],
               "U" if old else "I")


def save_cin_vendor(conn, lifnr, data, user):
    with transaction(conn):
        v = _vend(conn, lifnr)
        if v["land"] != "IN":
            raise MMError("CIN details are only for vendors in India (country %s)" % v["land"],
                          "J1I", "020")
        pan = _s(data.get("pan")).upper()
        check_pan(pan)
        gstin = check_gstin(data.get("gstin"), pan)
        vtype = _s(data.get("vtype")).upper()
        if vtype not in CIN_VENDOR_TYPES:
            raise MMError("Vendor type %s not allowed (MA, DE, FS, SS, IM)" % vtype, "J1I", "021")
        ssi = _s(data.get("ssi"))
        if ssi not in SSI_STATUS:
            raise MMError("SSI status %s not allowed" % ssi, "J1I", "022")
        old = conn.execute("SELECT * FROM md_cin_vend WHERE lifnr=?", (v["lifnr"],)).fetchone()
        conn.execute("INSERT OR REPLACE INTO md_cin_vend VALUES (?,?,?,?,?,?,?,?)",
                     (v["lifnr"], gstin, pan, vtype, ssi, _s(data.get("excise_reg")).upper(),
                      _s(data.get("ecc_no")).upper(), 0 if data.get("cenvat") in (0, "0", False) else 1))
        cd.log(conn, "KRED", v["lifnr"], "J1ID", user,
               [("J_1IMOVEND", v["lifnr"], "gstin", old["gstin"] if old else "", gstin),
                ("J_1IMOVEND", v["lifnr"], "pan", old["pan"] if old else "", pan)],
               "U" if old else "I")


def number_ranges(conn):
    out = []
    for kind, groups, ranges, table, key in (("Customer", CUST_GROUPS, CUST_RANGES, "customer", "kunnr"),
                                             ("Vendor", VEND_GROUPS, VEND_RANGES, "vendor", "lifnr")):
        for nr, (lo, hi, ext) in ranges.items():
            cur = conn.execute("SELECT MAX(%s), COUNT(*) FROM %s WHERE length(%s)=? AND %s "
                               "BETWEEN ? AND ?" % (key, table, key, key),
                               (len(lo), lo, hi)).fetchone()
            out.append(dict(kind=kind, nr=nr, frm=lo, to=hi, ext="X" if ext else "",
                            current=cur[0] or "", used=cur[1],
                            groups=", ".join("%s %s" % (k, g["text"]) for k, g in groups.items()
                                             if g["nr"] == nr)))
    return out


def _one(conn, sql, args):
    r = conn.execute(sql, args).fetchone()
    return dict(r) if r else None
