"""ZPP_BOARD production status board (shop-floor TV screen), with its inputs
ZPP_LINEPLAN (daily plan per line) and ZPP_LOSS (downtime log).

Per line (work center) and day:
  PLAN     planned quantity of the day (ZPP_LINEPLAN)
  TARGET   the part of the plan that should be done by now: plan x elapsed share of the shift
  PROD     confirmed yield of the day (CO11N confirmations of the line)
  DIFF     PROD - TARGET  (behind plan when negative)
  ACH %    PROD / TARGET
  ON TIME  share of the elapsed shift hours in which the hourly output reached the target
           units per hour ('-' when the confirmations carry no time of the day)
  DEFECT % scrap / (yield + scrap)
  LOSS     downtime minutes of the day (ZPP_LOSS) and the units lost by it (minutes x UPH)
  UPH      target units per hour and the result (PROD / elapsed hours)
  MAN      operators on the line
Lines are grouped by the work center's area. Below the lines: shipping, attendance,
material shortages, quality (scrap / rework) and late purchase order items.
"""
import datetime

from mm import util as clock
from mm.db import transaction
from mm.util import MMError, now_ts, parse_date, parse_int, parse_qty, rdiv

LOSS_REASONS = {"MAT": "Material shortage", "MACH": "Machine breakdown", "CHG": "Model changeover",
                "QUAL": "Quality problem", "MAN": "Manpower shortage", "UTIL": "Power / utilities",
                "OTH": "Other"}


def _wc(conn, arbpl):
    r = conn.execute("SELECT * FROM work_center WHERE arbpl=?", ((arbpl or "").upper(),)).fetchone()
    if not r:
        raise MMError("Line (work center) %s does not exist" % arbpl, "PB", "951")
    return r


def _hhmm(text):
    try:
        h, m = str(text or "").strip().split(":")
        h, m = int(h), int(m)
        if 0 <= h < 24 and 0 <= m < 60:
            return "%02d:%02d" % (h, m)
    except ValueError:
        pass
    raise MMError("Enter the shift start as HH:MM", "PB", "952")


def save_plan(conn, data, user):
    """ZPP_LINEPLAN: plan of one line for one day"""
    datum = parse_date(data.get("datum"))
    with transaction(conn):
        wc = _wc(conn, data.get("arbpl"))
        aufnr = (data.get("aufnr") or "").strip()
        matnr = (data.get("matnr") or "").strip().upper()
        if aufnr:
            o = conn.execute("SELECT * FROM orders WHERE aufnr=?", (aufnr,)).fetchone()
            if not o:
                raise MMError("Order %s does not exist" % aufnr, "PB", "953")
            matnr = matnr or (o["matnr"] or "")
        if matnr and not conn.execute("SELECT 1 FROM material WHERE matnr=?", (matnr,)).fetchone():
            raise MMError("Material %s does not exist" % matnr, "PB", "954")
        plan = parse_qty(data.get("plan") or "0", allow_zero=True)
        uph = parse_qty(data.get("uph") or "0", allow_zero=True)
        hours = parse_int(data.get("hours") or 8, "shift hours", 1, 24)
        if plan and not uph:
            uph = rdiv(plan, hours)                       # default: plan spread over the shift
        conn.execute("INSERT OR REPLACE INTO pp_lineplan (datum,arbpl,aufnr,matnr,plan,uph,man,start,hours,usnam,ts) "
                     "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                     (datum, wc["arbpl"], aufnr or None, matnr or None, plan, uph,
                      parse_int(data.get("man") or 0, "operators", 0, 9999), _hhmm(data.get("start") or "08:00"),
                      hours, user, now_ts()))
    return {"message": "Plan of line %s for %s saved" % (wc["arbpl"], datum)}


