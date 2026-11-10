"""Sources of supply.

ME11/ME12  purchasing info record: gross price (PB00), discount (RA01),
           freight (FRB1), planned delivery time, vendor material number
ME01       source list: allowed / fixed / blocked vendors per material
MEQ1       quota arrangement: split of requirements between vendors
ME31K      outline agreement (quantity contract MK / value contract WK)
ME41/ME47/ME49  RFQ, quotation entry, price comparison, award

Source determination (like SAP, when a requisition is assigned):
  1. valid contract in the source list (or any valid contract)
  2. fixed vendor in the source list
  3. quota arrangement: vendor with the lowest quota rating
     (allocated quantity + requirement) / quota
  4. cheapest valid info record of an allowed (not blocked) vendor
"""
import datetime

from mm.db import next_number, rows, transaction
from mm.util import MMError, now_ts, parse_amount, parse_date, parse_qty, rdiv, value_of
from mm import util as mmclock  # noqa: E402


def net_price(brutto, rabatt):
    """PB00 gross minus RA01 discount (1/100 %)."""
    return brutto - rdiv(brutto * (rabatt or 0), 10000)


# ====================================================================== info record
def save_info_record(conn, lifnr, matnr, brutto, peinh=1, rabatt=0, frb=0, aplfz=7,
                     norbm=0, idnlf="", werks="1000", datab=None):
    lifnr, matnr = lifnr.upper(), matnr.upper()
    with transaction(conn):
        if not conn.execute("SELECT 1 FROM vendor WHERE lifnr=?", (lifnr,)).fetchone():
            raise MMError("Vendor %s does not exist" % lifnr, "06", "301")
        if not conn.execute("SELECT 1 FROM material_plant WHERE matnr=? AND werks=?",
                            (matnr, werks)).fetchone():
            raise MMError("Material %s not maintained in plant %s" % (matnr, werks),
                          "06", "302")
        b = brutto if isinstance(brutto, int) else parse_amount(brutto)
        r = rabatt if isinstance(rabatt, int) else int(round(float(rabatt or 0) * 100))
        f = frb if isinstance(frb, int) else parse_amount(frb or "0", allow_zero=True)
        ex = conn.execute("SELECT infnr FROM info_record WHERE lifnr=? AND matnr=? AND "
                          "werks=?", (lifnr, matnr, werks)).fetchone()
        if ex:
            conn.execute("UPDATE info_record SET brutto=?, rabatt=?, frb=?, peinh=?, aplfz=?,"
                         " norbm=?, idnlf=COALESCE(NULLIF(?,''),idnlf), datab=? WHERE "
                         "infnr=?", (b, r, f, int(peinh), int(aplfz),
                                     parse_qty(norbm or "0", allow_zero=True)
                                     if not isinstance(norbm, int) else norbm,
                                     idnlf, datab or now_ts()[:10], ex["infnr"]))
            return ex["infnr"]
        infnr = str(next_number(conn, "INFO"))
        conn.execute("INSERT INTO info_record (infnr,lifnr,matnr,werks,brutto,rabatt,frb,"
                     "peinh,aplfz,norbm,idnlf,datab) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                     (infnr, lifnr, matnr, werks, b, r, f, int(peinh), int(aplfz),
                      parse_qty(norbm or "0", allow_zero=True) if not isinstance(norbm, int)
                      else norbm, idnlf, datab or now_ts()[:10]))
        return infnr


def info_records(conn, matnr=None, lifnr=None):
    sql = ("SELECT i.*, v.name, m.maktx, m.meins FROM info_record i JOIN vendor v ON "
           "v.lifnr=i.lifnr JOIN material m ON m.matnr=i.matnr WHERE i.loekz=0")
    args = []
    if matnr:
        sql += " AND i.matnr=?"
        args.append(matnr.upper())
    if lifnr:
        sql += " AND i.lifnr=?"
        args.append(lifnr.upper())
    out = rows(conn.execute(sql + " ORDER BY i.matnr, i.lifnr", args))
    for r in out:
        r["netpr"] = net_price(r["brutto"], r["rabatt"])
    return out


