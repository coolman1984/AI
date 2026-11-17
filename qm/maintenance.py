"""Plant maintenance of the factory's own machines.

1. Machine (IE01): technical object on a production line (work center) with its cost center.
2. Preventive plan (IP01): task every N days; scheduling (IP30) creates the PM02 orders that are due.
3. Notification (IW21): M1 = maintenance request, M2 = breakdown with the time the machine stopped.
4. Order (IW31): PM01 corrective / PM02 preventive. Spare parts are issued from stock to the
   machine's cost center (goods issue 201, real FI / CO posting); hours are confirmed (IW41).
5. Completion (IW32 TECO): a breakdown needs its end time - the downtime is written to the
   production line's downtime log (ZPP_LOSS, reason 'machine breakdown'), so the production
   board and OEE show it. A preventive order moves the plan's next due date.
6. Analysis: MTBF, MTTR, availability and maintenance cost per machine.
"""
import datetime

from mm import util as clock
from mm.db import _next_number, transaction
from mm.util import MMError, amt_out, now_ts, parse_date, parse_int, rdiv

ORDER_TYPES = {"PM01": "Corrective maintenance", "PM02": "Preventive maintenance"}
NOTIF_TYPES = {"M1": "Maintenance request", "M2": "Breakdown"}
CRIT = {"A": "Critical - line stops", "B": "Important", "C": "Low"}


def _ts(v, what):
    """'YYYY-MM-DD HH:MM' (or ISO with T) -> datetime"""
    s = str(v or "").strip().replace("T", " ")[:16]
    try:
        return datetime.datetime.strptime(s, "%Y-%m-%d %H:%M")
    except ValueError:
        raise MMError("Enter the %s as date and time (YYYY-MM-DD HH:MM)" % what, "IW", "901")


def rate(conn):
    r = conn.execute("SELECT value FROM tax_setting WHERE key='pm_rate'").fetchone()
    return int(r["value"]) if r else 25000


def _equi(conn, equnr):
    r = conn.execute("SELECT * FROM pm_equi WHERE equnr=?", ((equnr or "").strip().upper(),)).fetchone()
    if not r:
        raise MMError("Machine %s does not exist (IE01)" % (equnr or "''"), "IE", "901")
    return r


# ------------------------------------------------------------------ machines and plans
def save_equipment(conn, data, user):
    equnr = (data.get("equnr") or "").strip().upper()
    if not equnr:
        raise MMError("Enter the machine number", "IE", "902")
    text = (data.get("eqktx") or "").strip()
    if not text:
        raise MMError("Enter the machine description", "IE", "903")
    kostl = (data.get("kostl") or "").strip()
    arbpl = (data.get("arbpl") or "").strip().upper() or None
    if arbpl:
        wc = conn.execute("SELECT * FROM work_center WHERE arbpl=?", (arbpl,)).fetchone()
        if not wc:
            raise MMError("Line (work center) %s does not exist" % arbpl, "IE", "904")
        kostl = kostl or wc["kostl"]
    if not conn.execute("SELECT 1 FROM cost_center WHERE kostl=?", (kostl,)).fetchone():
        raise MMError("Cost center %s does not exist" % (kostl or "''"), "IE", "905")
    crit = (data.get("crit") or "B").upper()
    if crit not in CRIT:
        raise MMError("Criticality must be A, B or C", "IE", "906")
    inbdt = parse_date(data["inbdt"]) if data.get("inbdt") else None
    with transaction(conn):
        conn.execute("INSERT OR REPLACE INTO pm_equi VALUES (?,?,?,?,?,?,?,?,?,?)",
                     (equnr, text[:60], (data.get("werks") or "1000").upper(), arbpl, kostl, crit, inbdt,
                      0 if data.get("inactive") else 1, user, now_ts()))
    return {"equnr": equnr, "message": "Machine %s saved" % equnr}


