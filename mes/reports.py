"""GMES reports: hourly production per line, quality (FPY / RTY / DPU / DPMO, defect Pareto), WIP by
operation with aging, cycle time vs standard and takt, operator performance and the GMES cockpit.

Definitions (standard shop-floor metrics):
  FPY  first pass yield of an operation = units passing at the first attempt / units tested the first time
  RTY  rolled throughput yield of a route = product of the FPY of its operations
  DPU  defects per unit = NG bookings / units processed
  DPMO defects per million opportunities = NG / (units x opportunities per unit) x 1,000,000
  Takt available minutes / planned units; output of a line = units passing the line's last operation
"""
import datetime

from mm import util as clock

from .track import ANDON, DEFECTS


def _range(d1, d2, days=7):
    d2 = d2 or clock.today().isoformat()
    d1 = d1 or (datetime.date.fromisoformat(d2) - datetime.timedelta(days=days - 1)).isoformat()
    return d1, d2


def _last_ops(conn):
    """(matnr, arbpl) -> last operation of that material on that line"""
    out = {}
    for r in conn.execute("SELECT matnr, arbpl, MAX(vornr) v FROM routing WHERE arbpl IS NOT NULL GROUP BY matnr, arbpl"):
        out[(r["matnr"], r["arbpl"])] = r["v"]
    return out


def lines(conn):
    return [dict(r) for r in conn.execute("SELECT DISTINCT w.arbpl, w.ktext FROM work_center w JOIN mes_station s ON s.arbpl=w.arbpl "
                                          "ORDER BY w.arbpl")]


# ------------------------------------------------------------------ hourly production board
def hourly(conn, day=None, arbpl=None):
    day = day or clock.today().isoformat()
    last = _last_ops(conn)
    out = []
    for ln in lines(conn):
        if arbpl and ln["arbpl"] != arbpl:
            continue
        p = conn.execute("SELECT * FROM pp_lineplan WHERE datum=? AND arbpl=?", (day, ln["arbpl"])).fetchone()
        start = int((p["start"] if p else "08:00")[:2])
        hours = p["hours"] if p else 8
        uph = (p["uph"] / 1000.0) if p else 0
        done = {}
        for e in conn.execute("SELECT matnr, vornr, ts FROM mes_event WHERE day=? AND arbpl=? AND result='OK'", (day, ln["arbpl"])):
            if last.get((e["matnr"], ln["arbpl"])) == e["vornr"]:
                h = int(e["ts"][11:13])
                done[h] = done.get(h, 0) + 1
        ng = {}
        for e in conn.execute("SELECT ts FROM mes_event WHERE day=? AND arbpl=? AND result='NG'", (day, ln["arbpl"])):
            h = int(e["ts"][11:13])
            ng[h] = ng.get(h, 0) + 1
        hrs = sorted(set(range(start, start + hours)) | set(done) | set(ng))
        rows, cp, ca = [], 0.0, 0
        for h in hrs:
            plan = uph if start <= h < start + hours else 0
            cp += plan
            ca += done.get(h, 0)
            rows.append(dict(hour="%02d:00" % h, plan=round(plan, 1), actual=done.get(h, 0), ng=ng.get(h, 0),
                             cum_plan=round(cp, 1), cum_actual=ca, gap=round(ca - cp, 1),
                             ach=round(100.0 * done.get(h, 0) / plan, 1) if plan else None))
        total_plan = round(uph * hours, 1)
        andon = conn.execute("SELECT COUNT(*) FROM mes_andon WHERE arbpl=? AND status<>'CLOSED'", (ln["arbpl"],)).fetchone()[0]
        out.append(dict(arbpl=ln["arbpl"], text=ln["ktext"], plan=total_plan, actual=ca, uph=uph,
                        ach=round(100.0 * ca / total_plan, 1) if total_plan else None, ng=sum(ng.values()), open_andon=andon,
                        takt_sec=round(3600.0 / uph, 1) if uph else None, hours=rows))
    return {"day": day, "lines": out}