def copy_plans(conn, src, dst, user):
    src, dst = parse_date(src), parse_date(dst)
    rows = conn.execute("SELECT * FROM pp_lineplan WHERE datum=?", (src,)).fetchall()
    if not rows:
        raise MMError("No line plan on %s to copy" % src, "PB", "955")
    with transaction(conn):
        for r in rows:
            conn.execute("INSERT OR REPLACE INTO pp_lineplan (datum,arbpl,aufnr,matnr,plan,uph,man,start,hours,usnam,ts) "
                         "VALUES (?,?,?,?,?,?,?,?,?,?,?)", (dst, r["arbpl"], r["aufnr"], r["matnr"], r["plan"], r["uph"],
                                                            r["man"], r["start"], r["hours"], user, now_ts()))
    return {"message": "%d line plan(s) copied from %s to %s" % (len(rows), src, dst)}


def plans(conn, datum):
    datum = parse_date(datum)
    out = []
    for w in conn.execute("SELECT * FROM work_center ORDER BY COALESCE(area,''), arbpl"):
        p = conn.execute("SELECT * FROM pp_lineplan WHERE datum=? AND arbpl=?", (datum, w["arbpl"])).fetchone()
        d = dict(arbpl=w["arbpl"], ktext=w["ktext"], area=w["area"] or "", datum=datum)
        d.update({k: p[k] for k in ("aufnr", "matnr", "plan", "uph", "man", "start", "hours")} if p else
                 dict(aufnr="", matnr="", plan=0, uph=0, man=0, start="08:00", hours=8))
        out.append(d)
    return out


def add_loss(conn, data, user):
    """ZPP_LOSS: downtime of a line"""
    datum = parse_date(data.get("datum"))
    reason = (data.get("reason") or "").upper()
    if reason not in LOSS_REASONS:
        raise MMError("Reason %s does not exist" % reason, "PB", "956")
    minutes = parse_int(data.get("minutes"), "minutes", 1, 24 * 60)
    with transaction(conn):
        wc = _wc(conn, data.get("arbpl"))
        lid = conn.execute("INSERT INTO pp_loss (datum,arbpl,minutes,reason,text,usnam,ts) VALUES (?,?,?,?,?,?,?)",
                           (datum, wc["arbpl"], minutes, reason, (data.get("text") or "")[:80], user,
                            now_ts())).lastrowid
    return {"id": lid, "message": "%d minutes %s on line %s recorded" % (minutes, LOSS_REASONS[reason].lower(),
                                                                         wc["arbpl"])}


def losses(conn, datum):
    out = []
    for r in conn.execute("SELECT * FROM pp_loss WHERE datum=? ORDER BY arbpl, id", (parse_date(datum),)):
        d = dict(r)
        d["reason_text"] = LOSS_REASONS.get(r["reason"], r["reason"])
        out.append(d)
    return out


# ------------------------------------------------------------------ the board
def _elapsed(datum, start, hours, now):
    """share of the shift that has passed (0..1) at the moment 'now'"""
    day = datetime.date.fromisoformat(datum)
    if day < now.date():
        return 1.0
    if day > now.date():
        return 0.0
    h, m = (int(x) for x in start.split(":"))
    begin = datetime.datetime.combine(day, datetime.time(h, m))
    return max(0.0, min(1.0, (now - begin).total_seconds() / (hours * 3600.0)))


