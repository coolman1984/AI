"""Sales and warehouse in depth: customer rebate agreements with accrual and settlement
(ZREB01 / ZREB02 / ZREB_ACR / ZREB03), quotation follow-up (ZSD_QFU), sales configuration and
month-end (ZSD_CONF / ZSD_CLOSE), stock aging (ZMM_AGING), ABC analysis (ZMM_ABC), range of
coverage (ZMM_COVER), warehouse configuration and month-end (ZMM_CONF / ZMM_CLOSE)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fixture  # noqa: E402,F401
from mm import seed  # noqa: E402
from mm.db import connect  # noqa: E402
from mm.util import MMError, value_of  # noqa: E402

T = fixture.T
TODAY = T.isoformat()
Y = T.year
U = "SALES1"


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


class Rebates(unittest.TestCase):
    def test_tiers_accrual_and_settlement(self):
        from sd import rebate
        c = system()
        sales = c.execute("SELECT COALESCE(SUM(netwr),0) FROM billing WHERE cancelled=0 AND COALESCE(kunrg,kunnr)="
                          "'C1001' AND fkdat BETWEEN ? AND ?", ("%d-01-01" % Y, TODAY)).fetchone()[0]
        self.assertGreater(sales, 0)
        low, high = sales // 200, sales * 2                                 # first tier reached, second not
        k = rebate.create(c, {"kunnr": "C1001", "datab": "%d-01-01" % Y, "datbi": TODAY, "text": "Dealer 2026",
                              "scale": [["%.2f" % (low / 100.0), "2"], ["%.2f" % (high / 100.0), "3.5"]]}, U)["knuma"]
        s = rebate.status(c, k, TODAY)
        self.assertEqual((s["basis"], s["rate"]), (sales, 200))
        self.assertEqual(s["earned"], round(sales * 0.02))
        self.assertEqual(s["next"]["missing"], high - sales)
        err(self, lambda: rebate.create(c, {"kunnr": "C1001", "datab": TODAY, "datbi": TODAY,
                                            "scale": [["1", "1"]]}, U), "967")              # overlapping agreement
        err(self, lambda: rebate.create(c, {"kunnr": "C1002", "datab": TODAY, "datbi": TODAY, "scale": []}, U), "963")
        err(self, lambda: rebate.create(c, {"kunnr": "C1002", "datab": TODAY, "datbi": TODAY,
                                            "scale": [["100", "3"], ["200", "2"]]}, U), "964")
        err(self, lambda: rebate.create(c, {"kunnr": "NOPE", "datab": TODAY, "datbi": TODAY,
                                            "scale": [["1", "1"]]}, U), "966")
        a0 = bal(c, "291000")
        test = rebate.accrue(c, TODAY, U, test=True)
        self.assertEqual(bal(c, "291000"), a0)                                # test run posts nothing
        r = rebate.accrue(c, TODAY, U)
        self.assertEqual(r["total"], s["earned"])
        self.assertEqual(test["total"], r["total"])
        self.assertEqual(a0 - bal(c, "291000"), s["earned"])                  # liability credited
        self.assertEqual(rebate.accrue(c, TODAY, U)["rows"], [])              # nothing new to accrue
        open0 = c.execute("SELECT COUNT(*) FROM acc_doc_item WHERE koart='D' AND kunnr='C1001' AND augbl IS NULL"
                          ).fetchone()[0]
        res = rebate.settle(c, k, TODAY, U)
        self.assertEqual(res["earned"], s["earned"])
        self.assertEqual(bal(c, "291000"), a0)                                # accrual cleared
        self.assertEqual(c.execute("SELECT COUNT(*) FROM acc_doc_item WHERE koart='D' AND kunnr='C1001' AND "
                                   "augbl IS NULL").fetchone()[0], open0 + 1)  # credit for the customer
        err(self, lambda: rebate.settle(c, k, TODAY, U), "968")
        k2 = rebate.create(c, {"kunnr": "C1002", "datab": TODAY, "datbi": "%d-12-31" % Y,
                               "scale": [["1", "1"]]}, U)["knuma"]
        err(self, lambda: rebate.settle(c, k2, TODAY, U), "969")             # not yet ended


class SalesFollowUp(unittest.TestCase):
    def test_quotations_config_and_month_end(self):
        from sd import closing
        c = system()
        q = closing.quotations(c, TODAY)
        self.assertTrue(q["rows"])
        r = q["rows"][0]
        self.assertEqual(r["conversion"], round(r["ordered"] * 100.0 / r["netwr"], 1))
        self.assertEqual(q["hit_rate"], round(q["won"] * 100.0 / q["total"], 1))
        cf = closing.config(c)
        self.assertTrue(cf["doc_types"] and cf["conditions"] and cf["accounts"])
        st = closing.status(c, Y, T.month)
        self.assertEqual(st["steps"][0]["tcode"], "VKM1")
        self.assertIn("ZREB_ACR", [s["tcode"] for s in st["steps"]])
        self.assertEqual(st["done"], sum(1 for s in st["steps"] if s["status"] == "done"))


class WarehouseAnalysis(unittest.TestCase):
    def test_aging_abc_coverage_and_month_end(self):
        from mm import analysis, inventory
        c = system()
        ag = analysis.aging(c, TODAY)
        self.assertEqual(ag["total"]["value"], sum(ag["total"][b["key"]] for b in ag["buckets"]))
        self.assertEqual(ag["total"]["value"], sum(r["value"] for r in ag["rows"]))
        ab = analysis.abc(c, "1000", TODAY)
        self.assertEqual(ab["rows"][-1]["cum"], 100.0)
        self.assertEqual(ab["rows"][0]["abc"], "A")
        self.assertEqual([r["value"] for r in ab["rows"]], sorted((r["value"] for r in ab["rows"]), reverse=True))
        a_share = sum(r["value"] for r in ab["rows"] if r["abc"] == "A") * 100.0 / ab["total"]
        self.assertGreaterEqual(a_share, 80.0)
        analysis.save_abc(c, "1000", TODAY, "WH1")
        top = ab["rows"][0]["matnr"]
        self.assertEqual(c.execute("SELECT abcin FROM material_plant WHERE matnr=? AND werks='1000'", (top,))
                         .fetchone()[0], "A")
        self.assertEqual(analysis.save_abc(c, "1000", TODAY, "WH1")["changed"], 0)     # already saved
        self.assertTrue(all(p["abc"] in "ABC" for p in inventory.cycle_proposal(c, "1000", T)))
        cv = analysis.coverage(c, "1000", TODAY, 90)
        for r in cv["rows"]:
            if r["used"] > 0:
                self.assertAlmostEqual(r["cover_days"], round(r["stock"] / (r["used"] / 90.0), 1), 1)
            else:
                self.assertIsNone(r["cover_days"])
        st = analysis.status(c, Y, T.month)
        self.assertEqual(st["steps"][-1]["tcode"], "MMPV")
        cf = analysis.config(c)
        self.assertTrue(cf["slocs"] and cf["movement_types"])
        self.assertEqual(value_of(1000, 100, 1), 100)


if __name__ == "__main__":
    unittest.main()
