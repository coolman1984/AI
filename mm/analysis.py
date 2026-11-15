"""Warehouse in depth:

1-1 ZMM_CONF   warehouse configuration (display): plants, storage locations, bins, movement
               types, cycle counting intervals, MM period
1-5 ZMM_CLOSE  warehouse month-end: the open work in order with its status
6-1 ZMM_AGING  stock aging by goods receipt date (0-30, 31-90, 91-180, 181-365, > 365 days),
               value per bucket - old stock ties up cash and may be obsolete
6-2 ZMM_ABC    ABC analysis by consumption value of the last 12 months (A = first 80 % of the
               value, B = next 15 %, C = the rest); the result can be saved as the ABC indicator
               of the material, which drives the cycle counting interval (MICN)
6-3 ZMM_COVER  range of coverage: stock / average daily consumption of the last 90 days
"""
import calendar
import datetime

from mm import util as clock
from mm.config import MOVEMENT_TYPES
from mm.db import transaction
from mm.util import MMError, parse_date, parse_int, value_of

AGE_BUCKETS = [("d30", "0-30", 30), ("d90", "31-90", 90), ("d180", "91-180", 180), ("d365", "181-365", 365),
               ("old", "> 365", 10 ** 6)]
CONSUMPTION = ("201", "261", "601", "551", "543")          # issues that consume the material
REVERSALS = ("202", "262", "602", "552", "544")
ABC_LIMITS = (80.0, 95.0)                                    # cumulative % for A and B


def _price(conn, matnr, werks, cache):
    k = (matnr, werks)
    if k not in cache:
        v = conn.execute("SELECT * FROM valuation WHERE matnr=? AND bwkey=?", (matnr, werks)).fetchone()
        cache[k] = (v["stprs"] if v["vprsv"] == "S" else v["verpr"], v["peinh"] or 1) if v else (0, 1)
    return cache[k]


def config(conn):
    from .inventory import CYCLE_DAYS
    from . import periods
    return {
        "plants": [dict(r) for r in conn.execute("SELECT * FROM plant ORDER BY werks")],
        "slocs": [dict(r, bins=conn.execute("SELECT COUNT(*) FROM bin WHERE werks=? AND lgort=?",
                                            (r["werks"], r["lgort"])).fetchone()[0])
                  for r in conn.execute("SELECT * FROM sloc ORDER BY werks, lgort")],
        "movement_types": [dict(bwart=k, text=v["text"], kind=v.get("kind", ""), value=v.get("value", ""))
                           for k, v in sorted(MOVEMENT_TYPES.items())],
        "cycle_days": [dict(abc=k, days=v) for k, v in CYCLE_DAYS.items()],
        "abc_limits": {"A": ABC_LIMITS[0], "B": ABC_LIMITS[1] - ABC_LIMITS[0], "C": 100 - ABC_LIMITS[1]},
        "period": periods.current(conn),
        "stock_types": [dict(insmk="U", text="Unrestricted"), dict(insmk="Q", text="Quality inspection"),
                        dict(insmk="B", text="Blocked (defective)")],
    }


def aging(conn, key_date=None, werks=None):
    kd = datetime.date.fromisoformat(parse_date(key_date) if key_date else clock.today().isoformat())
    cache, mats = {}, {}
    sql, a = "SELECT q.*, m.maktx, m.meins FROM quant q JOIN material m ON m.matnr=q.matnr WHERE q.qty>0", []
    if werks:
        sql += " AND q.werks=?"
        a.append(werks)
    for q in conn.execute(sql, a):
        days = (kd - datetime.date.fromisoformat(q["wdatu"])).days
        b = next(k for k, _, lim in AGE_BUCKETS if days <= lim)
        p, pe = _price(conn, q["matnr"], q["werks"], cache)
        v = value_of(q["qty"], p, pe)
        m = mats.setdefault((q["matnr"], q["werks"]), dict(matnr=q["matnr"], werks=q["werks"], maktx=q["maktx"],
                                                          meins=q["meins"], qty=0, value=0, oldest=q["wdatu"],
                                                          **{k: 0 for k, _, _ in AGE_BUCKETS}))
        m["qty"] += q["qty"]
        m["value"] += v
        m[b] += v
        m["oldest"] = min(m["oldest"], q["wdatu"])
    rows = sorted(mats.values(), key=lambda r: -(r["old"] + r["d365"]) or -r["value"])
    for r in rows:
        r["age_days"] = (kd - datetime.date.fromisoformat(r["oldest"])).days
    total = {k: sum(r[k] for r in rows) for k in ["value"] + [b for b, _, _ in AGE_BUCKETS]}
    return {"key_date": kd.isoformat(), "rows": rows, "total": total,
            "buckets": [dict(key=k, text=t) for k, t, _ in AGE_BUCKETS]}


