"""Talent: training (plan, participants, results - passing a skill training certifies the employee in the
skills matrix), yearly performance appraisal (goals, competencies, attendance -> overall rating 1-5) with
the rating distribution, and the end-of-service settlement under Labour Law 14/2025."""
import datetime

from mm import util as clock
from mm.db import transaction
from mm.util import MMError, now_ts, parse_amount, parse_date, parse_int, parse_qty

RATINGS = {5: "Outstanding", 4: "Exceeds expectations", 3: "Meets expectations", 2: "Needs improvement", 1: "Unsatisfactory"}
# typical guidance for a healthy distribution (not a forced ranking)
GUIDE = {5: 10, 4: 20, 3: 50, 2: 15, 1: 5}


# ------------------------------------------------------------------ training
def plan_training(conn, data, user):
    title = (data.get("title") or "").strip()
    if not title:
        raise MMError("Enter the title of the training", "PH", "920")
    skill = (data.get("skill") or "").strip().upper() or None
    if skill and not conn.execute("SELECT 1 FROM hr_skill WHERE code=?", (skill,)).fetchone():
        raise MMError("Skill %s does not exist" % skill, "PH", "921")
    with transaction(conn):
        tid = conn.execute("INSERT INTO hr_training (title, skill, datum, hours, trainer, cost, status, usnam, ts) VALUES "
                           "(?,?,?,?,?,?,'PLANNED',?,?)", (title[:80], skill, parse_date(data.get("datum")),
                                                           parse_qty(data.get("hours") or "0", allow_zero=True), (data.get("trainer") or "")[:40],
                                                           parse_amount(data.get("cost") or "0", allow_zero=True), user, now_ts())).lastrowid
        for p in data.get("participants") or []:
            if not conn.execute("SELECT 1 FROM hr_employee WHERE pernr=?", (str(p),)).fetchone():
                raise MMError("Employee %s does not exist" % p, "PH", "922")
            conn.execute("INSERT OR IGNORE INTO hr_training_part (tid, pernr) VALUES (?,?)", (tid, str(p)))
    return {"id": tid, "message": "Training %d planned: %s" % (tid, title)}


def complete_training(conn, tid, results, user):
    """results {pernr: PASS/FAIL}; passing a skill training certifies the employee (level 1)"""
    from .skills import qualify
    t = conn.execute("SELECT * FROM hr_training WHERE id=?", (parse_int(tid, "training"),)).fetchone()
    if not t:
        raise MMError("Training %s does not exist" % tid, "PH", "923")
    if t["status"] == "DONE":
        raise MMError("Training %s is already completed" % t["id"], "PH", "924")
    parts = {r["pernr"] for r in conn.execute("SELECT pernr FROM hr_training_part WHERE tid=?", (t["id"],))}
    if not parts:
        raise MMError("Training %s has no participants" % t["id"], "PH", "925")
    passed = 0
    with transaction(conn):
        for p in parts:
            res = (results or {}).get(p, "PASS").upper()
            if res not in ("PASS", "FAIL"):
                raise MMError("Result must be PASS or FAIL", "PH", "926")
            conn.execute("UPDATE hr_training_part SET result=? WHERE tid=? AND pernr=?", (res, t["id"], p))
            passed += res == "PASS"
        conn.execute("UPDATE hr_training SET status='DONE' WHERE id=?", (t["id"],))
    if t["skill"]:
        for p in parts:
            if (results or {}).get(p, "PASS").upper() == "PASS":
                have = conn.execute("SELECT level FROM hr_qual WHERE pernr=? AND skill=?", (p, t["skill"])).fetchone()
                qualify(conn, p, t["skill"], have["level"] if have else 1, t["datum"], user, trainer=t["trainer"] or "",
                        note="Training %d" % t["id"])
    return {"message": "Training %d completed: %d of %d passed%s" % (t["id"], passed, len(parts),
                                                                       " and certified for %s" % t["skill"] if t["skill"] else "")}


