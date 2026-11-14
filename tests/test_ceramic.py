"""Ceramic company example (tools/demo/ceramic_example.py, docs/ceramic): the Excel workbook
loads into an empty system without one error and with a balanced opening balance, and the
November story of the sheet "الخطوات" gives exactly the numbers written in the guide."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools", "demo"))

import fixture  # noqa: E402,F401
import ceramic_example as X  # noqa: E402
from mm import dataimport as D, seed, util  # noqa: E402
from mm.db import connect, transaction  # noqa: E402
from qa.invariants import check  # noqa: E402


def loaded():
    c = connect(":memory:")
    seed.mark_no_demo(c)
    r = D.run_xlsx(c, X.build(), "QA", simulate=False)
    return c, r


class CeramicExample(unittest.TestCase):
    def setUp(self):
        self.old = util.set_clock("2026-11-14")          # the business date of the guide

    def tearDown(self):
        util.set_clock(self.old)

    def test_workbook_loads_completely_and_balanced(self):
        c, r = loaded()
        self.assertEqual((r["ok"], r["errors"]), (66, 0), r["message"])
        self.assertEqual(D.takeover_balance(c), 0)                  # opening balance sheet balances
        self.assertEqual(c.execute("SELECT altkn FROM vendor WHERE lifnr='100001'").fetchone()[0], "V-CLAY")
        stock = c.execute("SELECT SUM(salk3) FROM valuation").fetchone()[0]
        self.assertEqual(stock, 66490000)                           # 664,900.00 as in the guide
        self.assertEqual(check(c), [])

    def test_november_story_gives_the_numbers_of_the_guide(self):
        c, _ = loaded()
        with transaction(c):
            d = X.run_story(c, "QA")
        q = lambda sql, *a: c.execute(sql, a).fetchone()             # noqa: E731
        self.assertEqual(tuple(q("SELECT netwr, mwsbk FROM sd_vbak WHERE vbeln=?", d["sales_order"])),
                         (61110000, 8555400))                       # 611,100 + 85,554
        self.assertEqual(q("SELECT gamng FROM orders WHERE aufnr=?", d["prod_order"])[0], 1800000)
        self.assertEqual(q("SELECT netpr FROM po_item WHERE ebeln=?", d["glaze_po"])[0], 3430)   # 34.30
        self.assertEqual(q("SELECT stprs FROM valuation WHERE matnr='FG-FLOOR60'")[0], 11010)    # 110.10
        self.assertEqual(q("SELECT stprs FROM valuation WHERE matnr='FG-WALL3060'")[0], 7945)    # 79.45
        self.assertEqual(q("SELECT SUM(lfimg) FROM sd_lips WHERE vbeln=?", d["delivery"])[0], 2960000)
        self.assertEqual(tuple(q("SELECT netwr, mwsbk FROM billing WHERE vbeln=?", d["invoice"])),
                         (60295200, 8441328))                       # 602,952 + 84,413.28
        from hr import payroll
        t = payroll._totals(payroll.results(c, 2026, 11))
        self.assertEqual((t["gross"], t["net"]), (7320000, 6054195))  # 73,200 / 60,541.95
        from fi import reports
        st = reports.statements(c, 2026, 11, 11)
        self.assertTrue(st["balanced"])
        self.assertEqual(st["result"], 141465.66)
        self.assertEqual(st["assets"], 11712185.74)
        self.assertEqual(check(c), [])


if __name__ == "__main__":
    unittest.main()