def save_plan(conn, data, user):
    e = _equi(conn, data.get("equnr"))
    text = (data.get("text") or "").strip()
    if not text:
        raise MMError("Describe the maintenance task", "IP", "901")
    days = parse_int(data.get("interval_days"), "interval (days)", 1, 3650)
    minutes = parse_int(data.get("minutes") or 60, "planned minutes", 1, 100000)
    first = parse_date(data.get("next_due"))
    with transaction(conn):
        warpl = (data.get("warpl") or "").strip() or "P%05d" % _next_number(conn, "PMPLAN")
        conn.execute("INSERT OR REPLACE INTO pm_plan (warpl,equnr,text,interval_days,minutes,next_due,last_done,active,"
                     "usnam,ts) VALUES (?,?,?,?,?,?,(SELECT last_done FROM pm_plan WHERE warpl=?),1,?,?)",
                     (warpl, e["equnr"], text[:80], days, minutes, first, warpl, user, now_ts()))
    return {"warpl": warpl, "message": "Plan %s: %s every %d days, next %s" % (warpl, text, days, first)}


def schedule(conn, user, horizon=0):
    """IP30: a PM02 order for every active plan due within the horizon (none twice)"""
    limit = (clock.today() + datetime.timedelta(days=parse_int(horizon, "horizon", 0, 365, 0))).isoformat()
    made = []
    with transaction(conn):
        for p in conn.execute("SELECT * FROM pm_plan WHERE active=1 AND next_due<=? ORDER BY next_due", (limit,)).fetchall():
            if conn.execute("SELECT 1 FROM pm_order WHERE warpl=? AND status<>'TECO'", (p["warpl"],)).fetchone():
                continue
            made.append(_order(conn, "PM02", p["equnr"], p["text"], user, warpl=p["warpl"], due=p["next_due"],
                               minutes=p["minutes"]))
    return {"orders": made, "message": "%d preventive order(s) created" % len(made)}


# ------------------------------------------------------------------ notifications and orders
def _order(conn, auart, equnr, text, user, warpl=None, qmnum=None, due=None, minutes=0):
    no = str(_next_number(conn, "PMORD"))
    conn.execute("INSERT INTO pm_order (aufnr,auart,equnr,warpl,qmnum,text,status,created,due,usnam,ts) VALUES "
                 "(?,?,?,?,?,?,'REL',?,?,?,?)", (no, auart, equnr, warpl, qmnum, text[:80], clock.today().isoformat(),
                                                 due or clock.today().isoformat(), user, now_ts()))
    return no


def create_notification(conn, data, user):
    qmart = (data.get("qmart") or "").upper()
    if qmart not in NOTIF_TYPES:
        raise MMError("Notification type must be M1 (request) or M2 (breakdown)", "IW", "902")
    e = _equi(conn, data.get("equnr"))
    text = (data.get("text") or "").strip()
    if not text:
        raise MMError("Describe the problem", "IW", "903")
    start = _ts(data.get("start"), "start of the malfunction") if qmart == "M2" else None
    if start and start > clock.now() + datetime.timedelta(minutes=5):
        raise MMError("The breakdown cannot start in the future", "IW", "904")
    with transaction(conn):
        no = str(_next_number(conn, "PMNOT"))
        aufnr = _order(conn, "PM01", e["equnr"], text, user, qmnum=no) if data.get("order") or qmart == "M2" else None
        conn.execute("INSERT INTO pm_notif (qmnum,qmart,equnr,text,start,aufnr,status,created,usnam,ts) VALUES "
                     "(?,?,?,?,?,?,?,?,?,?)", (no, qmart, e["equnr"], text[:120],
                                               start.strftime("%Y-%m-%d %H:%M") if start else None, aufnr,
                                               "IN PROCESS" if aufnr else "OPEN", clock.today().isoformat(), user,
                                               now_ts()))
    return {"qmnum": no, "aufnr": aufnr, "message": "%s %s for %s%s" % (
        NOTIF_TYPES[qmart], no, e["eqktx"], " - order %s created" % aufnr if aufnr else "")}


