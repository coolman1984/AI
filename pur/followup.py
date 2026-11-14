"""Purchasing follow-up (7-x / 8-x):

ME91F    delivery reminders: PO items whose delivery date has passed and that are not fully
         received; reminder level 1 (1-7 days late), 2 (8-14), 3 (more than 14 days).
         Sending records the reminder per item (level and date) - a letter per vendor.
ZPUR_PRICE  purchase price history of a material: every PO price over time with the change
         against the previous order, the vendor and the current info record price.
ZPUR_CONF   purchasing configuration (display).
ZPUR_CLOSE  purchasing month-end: the open work in order with its status.
"""
import datetime

from mm import util as clock
from mm.db import transaction
from mm.util import MMError, parse_date, value_of

LEVELS = [(7, 1), (14, 2), (10 ** 6, 3)]
LEVEL_TEXT = {1: "1st reminder - please confirm the delivery date",
              2: "2nd reminder - delivery is urgently needed",
              3: "Final reminder - we reserve the right to cancel and buy elsewhere"}


def _level(days):
    return next(lv for lim, lv in LEVELS if days <= lim)


def overdue(conn, key_date=None, lifnr=None):
    kd = parse_date(key_date) if key_date else clock.today().isoformat()
    sql = ("SELECT i.*, h.lifnr, h.bedat, h.waers, v.name FROM po_item i JOIN po_header h ON h.ebeln=i.ebeln "
           "LEFT JOIN vendor v ON v.lifnr=h.lifnr WHERE COALESCE(i.loekz,0)=0 AND i.elikz=0 "
           "AND i.wemng < i.menge AND i.eindt IS NOT NULL AND i.eindt < ?")
    a = [kd]
    if lifnr:
        sql += " AND h.lifnr=?"
        a.append(lifnr.upper())
    out = []
    for r in conn.execute(sql + " ORDER BY i.eindt, i.ebeln, i.ebelp", a):
        d = dict(r)
        d["days"] = (datetime.date.fromisoformat(kd) - datetime.date.fromisoformat(r["eindt"])).days
        d["level"] = _level(d["days"])
        d["open"] = r["menge"] - r["wemng"]
        d["open_value"] = value_of(d["open"], r["netpr"], r["peinh"])
        last = conn.execute("SELECT MAX(level), MAX(sent), COUNT(*) FROM po_reminder WHERE ebeln=? AND ebelp=?",
                            (r["ebeln"], r["ebelp"])).fetchone()
        d["sent_level"], d["last_sent"], d["reminders"] = last[0] or 0, last[1] or "", last[2]
        d["due"] = d["level"] > d["sent_level"]          # a new (higher) reminder is due
        out.append(d)
    return out


def send(conn, items, user, key_date=None):
    """record the reminders for the selected items [[ebeln, ebelp], ...] (or all that are due)"""
    kd = parse_date(key_date) if key_date else clock.today().isoformat()
    rows = overdue(conn, kd)
    if items:
        keys = set()
        for x in items:
            try:
                e, p = x
                keys.add((str(e), int(p)))
            except (TypeError, ValueError):
                raise MMError("Select purchase order items as [PO, item]", "ME", "933")
        rows = [r for r in rows if (r["ebeln"], r["ebelp"]) in keys]
    else:
        rows = [r for r in rows if r["due"]]
    if not rows:
        raise MMError("No reminders due", "ME", "931")
    with transaction(conn):
        for r in rows:
            conn.execute("INSERT INTO po_reminder (ebeln,ebelp,level,sent,days,usnam) VALUES (?,?,?,?,?,?)",
                         (r["ebeln"], r["ebelp"], r["level"], kd, r["days"], user))
    letters = {}
    for r in rows:
        v = letters.setdefault(r["lifnr"], {"lifnr": r["lifnr"], "name": r["name"], "items": []})
        v["items"].append({k: r[k] for k in ("ebeln", "ebelp", "matnr", "txz01", "eindt", "days", "level", "open")})
    for v in letters.values():
        v["level"] = max(i["level"] for i in v["items"])
        v["text"] = LEVEL_TEXT[v["level"]]
    return {"sent": len(rows), "letters": list(letters.values()),
            "message": "%d reminder(s) sent to %d vendor(s)" % (len(rows), len(letters))}


def price_history(conn, matnr, lifnr=None):
    matnr = (matnr or "").strip().upper()
    m = conn.execute("SELECT * FROM material WHERE matnr=?", (matnr,)).fetchone()
    if not m:
        raise MMError("Material %s does not exist" % matnr, "ME", "932")
    sql = ("SELECT i.ebeln, i.ebelp, i.netpr, i.peinh, i.menge, i.meins, h.bedat, h.lifnr, h.waers, v.name "
           "FROM po_item i JOIN po_header h ON h.ebeln=i.ebeln LEFT JOIN vendor v ON v.lifnr=h.lifnr "
           "WHERE i.matnr=? AND COALESCE(i.loekz,0)=0")
    a = [matnr]
    if lifnr:
        sql += " AND h.lifnr=?"
        a.append(lifnr.upper())
    rows, prev = [], {}
    for r in conn.execute(sql + " ORDER BY h.bedat, i.ebeln, i.ebelp", a):
        d = dict(r)
        d["price"] = round(r["netpr"] / 100.0 / (r["peinh"] or 1), 4)       # per unit, PO currency
        p = prev.get(r["waers"])
        d["change_pct"] = round((d["price"] - p) * 100.0 / p, 1) if p else None
        prev[r["waers"]] = d["price"]
        rows.append(d)
    info = [dict(r) for r in conn.execute(
        "SELECT r.lifnr, v.name, r.brutto, r.rabatt, r.peinh, r.frb FROM info_record r LEFT JOIN vendor v "
        "ON v.lifnr=r.lifnr WHERE r.matnr=? AND COALESCE(r.loekz,0)=0", (matnr,))]
    for i in info:
        i["net"] = round(i["brutto"] * (10000 - i["rabatt"]) / 10000 / 100.0 / (i["peinh"] or 1), 4)
    stats = {}
    for w in {r["waers"] for r in rows}:
        ps = [r["price"] for r in rows if r["waers"] == w]
        first, last = ps[0], ps[-1]
        stats[w] = {"orders": len(ps), "min": min(ps), "max": max(ps), "avg": round(sum(ps) / len(ps), 4),
                    "last": last, "change_pct": round((last - first) * 100.0 / first, 1) if first else None}
    return {"matnr": matnr, "maktx": m["maktx"] if "maktx" in m.keys() else "", "rows": rows,
            "info_records": info, "stats": stats}
