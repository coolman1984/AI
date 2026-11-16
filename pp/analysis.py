"""Production in depth:

1-1 ZPP_CONF     production configuration (display): order types, control keys, MRP types,
                 lot sizes, strategies, scrap reasons, work centers, working days
1-5 ZPP_CLOSE    production month-end: the open work in order with its status
7-1 ZPP_OEE      OEE per line (work center) for a period = availability x performance x quality
                   availability = (planned time - downtime) / planned time      (ZPP_LINEPLAN, ZPP_LOSS)
                   performance  = (good + scrap) / (run time x target units per hour)
                   quality      = good / (good + scrap)                         (CO11N)
                 world class is 85 %; the downtime by reason shows where the time is lost
7-2 ZPP_SCRAP    scrap analysis (Pareto): scrap quantity and value by reason, material and line
7-3 ZPP_PROGRESS order progress: confirmed / delivered %, days late, missing parts
"""
import calendar
import datetime

from mm import util as clock
from mm.util import parse_date, value_of

from . import config as c

DONE = ("DLV", "TECO", "CLSD")


def config(conn):
    return {
        "order_types": [dict(auart=k, text=v["text"], settle=v["settle"], material="yes" if v["material"] else "no",
                             variance="yes" if v["variance"] else "no", over_conf=v["over_conf"] / 100.0)
                        for k, v in c.ORDER_TYPES.items()],
        "control_keys": [dict(steus=k, text=v["text"], conf="yes" if v["conf"] else "no",
                              external="yes" if v["external"] else "no", auto_gr="yes" if v["auto_gr"] else "no")
                         for k, v in c.CONTROL_KEYS.items()],
        "mrp_types": [dict(dismm=k, text=v) for k, v in c.MRP_TYPES.items()],
        "lot_sizes": [dict(disls=k, text=v) for k, v in c.LOT_SIZES.items()],
        "strategies": [dict(strgr=k, text=v) for k, v in c.STRATEGIES.items()],
        "scrap_reasons": [dict(grund=k, text=v) for k, v in c.SCRAP_REASONS.items()],
        "status": [dict(stat=k, text=v) for k, v in c.STATUS.items()],
        "work_centers": [dict(r) for r in conn.execute(
            "SELECT arbpl, werks, ktext, kostl, lstar, kapaz, shifts, ngrad, COALESCE(area,'') area FROM work_center "
            "ORDER BY arbpl")],
        "workdays": ", ".join(calendar.day_abbr[d] for d in c.WORKDAYS),
        "accounts": [dict(use="Work in process (WIP)", hkont=c.WIP_ACCOUNT), dict(use="Change in WIP", hkont=c.WIP_CHANGE),
                     dict(use="External processing fee", hkont=c.EXT_COST_ELEMENT)],
    }


def _period(d1, d2):
    d1 = parse_date(d1)
    d2 = parse_date(d2)
    return d1, d2


def oee(conn, d1, d2):
    d1, d2 = _period(d1, d2)
    from .board import LOSS_REASONS
    out = []
    for w in conn.execute("SELECT * FROM work_center ORDER BY COALESCE(area,''), arbpl"):
        plans = {r["datum"]: r for r in conn.execute("SELECT * FROM pp_lineplan WHERE arbpl=? AND datum BETWEEN ? AND ?",
                                                     (w["arbpl"], d1, d2))}
        conf = conn.execute("SELECT budat, COALESCE(SUM(lmnga),0) good, COALESCE(SUM(xmnga),0) scrap FROM confirmation "
                            "WHERE arbpl=? AND stokz=0 AND budat BETWEEN ? AND ? GROUP BY budat",
                            (w["arbpl"], d1, d2)).fetchall()
        days = set(plans) | {r["budat"] for r in conf}
        if not days:
            continue
        default_h = (w["kapaz"] or 8000) / 1000.0
        planned_min = sum((plans[d]["hours"] if d in plans else default_h) * 60 for d in days)
        down = conn.execute("SELECT COALESCE(SUM(minutes),0) FROM pp_loss WHERE arbpl=? AND datum BETWEEN ? AND ?",
                            (w["arbpl"], d1, d2)).fetchone()[0]
        run_min = max(0.0, planned_min - down)
        good = sum(r["good"] for r in conf)
        scrap = sum(r["scrap"] for r in conf)
        # ideal output in the run time, day by day (units per hour of the plan of that day)
        ideal = 0.0
        for d in days:
            p = plans.get(d)
            if p and p["uph"]:
                dd = conn.execute("SELECT COALESCE(SUM(minutes),0) FROM pp_loss WHERE arbpl=? AND datum=?",
                                  (w["arbpl"], d)).fetchone()[0]
                ideal += max(0, p["hours"] * 60 - dd) / 60.0 * p["uph"]
        avail = run_min / planned_min if planned_min else 0.0
        perf = min(1.0, (good + scrap) / ideal) if ideal else None
        qual = good / float(good + scrap) if good + scrap else None
        o = avail * perf * qual if perf is not None and qual is not None else None
        losses = [dict(reason=r["reason"], text=LOSS_REASONS.get(r["reason"], r["reason"]), minutes=r["m"])
                  for r in conn.execute("SELECT reason, SUM(minutes) m FROM pp_loss WHERE arbpl=? AND datum BETWEEN ? "
                                        "AND ? GROUP BY reason ORDER BY m DESC", (w["arbpl"], d1, d2))]
        pct = lambda x: None if x is None else round(x * 100, 1)       # noqa: E731
        out.append(dict(arbpl=w["arbpl"], ktext=w["ktext"], area=w["area"] or "", days=len(days),
                        planned_min=int(planned_min), downtime=down, run_min=int(run_min), good=good, scrap=scrap,
                        ideal=int(round(ideal / 1000.0)) * 1000, availability=pct(avail), performance=pct(perf), quality=pct(qual),
                        oee=pct(o), losses=losses, world_class=o is not None and o >= 0.85))
    vals = [r["oee"] for r in out if r["oee"] is not None]
    return {"d1": d1, "d2": d2, "rows": out, "average": round(sum(vals) / len(vals), 1) if vals else None,
            "world_class": 85.0}


