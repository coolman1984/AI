"""Customer service and CRM.

IE01/IE02/IE03  equipment (installed base): created automatically at goods issue for
                serial-number materials; warranty 24 months from the goods issue (BGM1)
IW51/IW52/IW53  service notification; warranty check against the equipment
IW31 / IW41     service order SM01 (operations on the repair work center, spare parts),
                confirmation; settlement to CO-PA (after-sales / warranty costs)
DP90            resource-related billing for repairs outside warranty:
                hours x labour rate (ZLAB) + parts x sales price
VC01N / VC05    sales activities (calls, visits) and list
VB21 / VB23     sales deals / promotions -> ZDEA condition records
VB01 / VD51     material listing / exclusion, customer-material info records
"""
import datetime

from mm.db import next_number, rows, transaction
from mm.util import MMError, now_ts, parse_date, parse_qty, rdiv, value_of

from .config import SERVICE_RATE, WARRANTY_MONTHS
from mm import util as mmclock  # noqa: E402


# ====================================================================== equipment
def create_equipment(conn, data, user=""):
    matnr = (data.get("matnr") or "").upper()
    kunnr = (data.get("kunnr") or "").upper()
    if not conn.execute("SELECT 1 FROM material WHERE matnr=?", (matnr,)).fetchone():
        raise MMError("Material %s does not exist" % matnr, "IE", "001")
    if not conn.execute("SELECT 1 FROM customer WHERE kunnr=?", (kunnr,)).fetchone():
        raise MMError("Customer %s does not exist" % kunnr, "IE", "002")
    inbdt = parse_date(data.get("inbdt"))
    d = datetime.date.fromisoformat(inbdt)
    m = d.month - 1 + int(data.get("months") or WARRANTY_MONTHS)
    gw = datetime.date(d.year + m // 12, m % 12 + 1, min(d.day, 28)).isoformat()
    with transaction(conn):
        eq = str(next_number(conn, "EQUI"))
        conn.execute("INSERT INTO sd_equi (equnr,matnr,sernr,kunnr,inbdt,gwlen,eqktx) VALUES (?,?,?,?,?,?,?)",
                     (eq, matnr, data.get("sernr") or "SN%s" % eq[-6:], kunnr, inbdt, gw,
                      data.get("eqktx") or matnr))
    return eq


def equipment(conn, kunnr=None, equnr=None):
    sql = ("SELECT e.*, c.name, m.maktx FROM sd_equi e JOIN customer c ON c.kunnr=e.kunnr JOIN material m "
           "ON m.matnr=e.matnr WHERE 1=1")
    args = []
    if kunnr:
        sql += " AND e.kunnr=?"
        args.append(kunnr.upper())
    if equnr:
        sql += " AND e.equnr=?"
        args.append(equnr)
    out = rows(conn.execute(sql + " ORDER BY e.equnr", args))
    today = mmclock.today().isoformat()
    for e in out:
        e["warranty"] = e["gwlen"] >= today
        e["notifications"] = conn.execute("SELECT COUNT(*) FROM sd_qmel WHERE equnr=?", (e["equnr"],)).fetchone()[0]
    return out


# ====================================================================== notifications / orders
def create_notification(conn, data, user):
    equnr = data.get("equnr") or None
    kunnr = (data.get("kunnr") or "").upper()
    matnr = (data.get("matnr") or "").upper()
    erdat = parse_date(data.get("erdat"))
    warranty = 0
    if equnr:
        e = conn.execute("SELECT * FROM sd_equi WHERE equnr=?", (equnr,)).fetchone()
        if not e:
            raise MMError("Equipment %s does not exist" % equnr, "IW", "001")
        kunnr, matnr = e["kunnr"], e["matnr"]
        warranty = 1 if e["gwlen"] >= erdat else 0
    if not kunnr or not conn.execute("SELECT 1 FROM customer WHERE kunnr=?", (kunnr,)).fetchone():
        raise MMError("Enter a customer or an equipment", "IW", "002")
    if not (data.get("qmtxt") or "").strip():
        raise MMError("Enter a description of the problem", "IW", "003")
    with transaction(conn):
        q = str(next_number(conn, "QMEL"))
        conn.execute("INSERT INTO sd_qmel (qmnum,qmart,equnr,kunnr,matnr,qmtxt,erdat,priok,warranty,ernam) VALUES "
                     "(?,?,?,?,?,?,?,?,?,?)", (q, data.get("qmart") or "S1", equnr, kunnr, matnr or None,
                                               data["qmtxt"].strip(), erdat, data.get("priok") or "3",
                                               warranty, user))
    return {"qmnum": q, "warranty": bool(warranty)}


def create_service_order(conn, qmnum, data, user):
    """IW31 from the notification: operations (repair work center) + spare parts."""
    with transaction(conn):
        n = conn.execute("SELECT * FROM sd_qmel WHERE qmnum=?", (qmnum,)).fetchone()
        if not n:
            raise MMError("Notification %s does not exist" % qmnum, "IW", "004")
        if n["aufnr"]:
            raise MMError("Notification %s already has service order %s" % (qmnum, n["aufnr"]), "IW", "005")
        from pp.order import create
        rec = n["matnr"] or (data.get("comps") or [{}])[0].get("matnr") or "SP-4001"
        a = create(conn, {"auart": "SM01", "ktext": ("Service %s %s" % (qmnum, n["qmtxt"]))[:40],
                          "gamng": "1", "gstrp": data.get("gstrp"), "kostl": "4200",
                          "ops": data.get("ops") or [dict(arbpl="WC-REPR", ltxa1="Repair at customer",
                                                          vgw="2")],
                          "comps": data.get("comps") or [],
                          "rules": [{"konty": "PA", "receiver": rec, "prozs": 100}],
                          "release": True}, user)
        conn.execute("UPDATE sd_qmel SET aufnr=?, status='ORAS' WHERE qmnum=?", (a, qmnum))
    return a


def notifications(conn):
    out = rows(conn.execute("SELECT q.*, c.name, o.stat FROM sd_qmel q JOIN customer c ON c.kunnr=q.kunnr LEFT JOIN "
                            "orders o ON o.aufnr=q.aufnr ORDER BY q.qmnum DESC"))
    for q in out:
        q["cost"] = conn.execute("SELECT COALESCE(SUM(wtg),0) FROM co_item WHERE objnr=? AND wrttp='04' AND "
                                 "vrgng<>'KOAO'", ("OR%s" % q["aufnr"],)).fetchone()[0] if q["aufnr"] else 0
    return out


def complete(conn, qmnum, user):
    """TECO the order, close the notification (NOCO)."""
    with transaction(conn):
        n = conn.execute("SELECT * FROM sd_qmel WHERE qmnum=?", (qmnum,)).fetchone()
        if n["aufnr"]:
            o = conn.execute("SELECT stat FROM orders WHERE aufnr=?", (n["aufnr"],)).fetchone()
            if o["stat"] == "REL":
                from pp.order import teco
                teco(conn, n["aufnr"], user)
        conn.execute("UPDATE sd_qmel SET status='NOCO' WHERE qmnum=?", (qmnum,))


def dp90(conn, qmnum, user, fkdat=None):
    """Resource-related billing of a repair outside warranty."""
    fkdat = parse_date(fkdat)
    with transaction(conn):
        n = conn.execute("SELECT * FROM sd_qmel WHERE qmnum=?", (qmnum,)).fetchone()
        if not n or not n["aufnr"]:
            raise MMError("Notification %s has no service order" % qmnum, "DP", "001")
        if n["warranty"]:
            raise MMError("Repair is under warranty - not billable (costs go to warranty in CO-PA)", "DP", "002")
        if n["billed"]:
            raise MMError("Notification %s is already billed (%s)" % (qmnum, n["billed"]), "DP", "003")
        a = n["aufnr"]
        hours = conn.execute("SELECT COALESCE(SUM(ism),0) FROM confirmation WHERE aufnr=? AND stokz=0",
                             (a,)).fetchone()[0]
        lab = conn.execute("SELECT kbetr FROM sd_cond WHERE kschl='ZLAB' AND loevm=0 AND datab<=? AND datbi>=? "
                           "ORDER BY knumh DESC LIMIT 1", (fkdat, fkdat)).fetchone()
        rate = lab["kbetr"] if lab else SERVICE_RATE
        c = conn.execute("SELECT * FROM customer WHERE kunnr=?", (n["kunnr"],)).fetchone()
        area = conn.execute("SELECT * FROM md_knvv WHERE kunnr=? ORDER BY vtweg LIMIT 1", (n["kunnr"],)).fetchone()
        tax = "A1" if (area["taxkd"] if area else "1") == "1" else "A0"
        items = []
        if hours:
            items.append(dict(matnr=None, werks="1000", qty=hours, gross=value_of(hours, rate, 1), disc=0,
                              freight=0, cogs=None, mwskz=tax, arktx="Repair labour %.2f h" % (hours / 1000.0),
                              ktgrm="02", pstyv="L2N"))
        from .pricing import find
        for m in conn.execute("SELECT matnr, SUM(CASE WHEN shkzg='H' THEN menge ELSE -menge END) q FROM mat_doc_item "
                              "WHERE aufnr=? AND bwart IN ('261','262') GROUP BY matnr", (a,)).fetchall():
            if m["q"] <= 0:
                continue
            rec, _ = find(conn, "PR00", n["kunnr"], m["matnr"], fkdat)
            if rec:
                price = rec["kbetr"]
            else:
                v = conn.execute("SELECT verpr, stprs, vprsv, peinh FROM valuation WHERE matnr=? AND bwkey='1000'",
                                 (m["matnr"],)).fetchone()
                price = rdiv((v["stprs"] if v["vprsv"] == "S" else v["verpr"]) * 130, 100 * v["peinh"])
            mk = conn.execute("SELECT maktx FROM material WHERE matnr=?", (m["matnr"],)).fetchone()
            items.append(dict(matnr=m["matnr"], werks="1000", qty=m["q"], gross=value_of(m["q"], price, 1), disc=0,
                              freight=0, cogs=None, mwskz=tax, arktx=mk["maktx"], ktgrm="02", pstyv="L2N"))
        if not items:
            raise MMError("No billable resources on service order %s" % a, "DP", "004")
        k = dict(kunnr=n["kunnr"], kunrg=n["kunnr"], vtweg=area["vtweg"] if area else "10",
                 zterm=c["zterm"] or "NT30", vbtyp="C", vbeln=a)
        from .billing import post
        r = post(conn, "ZSRV", k, c, items, fkdat, user, a, service_order=None)
        conn.execute("UPDATE sd_qmel SET billed=? WHERE qmnum=?", (r["vbeln"], qmnum))
    return r


# ====================================================================== CRM
def save_activity(conn, data, user):
    kunnr = (data.get("kunnr") or "").upper()
    if not conn.execute("SELECT 1 FROM customer WHERE kunnr=?", (kunnr,)).fetchone():
        raise MMError("Customer %s does not exist" % kunnr, "VC", "001")
    with transaction(conn):
        cur = conn.execute("INSERT INTO sd_activity (kunnr,ktaar,datum,subject,result,vbeln,followup,usnam,status) "
                           "VALUES (?,?,?,?,?,?,?,?,?)",
                           (kunnr, data.get("ktaar") or "0002", parse_date(data.get("datum")),
                            data.get("subject") or "", data.get("result") or "", data.get("vbeln") or None,
                            parse_date(data["followup"]) if data.get("followup") else None, user,
                            data.get("status") or "C"))
    return cur.lastrowid


def activities(conn):
    return rows(conn.execute("SELECT a.*, c.name FROM sd_activity a JOIN customer c USING (kunnr) ORDER BY datum DESC"))


def save_deal(conn, data, user):
    """VB21: promotion with a discount per material (ZDEA) and a budget."""
    from .pricing import save_condition
    with transaction(conn):
        knuma = str(data.get("knuma") or "") or "D%s" % now_ts()[2:10].replace("-", "")
        conn.execute("INSERT OR REPLACE INTO sd_deal VALUES (?,?,?,?,?,?,?)",
                     (knuma, data.get("botext") or "", parse_date(data.get("datab")), parse_date(data.get("datbi")),
                      int(round(float(data.get("budget") or 0) * 100)), "A", user))
        for m in data.get("materials") or []:
            save_condition(conn, "ZDEA", "A304", dict(matnr=m["matnr"], kbetr=m["pct"], datab=data.get("datab"),
                                                      datbi=data.get("datbi"), knuma=knuma), user)
    return knuma


def deals(conn):
    out = rows(conn.execute("SELECT * FROM sd_deal ORDER BY datab DESC"))
    for d in out:
        d["materials"] = rows(conn.execute("SELECT matnr, kbetr FROM sd_cond WHERE knuma=? AND loevm=0", (d["knuma"],)))
        d["used"] = -conn.execute("SELECT COALESCE(SUM(k.kwert),0) FROM sd_konv k JOIN sd_cond c ON c.knumh=k.knumh "
                                  "WHERE c.knuma=?", (d["knuma"],)).fetchone()[0]
    return out


def save_listing(conn, kunnr, matnr, kind, datab, datbi=None):
    if kind not in ("A", "B"):
        raise MMError("Kind must be A (listing) or B (exclusion)", "VB", "001")
    with transaction(conn):
        conn.execute("INSERT OR REPLACE INTO sd_listing VALUES (?,?,?,?,?)",
                     (kunnr.upper(), matnr.upper(), kind, parse_date(datab), parse_date(datbi or "9999-12-31")))


def save_custmat(conn, kunnr, matnr, kdmat, postx=""):
    with transaction(conn):
        if not conn.execute("SELECT 1 FROM material WHERE matnr=?", (matnr.upper(),)).fetchone():
            raise MMError("Material %s does not exist" % matnr, "VD", "001")
        conn.execute("INSERT OR REPLACE INTO sd_custmat VALUES (?,?,?,?)", (kunnr.upper(), matnr.upper(), kdmat, postx))


def listings(conn):
    return {"listing": rows(conn.execute("SELECT l.*, c.name, m.maktx FROM sd_listing l JOIN customer c USING (kunnr) "
                                         "JOIN material m USING (matnr)")),
            "custmat": rows(conn.execute("SELECT x.*, c.name, m.maktx FROM sd_custmat x JOIN customer c USING (kunnr) "
                                         "JOIN material m USING (matnr)"))}