# ====================================================================== source list
def save_source_list(conn, matnr, werks, entries):
    """entries: [{lifnr, vdatu, bdatu, flifn, notkz, konnr}]"""
    matnr = matnr.upper()
    with transaction(conn):
        conn.execute("DELETE FROM source_list WHERE matnr=? AND werks=?", (matnr, werks))
        if sum(1 for e in entries if e.get("flifn")) > 1:
            raise MMError("Only one fixed source per period is allowed", "06", "250")
        for n, e in enumerate(entries, start=1):
            if not conn.execute("SELECT 1 FROM vendor WHERE lifnr=?",
                                (e["lifnr"],)).fetchone():
                raise MMError("Vendor %s does not exist" % e["lifnr"], "06", "301")
            conn.execute("INSERT INTO source_list VALUES (?,?,?,?,?,?,?,?,?)",
                         (matnr, werks, n, e["lifnr"].upper(),
                          parse_date(e.get("vdatu") or "2000-01-01"),
                          parse_date(e.get("bdatu") or "9999-12-31"),
                          1 if e.get("flifn") else 0, 1 if e.get("notkz") else 0,
                          e.get("konnr") or None))


def save_quota(conn, matnr, werks, entries):
    """entries: [{lifnr, quote}] - quota numbers (e.g. 60 / 40)"""
    matnr = matnr.upper()
    with transaction(conn):
        old = {r["lifnr"]: r for r in conn.execute("SELECT * FROM quota WHERE matnr=? AND "
                                                   "werks=?", (matnr, werks))}
        conn.execute("DELETE FROM quota WHERE matnr=? AND werks=?", (matnr, werks))
        for e in entries:
            o = old.get(e["lifnr"])
            conn.execute("INSERT INTO quota VALUES (?,?,?,?,?,?)",
                         (matnr, werks, e["lifnr"].upper(), int(e["quote"]),
                          o["qubmg"] if o else 0, o["basmg"] if o else 0))


# ====================================================================== contract
def create_contract(conn, data, user):
    """ME31K: lifnr, bsart MK/WK, kdatb, kdate, ktwrt (target value, WK),
    items [{matnr, ktmng, netpr, peinh}]"""
    bsart = (data.get("bsart") or "MK").upper()
    with transaction(conn):
        v = conn.execute("SELECT * FROM vendor WHERE lifnr=?",
                         ((data.get("lifnr") or "").upper(),)).fetchone()
        if not v:
            raise MMError("Vendor %s does not exist" % data.get("lifnr"), "06", "301")
        konnr = str(next_number(conn, "CONTRACT"))
        conn.execute("INSERT INTO contract VALUES (?,?,?,?,?,?,?,?,?,?,?,0)",
                     (konnr, bsart, v["lifnr"], "1000", data.get("ekgrp") or "001",
                      parse_date(data.get("kdatb")), parse_date(data.get("kdate")),
                      parse_amount(data.get("ktwrt") or "0", allow_zero=True),
                      v["zterm"], user, now_ts()[:10]))
        for n, it in enumerate(data.get("items") or [], start=1):
            conn.execute("INSERT INTO contract_item VALUES (?,?,?,?,?,?,?)",
                         (konnr, n * 10, it["matnr"].upper(), it.get("werks") or "1000",
                          parse_qty(it.get("ktmng") or "0", allow_zero=True),
                          parse_amount(it["netpr"]), int(it.get("peinh") or 1)))
    return konnr


def contract_status(conn, konnr=None):
    """ME3M / ME33K: target vs released (call-offs = PO items with reference)."""
    sql = ("SELECT c.*, v.name, i.ktpnr, i.matnr, m.maktx, m.meins, i.ktmng, i.netpr, "
           "i.peinh FROM contract c JOIN vendor v ON v.lifnr=c.lifnr JOIN contract_item i "
           "ON i.konnr=c.konnr JOIN material m ON m.matnr=i.matnr")
    args = []
    if konnr:
        sql += " WHERE c.konnr=?"
        args.append(konnr)
    out = []
    for r in conn.execute(sql + " ORDER BY c.konnr, i.ktpnr", args):
        rel = conn.execute("SELECT COALESCE(SUM(menge),0) AS q, COALESCE(SUM(menge*netpr/"
                           "(1000*peinh)),0) AS v FROM po_item WHERE konnr=? AND ktpnr=? AND "
                           "loekz=0", (r["konnr"], r["ktpnr"])).fetchone()
        d = dict(r)
        d["released_qty"] = rel["q"]
        d["released_val"] = int(rel["v"])
        d["open_qty"] = max(r["ktmng"] - rel["q"], 0)
        d["target_val"] = value_of(r["ktmng"], r["netpr"], r["peinh"]) if r["ktmng"] \
            else r["ktwrt"]
        d["pct"] = round(rel["q"] / r["ktmng"] * 100, 1) if r["ktmng"] else None
        out.append(d)
    return out


