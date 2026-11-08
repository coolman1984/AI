"""Condition technique (VK11 / VK12 / VK13 / V/LD) and pricing procedure.

Access sequence: the most specific table first (A305 customer/material before
A304 material). Scales: the highest scale quantity not above the item quantity.
Pricing procedure RVAA01 (domestic) / RVAA02 (export, no output tax):

  PR00 price x qty             = gross (KZWI1)
  K004 material discount / unit, K005 cust/mat %, K007 customer %, ZDEA deal %,
  RA01 manual %                -> discounts (KZWI2)
  net value                    = gross - discounts
  KF00 freight % for DAP / DDP / CIF incoterms
  MWST 14 % if customer tax class 1 and material tax class 1 (RVAA01 only)
  VPRS cost (standard or moving price) - statistical, gives the margin
"""
import json

from mm.db import rows, transaction
from mm.util import MMError, now_ts, parse_amount, parse_date, rdiv, value_of

from .config import COND_TYPES, FREIGHT_INCOTERMS, PRICING_DETERMINATION, PRICING_PROCS


def save_condition(conn, kschl, kotab, data, user=""):
    """VK11: data kunnr / matnr / inco1, kbetr (amount EGP or %), datab, datbi,
    scales [{from, kbetr}], knuma (deal)."""
    kschl = kschl.upper()
    ct = COND_TYPES.get(kschl)
    if not ct:
        raise MMError("Condition type %s does not exist (V/06)" % kschl, "VK", "001")
    if kotab not in ct["access"] and not (kschl == "ZLAB" and kotab == "A304"):
        raise MMError("Table %s is not in the access sequence of %s" % (kotab, kschl), "VK", "002")
    kunnr = (data.get("kunnr") or "").upper() or None
    matnr = (data.get("matnr") or "").upper() or None
    if kotab in ("A305", "A307") and not kunnr:
        raise MMError("Enter a customer", "VK", "003")
    if kotab in ("A305", "A304") and not matnr and kschl != "ZLAB":
        raise MMError("Enter a material", "VK", "004")
    pct = ct["calc"] == "A"
    kbetr = int(round(float(data.get("kbetr")) * 100)) if data.get("kbetr") not in (None, "") else None
    if kbetr is None:
        raise MMError("Enter a rate / amount", "VK", "005")
    if pct and not 0 <= kbetr <= 10000:
        raise MMError("Percentage must be between 0 and 100", "VK", "006")
    datab = parse_date(data.get("datab"))
    datbi = parse_date(data.get("datbi") or "9999-12-31")
    if datbi < datab:
        raise MMError("Valid-to is before valid-from", "VK", "007")
    scales = []
    for s in data.get("scales") or []:
        if s.get("from") not in (None, "") and s.get("kbetr") not in (None, ""):
            scales.append([int(round(float(s["from"]) * 1000)), int(round(float(s["kbetr"]) * 100))])
    if scales and not ct["scales"]:
        raise MMError("Condition type %s does not allow scales" % kschl, "VK", "008")
    scales.sort()
    with transaction(conn):
        if kunnr and not conn.execute("SELECT 1 FROM customer WHERE kunnr=?", (kunnr,)).fetchone():
            raise MMError("Customer %s does not exist" % kunnr, "VK", "009")
        if matnr and not conn.execute("SELECT 1 FROM material WHERE matnr=?", (matnr,)).fetchone():
            raise MMError("Material %s does not exist" % matnr, "VK", "010")
        # a new record limits overlapping older ones (like SAP: new validity wins)
        conn.execute("UPDATE sd_cond SET loevm=1 WHERE kschl=? AND kotab=? AND COALESCE(kunnr,'')=? "
                     "AND COALESCE(matnr,'')=? AND COALESCE(inco1,'')=? AND datab=? AND loevm=0",
                     (kschl, kotab, kunnr or "", matnr or "", data.get("inco1") or "", datab))
        cur = conn.execute("INSERT INTO sd_cond (kschl,kotab,vkorg,vtweg,kunnr,matnr,inco1,datab,datbi,"
                           "kbetr,konwa,kpein,scales,knuma,ernam,erdat) VALUES "
                           "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                           (kschl, kotab, "1000", data.get("vtweg") or "", kunnr, matnr,
                            data.get("inco1") or None, datab, datbi, kbetr, "%" if pct else "EGP",
                            1, json.dumps(scales) if scales else "", data.get("knuma") or None,
                            user, now_ts()[:10]))
    return cur.lastrowid


