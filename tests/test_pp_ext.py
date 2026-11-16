"""Production in depth: OEE per line (ZPP_OEE), scrap analysis (ZPP_SCRAP), order progress
(ZPP_PROGRESS), production configuration (ZPP_CONF) and month-end (ZPP_CLOSE)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fixture  # noqa: E402,F401
from mm import seed  # noqa: E402
from mm.db import connect  # noqa: E402

T = fixture.T
_C = {}


def system():
    if "c" not in _C:
        c = connect(":memory:")
        seed.seed(c)
        _C["c"] = c
        _C["m"] = c.execute("SELECT value FROM settings WHERE key='pp_sample'").fetchone()[0]
    return _C["c"]


def month():
    system()
    return _C["m"] + "-01", _C["m"] + "-28"


class Oee(unittest.TestCase):
    def test_availability_performance_quality(self):
        from pp import analysis
        c = system()
        d1, d2 = month()
        r = {x["arbpl"]: x for x in analysis.oee(c, d1, d2)["rows"]}
        m = r["WC-MACH"]                                  # 2 plan days x 8 h, 120 min material shortage
        self.assertEqual((m["planned_min"], m["downtime"], m["run_min"]), (960, 120, 840))
        self.assertEqual(m["availability"], 87.5)
        self.assertEqual(m["losses"][0]["reason"], "MAT")
        a = r["WC-ASSY"]
        self.assertEqual(a["quality"], round(a["good"] * 100.0 / (a["good"] + a["scrap"]), 1))
        for x in r.values():                              # OEE = A x P x Q
            if x["oee"] is not None:
                self.assertAlmostEqual(x["oee"], x["availability"] * x["performance"] * x["quality"] / 10000, 0)
                self.assertLessEqual(x["performance"], 100.0)
        self.assertTrue(all(x["ideal"] % 1000 == 0 for x in r.values()))    # whole units
        self.assertLess(m["oee"], 85)
        self.assertFalse(m["world_class"])


class ScrapAndProgress(unittest.TestCase):
    def test_scrap_pareto_and_order_progress(self):
        from pp import analysis
        c = system()
        d1, d2 = month()
        s = analysis.scrap(c, d1, d2)
        conf = c.execute("SELECT COALESCE(SUM(xmnga),0), COALESCE(SUM(lmnga),0) FROM confirmation WHERE stokz=0 AND "
                         "budat BETWEEN ? AND ?", (d1, d2)).fetchone()
        self.assertEqual(s["scrap"], conf[0])
        self.assertEqual(sum(x["scrap"] for x in s["by_reason"]), s["scrap"])
        self.assertEqual(s["by_reason"][-1]["cum"], 100.0)
        self.assertGreater(s["value"], 0)                 # scrap valued at the material price
        p = analysis.progress(c, T.isoformat())
        self.assertTrue(p["rows"])
        for r in p["rows"]:
            self.assertNotIn(r["stat"], ("DLV", "TECO", "CLSD"))
            self.assertEqual(r["dlv_pct"], round(r["delivered"] * 100.0 / r["gamng"], 1) if r["gamng"] else 0)
        late = analysis.progress(c, "2099-01-01")         # everything open is late then
        self.assertEqual(late["late"], len(late["rows"]))


class ConfigAndClosing(unittest.TestCase):
    def test_configuration_and_month_end(self):
        from pp import analysis
        c = system()
        cf = analysis.config(c)
        self.assertIn("PP01", [x["auart"] for x in cf["order_types"]])
        self.assertTrue(cf["work_centers"] and cf["scrap_reasons"])
        y, m = (int(x) for x in _C["m"].split("-"))
        st = analysis.status(c, y, m)
        self.assertEqual(st["steps"][0]["tcode"], "CO05N")
        self.assertEqual(st["steps"][-1]["tcode"], "CO88")
        self.assertEqual(st["done"], sum(1 for s in st["steps"] if s["status"] == "done"))


if __name__ == "__main__":
    unittest.main()
