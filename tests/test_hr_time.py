"""HR time and attendance, talent and analytics: clock-in / out, the daily evaluation (late after grace,
absent, leave, missing clock-out, overtime by type with threshold, night shift over midnight, rest day,
public holiday, daily limit, exempt employees), overtime approval into payroll and the Law 14/2025 notice,
training that certifies, appraisal rules, end-of-service settlement and the HR analytics formulas."""
import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fixture  # noqa: E402,F401
from mm import seed  # noqa: E402
from mm.db import connect  # noqa: E402
from mm.util import MMError  # noqa: E402

U = "HR1"
TUE, FRI = "2026-11-10", "2026-11-13"


def system():
    c = connect(":memory:")
    seed.seed(c)
    return c


def err(test, fn, no):
    with test.assertRaises(MMError) as x:
        fn()
    test.assertEqual(x.exception.msg_no, no, str(x.exception))


def t(day, hhmm, plus_days=0):
    return datetime.datetime.fromisoformat("%s %s" % (day, hhmm)) + datetime.timedelta(days=plus_days)


class Attendance(unittest.TestCase):
    def test_daily_evaluation_rules(self):
        from hr import engine, time as tm
        c = system()
        P = dict(ontime="10004", late="10005", grace="10006", absent="10008", ot="10010", night="10011", incomplete="10013", leave="10014")
        tm.punch(c, P["ontime"], "IN", U, at=t(TUE, "07:55"))
        tm.punch(c, P["ontime"], "OUT", U, at=t(TUE, "16:40"))                     # 10 min over: below the 30 min threshold
        tm.punch(c, P["late"], "IN", U, at=t(TUE, "08:25"))
        tm.punch(c, P["late"], "OUT", U, at=t(TUE, "16:30"))
        tm.punch(c, P["grace"], "IN", U, at=t(TUE, "08:08"))                       # inside the 10 min grace
        tm.punch(c, P["grace"], "OUT", U, at=t(TUE, "16:00"))                      # 30 min early
        tm.punch(c, P["ot"], "IN", U, at=t(TUE, "08:00"))
        self.assertEqual(tm.punch(c, P["ot"], None, U, at=t(TUE, "20:00"))["kind"], "OUT")   # next clocking = OUT
        err(self, lambda: tm.punch(c, P["ot"], "OUT", U, at=t(TUE, "20:00")), "907")
        c.execute("UPDATE hr_employee SET shift='N1' WHERE pernr=?", (P["night"],))
        tm.punch(c, P["night"], "IN", U, at=t(TUE, "22:00"))
        tm.punch(c, P["night"], "OUT", U, at=t(TUE, "07:30", 1))                     # crosses midnight, 1 h extra
        tm.punch(c, P["incomplete"], "IN", U, at=t(TUE, "08:00"))
        engine.request_absence(c, P["leave"], "ANN", TUE, TUE, U, approve=True)
        c.execute("UPDATE hr_employee SET time_rec=0 WHERE pernr='10003'")
        r = {x["pernr"]: x for x in tm.evaluate(c, TUE)["rows"]}
        self.assertNotIn("10003", r)                                                # exempt from the time clock
        self.assertEqual((r[P["ontime"]]["status"], r[P["ontime"]]["ot_min"]), ("PRESENT", 0))
        self.assertEqual((r[P["late"]]["status"], r[P["late"]]["late_min"]), ("LATE", 25))
        self.assertEqual((r[P["grace"]]["status"], r[P["grace"]]["late_min"], r[P["grace"]]["early_min"]), ("PRESENT", 0, 30))
        self.assertEqual(r[P["absent"]]["status"], "ABSENT")
        self.assertEqual(r[P["leave"]]["status"], "LEAVE")
        self.assertEqual(r[P["incomplete"]]["status"], "INCOMPLETE")
        ot = r[P["ot"]]
        self.assertEqual((ot["worked_min"], ot["ot_min"], ot["ot_type"], ot["over_limit"]), (690, 210, "D", 1))  # 12 h - 30 break; > 10 h
        n = r[P["night"]]
        self.assertEqual((n["worked_min"], n["ot_min"], n["ot_type"]), (540, 60, "N"))
        # rest day (Friday) and public holiday: all worked time is rest-day overtime
        tm.punch(c, P["ontime"], "IN", U, at=t(FRI, "09:00"))
        tm.punch(c, P["ontime"], "OUT", U, at=t(FRI, "13:00"))
        f = {x["pernr"]: x for x in tm.evaluate(c, FRI)["rows"]}
        self.assertEqual((f[P["ontime"]]["status"], f[P["ontime"]]["ot_min"], f[P["ontime"]]["ot_type"]), ("OFF", 240, "R"))
        self.assertEqual(f[P["absent"]]["status"], "OFF")
        tm.save_holiday(c, "2026-11-11", "Company holiday")
        self.assertEqual({x["status"] for x in tm.evaluate(c, "2026-11-11")["rows"]}, {"HOLIDAY"})
        # overtime approval into payroll, once
        tm.approve_overtime(c, TUE, U)
        h = {x["pernr"]: x["hours"] for x in c.execute("SELECT pernr, hours FROM hr_overtime WHERE datum=?", (TUE,))}
        self.assertEqual(h[P["ot"]], 3500)
        self.assertEqual(h[P["night"]], 1000)
        err(self, lambda: tm.approve_overtime(c, TUE, U), "908")
        tm.evaluate(c, TUE)                                                          # re-evaluation keeps the approval
        self.assertEqual(c.execute("SELECT ot_posted FROM hr_attend WHERE pernr=? AND day=?", (P["ot"], TUE)).fetchone()[0], 1)
        # Law 14/2025: notice to the labour office within 7 days
        rows = {x["day"]: x for x in tm.ot_notices(c, TUE, TUE)["rows"]}
        self.assertEqual((rows[TUE]["due"], rows[TUE]["state"]), ("2026-11-17", "due"))
        err(self, lambda: tm.notify_overtime(c, TUE, " ", U), "909")
        err(self, lambda: tm.notify_overtime(c, "2026-11-12", "X", U), "910")
        tm.notify_overtime(c, TUE, "LO-1", U)
        self.assertEqual(tm.ot_notices(c, TUE, TUE)["rows"][0]["state"], "notified")
        m = {x["pernr"]: x for x in tm.month_report(c, "2026-11")["rows"]}
        self.assertGreaterEqual(m[P["late"]]["late_days"], 1)
        err(self, lambda: tm.save_shift(c, {"code": "X", "text": "x", "start": "25:00", "end": "08:00"}), "901")
        err(self, lambda: tm.assign_shift(c, "10004", "NOPE", U), "903")


