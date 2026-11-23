"""Time and attendance (positive time recording): shifts, public holidays, clock-in / clock-out, the daily
time evaluation (late, early leave, absence, overtime by type, daily limit), overtime approval into
payroll and the overtime notice to the labour office required by Labour Law 14/2025 (within 7 days).

Evaluation rules (per employee and day):
  * planned time = the shift (minus break) on a working day; Friday and public holidays are rest days
  * late = first clock-in after shift start + grace minutes; early leave = last clock-out before shift end
  * no clock-in on a working day: approved absence -> LEAVE, otherwise ABSENT (unexcused)
  * overtime = worked minutes beyond planned + the shift's overtime threshold; type R on rest days and
    holidays, N for night shifts, otherwise D; more than max_daily_hours in a day is flagged
"""
import datetime

from mm import util as clock
from mm.db import transaction
from mm.util import MMError, now_ts, parse_date

from .config import ABSENCE_TYPES

DEFAULT_SHIFTS = [("D1", "Day shift 08:00-16:30", "08:00", "16:30", 30, 0, 10, 30),
                  ("D2", "Evening shift 16:00-00:30", "16:00", "00:30", 30, 0, 10, 30),
                  ("N1", "Night shift 22:00-06:30", "22:00", "06:30", 30, 1, 10, 30)]
# fixed-date Egyptian public holidays (religious holidays move with the lunar calendar - enter them each year)
FIXED_HOLIDAYS = [("01-07", "Coptic Christmas"), ("01-25", "Revolution Day (25 January) / Police Day"),
                  ("04-25", "Sinai Liberation Day"), ("05-01", "Labour Day"), ("06-30", "30 June Revolution"),
                  ("07-23", "Revolution Day (23 July)"), ("10-06", "Armed Forces Day")]
STATUS = {"PRESENT": "Present", "LATE": "Late", "ABSENT": "Absent (unexcused)", "LEAVE": "On leave", "OFF": "Rest day",
          "HOLIDAY": "Public holiday", "INCOMPLETE": "Clock-out missing"}


def install_defaults(conn, year=None):
    for s in DEFAULT_SHIFTS:
        conn.execute("INSERT OR IGNORE INTO hr_shift (code, text, start, end, break_min, night, grace_min, ot_after_min) "
                     "VALUES (?,?,?,?,?,?,?,?)", s)
    y = year or clock.today().year
    for yy in (y, y + 1):
        for md, text in FIXED_HOLIDAYS:
            conn.execute("INSERT OR IGNORE INTO hr_holiday (day, text) VALUES (?,?)", ("%d-%s" % (yy, md), text))


def _hm(t):
    try:
        h, m = (t or "").strip().split(":")
        h, m = int(h), int(m)
        assert 0 <= h < 24 and 0 <= m < 60
        return h * 60 + m
    except (ValueError, AssertionError):
        raise MMError("Time as HH:MM, e.g. 08:00", "PH", "901")


def save_shift(conn, data):
    code = (data.get("code") or "").strip().upper()
    if not code or not (data.get("text") or "").strip():
        raise MMError("Enter code and text of the shift", "PH", "902")
    _hm(data.get("start")), _hm(data.get("end"))
    from mm.util import parse_int
    with transaction(conn):
        conn.execute("INSERT OR REPLACE INTO hr_shift (code, text, start, end, break_min, night, grace_min, ot_after_min) "
                     "VALUES (?,?,?,?,?,?,?,?)", (code[:6], data["text"].strip()[:60], data["start"], data["end"],
                                                  parse_int(data.get("break_min") or 30, "break", 0, 240),
                                                  1 if data.get("night") in (1, "1", True, "true") else 0,
                                                  parse_int(data.get("grace_min") or 10, "grace minutes", 0, 120),
                                                  parse_int(data.get("ot_after_min") or 30, "overtime threshold", 0, 240)))
    return {"message": "Shift %s saved" % code}


