"""ZMM_BOARD warehouse status board (TV screen for the stores).

Per storage location, grouped by plant:
  MATERIALS   number of materials in stock
  STOCK VALUE value of all stock (unrestricted + quality + blocked), at the material price
  QUALITY / BLOCKED  value in quality inspection / blocked (defective)
  GR / GI / TRANSFER  material documents of the day: receipts, issues, transfers
  BINS        bins with stock
  LAST MOVE   last movement date of the storage location
Panels: inbound (PO items due / late, receipts of the day), outbound (deliveries to pick /
ship), production supply (reservations due), below reorder point / safety stock, slow-moving
stock (no movement in 90 days) and physical inventory.
Values in EGP cents, quantities in milli.
"""
import datetime

from mm import util as clock
from mm.config import MOVEMENT_TYPES
from mm.util import parse_date, value_of


def _price(conn, matnr, werks, cache):
    k = (matnr, werks)
    if k not in cache:
        v = conn.execute("SELECT * FROM valuation WHERE matnr=? AND bwkey=?", (matnr, werks)).fetchone()
        cache[k] = (v["stprs"] if v["vprsv"] == "S" else v["verpr"], v["peinh"] or 1) if v else (0, 1)
    return cache[k]


def board(conn, datum=None, now=None, slow_days=90):
    now = now or clock.now()
    if isinstance(now, str):
        now = datetime.datetime.fromisoformat(now)
    datum = parse_date(datum) if datum else now.date().isoformat()
    day = datetime.date.fromisoformat(datum)
    cache = {}
    # ---------------------------------------------------------------- storage locations
    rows = {}
    for s in conn.execute("SELECT * FROM sloc ORDER BY werks, lgort"):
        rows[(s["werks"], s["lgort"])] = dict(werks=s["werks"], lgort=s["lgort"], name=s["name"], materials=0,
                                              value=0, quality=0, blocked=0, gr=0, gi=0, transfer=0, bins=0,
                                              last_move="")
    for q in conn.execute("SELECT matnr, werks, lgort, insmk, SUM(qty) qty FROM quant WHERE qty<>0 "
                          "GROUP BY matnr, werks, lgort, insmk"):
        r = rows.get((q["werks"], q["lgort"]))
        if not r:
            continue
        p, pe = _price(conn, q["matnr"], q["werks"], cache)
        v = value_of(q["qty"], p, pe)
        r["value"] += v
        if q["insmk"] == "Q":
            r["quality"] += v
        elif q["insmk"] == "B":
            r["blocked"] += v
    for r in rows.values():
        r["materials"] = conn.execute("SELECT COUNT(DISTINCT matnr) FROM quant WHERE werks=? AND lgort=? AND qty>0",
                                      (r["werks"], r["lgort"])).fetchone()[0]
        r["bins"] = conn.execute("SELECT COUNT(DISTINCT lgpla) FROM quant WHERE werks=? AND lgort=? AND qty>0 AND "
                                 "lgpla<>''", (r["werks"], r["lgort"])).fetchone()[0]
        r["last_move"] = conn.execute("SELECT MAX(h.budat) FROM mat_doc_item i JOIN mat_doc h ON h.mblnr=i.mblnr AND "
                                      "h.mjahr=i.mjahr WHERE i.werks=? AND i.lgort=? AND h.budat<=?",
                                      (r["werks"], r["lgort"], datum)).fetchone()[0] or ""
    seen = set()
    for m in conn.execute("SELECT i.mblnr, i.mjahr, i.bwart, i.werks, i.lgort FROM mat_doc_item i JOIN mat_doc h ON "
                          "h.mblnr=i.mblnr AND h.mjahr=i.mjahr WHERE h.budat=? AND i.xauto=0", (datum,)):
        kind = (MOVEMENT_TYPES.get(m["bwart"]) or {}).get("kind", "")
        col = "gr" if kind == "receipt" else "gi" if kind == "issue" else "transfer"
        key = (m["mblnr"], m["mjahr"], m["werks"], m["lgort"], col)
        r = rows.get((m["werks"], m["lgort"]))
        if r and key not in seen:
            seen.add(key)
            r[col] += 1
    plants = {}
    for r in rows.values():
        if r["value"] or r["gr"] or r["gi"] or r["transfer"] or r["materials"]:
            plants.setdefault(r["werks"], []).append(r)

    def total(rs):
        t = {k: sum(r[k] for r in rs) for k in ("materials", "value", "quality", "blocked", "gr", "gi", "transfer",
                                                  "bins")}
        t["lines"] = len(rs)
        t["active"] = sum(1 for r in rs if r["gr"] or r["gi"] or r["transfer"])
        return t
    groups = []
    for w, rs in sorted(plants.items()):
        pl = conn.execute("SELECT name FROM plant WHERE werks=?", (w,)).fetchone()
        groups.append(dict(area="Plant %s%s" % (w, " - " + pl["name"] if pl and pl["name"] else ""), lines=rs,
                           total=total(rs)))
    allrows = [r for g in groups for r in g["lines"]]
    # ---------------------------------------------------------------- panels
    from pur.followup import overdue
    late = overdue(conn, datum)
    one = lambda sql, *p: conn.execute(sql, p).fetchone()                     # noqa: E731
    inbound = dict(
        due_today=one("SELECT COUNT(*) FROM po_item WHERE COALESCE(loekz,0)=0 AND elikz=0 AND wemng<menge AND "
                      "eindt=?", datum)[0],
        late=len(late), late_value=sum(value_of(r["open"], r["netpr"], r["peinh"]) for r in late),
        received_today=one("SELECT COUNT(DISTINCT i.mblnr) FROM mat_doc_item i JOIN mat_doc h ON h.mblnr=i.mblnr AND "
                           "h.mjahr=i.mjahr WHERE h.budat=? AND i.bwart='101'", datum)[0],
        inspection=one("SELECT COUNT(DISTINCT matnr) FROM quant WHERE insmk='Q' AND qty>0")[0])
    outbound = dict(
        to_pick=one("SELECT COUNT(*) FROM sd_likp h WHERE h.wbstk<>'C' AND h.wadat<=? AND EXISTS (SELECT 1 FROM "
                    "sd_lips i WHERE i.vbeln=h.vbeln AND COALESCE(i.pikmg,0)<i.lfimg)", datum)[0],
        to_ship=one("SELECT COUNT(*) FROM sd_likp h WHERE h.wbstk<>'C' AND h.wadat<=? AND NOT EXISTS (SELECT 1 FROM "
                    "sd_lips i WHERE i.vbeln=h.vbeln AND COALESCE(i.pikmg,0)<i.lfimg)", datum)[0],
        shipped=one("SELECT COUNT(*) FROM sd_likp WHERE wbstk='C' AND COALESCE(wadat_ist,wadat)=?", datum)[0],
        later=one("SELECT COUNT(*) FROM sd_likp WHERE wbstk<>'C' AND wadat>?", datum)[0])
    supply = dict(
        items=one("SELECT COUNT(*) FROM pp_resb r LEFT JOIN orders o ON o.aufnr=r.aufnr WHERE r.xloek=0 AND r.kzear=0 "
                  "AND r.bdmng>r.enmng AND COALESCE(r.bdter,?)<=? AND (r.aufnr IS NULL OR o.stat='REL')",
                  datum, datum)[0],
        orders=one("SELECT COUNT(DISTINCT r.rsnum) FROM pp_resb r LEFT JOIN orders o ON o.aufnr=r.aufnr WHERE r.xloek=0 "
                   "AND r.kzear=0 AND r.bdmng>r.enmng AND COALESCE(r.bdter,?)<=? AND (r.aufnr IS NULL OR "
                   "o.stat='REL')", datum, datum)[0])
    reorder = []
    for p in conn.execute("SELECT p.matnr, p.werks, p.minbe, p.eisbe, m.maktx, m.meins FROM material_plant p JOIN "
                          "material m ON m.matnr=p.matnr WHERE p.minbe>0 OR p.eisbe>0"):
        st = one("SELECT COALESCE(SUM(qty),0) FROM quant WHERE matnr=? AND werks=? AND insmk='U'",
                 p["matnr"], p["werks"])[0]
        if (p["minbe"] and st < p["minbe"]) or (p["eisbe"] and st < p["eisbe"]):
            reorder.append(dict(matnr=p["matnr"], werks=p["werks"], maktx=p["maktx"], meins=p["meins"], stock=st,
                                reorder=p["minbe"], safety=p["eisbe"], below_safety=bool(p["eisbe"] and st < p["eisbe"])))
    reorder.sort(key=lambda r: (not r["below_safety"], r["matnr"]))
    since = (day - datetime.timedelta(days=slow_days)).isoformat()
    slow = []
    for q in conn.execute("SELECT matnr, werks, SUM(qty) qty FROM quant WHERE qty>0 GROUP BY matnr, werks"):
        lastm = one("SELECT MAX(h.budat) FROM mat_doc_item i JOIN mat_doc h ON h.mblnr=i.mblnr AND h.mjahr=i.mjahr "
                    "WHERE i.matnr=? AND i.werks=? AND h.budat<=?", q["matnr"], q["werks"], datum)[0]
        if not lastm or lastm < since:
            p, pe = _price(conn, q["matnr"], q["werks"], cache)
            m = one("SELECT maktx FROM material WHERE matnr=?", q["matnr"])
            slow.append(dict(matnr=q["matnr"], werks=q["werks"], maktx=m["maktx"] if m else "", qty=q["qty"],
                             value=value_of(q["qty"], p, pe), last_move=lastm or ""))
    slow.sort(key=lambda r: -r["value"])
    inv = dict(open=one("SELECT COUNT(*) FROM inv_doc WHERE status NOT IN ('POST','RCNT')")[0],
               last_count=one("SELECT MAX(count_date) FROM inv_doc WHERE status='POST'")[0] or "")
    lastd = one("SELECT MAX(budat) FROM mat_doc WHERE budat<=?", now.date().isoformat())[0]
    return {"datum": datum, "now": now.isoformat(timespec="seconds"), "groups": groups,
            "total": total(allrows) if allrows else None, "inbound": inbound, "outbound": outbound,
            "supply": supply, "reorder": reorder, "slow": slow[:10], "slow_value": sum(r["value"] for r in slow),
            "slow_count": len(slow), "slow_days": slow_days, "inventory": inv, "last_day": lastd}
