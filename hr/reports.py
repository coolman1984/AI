"""HR reports: headcount (by unit, cost center, group), HR cockpit, payroll trend."""
from mm.db import rows
from mm import util as mmclock

from .engine import _years


def headcount(conn):
    t = mmclock.today().isoformat()
    emps = rows(conn.execute("SELECT e.*, o.text AS org_text FROM hr_employee e LEFT JOIN hr_orgunit o USING (orgeh) "
                             "WHERE e.status='A'"))
    by_org, by_cc, by_grp = {}, {}, {}
    for e in emps:
        for d, k in ((by_org, "%s %s" % (e["orgeh"], e["org_text"] or "")), (by_cc, e["kostl"]), (by_grp, e["persk"])):
            d[k] = d.get(k, 0) + 1
    ages = [_years(e["birth_date"], t) for e in emps if e["birth_date"]]
    service = [_years(e["hire_date"], t) for e in emps]
    return dict(total=len(emps), by_org=sorted(by_org.items()), by_cc=sorted(by_cc.items()),
                by_group=sorted(by_grp.items()),
                female=sum(1 for e in emps if e["gender"] == "F"), male=sum(1 for e in emps if e["gender"] == "M"),
                avg_age=round(sum(ages) / len(ages), 1) if ages else None,
                avg_service=round(sum(service) / len(service), 1) if service else None,
                monthly_cost=sum(e["basic"] + e["allow_transport"] + e["allow_housing"] + e["allow_other"] for e in emps))


def cockpit(conn):
    t = mmclock.today()
    today = t.isoformat()
    h = headcount(conn)
    on_leave = rows(conn.execute("SELECT a.*, e.name FROM hr_absence a JOIN hr_employee e USING (pernr) WHERE "
                                 "a.status='A' AND a.begda<=? AND a.endda>=?", (today, today)))
    open_req = conn.execute("SELECT COUNT(*) FROM hr_absence WHERE status='R'").fetchone()[0]
    hires = conn.execute("SELECT COUNT(*) FROM hr_employee WHERE substr(hire_date,1,4)=?", (str(t.year),)).fetchone()[0]
    leavers = conn.execute("SELECT COUNT(*) FROM hr_employee WHERE substr(leave_date,1,4)=?", (str(t.year),)).fetchone()[0]
    trend = rows(conn.execute("SELECT gjahr, perio, COUNT(*) AS employees, SUM(gross) AS gross, SUM(si_er) AS si_er, "
                              "SUM(net) AS net, SUM(tax) AS tax, SUM(overtime) AS overtime FROM hr_payroll GROUP BY "
                              "gjahr, perio ORDER BY gjahr, perio"))
    last = trend[-1] if trend else None
    return dict(headcount=h, on_leave=on_leave, open_requests=open_req, hires_ytd=hires, leavers_ytd=leavers,
                turnover_pct=round(leavers * 100.0 / max(h["total"], 1), 1), trend=trend, last=last,
                runs=rows(conn.execute("SELECT * FROM hr_payroll_run ORDER BY gjahr DESC, perio DESC LIMIT 12")))