def assign_shift(conn, pernr, shift, user):
    if not conn.execute("SELECT 1 FROM hr_shift WHERE code=?", ((shift or "").upper(),)).fetchone():
        raise MMError("Shift %s does not exist" % shift, "PH", "903")
    with transaction(conn):
        n = conn.execute("UPDATE hr_employee SET shift=? WHERE pernr=?", (shift.upper(), str(pernr))).rowcount
    if not n:
        raise MMError("Employee %s does not exist" % pernr, "PH", "904")
    return {"message": "Employee %s works in shift %s" % (pernr, shift.upper())}


def save_holiday(conn, day, text):
    d = parse_date(day)
    if not (text or "").strip():
        raise MMError("Enter the name of the holiday", "PH", "905")
    with transaction(conn):
        conn.execute("INSERT OR REPLACE INTO hr_holiday (day, text) VALUES (?,?)", (d, text.strip()[:60]))
    return {"message": "Public holiday %s saved" % d}


# ------------------------------------------------------------------ time clock
def punch(conn, pernr, kind=None, user="", at=None, source="TERMINAL"):
    """clock-in / clock-out; without kind the next one is taken (IN after OUT and vice versa)"""
    e = conn.execute("SELECT pernr, name, status FROM hr_employee WHERE pernr=?", (str(pernr),)).fetchone()
    if not e or e["status"] != "A":
        raise MMError("Employee %s does not exist or has left" % pernr, "PH", "904")
    t = (at or clock.now()).replace(second=0, microsecond=0)
    last = conn.execute("SELECT kind, ts FROM hr_punch WHERE pernr=? ORDER BY ts DESC, id DESC LIMIT 1", (e["pernr"],)).fetchone()
    k = (kind or ("OUT" if last and last["kind"] == "IN" and
                  (t - datetime.datetime.fromisoformat(last["ts"])).total_seconds() < 16 * 3600 else "IN")).upper()
    if k not in ("IN", "OUT"):
        raise MMError("Punch kind must be IN or OUT", "PH", "906")
    if last and last["ts"] == t.isoformat(sep=" ") and last["kind"] == k:
        raise MMError("Already clocked %s at %s" % (k.lower(), t.strftime("%H:%M")), "PH", "907")
    with transaction(conn):
        conn.execute("INSERT INTO hr_punch (pernr, ts, kind, source, usnam) VALUES (?,?,?,?,?)",
                     (e["pernr"], t.isoformat(sep=" "), k, source, user))
    return {"kind": k, "message": "%s clocked %s at %s" % (e["name"], "in" if k == "IN" else "out", t.strftime("%H:%M"))}


# ------------------------------------------------------------------ daily evaluation
def _shift_window(day, s):
    d = datetime.date.fromisoformat(day)
    st = datetime.datetime.combine(d, datetime.time(*divmod(_hm(s["start"]), 60)))
    en = datetime.datetime.combine(d, datetime.time(*divmod(_hm(s["end"]), 60)))
    if en <= st:
        en += datetime.timedelta(days=1)                 # crosses midnight
    return st, en