# ------------------------------------------------------------------ quality metrics
def quality(conn, d1=None, d2=None, arbpl=None):
    d1, d2 = _range(d1, d2)
    q = "SELECT e.*, s.opps FROM mes_event e LEFT JOIN mes_station s ON s.station=e.station WHERE e.day BETWEEN ? AND ?"
    a = [d1, d2]
    if arbpl:
        q += " AND e.arbpl=?"
        a.append(arbpl)
    ev = [dict(r) for r in conn.execute(q, a)]
    ops = {}
    for e in ev:
        if e["result"] not in ("OK", "NG"):
            continue
        k = (e["matnr"], e["vornr"])
        o = ops.setdefault(k, dict(matnr=e["matnr"], vornr=e["vornr"], arbpl=e["arbpl"], station=e["station"], first=0,
                                   first_ok=0, units=set(), ng=0, opps=e["opps"] or 1))
        o["units"].add(e["serial"])
        if e["attempt"] == 1:
            o["first"] += 1
            o["first_ok"] += e["result"] == "OK"
        o["ng"] += e["result"] == "NG"
    rows = []
    for o in sorted(ops.values(), key=lambda x: (x["matnr"], x["vornr"])):
        u = len(o["units"])
        rows.append(dict(matnr=o["matnr"], vornr=o["vornr"], arbpl=o["arbpl"], station=o["station"], units=u, tested_first=o["first"],
                         passed_first=o["first_ok"], fpy=round(100.0 * o["first_ok"] / o["first"], 2) if o["first"] else None,
                         defects=o["ng"], dpu=round(o["ng"] / u, 4) if u else 0,
                         dpmo=round(1e6 * o["ng"] / (u * o["opps"])) if u else 0))
    rty = {}
    for r in rows:
        if r["fpy"] is not None:
            rty[r["matnr"]] = rty.get(r["matnr"], 1.0) * r["fpy"] / 100.0
    units = len({e["serial"] for e in ev})
    ng = sum(1 for e in ev if e["result"] == "NG")
    first = [e for e in ev if e["attempt"] == 1 and e["result"] in ("OK", "NG")]
    pareto = {}
    for e in ev:
        if e["result"] in ("NG", "SCRAP") and e["defect"]:
            p = pareto.setdefault(e["defect"], dict(code=e["defect"], text=DEFECTS.get(e["defect"], e["defect"]), count=0, stations={}))
            p["count"] += 1
            p["stations"][e["station"]] = p["stations"].get(e["station"], 0) + 1
    par = sorted(pareto.values(), key=lambda x: -x["count"])
    tot, cum = sum(p["count"] for p in par) or 1, 0
    for p in par:
        cum += p["count"]
        p["cum_pct"] = round(100.0 * cum / tot, 1)
        p["stations"] = ", ".join("%s (%d)" % kv for kv in sorted(p["stations"].items(), key=lambda kv: -kv[1]))
    scrap = sum(1 for e in ev if e["result"] == "SCRAP")
    return {"period": [d1, d2], "ops": rows, "rty": {k: round(100 * v, 2) for k, v in rty.items()}, "units": units, "defects": ng,
            "fpy": round(100.0 * sum(1 for e in first if e["result"] == "OK") / len(first), 2) if first else None,
            "dpu": round(ng / units, 4) if units else 0, "scrap": scrap, "repairs": sum(1 for e in ev if e["result"] == "REPAIRED"),
            "pareto": par}


# ------------------------------------------------------------------ WIP and cycle time
def wip(conn):
    now = clock.now()
    by = {}
    units = []
    for u in conn.execute("SELECT u.*, (SELECT MAX(ts) FROM mes_event e WHERE e.serial=u.serial) last FROM mes_unit u "
                          "WHERE u.status IN ('WIP','REPAIR')"):
        last = u["last"] or u["created"]
        age_h = round((now - datetime.datetime.fromisoformat(last)).total_seconds() / 3600.0, 1) if last else 0
        k = ("REPAIR" if u["status"] == "REPAIR" else u["next_vornr"], u["matnr"])
        b = by.setdefault(k, dict(step=k[0], matnr=u["matnr"], units=0, max_age_h=0, old=0))
        b["units"] += 1
        b["max_age_h"] = max(b["max_age_h"], age_h)
        b["old"] += age_h > 24
        units.append(dict(serial=u["serial"], aufnr=u["aufnr"], matnr=u["matnr"], status=u["status"], step=k[0], repairs=u["repairs"],
                          last=last, age_h=age_h))
    return {"by_step": sorted(by.values(), key=lambda x: (x["matnr"], x["step"])), "units": sorted(units, key=lambda x: -x["age_h"]),
            "total": len(units), "stuck": sum(1 for u in units if u["age_h"] > 24)}