def _price(conn, matnr, werks, cache):
    k = (matnr, werks)
    if k not in cache:
        v = conn.execute("SELECT * FROM valuation WHERE matnr=? AND bwkey=?", (matnr, werks)).fetchone()
        cache[k] = (v["stprs"] if v["vprsv"] == "S" else v["verpr"], v["peinh"] or 1) if v else (0, 1)
    return cache[k]


def scrap(conn, d1, d2):
    d1, d2 = _period(d1, d2)
    cache = {}
    rows = []
    for r in conn.execute("SELECT c.*, o.matnr, o.werks FROM confirmation c JOIN orders o ON o.aufnr=c.aufnr WHERE "
                          "c.stokz=0 AND c.budat BETWEEN ? AND ? AND (c.xmnga>0 OR c.lmnga>0)", (d1, d2)):
        p, pe = _price(conn, r["matnr"], r["werks"], cache) if r["matnr"] else (0, 1)
        rows.append(dict(arbpl=r["arbpl"], matnr=r["matnr"] or "", grund=r["grund"] or "", good=r["lmnga"] or 0,
                         scrap=r["xmnga"] or 0, value=value_of(r["xmnga"] or 0, p, pe)))

    def group(key, text):
        g = {}
        for r in rows:
            k = r[key]
            x = g.setdefault(k, dict(key=k, text=text(k), good=0, scrap=0, value=0))
            x["good"] += r["good"]
            x["scrap"] += r["scrap"]
            x["value"] += r["value"]
        res = sorted((x for x in g.values() if x["scrap"]), key=lambda x: -x["value"] or -x["scrap"])
        tot = sum(x["value"] for x in res) or sum(x["scrap"] for x in res)
        cum = 0
        for x in res:
            cum += x["value"] if sum(y["value"] for y in res) else x["scrap"]
            x["rate"] = round(x["scrap"] * 100.0 / (x["good"] + x["scrap"]), 2) if x["good"] + x["scrap"] else 0
            x["cum"] = round(cum * 100.0 / tot, 1) if tot else 0
        return res
    mtext = lambda m: (conn.execute("SELECT maktx FROM material WHERE matnr=?", (m,)).fetchone() or [""])[0]  # noqa
    wtext = lambda a: (conn.execute("SELECT ktext FROM work_center WHERE arbpl=?", (a,)).fetchone() or [""])[0]  # noqa
    good = sum(r["good"] for r in rows)
    sc = sum(r["scrap"] for r in rows)
    return {"d1": d1, "d2": d2, "good": good, "scrap": sc, "value": sum(r["value"] for r in rows),
            "rate": round(sc * 100.0 / (good + sc), 2) if good + sc else 0,
            "by_reason": group("grund", lambda k: c.SCRAP_REASONS.get(k, "Not specified")),
            "by_material": group("matnr", mtext), "by_line": group("arbpl", wtext)}


