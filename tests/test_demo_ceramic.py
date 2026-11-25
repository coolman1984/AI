"""Ceramic factory demo (run.py --reset --demo ceramic): the whole factory loads into an empty
system through the takeover objects and the engines without an error, the takeover account
399999 ends at zero, this month's business is there (purchase, production with scrap, domestic
and export sales), and the Excel workbook of the same data loads through ZIMPORT unchanged."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fixture  # noqa: E402,F401
from mm.db import connect  # noqa: E402

_C = {}


def factory():
    if "c" not in _C:
        from mm import demo_ceramic
        c = connect(":memory:")
        demo_ceramic.load(c)
        _C["c"] = c
    return _C["c"]


class CeramicDemo(unittest.TestCase):
    def test_factory_loads_and_balances(self):
        from mm.dataimport import takeover_balance
        c = factory()
        self.assertEqual(takeover_balance(c), 0)
        n = lambda sql: c.execute(sql).fetchone()[0]
        self.assertEqual(n("SELECT COUNT(*) FROM customer"), 7)
        self.assertEqual(n("SELECT COUNT(*) FROM vendor"), 9)
        self.assertEqual(n("SELECT COUNT(*) FROM hr_employee"), 20)
        self.assertEqual(n("SELECT COUNT(*) FROM asset"), 10)
        self.assertEqual(n("SELECT meins FROM material WHERE matnr='FG-P612'"), "M2")
        # the standard demo is never loaded on top of it
        from mm import seed
        self.assertTrue(seed.no_demo(c))
        self.assertIsNone(seed.seed(c))

    def test_this_months_business(self):
        c = factory()
        n = lambda sql, *a: c.execute(sql, a).fetchone()[0]
        self.assertEqual(n("SELECT COUNT(*) FROM po_header"), 5)
        self.assertEqual(n("SELECT COUNT(*) FROM orders"), 6)
        self.assertEqual(n("SELECT COUNT(*) FROM sd_vbak"), 7)
        self.assertEqual(n("SELECT COUNT(*) FROM billing WHERE cancelled=0"), 5)
        # tiles produced into the finished goods store, kiln scrap recorded
        self.assertGreater(n("SELECT COUNT(*) FROM mat_doc_item WHERE bwart='101' AND aufnr IS NOT NULL"), 2)
        # export invoice in US dollars
        self.assertEqual(n("SELECT COUNT(*) FROM billing WHERE kunnr='C1006' AND waerk='USD'"), 1)

    def test_excel_workbook_loads_through_zimport(self):
        from mm import dataimport, demo_ceramic
        x = demo_ceramic.excel()
        c = connect(":memory:")
        r = dataimport.run_xlsx(c, x, "ADMIN", simulate=False)
        self.assertEqual(r["errors"], 0, [l for l in r["log"] if l["status"] != "S"][:3])
        self.assertGreater(r["ok"], 150)
        self.assertEqual(dataimport.takeover_balance(c), 0)

    def test_not_on_top_of_existing_data(self):
        from mm import demo_ceramic
        from mm.util import MMError
        with self.assertRaises(MMError):
            demo_ceramic.load(factory())


if __name__ == "__main__":
    unittest.main()