def create_order(conn, data, user):
    """IW31 from a request (M1) or directly"""
    auart = (data.get("auart") or "PM01").upper()
    if auart not in ORDER_TYPES:
        raise MMError("Order type must be PM01 or PM02", "IW", "905")
    qmnum = (data.get("qmnum") or "").strip() or None
    with transaction(conn):
        if qmnum:
            n = conn.execute("SELECT * FROM pm_notif WHERE qmnum=?", (qmnum,)).fetchone()
            if not n:
                raise MMError("Notification %s does not exist" % qmnum, "IW", "906")
            if n["aufnr"]:
                raise MMError("Notification %s already has order %s" % (qmnum, n["aufnr"]), "IW", "907")
            equnr, text = n["equnr"], data.get("text") or n["text"]
        else:
            equnr, text = _equi(conn, data.get("equnr"))["equnr"], (data.get("text") or "").strip()
            if not text:
                raise MMError("Describe the work", "IW", "903")
        no = _order(conn, auart, equnr, text, user, qmnum=qmnum, due=parse_date(data.get("due")))
        if qmnum:
            conn.execute("UPDATE pm_notif SET aufnr=?, status='IN PROCESS' WHERE qmnum=?", (no, qmnum))
    return {"aufnr": no, "message": "Maintenance order %s created" % no}


def _open_order(conn, aufnr):
    o = conn.execute("SELECT o.*, e.kostl, e.eqktx, e.arbpl FROM pm_order o JOIN pm_equi e ON e.equnr=o.equnr "
                     "WHERE aufnr=?", (str(aufnr or ""),)).fetchone()
    if not o:
        raise MMError("Maintenance order %s does not exist" % aufnr, "IW", "908")
    if o["status"] == "TECO":
        raise MMError("Order %s is completed" % aufnr, "IW", "909")
    return o


def issue_parts(conn, aufnr, items, user, budat=None):
    """spare parts to the order: goods issue 201 to the machine's cost center"""
    from mm.posting import post_goods_movement
    o = _open_order(conn, aufnr)
    lines = []
    for it in items or []:
        if not str(it.get("matnr") or "").strip():
            continue
        lines.append({"bwart": "201", "matnr": it["matnr"], "werks": "1000", "lgort": it.get("lgort") or "",
                      "qty": it.get("qty"), "kostl": o["kostl"], "sgtxt": "PM order %s %s" % (o["aufnr"], o["equnr"])})
    if not lines:
        raise MMError("Enter the spare parts", "IW", "910")
    with transaction(conn):
        res = post_goods_movement(conn, {"budat": parse_date(budat), "bktxt": "Spare parts PM order %s" % o["aufnr"],
                                         "xblnr": o["aufnr"]}, lines, user, tcode="IW31")
        total = 0
        for l in conn.execute("SELECT * FROM mat_doc_item WHERE mblnr=? AND mjahr=?", (res["mblnr"], res["mjahr"])):
            conn.execute("INSERT INTO pm_part (aufnr,matnr,qty,value,mblnr,mjahr,usnam,ts) VALUES (?,?,?,?,?,?,?,?)",
                         (o["aufnr"], l["matnr"], l["menge"], l["dmbtr"], res["mblnr"], res["mjahr"], user, now_ts()))
            total += l["dmbtr"] or 0
        conn.execute("UPDATE pm_order SET parts=parts+? WHERE aufnr=?", (total, o["aufnr"]))
    return {"mblnr": res["mblnr"], "value": total,
            "message": "Spare parts issued (document %s, %s EGP) to cost center %s" % (res["mblnr"], amt_out(total),
                                                                                      o["kostl"])}


