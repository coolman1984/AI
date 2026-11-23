"""What-If simulator (ZWHATIF): the baseline is the year from the books; each lever moves the right
line; the goal seek hits the target exactly; inputs are validated; scenarios are saved, compared and
deleted; Arabic or English."""
import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fixture  # noqa: E402,F401
from mm import seed  # noqa: E402
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


class Simulation(unittest.TestCase):
    def test_baseline_levers_and_goal_seek(self):
        from ai import whatif as W
        from fi.reports import statements
        from mm import util as clock
        c = system()
        b = W.baseline(c)
        t = clock.today()
        ytd = statements(c, t.year, 1, t.month)["result"]
        self.assertAlmostEqual(b["result"], round(ytd * 12.0 / b["months"], 2), delta=1)   # the books, annualised
        r = W.simulate(c, {})
        self.assertEqual(r["sim"]["result"], r["base"]["result"])
        self.assertEqual(r["impact"], [])
        rev, mat = b["pl"]["revenue"], b["pl"]["material"]
        r = W.simulate(c, {"price": 10})
        self.assertAlmostEqual(r["diff"], rev * 0.10, delta=1)                               # price: only revenue
        r = W.simulate(c, {"volume": 10})
        self.assertAlmostEqual(r["diff"], (rev + mat) * 0.10, delta=1)                       # volume: revenue and material
        r = W.simulate(c, {"fx": 20})
        self.assertAlmostEqual(r["diff"], rev * b["export_share"] / 100 * 0.2 + mat * b["imported_pct"] / 100 * 0.2, delta=1)
        r = W.simulate(c, {"staff": 2})
        self.assertAlmostEqual(r["diff"], -2 * b["staff_cost_month"] * 12, delta=1)
        r = W.simulate(c, {"rate": 2})
        self.assertAlmostEqual(r["diff"], -b["loans"] * 0.02, delta=1)
        r = W.simulate(c, {"capex": 1000000, "capex_years": 5})
        self.assertAlmostEqual(r["diff"], -200000, delta=1)
        self.assertAlmostEqual(r["sim"]["cash_capex"], -1000000)
        r = W.simulate(c, {"dso": b["dso"] - 30})
        self.assertAlmostEqual(r["sim"]["cash_working_capital"], 30 * rev / 365.0, delta=1)  # faster collection frees cash
        r = W.simulate(c, {"price": 10, "material": -5, "salaries": 10})
        self.assertEqual([x["lever"] for x in r["impact"]], sorted([x["lever"] for x in r["impact"]],
                         key=lambda k: -abs(next(i["effect"] for i in r["impact"] if i["lever"] == k))))
        self.assertIn(r["impact"][0]["name"], r["opinion"])                                # the biggest driver is named
        for lever in ("price", "volume", "material", "salaries", "other"):                    # goal seek is exact
            g = W.goal_seek(c, b["result"] + 100000, lever)
            r = W.simulate(c, {lever: g["value"]})
            self.assertAlmostEqual(r["sim"]["result"], b["result"] + 100000, delta=abs(g["value"]) * 50 + 5)
        err(self, lambda: W.simulate(c, {"price": "x"}), "901")
        err(self, lambda: W.simulate(c, {"price": 500}), "902")
        err(self, lambda: W.goal_seek(c, 0, "fx"), "903")
        err(self, lambda: W.goal_seek(c, "abc", "price"), "904")
        err(self, lambda: W.simulate(c, {"staff": -(b["staff"] + 1)}), "908")

    def test_scenarios_and_languages(self):
        from ai import whatif as W
        c = system()
        err(self, lambda: W.save(c, {"name": " ", "params": {}}, "U1"), "906")
        a = W.save(c, {"name": "Dollar +20%", "params": {"fx": 20}}, "U1")["id"]
        b = W.save(c, {"name": "Prices +10%", "params": {"price": 10}}, "U1")["id"]
        self.assertEqual([s["name"] for s in W.scenarios(c)], ["Prices +10%", "Dollar +20%"])
        cmp = W.compare(c, [a, b])
        self.assertEqual(len(cmp["columns"]), 3)
        self.assertEqual(cmp["best"], "Prices +10%")
        W.delete(c, a, "U1")
        err(self, lambda: W.delete(c, a, "U1"), "907")
        err(self, lambda: W.delete(c, "x", "U1"), "088")
        en = W.simulate(c, {"price": 10, "dso": 40}, lang="en")
        self.assertFalse(re.search("[\\u0600-\\u06FF]", json.dumps({k: en[k] for k in ("opinion", "impact", "levers")},
                                                                    ensure_ascii=False)))
        self.assertTrue(re.search("[\\u0600-\\u06FF]", W.simulate(c, {"price": 10})["opinion"]))
        self.assertEqual(len(W.presets("en")), len(W.PRESETS))
        for p in W.presets():                                                     # every ready scenario is valid
            W.simulate(c, p["params"])


if __name__ == "__main__":
    unittest.main()