def evaluate(conn, day, pernr=None):
    """time evaluation of one day for all active employees (or one); results in hr_attend"""
    from pp.config import WORKDAYS
    from .engine import cfg_int
    day = parse_date(day)
    d = datetime.date.fromisoformat(day)
    hol = conn.execute("SELECT text FROM hr_holiday WHERE day=?", (day,)).fetchone()
    workday = d.weekday() in WORKDAYS and not hol
    maxh = cfg_int(conn, "max_daily_hours") * 60
    q = "SELECT * FROM hr_employee WHERE COALESCE(time_rec,1)=1 AND hire_date<=? AND (COALESCE(leave_date,'')='' OR leave_date>?)"
    a = [day, day]
    if pernr:
        q += " AND pernr=?"
        a.append(str(pernr))
    out = []
    with transaction(conn):
        for e in conn.execute(q, a).fetchall():
            s = conn.execute("SELECT * FROM hr_shift WHERE code=?", (e["shift"] or "D1",)).fetchone() or \
                conn.execute("SELECT * FROM hr_shift WHERE code='D1'").fetchone()
            st, en = _shift_window(day, s)
            lo, hi = st - datetime.timedelta(hours=4), en + datetime.timedelta(hours=8)
            ps = conn.execute("SELECT kind, ts FROM hr_punch WHERE pernr=? AND ts BETWEEN ? AND ? ORDER BY ts",
                              (e["pernr"], lo.isoformat(sep=" "), hi.isoformat(sep=" "))).fetchall()
            ins = [datetime.datetime.fromisoformat(p["ts"]) for p in ps if p["kind"] == "IN"]
            outs = [datetime.datetime.fromisoformat(p["ts"]) for p in ps if p["kind"] == "OUT"]
            worked = 0
            cur = None
            for p in ps:                                  # pair IN -> OUT
                t = datetime.datetime.fromisoformat(p["ts"])
                if p["kind"] == "IN":
                    cur = cur or t
                elif cur:
                    worked += int((t - cur).total_seconds() // 60)
                    cur = None
            planned = int((en - st).total_seconds() // 60) - s["break_min"] if workday else 0
            if worked > 6 * 60:
                worked -= s["break_min"]                  # statutory break not counted
            ab = conn.execute("SELECT awart FROM hr_absence WHERE pernr=? AND status='A' AND begda<=? AND endda>=?",
                              (e["pernr"], day, day)).fetchone()
            late = early = ot = 0
            if not workday:
                status = "HOLIDAY" if hol else "OFF"
                ot = worked if worked else 0
            elif ab:
                status = "LEAVE"
            elif not ins:
                status = "ABSENT"
            elif cur and not outs:
                status = "INCOMPLETE"
            else:
                late = max(0, int((min(ins) - st).total_seconds() // 60))
                late = late if late > s["grace_min"] else 0
                early = max(0, int((en - max(outs)).total_seconds() // 60)) if outs else 0
                status = "LATE" if late else "PRESENT"
                extra = worked - planned
                ot = extra if extra >= s["ot_after_min"] else 0
            ot_type = None
            if ot:
                ot_type = "R" if not workday else "N" if s["night"] else "D"
            row = dict(pernr=e["pernr"], name=e["name"], day=day, shift=s["code"], first_in=min(ins).strftime("%H:%M") if ins else None,
                       last_out=max(outs).strftime("%H:%M") if outs else None, planned_min=planned, worked_min=worked, late_min=late,
                       early_min=early, ot_min=ot, ot_type=ot_type, status=status, absence=ab["awart"] if ab else None,
                       over_limit=1 if worked > maxh else 0)
            old = conn.execute("SELECT ot_posted FROM hr_attend WHERE pernr=? AND day=?", (e["pernr"], day)).fetchone()
            conn.execute("INSERT OR REPLACE INTO hr_attend (pernr, day, shift, first_in, last_out, planned_min, worked_min, late_min, "
                         "early_min, ot_min, ot_type, status, absence, over_limit, ot_posted, ts) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                         (e["pernr"], day, s["code"], row["first_in"], row["last_out"], planned, worked, late, early, ot, ot_type, status,
                          row["absence"], row["over_limit"], old["ot_posted"] if old else 0, now_ts()))
            out.append(row)
    return {"day": day, "workday": workday, "holiday": hol["text"] if hol else None, "rows": out,
            "counts": {k: sum(1 for r in out if r["status"] == k) for k in STATUS}}


def attendance(conn, day):
    rows = [dict(r) for r in conn.execute("SELECT a.*, e.name, e.orgeh FROM hr_attend a JOIN hr_employee e USING (pernr) "
                                          "WHERE a.day=? ORDER BY a.status, e.pernr", (parse_date(day),))]
    return {"day": day, "rows": rows, "counts": {k: sum(1 for r in rows if r["status"] == k) for k in STATUS}, "status": STATUS}


def approve_overtime(conn, day, user, pernrs=None):
    """evaluated overtime -> overtime entries for payroll (hr_overtime), each day only once"""
    from .engine import add_overtime
    day = parse_date(day)
    rows = conn.execute("SELECT * FROM hr_attend WHERE day=? AND ot_min>0 AND ot_posted=0", (day,)).fetchall()
    n = 0
    for r in rows:
        if pernrs and r["pernr"] not in pernrs:
            continue
        add_overtime(conn, r["pernr"], day, r["ot_type"], "%.2f" % (r["ot_min"] / 60.0), user)
        with transaction(conn):
            conn.execute("UPDATE hr_attend SET ot_posted=1 WHERE pernr=? AND day=?", (r["pernr"], day))
        n += 1
    if not n:
        raise MMError("No evaluated overtime to approve on %s" % day, "PH", "908")
    return {"message": "%d overtime entries of %s approved for payroll" % (n, day)}


def ot_notices(conn, d1=None, d2=None):
    """Law 14/2025: overtime must be notified to the labour office within 7 days"""
    from .engine import cfg_int
    days_ = cfg_int(conn, "ot_notice_days")
    today = clock.today()
    d2 = d2 or today.isoformat()
    d1 = d1 or (today - datetime.timedelta(days=60)).isoformat()
    rows = []
    for r in conn.execute("SELECT datum day, COUNT(DISTINCT pernr) people, SUM(hours) h FROM hr_overtime WHERE datum BETWEEN ? AND ? "
                          "GROUP BY datum ORDER BY datum DESC", (d1, d2)):
        n = conn.execute("SELECT * FROM hr_ot_notice WHERE day=?", (r["day"],)).fetchone()
        due = (datetime.date.fromisoformat(r["day"]) + datetime.timedelta(days=days_)).isoformat()
        state = "notified" if n and n["notified"] else "overdue" if due < today.isoformat() else "due"
        rows.append(dict(day=r["day"], people=r["people"], hours=round((r["h"] or 0) / 1000.0, 2), due=due, state=state,
                         notified=n["notified"] if n else None, ref=n["ref"] if n else None))
    return {"rows": rows, "overdue": sum(1 for r in rows if r["state"] == "overdue"), "due": sum(1 for r in rows if r["state"] == "due"),
            "days": days_}


def notify_overtime(conn, day, ref, user):
    day = parse_date(day)
    if not (ref or "").strip():
        raise MMError("Enter the reference of the notice to the labour office", "PH", "909")
    if not conn.execute("SELECT 1 FROM hr_overtime WHERE datum=?", (day,)).fetchone():
        raise MMError("No overtime on %s" % day, "PH", "910")
    with transaction(conn):
        conn.execute("INSERT OR REPLACE INTO hr_ot_notice (day, notified, ref, usnam) VALUES (?,?,?,?)",
                     (day, clock.today().isoformat(), ref.strip()[:40], user))
    return {"message": "Overtime of %s notified (%s)" % (day, ref.strip())}


def month_report(conn, month):
    """attendance per employee for a month (from the daily evaluations)"""
    rows = []
    for r in conn.execute("SELECT a.pernr, e.name, e.orgeh, SUM(a.status IN ('PRESENT','LATE')) present, SUM(a.status='LATE') late_days, "
                          "SUM(a.late_min) late_min, SUM(a.status='ABSENT') absent, SUM(a.status='LEAVE') leave, "
                          "SUM(a.status='INCOMPLETE') incomplete, SUM(a.planned_min) planned, SUM(a.worked_min) worked, "
                          "SUM(a.ot_min) ot, SUM(a.over_limit) over_limit FROM hr_attend a JOIN hr_employee e USING (pernr) "
                          "WHERE substr(a.day,1,7)=? GROUP BY a.pernr ORDER BY a.pernr", (month,)):
        d = dict(r)
        d["worked_h"], d["planned_h"], d["ot_h"] = round(d["worked"] / 60.0, 1), round(d["planned"] / 60.0, 1), round(d["ot"] / 60.0, 1)
        days_ = d["present"] + d["absent"]
        d["punctuality"] = round(100.0 * (d["present"] - d["late_days"]) / d["present"], 1) if d["present"] else None
        d["attendance"] = round(100.0 * d["present"] / days_, 1) if days_ else None
        rows.append(d)
    return {"month": month, "rows": rows, "absence_types": {k: v["text"] for k, v in ABSENCE_TYPES.items()}}
