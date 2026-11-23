"""GMES (ZMES_*): serial numbers per released order, route enforcement (no skipping, no double booking),
operator certification from the HR skills matrix, the repair loop with a limit, genealogy forward /
backward, confirmation to the production order, hourly output, FPY / RTY / DPU / DPMO, andon response
times, SPC limits, capability and run rules."""
import datetime
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


def new_order(c, qty="4", release=True):
    from pp import order
    a = order.create(c, {"auart": "PP01", "matnr": "FG-3003", "gamng": qty, "gstrp": clock.today().isoformat(), "lgort": "0003"}, "T")
    if release:
        order.release(c, a, "T", clock.today().isoformat())
    return a


def at(h, m=0, k=0):
    return datetime.datetime.combine(clock.today() - datetime.timedelta(days=k), datetime.time(h, m))


class Execution(unittest.TestCase):
    def test_route_enforcement_certification_repair_loop(self):
        from mes import track as T
        c = system()
        err(self, lambda: T.release_units(c, new_order(c, release=False), 1, "T"), "908")
        a = new_order(c)
        err(self, lambda: T.release_units(c, a, 5, "T"), "910")                       # order is for 4 units
        s1, s2, s3, s4 = T.release_units(c, a, 4, "T")["serials"]
        err(self, lambda: T.book(c, s1, "ASSY-20", "OK", "10013", "T", at=at(8)), "919")   # skipping operation 0010
        err(self, lambda: T.book(c, s1, "ASSY-10", "OK", "10013", "T", at=at(8)), "913")   # 10013 not certified for ASSY
        err(self, lambda: T.book(c, s1, "MACH-10", "OK", "10006", "T", at=at(8)), "913")   # expired CNC certificate
        err(self, lambda: T.book(c, s1, "ASSY-10", "NG", "10008", "T", at=at(8)), "921")   # NG needs a defect code
        T.book(c, s1, "ASSY-10", "OK", "10008", "T", at=at(8, 5), components=[{"matnr": "SF-3101", "lot": "LOT-A1"},
                                                                              {"matnr": "TR-5001", "lot": "LOT-T7"}])
        err(self, lambda: T.book(c, s1, "ASSY-10", "OK", "10008", "T", at=at(8, 6)), "919")  # double booking
        r = T.book(c, s1, "ASSY-20", "NG", "10014", "T", defect="FUNC", at=at(9))
        self.assertEqual(r["status"], "REPAIR")
        err(self, lambda: T.book(c, s1, "ASSY-20", "OK", "10014", "T", at=at(9, 1)), "918")  # must go to repair first
        err(self, lambda: T.book(c, s2, "ASSY-RP", "REPAIRED", "10007", "T", at=at(9, 2)), "915")
        for i in range(3):
            T.book(c, s1, "ASSY-RP", "REPAIRED", "10007", "T", at=at(9, 10 + i * 10))
            if i < 2:
                T.book(c, s1, "ASSY-20", "NG", "10014", "T", defect="FUNC", at=at(9, 15 + i * 10))
        self.assertEqual(T.unit(c, s1)["repairs"], 3)
        T.book(c, s1, "ASSY-20", "NG", "10014", "T", defect="ELEC", at=at(10))
        err(self, lambda: T.book(c, s1, "ASSY-RP", "REPAIRED", "10007", "T", at=at(10, 5)), "917")  # max 3 repairs
        self.assertEqual(T.book(c, s1, "ASSY-RP", "SCRAP", "10007", "T", at=at(10, 6))["status"], "SCRAP")
        err(self, lambda: T.book(c, s1, "ASSY-20", "OK", "10014", "T", at=at(10, 7)), "914")
        for i, sn in enumerate((s2, s3)):
            T.book(c, sn, "ASSY-10", "OK", "10009", "T", at=at(11, i), components=[{"matnr": "SF-3101", "lot": "LOT-A1"}])
            self.assertEqual(T.book(c, sn, "ASSY-20", "OK", "10013", "T", at=at(12, i))["status"], "DONE")
        # genealogy: backward from a unit, forward from a lot
        b = T.trace(c, s2)
        self.assertEqual(b["direction"], "backward")
        self.assertEqual([e["result"] for e in b["unit"]["events"]], ["OK", "OK"])
        f = T.trace(c, "LOT-A1")
        self.assertEqual(sorted(u["serial"] for u in f["units"]), sorted([s1, s2, s3]))
        self.assertEqual(f["in_house"], 3)
        err(self, lambda: T.trace(c, "NOPE"), "928")
        # hand over to the production order (CO11N)
        r = T.confirm_to_order(c, a, "T")
        self.assertEqual((r["yield"], r["scrap"]), (2, 1))
        op = c.execute("SELECT lmnga, xmnga FROM pp_oper WHERE aufnr=? AND vornr='0020'", (a,)).fetchone()
        self.assertEqual((op["lmnga"], op["xmnga"]), (2000, 1000))
        err(self, lambda: T.confirm_to_order(c, a, "T"), "923")                       # nothing new to confirm
        self.assertEqual(T.unit(c, s4)["status"], "WIP")

    def test_reports_andon_and_spc(self):
        from hr import skills
        from mes import reports as R, track as T
        c = system()
        c.execute("DELETE FROM mes_event")
        c.execute("DELETE FROM mes_unit")
        c.commit()
        a = new_order(c, "4")
        sn = T.release_units(c, a, 4, "T")["serials"]
        c.execute("INSERT OR REPLACE INTO pp_lineplan (datum,arbpl,aufnr,matnr,plan,uph,man,start,hours,usnam,ts) VALUES "
                  "(?,?,?,?,?,?,?,?,?,?,?)", (at(8, 0, 1).date().isoformat(), "WC-ASSY", a, "FG-3003", 16000, 2000, 2, "08:00", 8, "T", ""))
        c.commit()
        for i, s in enumerate(sn):
            T.book(c, s, "ASSY-10", "OK", "10008", "T", cycle_sec=200, at=at(8, 10 * i, 1))
        T.book(c, sn[0], "ASSY-20", "NG", "10014", "T", defect="FUNC", cycle_sec=70, at=at(9, 0, 1))
        T.book(c, sn[0], "ASSY-RP", "REPAIRED", "10007", "T", at=at(9, 20, 1))
        T.book(c, sn[0], "ASSY-20", "OK", "10014", "T", cycle_sec=60, at=at(9, 30, 1))
        T.book(c, sn[1], "ASSY-20", "OK", "10013", "T", cycle_sec=60, at=at(9, 40, 1))
        T.book(c, sn[2], "ASSY-20", "OK", "10013", "T", cycle_sec=60, at=at(10, 5, 1))
        day = at(8, 0, 1).date().isoformat()
        q = R.quality(c, day, day)
        ops = {o["vornr"]: o for o in q["ops"]}
        self.assertEqual(ops["0010"]["fpy"], 100.0)
        self.assertAlmostEqual(ops["0020"]["fpy"], round(100 * 2 / 3, 2))           # 3 first tests, 2 passed
        self.assertAlmostEqual(q["rty"]["FG-3003"], round(100 * 1.0 * 2 / 3, 2))
        self.assertEqual(ops["0020"]["dpmo"], round(1e6 * 1 / (3 * 6)))              # 1 defect, 3 units, 6 opportunities
        self.assertEqual(q["pareto"][0]["code"], "FUNC")
        h = next(l for l in R.hourly(c, day)["lines"] if l["arbpl"] == "WC-ASSY")
        self.assertEqual(h["actual"], 3)                                             # passed the last operation of the line
        self.assertEqual({x["hour"]: x["actual"] for x in h["hours"] if x["actual"]}, {"09:00": 2, "10:00": 1})
        self.assertEqual(h["plan"], 16.0)
        w = R.wip(c)
        self.assertEqual(w["total"], 1)
        self.assertEqual(w["by_step"][0]["step"], "0020")
        cy = {s["station"]: s for s in R.cycle(c, day, day)["stations"]}
        self.assertEqual(cy["ASSY-10"]["efficiency"], 90.0)                           # 180 standard / 200 actual
        # andon: response and resolution times
        aid = T.andon_open(c, "WC-ASSY", "MAT", "Screws missing", "T", at=at(9, 0, 1))["id"]
        err(self, lambda: T.andon_step(c, aid, "close", "T", "", at=at(9, 5, 1)), "932")
        T.andon_step(c, aid, "ack", "T", at=at(9, 4, 1))
        err(self, lambda: T.andon_step(c, aid, "ack", "T", at=at(9, 5, 1)), "931")
        T.andon_step(c, aid, "close", "T", "Brought from store", at=at(9, 30, 1))
        k = next(x for x in T.andon_board(c, day, day)["by_kind"] if x["kind"] == "MAT")
        self.assertEqual((k["avg_respond_min"], k["avg_resolve_min"]), (4.0, 30.0))
        err(self, lambda: T.andon_open(c, "WC-ASSY", "XX", "", "T"), "929")
        # SPC: limits from the subgroups, capability and a shift signal
        err(self, lambda: T.save_char(c, {"code": "W", "text": "Width", "lsl": "5", "usl": "4"}), "935")
        T.save_char(c, {"code": "W", "text": "Width", "lsl": "9", "usl": "11", "n": "4"})
        vals = [10.0, 10.1, 9.9, 10.0] * 6 + [10.3, 10.4, 10.3, 10.4] * 8            # 6 centred subgroups, then 8 shifted
        for i, v in enumerate(vals):
            T.measure(c, "W", v, "T", at=at(8, 0) + datetime.timedelta(minutes=i))
        s = T.spc(c, "W")
        self.assertEqual(len(s["groups"]), 14)
        rb = s["rbar"]
        self.assertAlmostEqual(s["ucl"], round(s["xbarbar"] + 0.729 * rb, 4), places=3)
        self.assertTrue(any(r["rule"] == 2 for r in s["rules"]))
        self.assertFalse(s["in_control"])
        self.assertTrue(T.measure(c, "W", 12, "T")["out_of_spec"])
        # skills matrix
        m = skills.matrix(c)
        self.assertGreaterEqual(m["expired"], 1)
        self.assertGreaterEqual(m["expiring"], 1)
        err(self, lambda: skills.qualify(c, "99999", "ASSY", 1), "902")
        err(self, lambda: skills.qualify(c, "10008", "NOPE", 1), "903")
        err(self, lambda: skills.qualify(c, "10008", "ASSY", 5), "089")


if __name__ == "__main__":
    unittest.main()