def _line(conn, w, datum, now):
    p = conn.execute("SELECT * FROM pp_lineplan WHERE datum=? AND arbpl=?", (datum, w["arbpl"])).fetchone()
    conf = conn.execute("SELECT * FROM confirmation WHERE arbpl=? AND budat=? AND stokz=0", (w["arbpl"], datum)).fetchall()
    prod = sum(c["lmnga"] or 0 for c in conf)
    scrap = sum(c["xmnga"] or 0 for c in conf)
    if not p and not conf:
        return None
    plan = p["plan"] if p else 0
    uph = p["uph"] if p else 0
    hours = p["hours"] if p else 8
    start = p["start"] if p else "08:00"
    share = _elapsed(datum, start, hours, now)
    target = int(plan * share) // 1000 * 1000                     # whole units reached by now
    worked = hours * share
    loss_min = conn.execute("SELECT COALESCE(SUM(minutes),0) FROM pp_loss WHERE datum=? AND arbpl=?",
                            (datum, w["arbpl"])).fetchone()[0]
    # hourly output from the confirmation time of the day (only confirmations entered on that day)
    on_time = None
    if uph and share > 0:
        h0 = int(start[:2])
        timed = [c for c in conf if (c["ersda"] or "")[:10] == datum]
        if timed and len(timed) == len(conf):
            per_hour = {}
            for c in timed:
                hr = int(c["ersda"][11:13])
                per_hour[hr] = per_hour.get(hr, 0) + (c["lmnga"] or 0)
            done_hours = [h0 + i for i in range(max(1, int(worked)))]
            ok = sum(1 for hr in done_hours if per_hour.get(hr, 0) >= uph)
            on_time = round(ok * 100.0 / len(done_hours), 1)
    model = (p["matnr"] if p else "") or ""
    if not model and conf:
        o = conn.execute("SELECT matnr, ktext FROM orders WHERE aufnr=?", (conf[-1]["aufnr"],)).fetchone()
        model = (o["matnr"] or o["ktext"] or "") if o else ""
    mtext = conn.execute("SELECT maktx FROM material WHERE matnr=?", (model,)).fetchone()
    orders = sorted({c["aufnr"] for c in conf} | ({p["aufnr"]} if p and p["aufnr"] else set()))
    return dict(
        arbpl=w["arbpl"], ktext=w["ktext"], area=w["area"] or "Plant %s" % (w["werks"] or ""),
        model=model, model_text=mtext["maktx"] if mtext else "", orders=orders,
        plan=plan, target=target, prod=prod, diff=prod - target, scrap=scrap,
        ach=round(prod * 100.0 / target, 1) if target else None,
        on_time=on_time,
        defect=round(scrap * 100.0 / (prod + scrap), 2) if prod + scrap else 0.0,
        loss_min=loss_min, loss_units=rdiv(rdiv(loss_min * uph, 60), 1000) * 1000 if uph else 0,
        uph_target=uph, uph_result=int(round(prod / worked / 1000.0)) * 1000 if worked > 0 else 0,
        man=p["man"] if p else 0, share=round(share * 100, 1), start=start, hours=hours,
        status="none" if not plan else "ahead" if prod >= target else "behind")


def _total(rows):
    t = dict(lines=len(rows), running=sum(1 for r in rows if r["prod"] > 0),
             plan=sum(r["plan"] for r in rows), target=sum(r["target"] for r in rows),
             prod=sum(r["prod"] for r in rows), scrap=sum(r["scrap"] for r in rows),
             loss_min=sum(r["loss_min"] for r in rows), loss_units=sum(r["loss_units"] for r in rows),
             uph_target=sum(r["uph_target"] for r in rows), uph_result=sum(r["uph_result"] for r in rows),
             man=sum(r["man"] for r in rows))
    t["diff"] = t["prod"] - t["target"]
    t["ach"] = round(t["prod"] * 100.0 / t["target"], 1) if t["target"] else None
    t["defect"] = round(t["scrap"] * 100.0 / (t["prod"] + t["scrap"]), 2) if t["prod"] + t["scrap"] else 0.0
    ot = [r["on_time"] for r in rows if r["on_time"] is not None]
    t["on_time"] = round(sum(ot) / len(ot), 1) if ot else None
    t["ahead"] = sum(1 for r in rows if r["status"] == "ahead")
    return t


def _week(day):
    mon = day - datetime.timedelta(days=day.weekday())
    return mon, mon + datetime.timedelta(days=6)