def _consumption(conn, werks, d1, d2):
    """consumed quantity and value per material (issues minus their reversals)"""
    out = {}
    for r in conn.execute("SELECT i.matnr, i.bwart, SUM(i.menge) q, SUM(i.dmbtr) v FROM mat_doc_item i JOIN mat_doc h "
                          "ON h.mblnr=i.mblnr AND h.mjahr=i.mjahr WHERE i.werks=? AND h.budat BETWEEN ? AND ? AND "
                          "i.bwart IN (%s) GROUP BY i.matnr, i.bwart" % ",".join("?" * len(CONSUMPTION + REVERSALS)),
                          [werks, d1, d2] + list(CONSUMPTION + REVERSALS)):
        sign = 1 if r["bwart"] in CONSUMPTION else -1
        o = out.setdefault(r["matnr"], dict(qty=0, value=0))
        o["qty"] += sign * (r["q"] or 0)
        o["value"] += sign * abs(r["v"] or 0)
    return out


def abc(conn, werks="1000", key_date=None, months=12):
    kd = datetime.date.fromisoformat(parse_date(key_date) if key_date else clock.today().isoformat())
    y, m = kd.year, kd.month - months
    while m <= 0:
        y, m = y - 1, m + 12
    d1 = datetime.date(y, m, min(kd.day, calendar.monthrange(y, m)[1])).isoformat()
    cons = _consumption(conn, werks, d1, kd.isoformat())
    rows = []
    for matnr, c in cons.items():
        if c["value"] <= 0:
            continue
        mt = conn.execute("SELECT m.maktx, COALESCE(p.abcin,'') abcin FROM material m LEFT JOIN material_plant p ON "
                          "p.matnr=m.matnr AND p.werks=? WHERE m.matnr=?", (werks, matnr)).fetchone()
        rows.append(dict(matnr=matnr, maktx=mt["maktx"] if mt else "", qty=c["qty"], value=c["value"],
                         current=mt["abcin"] if mt else ""))
    rows.sort(key=lambda r: -r["value"])
    total = sum(r["value"] for r in rows)
    cum = 0
    for r in rows:
        before = cum * 100.0 / total if total else 0
        cum += r["value"]
        r["share"] = round(r["value"] * 100.0 / total, 2) if total else 0
        r["cum"] = round(cum * 100.0 / total, 2) if total else 0
        r["abc"] = "A" if before < ABC_LIMITS[0] else "B" if before < ABC_LIMITS[1] else "C"
        r["changed"] = r["abc"] != (r["current"] or "C")
    # materials in stock without consumption are C (nothing used in the period)
    used = {r["matnr"] for r in rows}
    idle = [dict(matnr=x["matnr"], maktx=x["maktx"], current=x["abcin"] or "") for x in conn.execute(
        "SELECT DISTINCT q.matnr, m.maktx, COALESCE(p.abcin,'') abcin FROM quant q JOIN material m ON m.matnr=q.matnr "
        "LEFT JOIN material_plant p ON p.matnr=q.matnr AND p.werks=q.werks WHERE q.werks=? AND q.qty>0", (werks,))
        if x["matnr"] not in used]
    summary = {k: dict(count=sum(1 for r in rows if r["abc"] == k), value=sum(r["value"] for r in rows if r["abc"] == k))
               for k in "ABC"}
    summary["C"]["count"] += len(idle)
    return {"werks": werks, "d1": d1, "d2": kd.isoformat(), "rows": rows, "idle": idle, "total": total,
            "summary": summary}


def save_abc(conn, werks, key_date, user):
    """write the ABC class as indicator of the material in the plant (used by MICN cycle counting)"""
    res = abc(conn, werks, key_date)
    changes = [(r["abc"], r["matnr"]) for r in res["rows"]] + [("C", r["matnr"]) for r in res["idle"]]
    with transaction(conn):
        n = 0
        for cls, matnr in changes:
            cur = conn.execute("SELECT COALESCE(abcin,'') FROM material_plant WHERE matnr=? AND werks=?",
                               (matnr, werks)).fetchone()
            if cur is not None and cur[0] != cls:
                conn.execute("UPDATE material_plant SET abcin=? WHERE matnr=? AND werks=?", (cls, matnr, werks))
                n += 1
    return {"changed": n, "message": "ABC indicator changed for %d material(s) in plant %s" % (n, werks)}


