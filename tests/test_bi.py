"""BI: every catalog report runs on the live data; the P/L structure adds up;
filters, drill-down, column spread and saved views work."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fixture  # noqa: E402,F401
from mm import seed  # noqa: E402
from mm.db import connect  # noqa: E402
from mm.util import MMError  # noqa: E402

_DB = {}


def demo():
    if "c" not in _DB:
        c = connect(":memory:")
        seed.seed(c)
        _DB["c"] = c
    return _DB["c"]


class Reports(unittest.TestCase):
    def test_every_report_runs(self):
        from bi import catalog, engine
        c = demo()
        n = 0
        for rid, r in catalog.flat().items():
            if "dashboard" in r["query"]:
                continue
            res = engine.run(c, dict(r["query"]))
            self.assertTrue(res["columns"], rid)
            n += 1
        self.assertGreater(n, 40)

    def test_pl_structure_adds_up_and_matches_copa(self):
        from bi import engine
        c = demo()
        res = engine.run(c, dict(provider="COPA", structure="PL", year=2026, period=11,
                                 columns=[dict(version="ACT", time="YTD"), dict(pct=True)]))
        v = {r["node"]: r["values"][0] for r in res["rows"]}
        self.assertAlmostEqual(v["NS"], v["GS"] - v["SD"], 2)
        self.assertAlmostEqual(v["COGS"], v["MAT"] + v["LAB"] + v["MAC"] + v["MOH"], 2)
        self.assertAlmostEqual(v["OP"], v["GM"] - v["VAR"] - v["OPEX"], 2)
        self.assertAlmostEqual(v["NI"], v["OP"] - v["TAX"], 2)
        gs = c.execute("SELECT SUM(vv010) FROM copa_item WHERE plikz=0 AND gjahr=2026 AND perio<=11").fetchone()[0]
        self.assertAlmostEqual(v["GS"], gs / 100.0, 2)
        ns_pct = [r for r in res["rows"] if r["node"] == "NS"][0]["values"][1]
        self.assertEqual(ns_pct, 100.0)

    def test_filter_drilldown_spread_and_total(self):
        from bi import engine
        c = demo()
        res = engine.run(c, dict(provider="SALES", rows=["customer"], columns=[dict(kf="net"), dict(kf="net", pct=True)]))
        total = res["rows"][-1]
        self.assertTrue(total["total"])
        self.assertAlmostEqual(sum(r["values"][0] for r in res["rows"][:-1]), total["values"][0], 2)
        one = res["rows"][0]["labels"][0]
        f = engine.run(c, dict(provider="SALES", rows=["material"], columns=[dict(kf="net")],
                               filters={"customer": [one]}))
        self.assertAlmostEqual(f["rows"][-1]["values"][0], res["rows"][0]["values"][0], 2)
        s = engine.run(c, dict(provider="INV", rows=["matkl"], columns=[dict(kf="value")], colchar="aging"))
        self.assertEqual(s["columns"][-1]["label"].split()[0], "Total")
        with self.assertRaises(MMError):
            engine.run(c, dict(provider="NOPE"))
        with self.assertRaises(MMError):
            engine.run(c, dict(provider="SALES", rows=["nope"]))

    def test_saved_views_per_user(self):
        from bi import catalog
        c = demo()
        n = catalog.save_view(c, "U1", "SD_SALES", "My sales", {"provider": "SALES", "rows": ["region"]})
        self.assertEqual([v["title"] for v in catalog.views(c, "U1")], ["My sales"])
        self.assertEqual(catalog.views(c, "U2"), [])
        catalog.delete_view(c, "U1", n)
        self.assertEqual(catalog.views(c, "U1"), [])


class Overview(unittest.TestCase):
    def test_erp_dashboard_counts_confirmations_and_scrap(self):
        """Confirmations that are not cancelled (stokz 0 / '') count for yield and scrap."""
        from bi import overview, providers
        c = demo()
        n, scrap = c.execute("SELECT COUNT(*), COALESCE(SUM(xmnga),0) FROM confirmation WHERE "
                             "COALESCE(stokz,0) IN (0,'0','')").fetchone()
        d = overview.overview(c, "QA", everything=True)
        self.assertEqual(d["quality"]["confirmations"], n)
        self.assertEqual(d["quality"]["scrap"], scrap / 1000.0)
        if scrap:
            self.assertLess(d["quality"]["yield_pct"], 100.0)
        self.assertEqual(sum(f["scrap"] for f in providers.production(c)), scrap)
        for key in ("finance", "profit", "production", "quality", "warehouse", "procurement", "sales",
                    "controlling", "analytics", "tasks", "hr"):
            self.assertIn(key, d)
        self.assertAlmostEqual(d["warehouse"]["value"],
                               sum(f["value"] for f in providers.inventory(c)) / 100.0, 2)
        self.assertTrue(d["tasks"])                       # demo has open approvals


class Dashboards(unittest.TestCase):
    def test_status_dashboards_currency_and_scaling(self):
        from bi import dashboards as D, engine
        c = demo()
        for did in D.DASHBOARDS:
            d = D.run(c, did, {"year": 2026, "period": 11})
            self.assertEqual(len(d["widgets"]), 3, did)
            for w in d["widgets"]:
                self.assertEqual(len(w["categories"]), len(w["bars"][0]["values"]), did)
            self.assertTrue(d["table"]["rows"], did)
        pl = D.run(c, "PL_STATUS", {"year": 2026, "period": 11})
        ns = pl["table"]["rows"][0]["values"]
        ref = engine.run(c, dict(provider="COPA", structure="PL", year=2026, period=11,
                                 columns=[dict(version="ACT", time="P")]))
        self.assertAlmostEqual(ns[1], [r for r in ref["rows"] if r["node"] == "NS"][0]["values"][0], 2)
        usd = D.run(c, "PL_STATUS", {"year": 2026, "period": 11, "currency": "USD", "scale": "1000"})
        self.assertTrue(usd["note"].startswith("Currency: USD"))
        self.assertLess(usd["table"]["rows"][0]["values"][1], ns[1] / 1000)
        with self.assertRaises(MMError):
            D.run(c, "PL_STATUS", {"scale": "7"})
        with self.assertRaises(MMError):
            D.run(c, "NOPE", {})


if __name__ == "__main__":
    unittest.main()