def _shipping(conn, day):
    out = []
    for back in (1, 0):
        d1, d2 = _week(day - datetime.timedelta(days=7 * back))
        a, b = d1.isoformat(), d2.isoformat()
        ordered = conn.execute("SELECT COALESCE(SUM(e.wmeng),0) FROM sd_vbep e JOIN sd_vbak k ON k.vbeln=e.vbeln "
                               "WHERE e.edatu BETWEEN ? AND ?", (a, b)).fetchone()[0]
        created = conn.execute("SELECT COALESCE(SUM(i.lfimg),0) FROM sd_lips i JOIN sd_likp h ON h.vbeln=i.vbeln "
                               "WHERE h.wadat BETWEEN ? AND ?", (a, b)).fetchone()[0]
        shipped = conn.execute("SELECT COALESCE(SUM(i.lfimg),0) FROM sd_lips i JOIN sd_likp h ON h.vbeln=i.vbeln "
                               "WHERE h.wbstk='C' AND COALESCE(h.wadat_ist,h.wadat) BETWEEN ? AND ?",
                               (a, b)).fetchone()[0]
        out.append(dict(week="W%02d" % d1.isocalendar()[1], d1=a, d2=b, ordered=ordered, delivery=created,
                        shipped=shipped, open=max(0, created - shipped),
                        rate=round(shipped * 100.0 / created, 1) if created else None))
    return out


def _attendance(conn, datum):
    out = []
    for u in conn.execute("SELECT * FROM hr_orgunit ORDER BY orgeh"):
        total = conn.execute("SELECT COUNT(*) FROM hr_employee WHERE status='A' AND orgeh=? AND hire_date<=? AND "
                             "(leave_date IS NULL OR leave_date='' OR leave_date>=?)",
                             (u["orgeh"], datum, datum)).fetchone()[0]
        if not total:
            continue
        absent = conn.execute("SELECT COUNT(DISTINCT a.pernr) FROM hr_absence a JOIN hr_employee e ON e.pernr=a.pernr "
                              "WHERE e.orgeh=? AND a.status='A' AND ? BETWEEN a.begda AND a.endda",
                              (u["orgeh"], datum)).fetchone()[0]
        attend = total - absent
        out.append(dict(team=u["text"], total=total, absent=absent, attend=attend,
                        rate=round(attend * 100.0 / total, 1)))
    return out


def _shortages(conn, datum):
    from pp.order import stock_unrestricted
    need = {}
    for r in conn.execute("SELECT r.matnr, r.werks, r.aufnr, r.bdter, r.bdmng-r.enmng AS open FROM pp_resb r JOIN "
                          "orders o ON o.aufnr=r.aufnr WHERE o.stat='REL' AND r.xloek=0 AND r.kzear=0 AND "
                          "r.bdmng>r.enmng AND COALESCE(r.bdter, ?) <= date(?, '+7 day')", (datum, datum)):
        k = (r["matnr"], r["werks"])
        n = need.setdefault(k, dict(matnr=r["matnr"], werks=r["werks"], required=0, orders=set(), bdter=r["bdter"]))
        n["required"] += r["open"]
        n["orders"].add(r["aufnr"])
        n["bdter"] = min(n["bdter"] or datum, r["bdter"] or datum)
    out = []
    for (matnr, werks), n in need.items():
        st = stock_unrestricted(conn, matnr, werks)
        if st < n["required"]:
            m = conn.execute("SELECT maktx FROM material WHERE matnr=?", (matnr,)).fetchone()
            out.append(dict(matnr=matnr, maktx=m["maktx"] if m else "", required=n["required"], stock=st,
                            short=n["required"] - st, orders=sorted(n["orders"]), bdter=n["bdter"]))
    return sorted(out, key=lambda x: x["bdter"] or "")


def _quality(conn, day):
    d = day.isoformat()
    d1 = (day - datetime.timedelta(days=1)).isoformat()
    w1, w2 = (x.isoformat() for x in _week(day))
    out = []
    for w in conn.execute("SELECT arbpl FROM work_center ORDER BY COALESCE(area,''), arbpl"):
        def s(a, b):
            return conn.execute("SELECT COALESCE(SUM(xmnga),0) FROM confirmation WHERE arbpl=? AND stokz=0 AND "
                                "budat BETWEEN ? AND ?", (w["arbpl"], a, b)).fetchone()[0]
        out.append(dict(arbpl=w["arbpl"], today=s(d, d), d1=s(d1, d1), week=s(w1, w2)))
    rework = conn.execute("SELECT COUNT(*) FROM orders WHERE auart IN ('ZP03','ZREF') AND stat IN ('CRTD','REL')"
                          ).fetchone()[0]
    blocked = conn.execute("SELECT COALESCE(SUM(qty),0) FROM quant WHERE insmk='B'").fetchone()[0]
    return {"lines": out, "rework_open": rework, "blocked_stock": blocked}