def trainings(conn, year=None):
    y = str(year or clock.today().year)
    rows = []
    for t in conn.execute("SELECT * FROM hr_training WHERE substr(datum,1,4)=? ORDER BY datum DESC", (y,)):
        ps = conn.execute("SELECT p.pernr, e.name, p.result FROM hr_training_part p JOIN hr_employee e USING (pernr) WHERE p.tid=?",
                          (t["id"],)).fetchall()
        rows.append(dict(t, participants=len(ps), passed=sum(1 for p in ps if p["result"] == "PASS"),
                         names=", ".join(p["name"] for p in ps), hours_total=round(t["hours"] * len(ps) / 1000.0, 1),
                         cost_egp=round(t["cost"] / 100.0, 2)))
    heads = conn.execute("SELECT COUNT(*) FROM hr_employee WHERE COALESCE(leave_date,'')=''").fetchone()[0] or 1
    hours = sum(r["hours_total"] for r in rows if r["status"] == "DONE")
    return {"year": y, "rows": rows, "hours": round(hours, 1), "hours_per_employee": round(hours / heads, 1),
            "cost": round(sum(r["cost_egp"] for r in rows if r["status"] == "DONE"), 2)}


# ------------------------------------------------------------------ appraisal
def save_appraisal(conn, data, user):
    """goals / competencies / attendance scores 1-5 -> rating = weighted 50 / 30 / 20 %, rounded"""
    p = str(data.get("pernr") or "")
    e = conn.execute("SELECT pernr, bname FROM hr_employee WHERE pernr=?", (p,)).fetchone()
    if not e:
        raise MMError("Employee %s does not exist" % p, "PH", "930")
    if e["bname"] and e["bname"] == user:
        raise MMError("You cannot appraise yourself", "PH", "931")
    y = parse_int(data.get("year") or clock.today().year, "year", 2000, 2100)
    g = parse_int(data.get("goals"), "goals score", 1, 5)
    c = parse_int(data.get("competencies"), "competencies score", 1, 5)
    a = parse_int(data.get("attendance") or attendance_score(conn, p, y), "attendance score", 1, 5)
    rating = int(round(g * 0.5 + c * 0.3 + a * 0.2 + 1e-9))
    old = conn.execute("SELECT status FROM hr_appraisal WHERE pernr=? AND year=?", (p, y)).fetchone()
    if old and old["status"] == "FINAL":
        raise MMError("The appraisal %d of %s is final" % (y, p), "PH", "932")
    status = "FINAL" if data.get("final") else "DRAFT"
    if rating <= 2 and not (data.get("comment") or "").strip():
        raise MMError("A rating of %d needs a comment with the improvement plan" % rating, "PH", "933")
    with transaction(conn):
        conn.execute("INSERT OR REPLACE INTO hr_appraisal (pernr, year, goals, competencies, attendance, rating, comment, appraiser, "
                     "status, ts) VALUES (?,?,?,?,?,?,?,?,?,?)", (p, y, g, c, a, rating, (data.get("comment") or "")[:400], user,
                                                                  status, now_ts()))
    return {"rating": rating, "message": "Appraisal %d of %s: %d - %s (%s)" % (y, p, rating, RATINGS[rating], status.lower())}


def attendance_score(conn, pernr, year):
    """1-5 from the evaluated attendance of the year (unexcused absence and lateness)"""
    r = conn.execute("SELECT SUM(status='ABSENT') ab, SUM(status='LATE') late, SUM(status IN ('PRESENT','LATE')) pr FROM hr_attend "
                     "WHERE pernr=? AND substr(day,1,4)=?", (str(pernr), str(year))).fetchone()
    if not r or not r["pr"]:
        return 3
    if r["ab"] == 0 and r["late"] <= r["pr"] * 0.02:
        return 5
    if r["ab"] <= 1 and r["late"] <= r["pr"] * 0.05:
        return 4
    if r["ab"] <= 3:
        return 3
    return 2 if r["ab"] <= 6 else 1


