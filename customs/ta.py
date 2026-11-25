"""Temporary admission (السماح المؤقت) of imported materials that are processed for export.

An import declaration with regime TA enters without paying duty and import VAT: the amounts are
only secured (guarantee) and recorded per line. At the release a balance is opened per line with a
deadline (release + TA months, setting). Every export declaration that is released discharges the
imported materials contained in the exported products: the bill of material is exploded down to the
TA materials (quantity incl. scrap %) and the oldest open balances are reduced first.
What is not exported before the deadline must be cleared for home use: duty and VAT of the open
quantity are then paid (into the import file costs and as input VAT, like a normal import).
Months, warning days and the use of the bill of material as consumption standard are defaults -
the official input / output standards of the customs authority always prevail."""
import datetime

from mm import util as clock
from mm.db import transaction
from mm.util import MMError, now_ts, parse_date, parse_int, rdiv

def _setting(conn, key, default):
    r = conn.execute("SELECT value FROM cus_setting WHERE key=?", (key,)).fetchone()
    try:
        return int(r[0]) if r and r[0] not in (None, "") else default
    except ValueError:
        return default


def _add_months(day, months):
    d = datetime.date.fromisoformat(day)
    y, m = d.year + (d.month - 1 + months) // 12, (d.month - 1 + months) % 12 + 1
    import calendar
    return datetime.date(y, m, min(d.day, calendar.monthrange(y, m)[1])).isoformat()


def open_balances(conn, d, day):
    """called at the release of a TA import declaration: one balance per line"""
    months = _setting(conn, "ta_months", 12)
    deadline = _add_months(day, months)
    for i in conn.execute("SELECT * FROM cus_item WHERE declno=? ORDER BY pos", (d["declno"],)).fetchall():
        if not i["matnr"] or not i["qty"]:
            continue
        conn.execute("INSERT OR REPLACE INTO cus_ta (declno,pos,matnr,qty,discharged,duty,vat,released,deadline,"
                     "status) VALUES (?,?,?,?,0,?,?,?,?,'OPEN')",
                     (d["declno"], i["pos"], i["matnr"], i["qty"], i["duty"] or 0, i["vat"] or 0, day, deadline))


def explode(conn, matnr, qty, werks="1000", depth=0, out=None):
    """raw materials in qty (milli) of a product: multi-level bill of material, scrap % included"""
    out = {} if out is None else out
    if depth > 10:
        raise MMError("Bill of material of %s is recursive" % matnr, "CU", "050")
    rows = conn.execute("SELECT * FROM bom WHERE matnr=? AND werks=?", (matnr, werks)).fetchall()
    if not rows:
        out[matnr] = out.get(matnr, 0) + qty
        return out
    for r in rows:
        need = rdiv(qty * r["menge"] * (10000 + (r["ausch"] or 0)), r["basis"] * 10000)
        explode(conn, r["idnrk"], need, werks, depth + 1, out)
    return out


def discharge(conn, exp, day):
    """called at the release of an export declaration: reduce the open TA balances (oldest first)"""
    open_mats = {r[0] for r in conn.execute("SELECT DISTINCT matnr FROM cus_ta WHERE status='OPEN' AND released<=? "
                                            "AND deadline>=?", (day, day))}
    if not open_mats:
        return []
    need = {}
    for i in conn.execute("SELECT * FROM cus_item WHERE declno=?", (exp["declno"],)).fetchall():
        if not i["matnr"]:
            continue
        for m, q in explode(conn, i["matnr"], i["qty"]).items():
            if m in open_mats:
                need[m] = need.get(m, 0) + q
    used = []
    for m, q in need.items():
        for b in conn.execute("SELECT * FROM cus_ta WHERE matnr=? AND status='OPEN' AND released<=? AND deadline>=? "
                              "ORDER BY deadline, declno, pos", (m, day, day)).fetchall():
            if q <= 0:
                break
            take = min(q, b["qty"] - b["discharged"])
            if take <= 0:
                continue
            conn.execute("UPDATE cus_ta SET discharged=discharged+?, status=CASE WHEN discharged+?>=qty THEN 'DONE' "
                         "ELSE status END WHERE declno=? AND pos=?", (take, take, b["declno"], b["pos"]))
            conn.execute("INSERT INTO cus_ta_use (exp_declno,declno,pos,matnr,qty,day,ts) VALUES (?,?,?,?,?,?,?)",
                         (exp["declno"], b["declno"], b["pos"], m, take, day, now_ts()))
            used.append(dict(declno=b["declno"], pos=b["pos"], matnr=m, qty=take))
            q -= take
    return used