# ====================================================================== RFQ
def create_rfq(conn, data, user):
    """ME41: one RFQ per vendor under one collective number.
    data: matnr, menge, werks, lfdat, angdt (deadline), vendors[], banfn, bnfpo"""
    vendors = [v.upper() for v in data.get("vendors") or []]
    if len(vendors) < 1:
        raise MMError("Enter at least one vendor", "06", "310")
    with transaction(conn):
        submi = "COLL-%04d" % next_number(conn, "SUBMI")
        out = []
        for v in vendors:
            if not conn.execute("SELECT 1 FROM vendor WHERE lifnr=?", (v,)).fetchone():
                raise MMError("Vendor %s does not exist" % v, "06", "301")
            anfnr = str(next_number(conn, "RFQ"))
            conn.execute("INSERT INTO rfq (anfnr,submi,lifnr,matnr,werks,menge,lfdat,angdt,"
                         "ekgrp,statu,banfn,bnfpo,ernam,erdat) VALUES "
                         "(?,?,?,?,?,?,?,?,?,'O',?,?,?,?)",
                         (anfnr, submi, v, data["matnr"].upper(), data.get("werks") or "1000",
                          parse_qty(data["menge"]), parse_date(data.get("lfdat")),
                          parse_date(data.get("angdt")), data.get("ekgrp") or "001",
                          data.get("banfn"), data.get("bnfpo"), user, now_ts()[:10]))
            out.append(anfnr)
    return {"submi": submi, "rfqs": out}


def enter_quotation(conn, anfnr, netpr, aplfz, quodt=None):
    """ME47"""
    with transaction(conn):
        r = conn.execute("SELECT * FROM rfq WHERE anfnr=?", (anfnr,)).fetchone()
        if not r:
            raise MMError("RFQ %s does not exist" % anfnr, "06", "311")
        if r["statu"] in ("A", "R"):
            raise MMError("RFQ %s is already closed" % anfnr, "06", "312")
        conn.execute("UPDATE rfq SET netpr=?, aplfz=?, quodt=?, statu='Q' WHERE anfnr=?",
                     (parse_amount(netpr), int(aplfz or 7), parse_date(quodt), anfnr))


def price_comparison(conn, submi):
    """ME49: quotations ranked by price; savings vs average quotation."""
    q = rows(conn.execute("SELECT r.*, v.name FROM rfq r JOIN vendor v ON v.lifnr=r.lifnr "
                          "WHERE submi=? ORDER BY CASE WHEN netpr IS NULL THEN 1 ELSE 0 END, "
                          "netpr", (submi,)))
    if not q:
        raise MMError("Collective number %s does not exist" % submi, "06", "313")
    quoted = [x for x in q if x["netpr"]]
    avg = sum(x["netpr"] for x in quoted) / len(quoted) if quoted else 0
    best = quoted[0]["netpr"] if quoted else 0
    for n, x in enumerate(q, start=1):
        x["rank"] = n if x["netpr"] else None
        x["value"] = value_of(x["menge"], x["netpr"], x["peinh"]) if x["netpr"] else None
        x["pct_of_avg"] = round(x["netpr"] / avg * 100, 1) if x["netpr"] and avg else None
        x["pct_of_best"] = round(x["netpr"] / best * 100, 1) if x["netpr"] and best else None
    return {"submi": submi, "items": q, "average": int(avg), "best": best,
            "saving_vs_avg": value_of(q[0]["menge"], int(avg) - best, 1) if quoted else 0}