def appraisals(conn, year=None):
    y = parse_int(year or clock.today().year, "year", 2000, 2100)
    rows = [dict(r, rating_text=RATINGS.get(r["rating"], "")) for r in conn.execute(
        "SELECT a.*, e.name, e.job, e.orgeh FROM hr_appraisal a JOIN hr_employee e USING (pernr) WHERE a.year=? ORDER BY a.rating DESC, e.name",
        (y,))]
    heads = conn.execute("SELECT COUNT(*) FROM hr_employee WHERE COALESCE(leave_date,'')='' OR leave_date>?",
                         ("%d-12-31" % y,)).fetchone()[0]
    n = len(rows) or 1
    dist = [dict(rating=k, text=v, count=sum(1 for r in rows if r["rating"] == k), pct=round(100.0 * sum(1 for r in rows if r["rating"] == k) / n, 1),
                 guide=GUIDE[k]) for k, v in RATINGS.items()]
    return {"year": y, "rows": rows, "distribution": dist, "done": len(rows), "employees": heads,
            "final": sum(1 for r in rows if r["status"] == "FINAL"),
            "average": round(sum(r["rating"] for r in rows) / len(rows), 2) if rows else None}


# ------------------------------------------------------------------ end of service (Labour Law 14/2025)
def end_of_service(conn, pernr, leave_date=None, reason="01", notice_given=True):
    """settlement estimate: unused leave, notice in lieu (3 months, indefinite contracts), end-of-service grant for
    fixed-term contracts renewed beyond 5 years (1 month per year), minimum compensation for unlawful dismissal
    (2 months per year, indefinite) - VERIFY with the labour lawyer before paying"""
    from .config import LEAVE_REASONS
    from .engine import _years, cfg_int, quota
    e = conn.execute("SELECT * FROM hr_employee WHERE pernr=?", (str(pernr),)).fetchone()
    if not e:
        raise MMError("Employee %s does not exist" % pernr, "PH", "940")
    d = parse_date(leave_date) if leave_date else clock.today().isoformat()
    if d < e["hire_date"]:
        raise MMError("The leaving date is before the hiring date", "PH", "941")
    if reason not in LEAVE_REASONS:
        raise MMError("Leaving reason must be one of %s" % ", ".join(LEAVE_REASONS), "PH", "942")
    monthly = (e["basic"] or 0) + (e["allow_transport"] or 0) + (e["allow_housing"] or 0) + (e["allow_other"] or 0)   # cents
    daily = monthly / 30.0
    hire = datetime.date.fromisoformat(e["hire_date"])
    yrs_exact = (datetime.date.fromisoformat(d) - hire).days / 365.25
    years = _years(e["hire_date"], d)
    q = quota(conn, e["pernr"], d[:4])
    months_in_year = int(d[5:7])
    accrued = q["entitlement"] * months_in_year / 12.0
    unused = max(0.0, round(accrued - q["taken"], 1))
    fixed = e["persg"] == "2"
    lines = [dict(code="LEAVE", text="Unused annual leave paid out: %.1f days (accrued %.1f this year, taken %d)" % (unused, accrued, q["taken"]),
                  amount=round(unused * daily))]
    if not fixed and not notice_given and reason in ("01", "03"):
        nm = cfg_int(conn, "notice_months")
        lines.append(dict(code="NOTICE", text="Notice period not respected: %d months' pay in lieu" % nm, amount=monthly * nm))
    if fixed and yrs_exact > 5:
        lines.append(dict(code="GRANT", text="End-of-service grant: fixed-term contract renewed beyond 5 years - 1 month per year (%.1f years)" % yrs_exact,
                          amount=round(monthly * yrs_exact)))
    if not fixed and reason == "03":
        lines.append(dict(code="DISMISS", text="Minimum compensation if the dismissal is found unlawful: 2 months per year (%.1f years)" % yrs_exact,
                          amount=round(monthly * 2 * yrs_exact), contingent=True))
    total = sum(l["amount"] for l in lines if not l.get("contingent"))
    return {"pernr": e["pernr"], "name": e["name"], "hire_date": e["hire_date"], "leave_date": d, "reason": LEAVE_REASONS[reason],
            "contract": "Fixed-term" if fixed else "Indefinite", "years": years, "years_exact": round(yrs_exact, 2),
            "monthly_pay": round(monthly / 100.0, 2), "lines": [dict(l, amount=round(l["amount"] / 100.0, 2)) for l in lines],
            "total": round(total / 100.0, 2), "contingent": round(sum(l["amount"] for l in lines if l.get("contingent")) / 100.0, 2),
            "note": "Estimate under Labour Law 14/2025 (secondary sources) - confirm with the labour lawyer; final salary of the month "
                    "and loans are settled in the payroll run."}
