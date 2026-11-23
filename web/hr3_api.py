"""JSON API of time and attendance, training, appraisal, end of service and HR analytics."""
from hr import analytics, talent, time as tm
from mm import util as clock
from mm.util import require

from .server import db, route


@route("GET", "/api/hr/time/day")
def time_day(req, q):
    return tm.attendance(db(), q.get("day") or clock.today().isoformat())


@route("GET", "/api/hr/time/month")
def time_month(req, q):
    return tm.month_report(db(), q.get("month") or clock.today().isoformat()[:7])


@route("GET", "/api/hr/time/notices")
def time_notices(req, q):
    return tm.ot_notices(db(), q.get("from") or None, q.get("to") or None)


@route("GET", "/api/hr/time/setup")
def time_setup(req, q):
    c = db()
    return {"shifts": [dict(r) for r in c.execute("SELECT * FROM hr_shift ORDER BY code")],
            "holidays": [dict(r) for r in c.execute("SELECT * FROM hr_holiday ORDER BY day")],
            "employees": [dict(r) for r in c.execute("SELECT pernr, name, job, shift, time_rec FROM hr_employee WHERE status='A' ORDER BY pernr")],
            "punches": [dict(r) for r in c.execute("SELECT p.*, e.name FROM hr_punch p JOIN hr_employee e USING (pernr) ORDER BY p.ts DESC, p.id DESC "
                                                   "LIMIT 15")]}


@route("POST", "/api/hr/time/(?P<act>punch|evaluate|approve|notify|shift|assign|holiday)")
def time_act(req, q, act):
    c, b = db(), req.body
    if act == "punch":
        require(b, "pernr")
        return tm.punch(c, b["pernr"], b.get("kind") or None, req.user)
    if act == "evaluate":
        return tm.evaluate(c, b.get("day") or clock.today().isoformat())
    if act == "approve":
        return tm.approve_overtime(c, b.get("day"), req.user)
    if act == "notify":
        return tm.notify_overtime(c, b.get("day"), b.get("ref"), req.user)
    if act == "shift":
        return tm.save_shift(c, b)
    if act == "assign":
        require(b, "pernr", "shift")
        return tm.assign_shift(c, b["pernr"], b["shift"], req.user)
    return tm.save_holiday(c, b.get("day"), b.get("text"))


@route("GET", "/api/hr/training")
def training_list(req, q):
    return talent.trainings(db(), q.get("year") or None)


@route("POST", "/api/hr/training/(?P<act>plan|complete)")
def training_act(req, q, act):
    b = req.body
    if act == "plan":
        if isinstance(b.get("participants"), str):
            b = dict(b, participants=[p.strip() for p in b["participants"].split(",") if p.strip()])
        return talent.plan_training(db(), b, req.user)
    res = b.get("results") if isinstance(b.get("results"), dict) else {}
    if isinstance(b.get("failed"), str):
        res = {p.strip(): "FAIL" for p in b["failed"].split(",") if p.strip()}
    return talent.complete_training(db(), b.get("id"), res, req.user)


@route("GET", "/api/hr/appraisal")
def appraisal_list(req, q):
    return dict(talent.appraisals(db(), q.get("year") or None), ratings=talent.RATINGS)


@route("POST", "/api/hr/appraisal")
def appraisal_save(req, q):
    return talent.save_appraisal(db(), req.body, req.user)


@route("GET", "/api/hr/eos")
def eos(req, q):
    return talent.end_of_service(db(), q.get("pernr"), q.get("date") or None, q.get("reason") or "01",
                                 (q.get("notice") or "1") == "1")


@route("GET", "/api/hr/analytics")
def hr_analytics(req, q):
    return analytics.analytics(db(), q.get("year") or None)
