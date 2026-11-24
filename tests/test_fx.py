"""Exchange rates of all currencies (ZFX / OB08): the ISO currency master, rates only for known foreign
currencies, the latest rate with change and age, bulk entry, history, cross rates through EGP, the
quotation unit (per 100 / 1000 units) and currencies used in the books without a rate."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fixture  # noqa: E402,F401
from mm import seed  # noqa: E402
from mm import util as clock  # noqa: E402
from mm.db import connect  # noqa: E402
from mm.util import MMError  # noqa: E402


def system():
    c = connect(":memory:")
    seed.seed(c)
    return c


def err(test, fn, no):
    with test.assertRaises(MMError) as x:
        fn()
    test.assertEqual(x.exception.msg_no, no, str(x.exception))


class Rates(unittest.TestCase):
    def test_ob08_accepts_only_known_foreign_currencies(self):
        from fi import gl
        c = system()
        err(self, lambda: gl.set_rate(c, "XYZ", clock.today().isoformat(), "1"), "106")   # unknown currency
        err(self, lambda: gl.set_rate(c, "EGP", clock.today().isoformat(), "1"), "107")   # the local currency has no rate
        gl.set_rate(c, "SAR", clock.today().isoformat(), "13.25")
        self.assertEqual(c.execute("SELECT ukurs FROM exch_rate WHERE waers='SAR'").fetchone()[0], 1325000)

    def test_all_currencies_bulk_history_cross_rates_and_missing(self):
        from fi import currency as fx
        c = system()
        t = clock.today().isoformat()
        lst = fx.overview(c)
        codes = {r["waers"] for r in lst["rows"]}
        self.assertGreaterEqual(len(codes), 150)
        self.assertTrue({"USD", "EUR", "GBP", "SAR", "AED", "KWD", "CNY", "JPY", "TRY"} <= codes)
        self.assertNotIn("EGP", codes)
        usd = next(r for r in lst["rows"] if r["waers"] == "USD")
        self.assertEqual(usd["rate"], 49.8)                                      # latest demo rate
        self.assertEqual(usd["previous"], 49.2)
        self.assertAlmostEqual(usd["change_pct"], round(100 * (49.8 - 49.2) / 49.2, 2))
        r = fx.save_rates(c, "SAR 13.25\nAED;13.55\nJPY 33.10\nKWD 161.4\nXYZ 1\nEUR abc", t, "FX")
        self.assertEqual(r["saved"], 4)
        self.assertEqual(len(r["errors"]), 3)                                    # XYZ unknown; EUR without rate; "abc" not a rate
        r = fx.save_rates(c, "CHF 61.2, GBP;%s;66.1 | CAD 35.4" % t, t, "FX")             # one line, mixed separators
        self.assertEqual((r["saved"], r["errors"]), (3, []))
        jpy = next(x for x in fx.overview(c)["rows"] if x["waers"] == "JPY")
        self.assertEqual(jpy["factor"], 100)                                     # quoted per 100 yen
        self.assertEqual(jpy["rate"], 33.10)
        self.assertEqual(c.execute("SELECT ukurs FROM exch_rate WHERE waers='JPY'").fetchone()[0], 33100)   # 0.331 per yen
        cv = fx.convert(c, "1000", "SAR", "USD", t)                              # cross rate through EGP
        self.assertAlmostEqual(cv["result"], round(1000 * 13.25 / 49.8, 2), places=2)
        self.assertAlmostEqual(fx.convert(c, "100", "USD", "EGP", t)["result"], 4980.0)
        err(self, lambda: fx.convert(c, "1", "USD", "XYZ", t), "106")
        err(self, lambda: fx.convert(c, "1", "BRL", "USD", t), "105")           # no rate yet
        h = fx.history(c, "USD")
        self.assertEqual([x["gdatu"] for x in h["rows"]], sorted(x["gdatu"] for x in h["rows"]))
        self.assertGreaterEqual(len(h["rows"]), 5)
        c.execute("UPDATE hr_employee SET waers='NOK' WHERE pernr='10024'")
        self.assertIn("NOK", [m["waers"] for m in fx.overview(c)["missing"]])  # used without a rate
        fx.set_active(c, "GBP", False)
        self.assertNotIn("GBP", {x["waers"] for x in fx.overview(c)["rows"]})
        self.assertIn("GBP", {x["waers"] for x in fx.overview(c, everything=True)["rows"]})


if __name__ == "__main__":
    unittest.main()