def coverage(conn, werks="1000", key_date=None, days=90):
    days = parse_int(days, "days", 7, 730)
    kd = datetime.date.fromisoformat(parse_date(key_date) if key_date else clock.today().isoformat())
    d1 = (kd - datetime.timedelta(days=days)).isoformat()
    cons = _consumption(conn, werks, d1, kd.isoformat())
    cache, out = {}, []
    for q in conn.execute("SELECT q.matnr, m.maktx, m.meins, SUM(q.qty) qty FROM quant q JOIN material m ON "
                          "m.matnr=q.matnr WHERE q.werks=? AND q.insmk='U' GROUP BY q.matnr HAVING SUM(q.qty)>0",
                          (werks,)):
        used = (cons.get(q["matnr"]) or {}).get("qty", 0)
        per_day = used / float(days)
        cover = round(q["qty"] / per_day, 1) if per_day > 0 else None
        p, pe = _price(conn, q["matnr"], werks, cache)
        out.append(dict(matnr=q["matnr"], maktx=q["maktx"], meins=q["meins"], stock=q["qty"], used=used,
                        per_day=round(per_day, 1), cover_days=cover, value=value_of(q["qty"], p, pe),
                        flag="no use" if cover is None else "short" if cover < 14 else "high" if cover > 180 else "ok"))
    order = {"short": 0, "high": 1, "no use": 2, "ok": 3}
    out.sort(key=lambda r: (order[r["flag"]], r["cover_days"] if r["cover_days"] is not None else 1e9))
    return {"werks": werks, "days": days, "d1": d1, "d2": kd.isoformat(), "rows": out}


def status(conn, gjahr, perio):
    from . import periods
    end = "%04d-%02d-%02d" % (gjahr, perio, calendar.monthrange(gjahr, perio)[1])
    kd = min(end, clock.today().isoformat())
    one = lambda sql, *a: conn.execute(sql, a).fetchone()[0]          # noqa: E731
    from pur.followup import overdue
    late_gr = len(overdue(conn, kd))
    qi = one("SELECT COUNT(DISTINCT matnr) FROM quant WHERE insmk='Q' AND qty>0")
    blocked = one("SELECT COUNT(DISTINCT matnr) FROM quant WHERE insmk='B' AND qty>0")
    resb = one("SELECT COUNT(*) FROM pp_resb r LEFT JOIN orders o ON o.aufnr=r.aufnr WHERE r.xloek=0 AND r.kzear=0 "
               "AND r.bdmng>r.enmng AND COALESCE(r.bdter,?)<=? AND (r.aufnr IS NULL OR o.stat='REL')", kd, kd)
    not_gi = one("SELECT COUNT(*) FROM sd_likp WHERE wbstk<>'C' AND wadat<=?", kd)
    pi_open = one("SELECT COUNT(*) FROM inv_doc WHERE status NOT IN ('POST','RCNT')")
    from .inventory import cycle_proposal
    cyc = sum(len(cycle_proposal(conn, w[0], datetime.date.fromisoformat(kd)))
              for w in conn.execute("SELECT werks FROM plant").fetchall())
    neg = one("SELECT COUNT(*) FROM valuation WHERE lbkum<0 OR salk3<0")
    cur = periods.current(conn)
    steps = [
        ("Late goods receipts (follow up the vendors)", "ME91F", late_gr, "%d PO item(s) late"),
        ("Stock in quality inspection", "MIGO", qi, "%d material(s) to release or block"),
        ("Blocked (defective) stock", "MB52", blocked, "%d material(s) to scrap, return or rework"),
        ("Reservations to issue", "MB25", resb, "%d reservation item(s) due"),
        ("Deliveries without goods issue", "VL06O", not_gi, "%d delivery(ies) not shipped"),
        ("Physical inventory documents open", "MI20", pi_open, "%d document(s) to count / post"),
        ("Cycle counting due", "MICN", cyc, "%d material(s) due for counting"),
        ("Negative stock / value", "MB5B", neg, "%d valuation record(s) negative"),
    ]
    out = [dict(no=n, step=s, tcode=t, count=c, info=txt % c, status="done" if not c else "open")
           for n, (s, t, c, txt) in enumerate(steps, start=1)]
    mm_ok = bool(cur) and (cur["gjahr"], cur["perio"]) > (gjahr, perio)
    out.append(dict(no=len(out) + 1, step="Close the materials period", tcode="MMPV", count=0,
                    info=("current MM period %02d/%s" % (cur["perio"], cur["gjahr"])) if cur else "period control not used",
                    status="n/a" if not cur else "done" if mm_ok else "open"))
    done = sum(1 for s in out if s["status"] == "done")
    return {"gjahr": gjahr, "perio": perio, "steps": out, "done": done,
            "needed": sum(1 for s in out if s["status"] != "n/a")}


def check_werks(conn, werks):
    if not conn.execute("SELECT 1 FROM plant WHERE werks=?", (werks,)).fetchone():
        raise MMError("Plant %s does not exist" % werks, "MM", "971")
    return werks
