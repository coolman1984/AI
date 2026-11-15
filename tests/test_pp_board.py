"""Production status board (ZPP_BOARD) with the daily line plan (ZPP_LINEPLAN) and the
downtime log (ZPP_LOSS)."""
import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fixture  # noqa: E402,F401
from mm import seed  # noqa: E402
from mm.db import connect  # noqa: E402
from mm.util import MMError  # noqa: E402

_P = {}


def d(day):
    y, m = (int(x) for x in _P["month"].split("-"))
    return datetime.date(y, m, day).isoformat()


def system():
    c = connect(":memory:")
    seed.seed(c)
    _P["month"] = c.execute("SELECT value FROM settings WHERE key='pp_sample'").fetchone()[0]   # PP demo month
    return c


def err(test, fn, no):
    with test.assertRaises(MMError) as x:
        fn()
    test.assertEqual(x.exception.msg_no, no, str(x.exception))


def line(b, arbpl):
    return [r for g in b["groups"] for r in g["lines"] if r["arbpl"] == arbpl][0]


class Board(unittest.TestCase):
    def test_lines_grouped_with_plan_target_production_and_loss(self):
        from pp import board
        c = system()
        b = board.board(c, d(7), "%sT18:00:00" % d(7))                    # day over: target = plan
        self.assertEqual({g["area"] for g in b["groups"]}, {"MACHINING", "ASSEMBLY", "SERVICE & REPAIR"})
        a = line(b, "WC-ASSY")
        self.assertEqual((a["plan"], a["target"], a["prod"]), (32000, 32000, 29000))   # 19 + 10 confirmed
        self.assertEqual(a["diff"], -3000)
        self.assertEqual(a["status"], "behind")
        self.assertEqual(a["loss_min"], 25)
        m = line(b, "WC-MACH")
        self.assertEqual((m["prod"], m["loss_min"], m["loss_units"]), (0, 120, 3000))  # 2 h x 1.25 / h = 2.5 -> 3 units
        t = b["total"]
        self.assertEqual(t["prod"], sum(r["prod"] for g in b["groups"] for r in g["lines"]))
        self.assertEqual(t["lines"], 3)
        q = line(board.board(c, d(6), "%sT18:00:00" % d(6)), "WC-ASSY")
        self.assertAlmostEqual(q["defect"], 9.52, 2)                          # 2 scrap / 21
        self.assertTrue(b["attendance"] and b["shipping"])
        self.assertEqual(len(b["shipping"]), 2)                               # last week and this week

    def test_target_follows_the_clock_during_the_shift(self):
        from pp import board
        c = system()
        noon = board.board(c, d(7), "%sT12:00:00" % d(7))                   # 4 of 8 hours passed
        self.assertEqual(line(noon, "WC-ASSY")["target"], 16000)
        odd = line(board.board(c, d(7), "%sT09:20:00" % d(7)), "WC-ASSY")   # 32 x 80/480 = 5.33
        self.assertEqual(odd["target"], 5000)                                 # whole units only
        self.assertEqual(odd["loss_units"] % 1000, 0)
        self.assertEqual(odd["uph_result"] % 1000, 0)
        early = board.board(c, d(7), "%sT07:00:00" % d(7))                  # before the shift
        self.assertEqual(line(early, "WC-ASSY")["target"], 0)
        self.assertIsNone(line(early, "WC-ASSY")["ach"])


class Inputs(unittest.TestCase):
    def test_line_plan_copy_and_downtime_checks(self):
        from pp import board
        c = system()
        board.save_plan(c, {"datum": d(10), "arbpl": "WC-ASSY", "aufnr": "1000004", "plan": "40", "hours": "8"}, "P")
        p = [x for x in board.plans(c, d(10)) if x["arbpl"] == "WC-ASSY"][0]
        self.assertEqual((p["matnr"], p["plan"], p["uph"]), ("FG-3003", 40000, 5000))   # UPH = plan / hours
        err(self, lambda: board.save_plan(c, {"datum": d(10), "arbpl": "NOPE", "plan": "1"}, "P"), "951")
        err(self, lambda: board.save_plan(c, {"datum": d(10), "arbpl": "WC-ASSY", "plan": "1",
                                              "start": "25:00"}, "P"), "952")
        err(self, lambda: board.save_plan(c, {"datum": d(10), "arbpl": "WC-ASSY", "aufnr": "999"}, "P"), "953")
        r = board.copy_plans(c, d(7), d(11), "P")
        self.assertIn("3 line plan", r["message"])
        err(self, lambda: board.copy_plans(c, d(20), d(21), "P"), "955")
        err(self, lambda: board.add_loss(c, {"datum": d(10), "arbpl": "WC-ASSY", "minutes": "10",
                                             "reason": "LUNCH"}, "P"), "956")
        board.add_loss(c, {"datum": d(10), "arbpl": "WC-ASSY", "minutes": "30", "reason": "MACH"}, "P")
        self.assertEqual(board.losses(c, d(10))[0]["reason_text"], "Machine breakdown")


if __name__ == "__main__":
    unittest.main()