def _po_pending(conn, day):
    from pur.config import PURCH_GROUPS
    from pur.followup import overdue
    rows = overdue(conn, (day + datetime.timedelta(days=1)).isoformat())     # include items due today
    out = {}
    for r in rows:
        late = r["days"] - 1                                                  # 0 = due today
        g = conn.execute("SELECT ekgrp FROM po_header WHERE ebeln=?", (r["ebeln"],)).fetchone()["ekgrp"] or "001"
        o = out.setdefault(g, {"ekgrp": g, "text": PURCH_GROUPS.get(g, g), "d0": 0, "d1": 0, "d2": 0, "d3": 0})
        o["d0" if late <= 0 else "d1" if late == 1 else "d2" if late == 2 else "d3"] += 1
    return sorted(out.values(), key=lambda x: x["ekgrp"])


def board(conn, datum=None, now=None):
    now = now or clock.now()
    if isinstance(now, str):
        now = datetime.datetime.fromisoformat(now)
    datum = parse_date(datum) if datum else now.date().isoformat()
    day = datetime.date.fromisoformat(datum)
    areas = {}
    for w in conn.execute("SELECT * FROM work_center ORDER BY COALESCE(area,''), arbpl"):
        r = _line(conn, w, datum, now)
        if r:
            areas.setdefault(r["area"], []).append(r)
    groups = [dict(area=a, lines=rows, total=_total(rows)) for a, rows in areas.items()]
    allrows = [r for g in groups for r in g["lines"]]
    last = conn.execute("SELECT MAX(d) FROM (SELECT MAX(datum) d FROM pp_lineplan WHERE datum<=? UNION ALL "
                        "SELECT MAX(budat) FROM confirmation WHERE budat<=? AND stokz=0)",
                        (now.date().isoformat(), now.date().isoformat())).fetchone()[0]
    return {"datum": datum, "now": now.isoformat(timespec="seconds"), "groups": groups,
            "total": _total(allrows) if allrows else None, "last_day": last,
            "shipping": _shipping(conn, day), "attendance": _attendance(conn, datum),
            "shortages": _shortages(conn, datum), "quality": _quality(conn, day),
            "po_pending": _po_pending(conn, day), "reasons": LOSS_REASONS}


def sample(conn, days, user="PLANNER"):
    """demo: line areas, plans and downtime for the sample production days
    days: dict day-number -> ISO date"""
    for arbpl, area in (("WC-MACH", "MACHINING"), ("WC-ASSY", "ASSEMBLY"), ("WC-REPR", "SERVICE & REPAIR")):
        conn.execute("UPDATE work_center SET area=? WHERE arbpl=? AND COALESCE(area,'')=''", (area, arbpl))
    for day, arbpl, aufnr, matnr, plan, uph, man in (
            (3, "WC-MACH", "1000002", "", "21", "3", 6), (6, "WC-ASSY", "1000003", "", "20", "2.5", 4),
            (7, "WC-ASSY", "1000004", "", "32", "4", 4), (7, "WC-MACH", "", "SF-3101", "10", "1.25", 6),
            (7, "WC-REPR", "", "", "2", "0.25", 2), (5, "WC-REPR", "1000006", "", "10", "1.25", 2)):
        save_plan(conn, dict(datum=days[day], arbpl=arbpl, aufnr=aufnr, matnr=matnr, plan=plan, uph=uph, man=man),
                  user)
    add_loss(conn, dict(datum=days[7], arbpl="WC-MACH", minutes="120", reason="MAT",
                        text="Steel sheets RM-1001 late from the warehouse"), user)
    add_loss(conn, dict(datum=days[7], arbpl="WC-ASSY", minutes="25", reason="CHG",
                        text="Changeover to the new order"), user)
    add_loss(conn, dict(datum=days[6], arbpl="WC-ASSY", minutes="40", reason="QUAL", text="Hinge rework"), user)
