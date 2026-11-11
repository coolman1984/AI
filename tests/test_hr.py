"""HR: personnel administration, organization, leave and overtime, Egyptian payroll with
posting to FI / CO, payment, confidentiality of personnel data."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fixture  # noqa: E402,F401
from mm import seed  # noqa: E402
from mm.db import connect  # noqa: E402
from mm.util import MMError  # noqa: E402

T, TODAY, U = fixture.T, fixture.TODAY, "HRQA"


def system():
    c = connect(":memory:")
    seed.seed(c)
    return c


def err(test, fn, no):
    with test.assertRaises(MMError) as x:
        fn()
    test.assertEqual(x.exception.msg_no, no, str(x.exception))


NEW = dict(name="Test Employee", birth_date="1995-04-12", national_id="29504120112345", orgeh="10004000",
           basic="10000", allow_transport="1000", hire_date="2026-11-01", persk="W", iban="EG380019000100000000004100001")


class Personnel(unittest.TestCase):
    def test_hire_checks_change_documents_and_leaving(self):
        from hr import engine
        c = system()
        err(self, lambda: engine.hire(c, dict(NEW, national_id="12345"), U), "010")
        err(self, lambda: engine.hire(c, dict(NEW, national_id="29604120112345"), U), "012")      # birth date mismatch
        err(self, lambda: engine.hire(c, dict(NEW, iban="DE123"), U), "014")
        err(self, lambda: engine.hire(c, dict(NEW, kostl="9999"), U), "008")
        err(self, lambda: engine.hire(c, dict(NEW, plans="50000001"), U), "007")                  # occupied position
        p = engine.hire(c, dict(NEW), U)
        self.assertEqual(engine.employee(c, p)["kostl"], "4400")                                # from the unit
        err(self, lambda: engine.hire(c, dict(NEW), U), "013")                                   # same national ID
        self.assertEqual(engine.change(c, p, {"basic": "11000"}, U, "03"), ["basic"])
        e = engine.employee(c, p)
        self.assertEqual((e["changes"][0]["field"], e["changes"][0]["old"], e["changes"][0]["new"]), ("basic", "1000000", "1100000"))
        engine.terminate(c, p, "2026-11-30", "01", U)
        err(self, lambda: engine.change(c, p, {"basic": "1"}, U), "020")
        self.assertEqual(engine.employee(c, p)["status"], "W")

    def test_organization_positions_and_headcount(self):
        from hr import engine, reports
        c = system()
        units = engine.org_structure(c)
        self.assertEqual(sum(u["headcount"] for u in units), reports.headcount(c)["total"])
        engine.save_orgunit(c, "10007000", "IT", "10000000", "9100")
        engine.save_position(c, "59000001", "IT Administrator", "10007000", "9100")
        err(self, lambda: engine.save_orgunit(c, "10008000", "X", "99999999"), "031")
        p = engine.hire(c, dict(NEW, orgeh="10007000", plans="59000001", national_id="29504120112346"), U)
        self.assertEqual(engine.employee(c, p)["orgeh"], "10007000")


class Time(unittest.TestCase):
    def test_leave_quota_casual_limit_overlap_and_approval(self):
        from hr import engine
        c = system()
        p = c.execute("SELECT pernr FROM hr_employee WHERE name='Omar Khaled'").fetchone()[0]
        q0 = engine.quota(c, p, 2026)
        self.assertEqual(q0["entitlement"], 21)
        senior = c.execute("SELECT pernr FROM hr_employee WHERE name='Ahmed Hassan'").fetchone()[0]
        self.assertEqual(engine.quota(c, senior, 2026)["entitlement"], 30)                     # 10+ years / age 50
        a = engine.request_absence(c, p, "ANN", "2026-11-15", "2026-11-17", U)
        self.assertEqual(engine.quota(c, p, 2026)["requested"], q0["requested"] + 3)
        err(self, lambda: engine.request_absence(c, p, "SIC", "2026-11-16", "2026-11-16", U), "044")
        err(self, lambda: engine.request_absence(c, p, "ANN", "2026-01-04", "2026-10-31", U), "046")
        engine.request_absence(c, p, "CAS", "2026-11-23", "2026-11-26", U, approve=True)
        err(self, lambda: engine.request_absence(c, p, "CAS", "2026-11-29", "2026-12-01", U), "047")
        c.execute("UPDATE hr_employee SET bname='OMARX' WHERE pernr=?", (p,))
        err(self, lambda: engine.decide_absence(c, a, True, "OMARX"), "049")                    # own request
        engine.decide_absence(c, a, True, "HR1")
        self.assertEqual(engine.quota(c, p, 2026)["taken"], q0["taken"] + 3 + 4)
        err(self, lambda: engine.request_absence(c, p, "ANN", "2026-11-20", "2026-11-20", U), "045")  # Friday


class Payroll(unittest.TestCase):
    def test_egyptian_payroll_calculation(self):
        from hr import engine, payroll
        c = system()
        p = engine.hire(c, dict(NEW, basic="20000", allow_transport="2000", hire_date="2026-01-01",
                                national_id="29504120112347"), U)
        engine.add_overtime(c, p, "2026-11-03", "N", "4", U)
        engine.request_absence(c, p, "UNP", "2026-11-04", "2026-11-04", U, approve=True)
        r = [x for x in payroll.run(c, 2026, 11, U, simulate=True)["results"] if x["pernr"] == p][0]
        # overtime: 20000 / 30 / 8 = 83.33 per hour x 4 h x 170 % = 566.67; unpaid: 22000 / 30 = 733.33
        self.assertEqual(r["overtime"], 56667)
        self.assertEqual(r["unpaid"], 73333)
        self.assertEqual(r["gross"], 2200000 + 56667 - 73333)
        self.assertEqual(r["si_ee"], 159500)                          # 11 % of the maximum insurable wage 14,500
        taxable_year = (r["gross"] - r["si_ee"]) * 12 - 2000000
        self.assertEqual(r["tax"], round(payroll.annual_tax(c, taxable_year) / 12))
        self.assertEqual(r["martyrs"], round(r["gross"] * 5 / 10000))
        self.assertEqual(r["net"], r["gross"] - r["si_ee"] - r["tax"] - r["martyrs"])
        top = [x for x in payroll.run(c, 2026, 11, U, simulate=True)["results"] if x["basic"] > 8000000][0]
        self.assertEqual(top["ins_wage"], 1450000)                    # maximum insurable wage
        self.assertEqual(payroll.annual_tax(c, 4000000), 0)
        self.assertEqual(payroll.annual_tax(c, 5500000), 150000)      # 10 % of 15,000

    def test_run_post_pay_reverse_and_books(self):
        from hr import engine, payroll
        from qa.invariants import check
        c = system()
        y, m = 2026, 10
        self.assertEqual(payroll.status(c, y, m)["status"], "REL")
        tot = sum(r["gross"] + r["si_er"] for r in payroll.results(c, y, m))
        co_sql = ("SELECT COALESCE(SUM(wtg),0) FROM co_item WHERE wrttp='04' AND objnr LIKE 'KS%' AND kstar IN "
                  "('420000','430000','440000') AND gjahr=? AND perio=?")
        co_before = c.execute(co_sql, (y, m)).fetchone()[0]
        b = payroll.post(c, y, m, U)["belnr"]
        exp = c.execute("SELECT COALESCE(SUM(dmbtr),0) FROM acc_doc_item WHERE belnr=? AND shkzg='S'", (b,)).fetchone()[0]
        self.assertEqual(exp, tot)
        self.assertEqual(c.execute(co_sql, (y, m)).fetchone()[0] - co_before, tot)   # actual costs on the cost centers
        err(self, lambda: payroll.run(c, y, m, U), "002")
        err(self, lambda: engine.add_overtime(c, "10005", "2026-10-15", "D", "1", U), "051")
        payroll.reverse_posting(c, y, m, U)
        payroll.post(c, y, m, U)
        r = payroll.pay(c, y, m, U)
        self.assertEqual(sum(t["local"] for t in r["transfers"]), sum(x["net"] for x in payroll.results(c, y, m)))
        self.assertEqual({t["waers"] for t in r["transfers"]}, {"EGP", "USD"})       # the expat is paid in USD
        bal = c.execute("SELECT COALESCE(SUM(CASE WHEN shkzg='S' THEN dmbtr ELSE -dmbtr END),0) FROM acc_doc_item "
                        "WHERE hkont='176000'").fetchone()[0]
        self.assertEqual(bal, 0)                                      # payroll payable cleared by the payments
        err(self, lambda: payroll.run(c, 2027, 1, U), "003")
        self.assertEqual(check(c), [])

    def test_usd_salary_insurance_and_tax_in_egp_paid_in_usd(self):
        """An employee paid in US dollars: social insurance and tax on the EGP equivalent at the
        month-end rate, the expense is booked in EGP, the net pay is transferred in USD."""
        from fi import gl
        from hr import engine, payroll
        from mm import forms
        c = system()
        err(self, lambda: engine.hire(c, dict(NEW, waers="XYZ", national_id="29504120112348"), U), "015")
        gl.set_rate(c, "USD", "2026-11-01", "50.00")
        p = engine.hire(c, dict(NEW, basic="1000", allow_transport="100", waers="usd", hire_date="2026-01-01",
                                national_id="29504120112348"), U)
        self.assertEqual(engine.employee(c, p)["waers"], "USD")
        r = [x for x in payroll.run(c, 2026, 11, U, simulate=True)["results"] if x["pernr"] == p][0]
        self.assertEqual((r["waers"], r["kurs"]), ("USD", 5000000))
        self.assertEqual(r["gross"], 110000 * 50)                       # 1,100 USD = 55,000 EGP
        self.assertEqual(r["ins_wage"], 1450000)                        # EGP maximum insurable wage
        self.assertEqual(r["si_ee"], 159500)
        self.assertEqual(r["tax"], round(payroll.annual_tax(c, (r["gross"] - r["si_ee"]) * 12 - 2000000) / 12))
        self.assertEqual(r["gross_fc"], 110000)
        self.assertEqual(r["net_fc"], round(r["net"] / 50))
        payroll.run(c, 2026, 11, U)
        payroll.post(c, 2026, 11, U)
        t = [x for x in payroll.pay(c, 2026, 11, U)["transfers"] if x["pernr"] == p][0]
        self.assertEqual((t["waers"], t["amount"]), ("USD", r["net_fc"]))
        html = forms.render(c, "PAYSLIP", "2026-11-%s" % p)
        self.assertIn("USD", html)

    def test_payslip_form(self):
        from mm import forms
        c = system()
        html = forms.render(c, "PAYSLIP", "2026-09-10005")
        self.assertIn("Net pay", html)
        err(self, lambda: forms.render(c, "PAYSLIP", "2026/09-10005"), "010")


class Confidentiality(unittest.TestCase):
    def test_hr_area_needs_explicit_authorization(self):
        from sec import auth
        c = system()
        sales, hr, audit = (auth.profile(c, u) for u in ("SALES1", "HR1", "AUDIT1"))
        self.assertFalse(auth.area_allowed(sales, "HR", "03"))        # display-everywhere does not include HR
        self.assertFalse(auth.area_allowed(audit, "HR", "03"))
        self.assertTrue(auth.area_allowed(hr, "HR", "02"))
        self.assertTrue(auth.object_allowed(hr, "P_ABSENCE"))
        self.assertFalse(auth.object_allowed(hr, "P_PYEVRUN"))
        self.assertEqual(auth.area_of_path("/api/forms/payslip/2026-09-10005"), "HR")
        self.assertEqual(auth.area_of_path("/api/hr/employees"), "HR")


if __name__ == "__main__":
    unittest.main()