def progress(conn, key_date=None, open_only=True):
    kd = parse_date(key_date) if key_date else clock.today().isoformat()
    sql = ("SELECT o.*, m.maktx FROM orders o LEFT JOIN material m ON m.matnr=o.matnr WHERE o.auart IN (%s)"
           % ",".join("?" * len(c.PROD_ORDER_TYPES)))
    a = list(c.PROD_ORDER_TYPES)
    if open_only:
        sql += " AND o.stat NOT IN ('DLV','TECO','CLSD')"
    out = []
    for o in conn.execute(sql + " ORDER BY COALESCE(o.gltrp,'9999'), o.aufnr", a):
        last = conn.execute("SELECT MAX(vornr) FROM pp_oper WHERE aufnr=?", (o["aufnr"],)).fetchone()[0]
        confirmed = conn.execute("SELECT COALESCE(SUM(lmnga),0) FROM pp_oper WHERE aufnr=? AND vornr=?",
                                 (o["aufnr"], last)).fetchone()[0] if last else o["igmng"] or 0
        gamng = o["gamng"] or 0
        done = o["stat"] in DONE
        late = (datetime.date.fromisoformat(kd) - datetime.date.fromisoformat(o["gltrp"])).days \
            if o["gltrp"] and not done and o["gltrp"] < kd else 0
        missing = "MSPT" in (o["sysst"] or "")
        out.append(dict(aufnr=o["aufnr"], auart=o["auart"], matnr=o["matnr"] or "", maktx=o["maktx"] or o["ktext"] or "",
                        stat=o["stat"], stat_text=c.STATUS.get(o["stat"], o["stat"]), gamng=gamng,
                        confirmed=confirmed, delivered=o["wemng"] or 0,
                        conf_pct=round(confirmed * 100.0 / gamng, 1) if gamng else 0,
                        dlv_pct=round((o["wemng"] or 0) * 100.0 / gamng, 1) if gamng else 0,
                        gstrp=o["gstrp"] or "", gltrp=o["gltrp"] or "", late_days=late, missing=missing,
                        not_started=o["stat"] == "CRTD" and bool(o["gstrp"]) and o["gstrp"] < kd))
    return {"key_date": kd, "rows": out, "late": sum(1 for r in out if r["late_days"]),
            "missing": sum(1 for r in out if r["missing"]), "not_started": sum(1 for r in out if r["not_started"])}


def status(conn, gjahr, perio):
    from co.closing import _docs
    end = "%04d-%02d-%02d" % (gjahr, perio, calendar.monthrange(gjahr, perio)[1])
    kd = min(end, clock.today().isoformat())
    types = ",".join("'%s'" % t for t in c.PROD_ORDER_TYPES)
    one = lambda sql, *a: conn.execute(sql, a).fetchone()[0]          # noqa: E731
    steps = []

    def add(step, tcode, count, info, done=None, needed=True):
        ok = (count == 0) if done is None else done
        steps.append(dict(no=len(steps) + 1, step=step, tcode=tcode, count=count, info=info,
                          status="done" if ok else ("open" if needed else "n/a")))
    n = one("SELECT COUNT(*) FROM orders WHERE auart IN (%s) AND stat='CRTD' AND gstrp<=?" % types, kd)
    add("Orders to release (start date reached)", "CO05N", n, "%d order(s) not released" % n)
    n = one("SELECT COUNT(*) FROM orders WHERE auart IN (%s) AND stat NOT IN ('CRTD','DLV','TECO','CLSD') AND "
            "gltrp<?" % types, kd)
    add("Released orders past the finish date", "COOIS", n, "%d order(s) late" % n)
    n = one("SELECT COUNT(*) FROM pp_resb r JOIN orders o ON o.aufnr=r.aufnr WHERE o.stat='REL' AND r.xloek=0 AND "
            "r.kzear=0 AND r.bdmng>r.enmng AND COALESCE(r.bdter,?)<=?", kd, kd)
    add("Components not issued", "MF60", n, "%d component(s) to pick" % n)
    n = one("SELECT COUNT(*) FROM orders WHERE auart IN ('PP01','ZP03','ZREF') AND stat NOT IN ('DLV','TECO','CLSD') "
            "AND igmng>wemng")
    add("Confirmed, goods receipt missing", "MIGO", n, "%d order(s) to receive" % n)
    n = one("SELECT COUNT(*) FROM orders WHERE auart IN (%s) AND stat='DLV'" % types)
    add("Delivered orders to complete (TECO)", "CO02", n, "%d order(s) not technically completed" % n)
    for step, tcode, vrgng in (("Overhead on orders", "KGI2", "KZPI"),):
        k = _docs(conn, vrgng, gjahr, perio)
        add(step, tcode, k, "%d document(s)" % k, done=k > 0)
    k = one("SELECT COUNT(*) FROM pp_wip WHERE gjahr=? AND perio=?", gjahr, perio)
    add("Work in process (WIP)", "KKAX", k, "%d order(s) valued" % k, done=k > 0)
    k = one("SELECT COUNT(DISTINCT aufnr) FROM order_variance WHERE gjahr=? AND perio=?", gjahr, perio)
    add("Variances", "KKS2", k, "%d order(s)" % k, done=k > 0)
    k = _docs(conn, "KOAO", gjahr, perio)
    add("Settlement", "CO88", k, "%d document(s)" % k, done=k > 0)
    done = sum(1 for s in steps if s["status"] == "done")
    return {"gjahr": gjahr, "perio": perio, "steps": steps, "done": done,
            "needed": sum(1 for s in steps if s["status"] != "n/a")}