def award(conn, anfnr, user, bedat=None):
    """Accept a quotation: info record + purchase order; reject the others."""
    from .po import create_po
    with transaction(conn):
        r = conn.execute("SELECT * FROM rfq WHERE anfnr=?", (anfnr,)).fetchone()
        if not r or r["statu"] != "Q":
            raise MMError("RFQ %s has no quotation to accept" % anfnr, "06", "314")
        save_info_record(conn, r["lifnr"], r["matnr"], r["netpr"], r["peinh"], 0, 0,
                         r["aplfz"] or 7, werks=r["werks"])
        bedat = parse_date(bedat)
        ebeln = create_po(conn, {"lifnr": r["lifnr"], "bedat": bedat, "ekgrp": r["ekgrp"],
                                 "angnr": anfnr, "items": [{
                                     "matnr": r["matnr"], "werks": r["werks"],
                                     "menge": str(r["menge"] / 1000.0),
                                     "netpr": "%.2f" % (r["netpr"] / 100.0),
                                     "eindt": r["lfdat"], "banfn": r["banfn"],
                                     "bnfpo": r["bnfpo"]}]}, user)
        conn.execute("UPDATE rfq SET statu='A', ebeln=? WHERE anfnr=?", (ebeln, anfnr))
        conn.execute("UPDATE rfq SET statu='R' WHERE submi=? AND anfnr<>?",
                     (r["submi"], anfnr))
    return ebeln


# ====================================================================== source determination
def determine_source(conn, matnr, werks, qty, date=None):
    """Returns dict(lifnr, how, infnr, konnr, ktpnr, brutto, rabatt, frb, peinh,
    aplfz) or None."""
    date = date or mmclock.today().isoformat()
    sl = conn.execute("SELECT * FROM source_list WHERE matnr=? AND werks=? AND vdatu<=? AND "
                      "bdatu>=? AND notkz=0 ORDER BY flifn DESC, zeord",
                      (matnr, werks, date, date)).fetchall()
    blocked = {r["lifnr"] for r in conn.execute(
        "SELECT lifnr FROM source_list WHERE matnr=? AND werks=? AND notkz=1", (matnr, werks))}
    allowed = {r["lifnr"] for r in sl}

    def info(lifnr):
        return conn.execute("SELECT * FROM info_record WHERE lifnr=? AND matnr=? AND "
                            "werks=? AND loekz=0", (lifnr, matnr, werks)).fetchone()

    def result(lifnr, how, konnr=None, ktpnr=None, price=None):
        i = info(lifnr)
        return dict(lifnr=lifnr, how=how, infnr=i["infnr"] if i else None, konnr=konnr,
                    ktpnr=ktpnr, brutto=price if price is not None else (i["brutto"] if i
                                                                         else None),
                    rabatt=0 if price is not None else (i["rabatt"] if i else 0),
                    frb=i["frb"] if i and price is None else 0,
                    peinh=i["peinh"] if i else 1, aplfz=i["aplfz"] if i else 7)
    # 1. contract
    for c in conn.execute("SELECT c.konnr, c.lifnr, i.ktpnr, i.netpr, i.ktmng FROM contract c "
                          "JOIN contract_item i ON i.konnr=c.konnr WHERE i.matnr=? AND "
                          "i.werks=? AND c.kdatb<=? AND c.kdate>=? AND c.loekz=0",
                          (matnr, werks, date, date)).fetchall():
        if c["lifnr"] in blocked or (allowed and c["lifnr"] not in allowed):
            continue
        st = contract_status(conn, c["konnr"])
        st = [s for s in st if s["ktpnr"] == c["ktpnr"]][0]
        if not c["ktmng"] or st["open_qty"] >= qty:
            return result(c["lifnr"], "Contract %s" % c["konnr"], c["konnr"], c["ktpnr"],
                          c["netpr"])
    # 2. fixed source
    for r in sl:
        if r["flifn"]:
            return result(r["lifnr"], "Fixed source (source list)")
    # 3. quota arrangement
    qs = conn.execute("SELECT * FROM quota WHERE matnr=? AND werks=? AND quote>0",
                      (matnr, werks)).fetchall()
    qs = [q for q in qs if q["lifnr"] not in blocked]
    if qs:
        best = min(qs, key=lambda q: ((q["qubmg"] + qty) / q["quote"], q["lifnr"]))
        return result(best["lifnr"], "Quota arrangement (rating %.0f)"
                      % ((best["qubmg"] + qty) / best["quote"] / 1000.0))
    # 4. cheapest info record
    cands = [r for r in conn.execute("SELECT * FROM info_record WHERE matnr=? AND werks=? AND "
                                     "loekz=0", (matnr, werks)).fetchall()
             if r["lifnr"] not in blocked and (not allowed or r["lifnr"] in allowed)]
    if cands:
        c = min(cands, key=lambda r: net_price(r["brutto"], r["rabatt"]) / r["peinh"])
        return result(c["lifnr"], "Cheapest info record")
    return None