class Talent(unittest.TestCase):
    def test_training_appraisal_end_of_service_analytics(self):
        from hr import analytics, engine, skills, talent
        c = system()
        err(self, lambda: talent.plan_training(c, {"title": "", "datum": TUE}, U), "920")
        err(self, lambda: talent.plan_training(c, {"title": "X", "skill": "NOPE", "datum": TUE}, U), "921")
        tid = talent.plan_training(c, {"title": "Assembly basics", "skill": "ASSY", "datum": TUE, "hours": "8",
                                       "participants": ["10012", "10015"]}, U)["id"]
        talent.complete_training(c, tid, {"10015": "FAIL"}, U)
        self.assertIsNone(skills.certified(c, "10012", "ASSY", TUE))                 # passed -> certified
        self.assertIsNotNone(skills.certified(c, "10015", "ASSY", TUE))              # failed -> not
        err(self, lambda: talent.complete_training(c, tid, {}, U), "924")
        # appraisal: weighted rating, rules
        r = talent.save_appraisal(c, {"pernr": "10012", "year": 2025, "goals": 4, "competencies": 3, "attendance": 5}, "BOSS")
        self.assertEqual(r["rating"], 4)                                             # 2.0 + 0.9 + 1.0 = 3.9
        err(self, lambda: talent.save_appraisal(c, {"pernr": "10015", "year": 2025, "goals": 1, "competencies": 2,
                                                    "attendance": 2}, "BOSS"), "933")
        c.execute("UPDATE hr_employee SET bname='SELF1' WHERE pernr='10005'")
        err(self, lambda: talent.save_appraisal(c, {"pernr": "10005", "year": 2025, "goals": 3, "competencies": 3}, "SELF1"), "931")
        talent.save_appraisal(c, {"pernr": "10004", "year": 2026, "goals": 4, "competencies": 4, "final": True}, "BOSS")
        err(self, lambda: talent.save_appraisal(c, {"pernr": "10004", "year": 2026, "goals": 5, "competencies": 5}, "BOSS"), "932")
        # end of service (Labour Law 14/2025)
        e = talent.end_of_service(c, "10005", "2026-12-31", "03", notice_given=False)
        codes = {l["code"]: l for l in e["lines"]}
        self.assertEqual(set(codes), {"LEAVE", "NOTICE", "DISMISS"})
        monthly = e["monthly_pay"]
        self.assertAlmostEqual(codes["NOTICE"]["amount"], monthly * 3, places=2)
        self.assertAlmostEqual(codes["DISMISS"]["amount"], round(monthly * 2 * e["years_exact"], 0), delta=monthly * 0.02)
        self.assertAlmostEqual(e["total"], codes["LEAVE"]["amount"] + codes["NOTICE"]["amount"], places=2)   # dismissal is contingent
        c.execute("UPDATE hr_employee SET persg='2', hire_date='2019-01-01' WHERE pernr='10006'")
        g = {l["code"] for l in talent.end_of_service(c, "10006", "2026-12-31", "02")["lines"]}
        self.assertIn("GRANT", g)                                                    # fixed-term renewed beyond 5 years
        err(self, lambda: talent.end_of_service(c, "10006", "2010-01-01", "01"), "941")
        err(self, lambda: talent.end_of_service(c, "10006", "2026-12-31", "99"), "942")
        # analytics: turnover = leavers / average headcount
        engine.terminate(c, "10016", "2026-11-05", "01", U)
        a = analytics.analytics(c, 2026)
        nov = next(m for m in a["months"] if m["month"] == "2026-11")
        self.assertEqual((nov["leavers"], nov["voluntary"]), (1, 1))
        self.assertAlmostEqual(nov["turnover"], round(100 * 1 / ((nov["headcount"] + 1 + nov["headcount"]) / 2.0), 2), places=2)
        self.assertGreaterEqual(nov["absenteeism"], 0)
        self.assertIn("FORK", a["single_skill_risk"])


if __name__ == "__main__":
    unittest.main()
