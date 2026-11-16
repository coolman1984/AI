"""HR in depth: employee loans / salary advances deducted by the payroll (ZHR_LOAN), one-time
payments and penalties (ZHR_ADDPAY), follow-up events (ZHR_EVENTS), leave balances
(ZHR_LEAVEBAL), payroll cost per cost center (ZHR_COST) and the HR month-end (ZHR_CLOSE)."""
import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fixture  # noqa: E402,F401
from mm import seed  # noqa: E402
from mm.db import connect  # noqa: E402
from mm.util import MMError  # noqa: E402

T = fixture.T
TODAY = T.isoformat()
U = "HR1"


def system():
    c = connect(":memory:")
    seed.seed(c)
    return c


def err(test, fn, no):
    with test.assertRaises(MMError) as x:
        fn()
    test.assertEqual(x.exception.msg_no, no, str(x.exception))


def bal(c, hkont):
    from fi.reports import gl_balance
    return gl_balance(c, hkont, "9999-12-31")


def open_month(c):
    r = c.execute("SELECT gjahr, perio FROM hr_payroll_run WHERE status='REL'").fetchone()
    return r["gjahr"], r["perio"]


def row(res, pernr):
    return [r for r in res["results"] if r["pernr"] == pernr][0]


class LoansAndPayments(unittest.TestCase):
    def test_payroll_deducts_installments_and_books_everything(self):
        from hr import extras, payroll
        c = system()
        y, p = open_month(c)
        base = row(payroll.run(c, y, p, U, simulate=True), "10004")
        l0, b0 = bal(c, "117000"), bal(c, "113100")
        extras.create_loan(c, {"pernr": "10004", "typ": "ADV", "amount": "3000", "installment": "1000",
                               "gjahr": y, "perio": p, "budat": TODAY}, U)
        self.assertEqual((bal(c, "117000") - l0, b0 - bal(c, "113100")), (300000, 300000))   # paid out
        err(self, lambda: extras.create_loan(c, {"pernr": "10004", "amount": "100", "installment": "200",
                                                 "gjahr": y, "perio": p}, U), "984")
        err(self, lambda: extras.create_loan(c, {"pernr": "10004", "amount": "500000", "installment": "100000",
                                                 "gjahr": y, "perio": p}, U), "985")          # above the net pay
        extras.add_payment(c, {"pernr": "10004", "wtype": "BONUS", "amount": "500", "gjahr": y, "perio": p}, U)
        extras.add_payment(c, {"pernr": "10004", "wtype": "PENALTY", "days": "1", "gjahr": y, "perio": p}, U)
        err(self, lambda: extras.add_payment(c, {"pernr": "10004", "wtype": "PENALTY", "days": "20",
                                                 "gjahr": y, "perio": p}, U), "987")
        err(self, lambda: extras.add_payment(c, {"pernr": "10004", "wtype": "GIFT", "amount": "1",
                                                 "gjahr": y, "perio": p}, U), "986")
        r = row(payroll.run(c, y, p, U), "10004")
        contract = c.execute("SELECT basic+allow_transport+allow_housing+allow_other FROM hr_employee WHERE "
                             "pernr='10004'").fetchone()[0]
        self.assertEqual(r["gross"], base["gross"] + 50000)                  # bonus is a taxable earning
        self.assertEqual(r["penalty"], round(contract / 30.0))              # one day of pay
        self.assertEqual(r["loan"], 100000)
        self.assertEqual(r["net"], r["gross"] - r["si_ee"] - r["tax"] - r["martyrs"] - r["penalty"] - r["loan"])
        f0 = bal(c, "177500")
        payroll.post(c, y, p, U)                                            # balanced posting
        self.assertEqual(bal(c, "117000") - l0, 200000)                      # loan reduced by the installment
        self.assertEqual(f0 - bal(c, "177500"), r["penalty"])                # penalty to the workers' fund
        loan = extras.loans(c)[0]
        self.assertEqual((loan["repaid"], loan["balance"], loan["status"]), (100000, 200000, "A"))
        err(self, lambda: extras.add_payment(c, {"pernr": "10004", "wtype": "BONUS", "amount": "1",
                                                 "gjahr": y, "perio": p}, U), "988")  # payroll posted
        payroll.reverse_posting(c, y, p, U)
        payroll.run(c, y, p, U)                                              # rerun: installment not doubled
        self.assertEqual(extras.loans(c)[0]["repaid"], 100000)


class FollowUpAndReports(unittest.TestCase):
    def test_events_leave_balances_cost_and_month_end(self):
        from hr import extras
        c = system()
        new_hire = (T - datetime.timedelta(days=80)).isoformat()            # probation ends in 10 days
        c.execute("UPDATE hr_employee SET hire_date=? WHERE pernr='10009'", (new_hire,))
        ev = extras.events(c, TODAY, 60)
        typs = {(r["pernr"], r["typ"]) for r in ev["rows"]}
        self.assertIn(("10009", "Probation ends"), typs)
        self.assertIn(("10010", "Contract ends"), typs)                      # demo fixed-term contract
        self.assertTrue(any(r["urgent"] for r in ev["rows"] if r["pernr"] == "10009"))
        lb = extras.leave_balances(c, T.year)
        for r in lb["rows"]:
            self.assertEqual(r["remaining"], r["entitlement"] - r["taken"] - r["requested"])
        co = extras.cost(c, T.year)
        paid = c.execute("SELECT COALESCE(SUM(gross+si_er),0) FROM hr_payroll WHERE gjahr=?", (T.year,)).fetchone()[0]
        self.assertEqual(co["total"], paid)
        y, p = open_month(c)
        st = extras.status(c, y, p)
        self.assertEqual(st["steps"][-1]["tcode"], "PC00_M99_DTA")
        self.assertEqual(st["done"], sum(1 for s in st["steps"] if s["status"] == "done"))


if __name__ == "__main__":
    unittest.main()