def cycle(conn, d1=None, d2=None):
    d1, d2 = _range(d1, d2)
    rows = []
    for r in conn.execute("SELECT e.station, s.text, s.ct_std, COUNT(*) n, AVG(e.cycle_sec) avg_ct, MIN(e.cycle_sec) min_ct, "
                          "MAX(e.cycle_sec) max_ct FROM mes_event e JOIN mes_station s ON s.station=e.station WHERE e.day BETWEEN ? AND ? "
                          "AND e.cycle_sec IS NOT NULL AND e.result IN ('OK','NG') GROUP BY e.station ORDER BY e.station", (d1, d2)):
        avg = r["avg_ct"] or 0
        rows.append(dict(station=r["station"], text=r["text"], bookings=r["n"], ct_std=r["ct_std"], avg_ct=round(avg, 1),
                         min_ct=r["min_ct"], max_ct=r["max_ct"],
                         efficiency=round(100.0 * r["ct_std"] / avg, 1) if avg and r["ct_std"] else None))
    bottleneck = max(rows, key=lambda x: x["avg_ct"]) if rows else None
    return {"period": [d1, d2], "stations": rows, "bottleneck": bottleneck["station"] if bottleneck else None}


def operators(conn, d1=None, d2=None):
    d1, d2 = _range(d1, d2)
    rows = []
    for r in conn.execute("SELECT e.operator, h.name, COUNT(*) n, SUM(e.result='OK') ok, SUM(e.result='NG') ng, "
                          "SUM(CASE WHEN e.attempt=1 AND e.result IN ('OK','NG') THEN 1 ELSE 0 END) first, "
                          "SUM(CASE WHEN e.attempt=1 AND e.result='OK' THEN 1 ELSE 0 END) first_ok, COUNT(DISTINCT e.day) days, "
                          "SUM(e.cycle_sec) secs, COUNT(DISTINCT e.station) stations FROM mes_event e "
                          "LEFT JOIN hr_employee h ON h.pernr=e.operator WHERE e.day BETWEEN ? AND ? AND e.result IN ('OK','NG','REPAIRED') "
                          "GROUP BY e.operator ORDER BY n DESC", (d1, d2)):
        rows.append(dict(operator=r["operator"], name=r["name"] or r["operator"], bookings=r["n"], ok=r["ok"], ng=r["ng"],
                         fpy=round(100.0 * r["first_ok"] / r["first"], 1) if r["first"] else None, days=r["days"],
                         per_day=round(r["n"] / r["days"], 1) if r["days"] else 0,
                         uph=round(r["n"] / (r["secs"] / 3600.0), 1) if r["secs"] else None, stations=r["stations"]))
    return {"period": [d1, d2], "operators": rows}


# ------------------------------------------------------------------ cockpit
def cockpit(conn, day=None):
    day = day or clock.today().isoformat()
    h = hourly(conn, day)
    q = quality(conn, day, day)
    q7 = quality(conn)
    w = wip(conn)
    a = conn.execute("SELECT kind, COUNT(*) n FROM mes_andon WHERE status<>'CLOSED' GROUP BY kind").fetchall()
    plan = sum(x["plan"] for x in h["lines"])
    act = sum(x["actual"] for x in h["lines"])
    to_conf = conn.execute("SELECT aufnr, SUM(status='DONE') done, SUM(status='SCRAP') scrap FROM mes_unit WHERE confirmed=0 "
                           "AND status IN ('DONE','SCRAP') GROUP BY aufnr").fetchall()
    return {"day": day, "plan": plan, "actual": act, "ach": round(100.0 * act / plan, 1) if plan else None,
            "fpy_today": q["fpy"], "fpy_7d": q7["fpy"], "dpu_7d": q7["dpu"], "rty_7d": q7["rty"], "top_defect": (q7["pareto"] or [None])[0],
            "wip": w["total"], "stuck": w["stuck"], "in_repair": sum(1 for u in w["units"] if u["status"] == "REPAIR"),
            "andon_open": {r["kind"]: r["n"] for r in a}, "andon_kinds": ANDON, "lines": h["lines"],
            "to_confirm": [dict(r) for r in to_conf]}
