"""HR analytics (ZHR_ANALYTICS) with the standard formulas:
  turnover rate       = leavers / average headcount x 100 (voluntary = resignation, involuntary = dismissal / end of contract)
  absenteeism rate    = unplanned absence days (sick, unexcused, unpaid + evaluated absences) / (working days x average headcount) x 100
  overtime ratio      = overtime hours / planned hours x 100
  punctuality         = days on time / days present x 100 (from the time evaluation)
  labour cost / unit  = personnel cost of the production cost centers / good units produced
  training hours per employee, certification coverage, appraisal average
Months with no data show what is there; nothing is invented."""
import datetime

from mm import util as clock

PRODUCTION_KOSTL = ("41",)          # cost centers 41xx = production (machining, assembly)


def _months(year):
    t = clock.today()
    last = t.month if int(year) == t.year else 12
    return ["%04d-%02d" % (int(year), m) for m in range(1, last + 1)]


def _eom(month):
    y, m = int(month[:4]), int(month[5:])
    nxt = datetime.date(y + (m == 12), m % 12 + 1, 1)
    return (nxt - datetime.timedelta(days=1)).isoformat()


def _head(conn, day):
    return conn.execute("SELECT COUNT(*) FROM hr_employee WHERE hire_date<=? AND (COALESCE(leave_date,'')='' OR leave_date>?)",
                        (day, day)).fetchone()[0]


def _workdays(month):
    from pp.config import WORKDAYS
    d = datetime.date.fromisoformat(month + "-01")
    n = 0
    while d.strftime("%Y-%m") == month:
        n += d.weekday() in WORKDAYS
        d += datetime.timedelta(days=1)
    return n


def analytics(conn, year=None):
    y = int(year or clock.today().year)
    rows = []
    for mo in _months(y):
        start, end = mo + "-01", _eom(mo)
        h0, h1 = _head(conn, (datetime.date.fromisoformat(start) - datetime.timedelta(days=1)).isoformat()), _head(conn, end)
        avg = (h0 + h1) / 2.0 or 1
        hires = conn.execute("SELECT COUNT(*) FROM hr_employee WHERE hire_date BETWEEN ? AND ?", (start, end)).fetchone()[0]
        lv = conn.execute("SELECT leave_reason r, COUNT(*) n FROM hr_employee WHERE leave_date BETWEEN ? AND ? GROUP BY leave_reason",
                          (start, end)).fetchall()
        vol = sum(r["n"] for r in lv if r["r"] == "01")
        invol = sum(r["n"] for r in lv if r["r"] in ("02", "03"))
        leavers = sum(r["n"] for r in lv)
        unplanned = conn.execute("SELECT COALESCE(SUM(days),0) FROM hr_absence WHERE status='A' AND awart IN ('SIC','ABS','UNP') "
                                 "AND begda BETWEEN ? AND ?", (start, end)).fetchone()[0]
        unplanned += conn.execute("SELECT COUNT(*) FROM hr_attend WHERE status='ABSENT' AND day BETWEEN ? AND ?", (start, end)).fetchone()[0]
        wd = _workdays(mo)
        ot_h = conn.execute("SELECT COALESCE(SUM(hours),0) FROM hr_overtime WHERE datum BETWEEN ? AND ?", (start, end)).fetchone()[0] / 1000.0
        planned_h = avg * wd * 8
        att = conn.execute("SELECT SUM(status IN ('PRESENT','LATE')) pr, SUM(status='LATE') late FROM hr_attend WHERE day BETWEEN ? AND ?",
                           (start, end)).fetchone()
        cost = conn.execute("SELECT COALESCE(SUM(p.gross + p.si_er),0) FROM hr_payroll p JOIN hr_employee e USING (pernr) "
                            "WHERE p.gjahr=? AND p.perio=? AND substr(e.kostl,1,2) IN (%s)" % ",".join("?" * len(PRODUCTION_KOSTL)),
                            [y, int(mo[5:])] + list(PRODUCTION_KOSTL)).fetchone()[0]
        units = conn.execute("SELECT COALESCE(SUM(lmnga),0) FROM confirmation WHERE budat BETWEEN ? AND ? AND COALESCE(stokz,0)=0",
                             (start, end)).fetchone()[0] / 1000.0
        rows.append(dict(month=mo, headcount=h1, hires=hires, leavers=leavers, voluntary=vol, involuntary=invol,
                         turnover=round(100.0 * leavers / avg, 2), absenteeism=round(100.0 * unplanned / (wd * avg), 2) if wd else 0,
                         unplanned_days=unplanned, overtime_h=round(ot_h, 1), overtime_ratio=round(100.0 * ot_h / planned_h, 2) if planned_h else 0,
                         punctuality=round(100.0 * (att["pr"] - att["late"]) / att["pr"], 1) if att and att["pr"] else None,
                         production_cost=round(cost / 100.0, 2), units=round(units, 1),
                         cost_per_unit=round(cost / 100.0 / units, 2) if units and cost else None))
    n = len(rows) or 1
    avg_head = sum(r["headcount"] for r in rows) / n
    leavers = sum(r["leavers"] for r in rows)
    ytd_turnover = round(100.0 * leavers / avg_head, 1) if avg_head else 0
    today = clock.today().isoformat()
    emp = conn.execute("SELECT * FROM hr_employee WHERE COALESCE(leave_date,'')='' OR leave_date>?", (today,)).fetchall()
    tenure = [(datetime.date.fromisoformat(today) - datetime.date.fromisoformat(e["hire_date"])).days / 365.25 for e in emp]
    ages = [(datetime.date.fromisoformat(today) - datetime.date.fromisoformat(e["birth_date"])).days / 365.25 for e in emp if e["birth_date"]]
    from .skills import matrix
    from .talent import appraisals, trainings
    m = matrix(conn)
    tr = trainings(conn, y)
    ap = appraisals(conn, y)
    by_org = [dict(r) for r in conn.execute(
        "SELECT o.text org, COUNT(*) n, SUM(e.gender='F') women FROM hr_employee e LEFT JOIN hr_orgunit o ON o.orgeh=e.orgeh "
        "WHERE COALESCE(e.leave_date,'')='' OR e.leave_date>? GROUP BY e.orgeh ORDER BY n DESC", (today,))]
    return {"year": y, "months": rows, "headcount": len(emp), "women_pct": round(100.0 * sum(1 for e in emp if e["gender"] == "F") / len(emp), 1) if emp else 0,
            "avg_tenure": round(sum(tenure) / len(tenure), 1) if tenure else 0, "avg_age": round(sum(ages) / len(ages), 1) if ages else 0,
            "turnover_ytd": ytd_turnover, "turnover_annualised": round(ytd_turnover * 12.0 / n, 1),
            "absenteeism_avg": round(sum(r["absenteeism"] for r in rows) / n, 2), "overtime_ratio_avg": round(sum(r["overtime_ratio"] for r in rows) / n, 2),
            "training_hours_per_employee": tr["hours_per_employee"], "certs_expired": m["expired"], "certs_expiring": m["expiring"],
            "single_skill_risk": [s for s, n_ in m["coverage"].items() if n_ < 2], "appraisal_average": ap["average"],
            "appraisals_done": ap["done"], "by_org": by_org}
