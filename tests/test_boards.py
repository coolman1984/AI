"""Sales status board (ZSD_BOARD) and warehouse status board (ZMM_BOARD): the figures must
agree with the source data (CO-PA plan / actual, sales orders, deliveries, receivables,
stock quants and material documents)."""
import calendar
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fixture  # noqa: E402,F401
from mm import seed  # noqa: E402
from mm.db import connect  # noqa: E402
from mm.util import value_of  # noqa: E402

_C = {}


def system():
    if "c" not in _C:
        c = connect(":memory:")
        seed.seed(c)
        _C["c"] = c
    return _C["c"]


def last_billing(c):
    return c.execute("SELECT MAX(fkdat) FROM billing WHERE cancelled=0").fetchone()[0]


class SalesBoard(unittest.TestCase):
    def test_plan_target_actual_and_panels(self):
        from fi.reports import aging
        from sd import board
        c = system()
        day = last_billing(c)
        b = board.board(c, day, day + "T18:00:00")
        y, m, dd = (int(x) for x in day.split("-"))
        rows = [r for g in b["groups"] for r in g["lines"]]
        plan = c.execute("SELECT COALESCE(SUM(vv010),0) FROM copa_item WHERE plikz=1 AND gjahr=? AND perio=? AND "
                         "matnr IS NOT NULL", (y, m)).fetchone()[0]
        self.assertEqual(b["total"]["plan"], plan)
        actual = c.execute("SELECT COALESCE(SUM(vv010),0) FROM copa_item WHERE plikz=0 AND budat BETWEEN ? AND ? AND "
                           "matnr IS NOT NULL", (day[:8] + "01", day)).fetchone()[0]
        self.assertEqual(b["total"]["actual"], actual)
        for r in rows:                                        # target = plan x elapsed share of the month
            share = dd / float(calendar.monthrange(y, m)[1])
            self.assertEqual(r["target"], int(round(r["plan"] * share)))
            self.assertEqual(r["diff"], r["actual"] - r["target"])
        self.assertEqual(b["total"]["diff"], b["total"]["actual"] - b["total"]["target"])
        self.assertGreater(b["orders"]["backlog"], 0)                       # open order not yet delivered
        self.assertEqual(b["orders"]["backlog"], sum(r["backlog"] for r in rows))
        ag = aging(c, "D", day)["rows"]
        self.assertAlmostEqual(sum(b["aging"].values()) / 100.0, sum(r["total"] for r in ag), 1)
        self.assertTrue(b["customers"] and b["einvoice"])
        self.assertEqual(b["last_day"], day)
        early = board.board(c, day[:8] + "01", day[:8] + "01T09:00:00")    # first day: small target
        self.assertLess(early["total"]["target"], b["total"]["target"])


class WarehouseBoard(unittest.TestCase):
    def test_stock_values_movements_and_panels(self):
        from mm import board
        c = system()
        day = c.execute("SELECT MAX(budat) FROM mat_doc").fetchone()[0]
        b = board.board(c, day, day + "T18:00:00")
        expect = 0
        for q in c.execute("SELECT q.qty, q.werks, v.vprsv, v.verpr, v.stprs, v.peinh FROM quant q JOIN sloc s ON "
                           "s.werks=q.werks AND s.lgort=q.lgort LEFT JOIN valuation v ON v.matnr=q.matnr AND "
                           "v.bwkey=q.werks WHERE q.qty<>0"):
            if q["vprsv"]:
                expect += value_of(q["qty"], q["stprs"] if q["vprsv"] == "S" else q["verpr"], q["peinh"] or 1)
        self.assertEqual(b["total"]["value"], expect)                           # stock value = quants x price
        docs = c.execute("SELECT COUNT(DISTINCT i.mblnr) FROM mat_doc_item i JOIN mat_doc h ON h.mblnr=i.mblnr "
                         "AND h.mjahr=i.mjahr WHERE h.budat=?", (day,)).fetchone()[0]
        moves = b["total"]["gr"] + b["total"]["gi"] + b["total"]["transfer"]
        self.assertGreaterEqual(moves, docs)                                     # every document of the day counted
        self.assertTrue(any(r["below_safety"] for r in b["reorder"]))
        for r in b["reorder"]:
            self.assertTrue(r["stock"] < r["reorder"] or r["stock"] < r["safety"])
        self.assertEqual(b["inbound"]["late"], len(__import__("pur.followup", fromlist=["x"]).overdue(c, day)))
        for s in b["slow"]:
            self.assertTrue(not s["last_move"] or s["last_move"] < day)
        self.assertEqual(b["last_day"], day)


if __name__ == "__main__":
    unittest.main()
