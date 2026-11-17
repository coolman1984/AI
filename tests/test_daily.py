"""Daily meeting boards next to ZPP_BOARD: in-house production, production pending, OQC pending,
production defect, material defect, material loss and pending scrap - every figure equals the
underlying documents."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fixture  # noqa: E402,F401
from mm import seed  # noqa: E402
from mm.db import connect  # noqa: E402

T = fixture.T
TODAY = T.isoformat()
_C = {}


def system():
    if "c" not in _C:
        c = connect(":memory:")
        seed.seed(c)
        _C["c"] = c
    return _C["c"]


class DailyMeeting(unittest.TestCase):
    def test_production_boards_equal_the_documents(self):
        from pp import daily
        c = system()
        day = daily.last_day(c, TODAY)
        mon = day[:8] + "01"
        b = daily.inhouse(c, day)
        conf = c.execute("SELECT COALESCE(SUM(lmnga),0), COALESCE(SUM(xmnga),0) FROM confirmation WHERE stokz=0 AND "
                         "aueru=1 AND budat BETWEEN ? AND ?", (mon, day)).fetchone()
        self.assertEqual(sum(g["total"]["month"] for g in b["groups"]), conf[0])
        self.assertEqual(sum(g["total"]["scrap"] for g in b["groups"]), conf[1])
        for g in b["groups"]:
            for r in g["lines"]:
                if r["plan"]:
                    self.assertEqual(r["diff"], r["today"] - r["plan"])
        p = daily.pending(c, TODAY)
        n = c.execute("SELECT COUNT(*) FROM orders WHERE stat IN ('CRTD','REL','DLV') AND gamng>wemng AND "
                      "auart<>'ZINT'").fetchone()[0]
        self.assertEqual(len(p["rows"]), n)
        self.assertEqual(p["late"] + p["today"] + p["next"], n)
        self.assertEqual(p["pending_qty"], sum(r["planned"] - r["done"] for r in p["rows"]))
        d = daily.pdefect(c, day)
        scrap = c.execute("SELECT COALESCE(SUM(xmnga),0) FROM confirmation WHERE stokz=0 AND budat BETWEEN ? AND ?",
                          (mon, day)).fetchone()[0]
        self.assertEqual(d["month"], scrap)
        self.assertEqual(sum(x["qty"] for x in d["pareto"]), scrap)

    def test_quality_loss_and_scrap_boards(self):
        from mm.posting import post_goods_movement
        from pp import daily
        c = system()
        o = daily.oqc(c, TODAY)
        self.assertTrue(any(r["matnr"] == "FG-3001" for r in o["stock"]))            # demo OQC lot
        self.assertTrue(o["lots"])
        m = daily.mdefect(c, TODAY)
        self.assertTrue(m["complaints"])                                            # glass vendor complaint
        s = daily.pending_scrap(c, TODAY)
        b = c.execute("SELECT COALESCE(SUM(qty),0) FROM quant WHERE insmk='B'").fetchone()[0]
        self.assertEqual(s["qty"], b)
        self.assertEqual(sum(s["aging"].values()), s["value"])
        l0 = daily.mloss(c, TODAY)
        r = c.execute("SELECT r.aufnr, r.matnr, r.lgort FROM pp_resb r JOIN orders o ON o.aufnr=r.aufnr JOIN confirmation f "
                      "ON f.aufnr=o.aufnr WHERE f.stokz=0 AND f.budat>=? AND o.stat IN ('REL','DLV') AND r.enmng>0 LIMIT 1",
                      (TODAY[:8] + "01",)).fetchone()
        if r:                                                                       # extra issue = loss
            post_goods_movement(c, {"budat": TODAY}, [{"bwart": "261", "aufnr": r["aufnr"], "matnr": r["matnr"],
                                                       "werks": "1000", "lgort": r["lgort"], "qty": "1"}], "T")
            l1 = daily.mloss(c, TODAY)
            self.assertGreater(l1["usage_value"], l0["usage_value"])
        self.assertEqual(l0["total"], l0["usage_value"] + max(l0["inv_value"], 0) + l0["scrap_value"])


if __name__ == "__main__":
    unittest.main()
