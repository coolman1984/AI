"""Controlling in depth: budget with availability control (2-x), accruals (5-x),
closing management and the CO period lock (1-5), sales adjustment KE21N (3-1),
plan copy KP97 and P&L simulation (7-x)."""
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
Y = T.year
U = "COQA"


def system():
    c = connect(":memory:")
    seed.seed(c)
    return c


def err(test, fn, no):
    with test.assertRaises(MMError) as x:
        fn()
    test.assertEqual(x.exception.msg_no, no, str(x.exception))


def expense(c, kostl, amount, hkont="475000", budat=TODAY):
    from co.fi import post_gl_document
    return post_gl_document(c, {"budat": budat, "bktxt": "QA expense"}, [
        {"hkont": hkont, "debit": amount, "kostl": kostl},
        {"hkont": "113100", "credit": amount}], U)["belnr"]


class Budget(unittest.TestCase):
    def test_original_release_availability_control_and_report(self):
        from co import budget
        c = system()
        used = budget.consumption(c, "KS4200", Y)
        base = used["actual"] + used["commitment"]
        budget.set_profile(c, warn_pct="80", err_pct="100", check_po=True)
        budget.post(c, "KS4200", Y, "ORIG", "%.2f" % ((base + 1000000) / 100.0), U, "Maintenance budget")
        err(self, lambda: expense(c, "4200", "100"), "603")                      # nothing released yet
        budget.post(c, "KS4200", Y, "REL", "%.2f" % ((base + 1000000) / 100.0), U)
        expense(c, "4200", "9000")                                                 # within (90 %: a warning)
        self.assertTrue(any(w["typ"] == "WARN" for w in budget.log(c, "KS4200", Y)))
        err(self, lambda: expense(c, "4200", "2000"), "603")                     # over the released budget
        err(self, lambda: budget.post(c, "KS4200", Y, "REL", "1", U), "611")      # cannot release more than budget
        budget.post(c, "KS4200", Y, "SUPP", "5000", U, "Extra repair")
        budget.post(c, "KS4200", Y, "REL", "5000", U)
        expense(c, "4200", "2000")
        from pur import po
        err(self, lambda: po.create_po(c, {"lifnr": "100005", "bedat": TODAY, "items": [
            {"txz01": "Overhaul", "matkl": "SERVICE", "meins": "AU", "menge": "1", "knttp": "K", "kostl": "4200",
             "sakto": "475000", "netpr": "6000"}]}, U), "603")                       # the PO commitment counts too
        r = [x for x in budget.report(c, Y) if x["objnr"] == "KS4200"][0]
        self.assertEqual(r["budget"], base + 1000000 + 500000)
        self.assertEqual(r["available"], r["released"] - r["actual"] - r["commitment"])
        err(self, lambda: budget.post(c, "KS4200", Y, "RET", "999999", U), "612")  # return more than free
        expense(c, "4100", "1000")                                                 # no budget: no check


class PeriodLock(unittest.TestCase):
    def test_locked_period_refuses_actual_postings(self):
        from co import closing
        c = system()
        closing.lock(c, Y, T.month, True, U)
        err(self, lambda: expense(c, "4200", "100"), "400")
        st = closing.status(c, Y, T.month)
        self.assertTrue(st["locked"])
        self.assertEqual([s["step"] for s in st["steps"]][:2], ["Accruals", "Activity prices"])
        closing.lock(c, Y, T.month, False, U)
        expense(c, "4200", "100")


class Accruals(unittest.TestCase):
    def test_monthly_accrual_run_reverse_and_year_total(self):
        from co import accrual
        c = system()
        rid = accrual.save_rule(c, {"text": "Annual bonus", "kostl": "9100", "hkont": "430000", "annual": "100000",
                                    "gjahr": Y}, U)
        r = accrual.run(c, Y, T.month, U)
        self.assertEqual(r["posted"], 1)
        doc = r["docs"][0]
        line = c.execute("SELECT * FROM acc_doc_item WHERE belnr=? AND hkont='190000'", (doc["belnr"],)).fetchone()
        self.assertEqual((line["shkzg"], line["dmbtr"]), ("H", 833333))                    # 100,000 / 12
        err(self, lambda: accrual.run(c, Y, T.month, U), "702")                           # once per period
        accrual.reverse(c, Y, T.month, U)
        accrual.run(c, Y, T.month, U)
        self.assertEqual(sum(accrual.monthly_amounts(10000000)), 10000000)                 # 12 parts add up
        rep = [x for x in accrual.report(c, Y) if x["id"] == rid][0]
        self.assertEqual(rep["accrued"], 833333)
        err(self, lambda: accrual.save_rule(c, {"text": "x", "kostl": "9100", "hkont": "113100", "annual": "1",
                                                "gjahr": Y}, U), "705")                   # not a cost element


class SalesAndPlanning(unittest.TestCase):
    def test_ke21n_kp97_and_simulation(self):
        from co import copa, planning, reports, simulation
        c = system()
        b = copa.manual_line(c, {"budat": TODAY, "kunnr": "C1001", "matnr": "FG-3001", "vv020": "1500",
                                 "text": "Year-end rebate"}, U)
        items = reports.ke24(c, Y, T.month, T.month)
        self.assertTrue(any(i["belnr"] == b and i["vrgar"] == "B" for i in items))
        err(self, lambda: copa.manual_line(c, {"budat": TODAY, "kunnr": "NOPE", "vv010": "1"}, U), "102")
        n = planning.copy_plan(c, Y, Y + 1, "10", U)
        self.assertGreater(n, 0)
        src = c.execute("SELECT SUM(wtg) FROM co_item WHERE wrttp='01' AND vrgng='RKP1' AND gjahr=?", (Y,)).fetchone()[0]
        dst = c.execute("SELECT SUM(wtg) FROM co_item WHERE wrttp='01' AND vrgng='RKP1' AND gjahr=?", (Y + 1,)).fetchone()[0]
        self.assertAlmostEqual(dst, src * 1.1, delta=200)
        s = simulation.run(c, {"gjahr": Y, "pfrom": 1, "pto": 12, "price": "10", "volume": "0"})
        ns = {r["node"]: r for r in s["rows"]}["NS"]
        self.assertAlmostEqual(ns["sim"], round(ns["base"] * 1.1, 2), delta=1)
        v = simulation.run(c, {"gjahr": Y, "pfrom": 1, "pto": 12, "volume": "5", "material": "-2"})
        m = {r["node"]: r for r in v["rows"]}["MAT"]
        self.assertAlmostEqual(m["sim"], round(m["base"] * 1.05 * 0.98, 2), delta=1)
        be = s["breakeven_volume_pct"]                                   # at the break-even volume the profit is 0
        if be is not None:
            z = simulation.run(c, {"gjahr": Y, "pfrom": 1, "pto": 12, "price": "10", "volume": "%.4f" % (be - 100)})
            self.assertAlmostEqual({r["node"]: r for r in z["rows"]}["OP"]["sim"], 0, delta=50)


if __name__ == "__main__":
    unittest.main()