def balances(conn, only_open=False):
    today = clock.today().isoformat()
    warn = _setting(conn, "ta_warn_days", 60)
    rows = []
    for r in conn.execute("SELECT t.*, m.maktx, m.meins, d.acid, d.decl_ref FROM cus_ta t LEFT JOIN material m USING "
                          "(matnr) LEFT JOIN cus_decl d USING (declno) %sORDER BY t.deadline, t.declno, t.pos" % (
                              "WHERE t.status='OPEN' " if only_open else "")).fetchall():
        x = dict(r)
        rest = x["qty"] - x["discharged"]
        x["open"] = rest if x["status"] == "OPEN" else 0
        x["days_left"] = (datetime.date.fromisoformat(x["deadline"]) - datetime.date.fromisoformat(today)).days
        x["duty_open"] = rdiv(x["duty"] * x["open"], x["qty"]) if x["qty"] else 0
        x["vat_open"] = rdiv(x["vat"] * x["open"], x["qty"]) if x["qty"] else 0
        x["alert"] = "EXPIRED" if x["open"] and x["days_left"] < 0 else (
            "SOON" if x["open"] and x["days_left"] <= warn else "")
        x["uses"] = [dict(u) for u in conn.execute("SELECT * FROM cus_ta_use WHERE declno=? AND pos=? ORDER BY day",
                                                   (x["declno"], x["pos"]))]
        rows.append(x)
    return dict(rows=rows, months=_setting(conn, "ta_months", 12), warn_days=warn,
                at_risk=sum(r["duty_open"] + r["vat_open"] for r in rows),
                expired=sum(1 for r in rows if r["alert"] == "EXPIRED"),
                soon=sum(1 for r in rows if r["alert"] == "SOON"),
                saved=sum(rdiv((r["duty"] + r["vat"]) * r["discharged"], r["qty"]) for r in rows if r["qty"]))


def to_home(conn, declno, pos, day, user, paid_by=None):
    """the open quantity of a TA line is cleared for home use: duty and VAT of it are paid now"""
    from fi.document import write
    from pur import importfile
    from .engine import BANK, INPUT_VAT
    day = parse_date(day)
    pos = parse_int(pos, "line")
    b = conn.execute("SELECT * FROM cus_ta WHERE declno=? AND pos=?", (str(declno or "").strip(), pos)).fetchone()
    if not b:
        raise MMError("Temporary admission line %s/%s does not exist" % (declno or "", pos), "CU", "051")
    if b["status"] != "OPEN":
        raise MMError("Line %s/%s is closed (%s)" % (b["declno"], pos, b["status"]), "CU", "052")
    d = conn.execute("SELECT * FROM cus_decl WHERE declno=?", (b["declno"],)).fetchone()
    rest = b["qty"] - b["discharged"]
    duty, vat = rdiv(b["duty"] * rest, b["qty"]), rdiv(b["vat"] * rest, b["qty"])
    cif = conn.execute("SELECT cif FROM cus_item WHERE declno=? AND pos=?", (b["declno"], pos)).fetchone()[0] or 0
    base = rdiv((cif + b["duty"]) * rest, b["qty"])
    broker = d["broker"] if str(paid_by or "").upper() == "BROKER" else None
    with transaction(conn):
        if duty:
            importfile.add_cost(conn, d["impno"], {"typ": "CUSTOMS", "amount": "%.2f" % (duty / 100.0), "budat": day,
                                                   "lifnr": broker or "", "xblnr": (d["decl_ref"] or d["declno"])[:16],
                                                   "text": "Temporary admission %s/%s to home use" % (b["declno"], pos)},
                                user)
        belnr = None
        if vat:
            txt = "Import VAT TA %s/%s" % (b["declno"], pos)
            credit = dict(lifnr=broker, koart="K", amount=-vat, sgtxt=txt) if broker else \
                dict(hkont=BANK, amount=-vat, sgtxt=txt)
            belnr = write(conn, "KR" if broker else "SA", day, user, "ZCUS", txt[:25], [
                dict(hkont=INPUT_VAT, amount=vat, mwskz="VI", txbase=base, sgtxt=txt), credit],
                xblnr=(d["decl_ref"] or d["declno"])[:16], tcode="ZCUS")
        conn.execute("UPDATE cus_ta SET status='HOME', home_qty=?, home_day=?, home_belnr=? WHERE declno=? AND pos=?",
                     (rest, day, belnr, b["declno"], pos))
    return {"duty": duty, "vat": vat, "message": "%s %s of line %s/%s cleared for home use: duty %.2f + VAT %.2f EGP" % (
        "{:,.3f}".format(rest / 1000.0), b["matnr"], b["declno"], pos, duty / 100.0, vat / 100.0)}


def day_text(conn):
    if not conn.execute("SELECT 1 FROM cus_ta WHERE status='OPEN' LIMIT 1").fetchone():
        return ""
    b = balances(conn, only_open=True)
    if not (b["expired"] or b["soon"]):
        return ""
    return "- السماح المؤقت: %d بند قرّب ميعاده و%d عدّى ميعاده - رسوم وضريبة معرّضة تقريباً %s جنيه" % (
        b["soon"], b["expired"], "{:,.0f}".format(b["at_risk"] / 100))