def conditions(conn, kschl=None, kunnr=None, matnr=None, valid_on=None):
    sql = "SELECT * FROM sd_cond WHERE loevm=0"
    args = []
    for col, v in (("kschl", kschl), ("kunnr", kunnr), ("matnr", matnr)):
        if v:
            sql += " AND %s=?" % col
            args.append(v.upper())
    if valid_on:
        sql += " AND datab<=? AND datbi>=?"
        args += [valid_on, valid_on]
    out = rows(conn.execute(sql + " ORDER BY kschl, kotab, kunnr, matnr, datab", args))
    for r in out:
        r["scales"] = json.loads(r["scales"]) if r["scales"] else []
    return out


def find(conn, kschl, kunnr, matnr, day, inco1=None, vtweg=None):
    """Access sequence: returns (record, table) or (None, None)."""
    for tab in COND_TYPES[kschl]["access"]:
        q = "SELECT * FROM sd_cond WHERE kschl=? AND kotab=? AND loevm=0 AND datab<=? AND datbi>=?"
        a = [kschl, tab, day, day]
        if tab in ("A305", "A307"):
            q += " AND kunnr=?"
            a.append(kunnr)
        if tab in ("A305", "A304"):
            q += " AND matnr=?"
            a.append(matnr)
        if tab == "A900":
            q += " AND inco1=?"
            a.append(inco1)
        r = conn.execute(q + " ORDER BY datab DESC, knumh DESC LIMIT 1", a).fetchone()
        if r:
            return r, tab
    return None, None


def _scale(rec, qty):
    if not rec["scales"]:
        return rec["kbetr"]
    best = rec["kbetr"]
    for frm, val in json.loads(rec["scales"]):
        if qty >= frm:
            best = val
    return best