def confirm(conn, aufnr, data, user):
    """IW41: working time on the order (labour cost = time x rate)"""
    o = _open_order(conn, aufnr)
    minutes = parse_int(data.get("minutes"), "minutes", 1, 10000)
    labour = rdiv(minutes * rate(conn), 60)
    with transaction(conn):
        conn.execute("INSERT INTO pm_conf (aufnr,datum,minutes,text,usnam,ts) VALUES (?,?,?,?,?,?)",
                     (o["aufnr"], parse_date(data.get("datum")), minutes, (data.get("text") or "")[:80], user, now_ts()))
        conn.execute("UPDATE pm_order SET minutes=minutes+?, labour=labour+? WHERE aufnr=?", (minutes, labour, o["aufnr"]))
    return {"message": "%d minutes confirmed on order %s" % (minutes, o["aufnr"])}


def complete(conn, aufnr, data, user):
    """IW32 technical completion; a breakdown needs the time the machine ran again"""
    o = _open_order(conn, aufnr)
    n = conn.execute("SELECT * FROM pm_notif WHERE qmnum=?", (o["qmnum"],)).fetchone() if o["qmnum"] else None
    msg = ""
    with transaction(conn):
        if n and n["qmart"] == "M2":
            end = _ts(data.get("finish"), "time the machine ran again")
            start = datetime.datetime.strptime(n["start"], "%Y-%m-%d %H:%M")
            if end <= start:
                raise MMError("The end must be after the start of the breakdown (%s)" % n["start"], "IW", "911")
            minutes = int((end - start).total_seconds() // 60)
            conn.execute("UPDATE pm_notif SET finish=?, minutes=?, status='CLOSED' WHERE qmnum=?",
                         (end.strftime("%Y-%m-%d %H:%M"), minutes, n["qmnum"]))
            if o["arbpl"]:                       # downtime of the production line (board, OEE)
                day, left = start, minutes
                while left > 0:
                    cut = min(left, int((datetime.datetime.combine(day.date() + datetime.timedelta(days=1),
                                                                   datetime.time()) - day).total_seconds() // 60))
                    cut = max(1, min(cut, 24 * 60))
                    conn.execute("INSERT INTO pp_loss (datum,arbpl,minutes,reason,text,usnam,ts) VALUES "
                                 "(?,?,?,?,?,?,?)", (day.date().isoformat(), o["arbpl"], cut, "MACH",
                                                     ("%s: %s" % (o["equnr"], n["text"]))[:80], user, now_ts()))
                    left -= cut
                    day = datetime.datetime.combine(day.date() + datetime.timedelta(days=1), datetime.time())
            msg = " - downtime %d min on line %s" % (minutes, o["arbpl"] or "-")
        elif n:
            conn.execute("UPDATE pm_notif SET status='CLOSED' WHERE qmnum=?", (n["qmnum"],))
        if o["warpl"]:
            p = conn.execute("SELECT * FROM pm_plan WHERE warpl=?", (o["warpl"],)).fetchone()
            nxt = (clock.today() + datetime.timedelta(days=p["interval_days"])).isoformat()
            conn.execute("UPDATE pm_plan SET last_done=?, next_due=? WHERE warpl=?",
                         (clock.today().isoformat(), nxt, p["warpl"]))
            msg += " - next preventive maintenance %s" % nxt
        conn.execute("UPDATE pm_order SET status='TECO', teco=?, ts=? WHERE aufnr=?",
                     (clock.today().isoformat(), now_ts(), o["aufnr"]))
    return {"message": "Order %s completed%s" % (o["aufnr"], msg)}


# ------------------------------------------------------------------ lists and analysis
def equipment(conn):
    return [dict(r, crit_text=CRIT.get(r["crit"])) for r in
            conn.execute("SELECT e.*, w.ktext line FROM pm_equi e LEFT JOIN work_center w ON w.arbpl=e.arbpl "
                         "ORDER BY e.equnr")]


def plans(conn):
    today = clock.today().isoformat()
    return [dict(r, overdue=r["next_due"] < today) for r in
            conn.execute("SELECT p.*, e.eqktx FROM pm_plan p JOIN pm_equi e ON e.equnr=p.equnr ORDER BY p.next_due")]


def orders(conn, status=None):
    today = clock.today().isoformat()
    q = "SELECT o.*, e.eqktx, e.kostl FROM pm_order o JOIN pm_equi e ON e.equnr=o.equnr"
    q += " WHERE o.status<>'TECO'" if status == "open" else ""
    out = []
    for r in conn.execute(q + " ORDER BY o.status<>'TECO' DESC, o.due, o.aufnr"):
        d = dict(r, type_text=ORDER_TYPES.get(r["auart"]), labour=amt_out(r["labour"]), parts=amt_out(r["parts"]),
                 total=amt_out(r["labour"] + r["parts"]), overdue=r["status"] != "TECO" and r["due"] < today)
        out.append(d)
    return out


def notifications(conn):
    return [dict(r, type_text=NOTIF_TYPES.get(r["qmart"])) for r in
            conn.execute("SELECT n.*, e.eqktx FROM pm_notif n JOIN pm_equi e ON e.equnr=n.equnr "
                         "ORDER BY n.created DESC, n.qmnum DESC")]


def reliability(conn, d1, d2):
    """per machine: breakdowns, downtime, MTTR, MTBF, availability, cost"""
    d1, d2 = parse_date(d1), parse_date(d2)
    span = ((datetime.date.fromisoformat(d2) - datetime.date.fromisoformat(d1)).days + 1) * 24 * 60
    out = []
    for e in conn.execute("SELECT * FROM pm_equi WHERE active=1 ORDER BY equnr").fetchall():
        b = conn.execute("SELECT COUNT(*) n, COALESCE(SUM(minutes),0) m FROM pm_notif WHERE equnr=? AND qmart='M2' "
                         "AND status='CLOSED' AND substr(start,1,10) BETWEEN ? AND ?", (e["equnr"], d1, d2)).fetchone()
        c = conn.execute("SELECT COALESCE(SUM(labour),0) l, COALESCE(SUM(parts),0) p, COUNT(*) n FROM pm_order "
                         "WHERE equnr=? AND created BETWEEN ? AND ?", (e["equnr"], d1, d2)).fetchone()
        n, down = b["n"], b["m"]
        out.append(dict(equnr=e["equnr"], eqktx=e["eqktx"], arbpl=e["arbpl"], crit=e["crit"], breakdowns=n,
                        downtime=down, mttr=round(down / n) if n else None,
                        mtbf=round((span - down) / n / 60.0, 1) if n else None,
                        availability=round(100.0 * (span - down) / span, 2), orders=c["n"],
                        cost=amt_out(c["l"] + c["p"]), labour=amt_out(c["l"]), parts=amt_out(c["p"])))
    return out


def cockpit(conn, d1, d2):
    rel = reliability(conn, d1, d2)
    op = orders(conn, "open")
    pl = plans(conn)
    down = sum(r["downtime"] for r in rel)
    br = sum(r["breakdowns"] for r in rel)
    pm2 = conn.execute("SELECT COUNT(*) FROM pm_order WHERE auart='PM02' AND teco BETWEEN ? AND ?",
                       (parse_date(d1), parse_date(d2))).fetchone()[0]
    done = conn.execute("SELECT COUNT(*) FROM pm_order WHERE teco BETWEEN ? AND ?", (parse_date(d1), parse_date(d2))).fetchone()[0]
    return {"open_orders": len(op), "overdue_orders": sum(1 for o in op if o["overdue"]),
            "overdue_plans": sum(1 for p in pl if p["overdue"]), "breakdowns": br, "downtime": down,
            "mttr": round(down / br) if br else None,
            "availability": round(sum(r["availability"] for r in rel) / len(rel), 2) if rel else None,
            "planned_share": round(100.0 * pm2 / done, 1) if done else None,
            "cost": amt_out(sum(int(round(float(r["cost"]) * 100)) for r in rel)),
            "machines": rel, "orders": op, "plans": pl}
