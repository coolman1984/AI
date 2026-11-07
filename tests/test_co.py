"""CO tests on the full demo (plan + one closed sample month).
Run:  python -m unittest discover -s tests -v"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from co import period_end, reports  # noqa: E402
from co.fi import post_gl_document  # noqa: E402
from co.seed import sample_period_start  # noqa: E402
from mm import seed  # noqa: E402
from mm.db import connect  # noqa: E402
from mm.posting import post_goods_movement  # noqa: E402
from mm.util import MMError  # noqa: E402

_DB = {}


def demo():
    if "c" not in _DB:
        c = connect(":memory:")
        seed.seed(c)
        _DB["c"] = c
    return _DB["c"]


P = sample_period_start()
Y, M = P.year, P.month


def balance(c, prefix):
    return c.execute("SELECT COALESCE(SUM(wtg),0) FROM co_item WHERE wrttp='04' AND "
                     "gjahr=? AND perio=? AND objnr LIKE ?", (Y, M, prefix + "%")
                     ).fetchone()[0]


class Planning(unittest.TestCase):
    def test_plan_prices_iterative(self):
        p = {(r["kostl"], r["lstar"]): (r["price_fix"], r["price_var"])
             for r in reports.activity_prices(demo(), Y, M)}
        # maintenance: (12000 + 4000 + 1500 rent + 1000 energy) / 80 h fixed,
        #              4000 / 80 h variable
        self.assertEqual(p[("4200", "MAINT")], (231.25, 50.0))
        # machining includes 50 maintenance hours at 281.25 (iteration)
        self.assertEqual(p[("4100", "MACH")], (499.25, 34.0))
        self.assertEqual(p[("4120", "LAB")], (157.0, 63.0))

    def test_plan_balances_close_except_overhead_cost_centers(self):
        c = demo()
        for k in ("4100", "4120", "4200", "4210", "9900"):
            b = c.execute("SELECT COALESCE(SUM(wtg),0) FROM co_item WHERE wrttp='01' AND "
                          "gjahr=? AND perio=? AND objnr=? AND vrgng<>'KEU5'",
                          (Y, M, "KS" + k)).fetchone()[0]
            self.assertLess(abs(b), 100, k)        # only cents of rounding


class ProductCosting(unittest.TestCase):
    def test_cost_estimate_structure(self):
        from co.costing import get_estimate
        e = get_estimate(demo(), matnr="FG-3001", werks="1000")
        comp = {x["ccomp"]: x["per_unit"] for x in e["components"]}
        self.assertEqual(comp[30], 550.0)            # 2.5 h x 220.00
        self.assertEqual(comp[40], 639.9)            # 1.2 h x 533.25
        self.assertAlmostEqual(comp[20], round(comp[10] * 0.05, 2), places=2)
        self.assertAlmostEqual(comp[50], round((550 + 639.9) * 0.10, 2), places=2)
        v = demo().execute("SELECT stprs FROM valuation WHERE matnr='FG-3001' AND "
                           "bwkey='1000'").fetchone()[0]
        self.assertEqual(v / 100.0, e["unit_cost"])   # CK24 updated the std price


class ClosingResults(unittest.TestCase):
    def test_all_cost_centers_and_orders_are_cleared(self):
        c = demo()
        self.assertEqual(balance(c, "KS"), 0)
        self.assertEqual(balance(c, "OR"), 0)

    def test_fi_result_equals_copa_operating_result(self):
        r = reports.reconcile(demo(), Y, M, M)
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["fi_result"], r["copa_ebit"])
        self.assertEqual(r["cogs_fi"], r["cogs_copa"])

    def test_variance_categories_add_up_to_settled_amount(self):
        c = demo()
        orders = c.execute("SELECT DISTINCT aufnr FROM order_variance").fetchall()
        self.assertEqual(len(orders), 2)
        for o in orders:
            v = c.execute("SELECT SUM(price_var+qty_var+res_var+rem_var) FROM "
                          "order_variance WHERE aufnr=?", (o["aufnr"],)).fetchone()[0]
            settled = -c.execute("SELECT COALESCE(SUM(wtg),0) FROM co_item WHERE objnr=? "
                                 "AND vrgng='KOAO'", ("OR" + o["aufnr"],)).fetchone()[0]
            self.assertEqual(v, settled)

    def test_quantity_variance_steel(self):
        c = demo()
        r = c.execute("SELECT * FROM order_variance WHERE ressource='RM-1001' AND "
                      "aufnr=(SELECT aufnr FROM orders WHERE matnr='FG-3001')").fetchone()
        price = c.execute("SELECT price FROM cost_estimate_item WHERE ressource='RM-1001' "
                          "AND id=(SELECT estimate_id FROM orders WHERE matnr='FG-3001')"
                          ).fetchone()[0]
        self.assertEqual(r["qty_var"], 30 * price)     # 1830 kg issued, 1800 target

    def test_copa_assessment_cleared_sales_costs(self):
        k = {r["code"]: r for r in reports.ke30(demo(), Y, M, M)["rows"]}
        # sales costs: salaries 26000 + marketing 18500 + freight 5900 + rent
        # share 1125 + trade fair order 12000 (settled to 8100)
        self.assertEqual(k["vv100"]["actual"], 63525.0)

    def test_cycle_rerun_reverses_first(self):
        c = demo()
        before = reports.reconcile(c, Y, M, M)["fi_result"]
        period_end.run_cycle(c, "COPA01", Y, M, "04")
        self.assertEqual(balance(c, "KS"), 0)
        self.assertTrue(reports.reconcile(c, Y, M, M)["ok"])
        self.assertEqual(reports.reconcile(c, Y, M, M)["fi_result"], before)

    def test_test_run_posts_nothing(self):
        c = demo()
        n = c.execute("SELECT COUNT(*) FROM co_doc").fetchone()[0]
        res = period_end.run_cycle(c, "DIST01", Y, M, "04", test=True)
        self.assertTrue(res["test"])
        self.assertEqual(c.execute("SELECT COUNT(*) FROM co_doc").fetchone()[0], n)


class Checks(unittest.TestCase):
    def test_expense_without_cost_center_rejected(self):
        with self.assertRaises(MMError) as e:
            post_gl_document(demo(), {"budat": P.isoformat()}, [
                dict(hkont="476000", debit="100"), dict(hkont="113100", credit="100")], "T")
        self.assertEqual(e.exception.msg_no, "235")

    def test_issue_to_unreleased_order_rejected(self):
        from co.master import create_order
        c = demo()
        o = create_order(c, {"auart": "PP01", "matnr": "FG-3001", "werks": "1000",
                             "gamng": "10"}, "T")
        with self.assertRaises(MMError):
            post_goods_movement(c, {"budat": P.isoformat()}, [
                {"bwart": "261", "matnr": "RM-1001", "werks": "1000", "lgort": "0001",
                 "qty": "1", "aufnr": o}], "T")

    def test_mm_consistency_still_ok(self):
        from mm.reports import consistency_check
        self.assertTrue(consistency_check(demo())["ok"])


if __name__ == "__main__":
    unittest.main()