def price_item(conn, cust, area, matnr, qty, day, werks="1000", manual_disc=None, price=None,
               free=False, inco1=None, vbtyp="C"):
    """Returns dict(conds=[...], gross, disc, net, freight, tax, cost, netpr, mwskz)."""
    proc = PRICING_PROCS[PRICING_DETERMINATION.get((area or {}).get("kalks") or "1", "RVAA01")]
    kunnr = cust["kunnr"]
    conds = []
    v = conn.execute("SELECT * FROM valuation WHERE matnr=? AND bwkey=?", (matnr, werks)).fetchone() \
        if matnr else None
    cost = value_of(qty, (v["stprs"] if v["vprsv"] == "S" else v["verpr"]), v["peinh"]) if v else 0
    if free:
        conds.append(dict(stunr=900, kschl="VPRS", krech="C", kbetr=cost * 1000 // qty if qty else 0,
                          kwert=cost, kinak="", manual=0, knumh=None))
        return dict(conds=conds, gross=0, disc=0, net=0, freight=0, tax=0, cost=cost, netpr=0,
                    mwskz="A0", proc=proc)
    gross = 0
    disc = 0
    for step, k in enumerate(proc, start=1):
        st = step * 10
        if vbtyp in ("K", "L") and k in ("K004", "K005", "K007", "ZDEA", "KF00"):
            continue                       # credit / debit memo: the agreed amount only
        if vbtyp == "H" and k == "KF00":
            continue                       # returns: no freight credit
        if k == "PR00":
            if price is not None:
                rate, knumh, manual = price, None, 1
            else:
                rec, _ = find(conn, "PR00", kunnr, matnr, day)
                if not rec:
                    raise MMError("Pricing error: mandatory condition PR00 is missing for %s "
                                  "(VK11)" % matnr, "V1", "805")
                rate, knumh, manual = _scale(rec, qty), rec["knumh"], 0
            gross = value_of(qty, rate, 1)
            conds.append(dict(stunr=st, kschl=k, krech="C", kbetr=rate, kwert=gross, kinak="",
                              manual=manual, knumh=knumh))
        elif k in ("K004",):
            rec, _ = find(conn, k, kunnr, matnr, day)
            if rec:
                rate = _scale(rec, qty)
                w = value_of(qty, rate, 1)
                disc += w
                conds.append(dict(stunr=st, kschl=k, krech="C", kbetr=-rate, kwert=-w, kinak="",
                                  manual=0, knumh=rec["knumh"]))
        elif k in ("K005", "K007", "ZDEA"):
            rec, _ = find(conn, k, kunnr, matnr, day)
            if rec:
                w = rdiv(gross * rec["kbetr"], 10000)
                disc += w
                conds.append(dict(stunr=st, kschl=k, krech="A", kbetr=-rec["kbetr"], kwert=-w,
                                  kinak="", manual=0, knumh=rec["knumh"]))
        elif k == "RA01" and manual_disc:
            bp = int(round(float(manual_disc) * 100))
            if not 0 < bp < 10000:
                raise MMError("Manual discount must be between 0 and 100 %", "V1", "806")
            w = rdiv(gross * bp, 10000)
            disc += w
            conds.append(dict(stunr=st, kschl=k, krech="A", kbetr=-bp, kwert=-w, kinak="", manual=1,
                              knumh=None))
    net = gross - disc
    freight = 0
    if "KF00" in proc and inco1 in FREIGHT_INCOTERMS and vbtyp not in ("H", "K", "L"):
        rec, _ = find(conn, "KF00", kunnr, matnr, day, inco1=inco1)
        bp = rec["kbetr"] if rec else FREIGHT_INCOTERMS[inco1]
        freight = rdiv(net * bp, 10000)
        conds.append(dict(stunr=70, kschl="KF00", krech="A", kbetr=bp, kwert=freight, kinak="",
                          manual=0, knumh=rec["knumh"] if rec else None))
    tax = 0
    mwskz = "A0"
    if "MWST" in proc:
        m = conn.execute("SELECT taxm1 FROM md_mvke WHERE matnr=? AND vkorg='1000' AND vtweg=?",
                         (matnr, (area or {}).get("vtweg") or "10")).fetchone() if matnr else None
        taxm = (m["taxm1"] if m else "1") or "1"
        taxk = (area or {}).get("taxkd") or "1"
        if taxm == "1" and taxk == "1":
            mwskz = "A1"
            tax = rdiv((net + freight) * 1400, 10000)
            conds.append(dict(stunr=80, kschl="MWST", krech="A", kbetr=1400, kwert=tax, kinak="",
                              manual=0, knumh=None))
    conds.append(dict(stunr=90, kschl="VPRS", krech="C", kbetr=cost * 1000 // qty if qty else 0,
                      kwert=cost, kinak="", manual=0, knumh=None))
    return dict(conds=conds, gross=gross, disc=disc, net=net, freight=freight, tax=tax, cost=cost,
                netpr=net * 1000 // qty if qty else 0, mwskz=mwskz, proc=proc)


def store(conn, knumv, kposn, conds):
    conn.execute("DELETE FROM sd_konv WHERE knumv=? AND kposn=?", (knumv, kposn))
    for c in conds:
        conn.execute("INSERT INTO sd_konv (knumv,kposn,stunr,kschl,krech,kbetr,kwert,kinak,manual,"
                     "knumh) VALUES (?,?,?,?,?,?,?,?,?,?)",
                     (knumv, kposn, c["stunr"], c["kschl"], c["krech"], c["kbetr"], c["kwert"],
                      c["kinak"], c["manual"], c["knumh"]))


def item_conditions(conn, knumv, kposn=None):
    sql = "SELECT * FROM sd_konv WHERE knumv=?"
    args = [knumv]
    if kposn is not None:
        sql += " AND kposn=?"
        args.append(kposn)
    out = rows(conn.execute(sql + " ORDER BY kposn, stunr", args))
    for c in out:
        c["text"] = COND_TYPES.get(c["kschl"], {}).get("text", "")
    return out


def pricing_report(conn, kschl=None, valid_on=None):
    """V/LD: condition records with their validity, scales and the deal."""
    out = conditions(conn, kschl, valid_on=valid_on)
    names = {r["matnr"]: r["maktx"] for r in conn.execute("SELECT matnr, maktx FROM material")}
    cust = {r["kunnr"]: r["name"] for r in conn.execute("SELECT kunnr, name FROM customer")}
    for r in out:
        r["maktx"] = names.get(r["matnr"], "")
        r["name"] = cust.get(r["kunnr"], "")
        r["text"] = COND_TYPES[r["kschl"]]["text"]
    return out
