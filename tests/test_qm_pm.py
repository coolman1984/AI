"""Quality management (inspection lot from the goods receipt, results, usage decision, complaints,
vendor quality) and plant maintenance (breakdown, spare parts, hours, completion with line
downtime, preventive plans, MTBF / MTTR)."""
import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fixture  # noqa: E402,F401
from mm import seed  # noqa: E402
from mm.db import connect  # noqa: E402
from mm.util import MMError  # noqa: E402

T = fixture.T
TODAY = T.isoformat()


def system():
    c = connect(":memory:")
    seed.seed(c)
    return c


def err(test, fn, no):
    with test.assertRaises(MMError) as x:
        fn()
    test.assertEqual(x.exception.msg_no, no, str(x.exception))


def stock(c, matnr, insmk, lgort="0001"):
    return c.execute("SELECT COALESCE(SUM(qty),0) FROM quant WHERE matnr=? AND werks='1000' AND lgort=? AND insmk=?",
                     (matnr, lgort, insmk)).fetchone()[0]


def receive(c, qty="100"):
    from mm.posting import post_goods_movement, propose_bin
    from pur import po
    lifnr = c.execute("SELECT lifnr FROM info_record WHERE matnr='RM-1005'").fetchone()[0]
    e = po.create_po(c, {"lifnr": lifnr, "bedat": TODAY, "items": [
        {"matnr": "RM-1005", "menge": qty, "netpr": "85", "lgort": "0001", "eindt": TODAY}]}, "T")
    po.release_all(c, e, "T")
    return post_goods_movement(c, {"budat": TODAY}, [{"bwart": "101", "ebeln": e, "ebelp": 10, "qty": qty,
                                                      "lgpla": propose_bin(c, "RM-1005", "1000", "0001")["lgpla"]}], "T")


class Quality(unittest.TestCase):
    def test_goods_receipt_lot_results_and_usage_decision(self):
        from mm.posting import cancel_document, post_goods_movement
        from qm import quality as qm
        c = system()
        q0, b0 = stock(c, "RM-1005", "Q"), stock(c, "RM-1005", "B")
        gr = receive(c, "100")
        lot = gr["lots"][0]                                             # QM-active material -> lot
        self.assertEqual(stock(c, "RM-1005", "Q") - q0, 100000)         # in inspection stock, not usable
        err(self, lambda: post_goods_movement(c, {"budat": TODAY}, [{"bwart": "321", "matnr": "RM-1005", "werks": "1000",
                                                                     "lgort": "0001", "qty": "100"}], "T"), "910")
        err(self, lambda: qm.usage_decision(c, lot, {"qty_ok": "100"}, "T"), "905")     # results first
        r = qm.record(c, lot, {"10": "4.3", "20": "400", "30": "OK", "40": "OK"}, "T")
        self.assertEqual(r["rejected"], 1)                               # thickness above 4.2
        err(self, lambda: qm.record(c, lot, {"30": "maybe"}, "T"), "904")
        err(self, lambda: qm.usage_decision(c, lot, {"qty_ok": "100"}, "T"), "909")      # out of tolerance
        err(self, lambda: qm.usage_decision(c, lot, {"qty_ok": "90", "qty_rej": "5", "defect": "DIM"}, "T"), "906")
        err(self, lambda: qm.usage_decision(c, lot, {"qty_ok": "90", "qty_rej": "10"}, "T"), "907")
        u0 = stock(c, "RM-1005", "U")
        res = qm.usage_decision(c, lot, {"qty_ok": "90", "qty_rej": "10", "defect": "DIM", "override": "sorted 100 %"}, "T")
        self.assertEqual(stock(c, "RM-1005", "U") - u0, 90000)
        self.assertEqual(stock(c, "RM-1005", "B") - b0, 10000)
        self.assertEqual(stock(c, "RM-1005", "Q"), q0)
        L = qm.lot(c, lot)
        self.assertEqual((L["status"], L["ud_code"]), ("UD", "P"))
        n = c.execute("SELECT * FROM qm_notif WHERE prueflos=?", (lot,)).fetchone()
        self.assertEqual((n["qmart"], n["qty"], n["defect"], n["qmnum"]), ("Q2", 10000, "DIM", res["qmnum"]))
        err(self, lambda: qm.usage_decision(c, lot, {"qty_ok": "100"}, "T"), "902")       # closed
        err(self, lambda: cancel_document(c, gr["mblnr"], gr["mjahr"], TODAY, "T"), "911")
        v = {r["lifnr"]: r for r in qm.vendor_quality(c, "2000-01-01", TODAY)}[n["lifnr"]]
        self.assertGreater(v["ppm"], 0)
        self.assertIn(v["grade"], ("A", "B", "C"))

    def test_reversal_cancels_lot_manual_lot_and_corrective_action(self):
        from mm.posting import cancel_document
        from qm import quality as qm
        c = system()
        gr = receive(c, "40")
        cancel_document(c, gr["mblnr"], gr["mjahr"], TODAY, "T")
        self.assertEqual(qm.lot(c, gr["lots"][0])["status"], "CANCELLED")
        u0 = stock(c, "RM-1001", "U")
        m = qm.create_lot(c, {"matnr": "RM-1001", "lgort": "0001", "qty": "5", "datum": TODAY}, "T")
        self.assertEqual(u0 - stock(c, "RM-1001", "U"), 5000)                       # 322 to inspection
        err(self, lambda: qm.record(c, m["prueflos"], {"10": "1"}, "T"), "903")     # no plan for RM-1001
        qm.usage_decision(c, m["prueflos"], {"qty_ok": "5"}, "T")
        self.assertEqual(stock(c, "RM-1001", "U"), u0)
        err(self, lambda: qm.create_notification(c, {"qmart": "Q2", "text": "x"}, "T"), "923")
        no = qm.create_notification(c, {"qmart": "Q3", "text": "Scratches", "defect": "SURF", "qty": "2"}, "T")["qmnum"]
        err(self, lambda: qm.update_notification(c, no, {"cause": "Tool worn", "close": True}, "T"), "927")
        qm.update_notification(c, no, {"cause": "Tool worn", "action": "Tool change every 500 parts", "close": True}, "T")
        self.assertEqual(c.execute("SELECT status FROM qm_notif WHERE qmnum=?", (no,)).fetchone()[0], "CLOSED")
        k = qm.cockpit(c, "2000-01-01", TODAY)
        self.assertEqual(k["open_lots"], len(qm.lots(c, "open")))
        self.assertTrue(any(p["code"] == "DMG" for p in k["pareto"]))                 # demo rejection


class Maintenance(unittest.TestCase):
    def test_breakdown_parts_hours_completion_and_line_downtime(self):
        from qm import maintenance as pm
        c = system()
        err(self, lambda: pm.save_equipment(c, {"equnr": "X1", "eqktx": "x", "arbpl": "NOPE"}, "T"), "904")
        pm.save_equipment(c, {"equnr": "LAS-01", "eqktx": "Laser cutter", "arbpl": "WC-MACH", "crit": "A"}, "T")
        start = datetime.datetime.combine(T, datetime.time(8, 0)) - datetime.timedelta(days=1)
        err(self, lambda: pm.create_notification(c, {"qmart": "M2", "equnr": "LAS-01", "text": "stopped",
                                                     "start": "yesterday"}, "T"), "901")
        n = pm.create_notification(c, {"qmart": "M2", "equnr": "LAS-01", "text": "Laser source failure",
                                       "start": start.strftime("%Y-%m-%d %H:%M")}, "T")
        a = n["aufnr"]                                                    # breakdown -> order at once
        sp0 = stock(c, "SP-4001", "U", "0004")
        p = pm.issue_parts(c, a, [{"matnr": "SP-4001", "qty": "2", "lgort": "0004"}], "T", TODAY)
        self.assertEqual(sp0 - stock(c, "SP-4001", "U", "0004"), 2000)
        mi = c.execute("SELECT * FROM mat_doc_item WHERE mblnr=?", (p["mblnr"],)).fetchone()
        self.assertEqual((mi["bwart"], mi["kostl"]), ("201", "4100"))     # cost center of the line
        self.assertTrue(mi["belnr"])                                      # FI document posted
        pm.confirm(c, a, {"minutes": "90", "datum": TODAY}, "T")
        o = c.execute("SELECT * FROM pm_order WHERE aufnr=?", (a,)).fetchone()
        self.assertEqual(o["labour"], 90 * pm.rate(c) // 60)
        self.assertEqual(o["parts"], p["value"])
        err(self, lambda: pm.complete(c, a, {}, "T"), "901")
        err(self, lambda: pm.complete(c, a, {"finish": (start - datetime.timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")},
                                      "T"), "911")
        loss0 = c.execute("SELECT COALESCE(SUM(minutes),0) FROM pp_loss WHERE arbpl='WC-MACH' AND reason='MACH'").fetchone()[0]
        pm.complete(c, a, {"finish": (start + datetime.timedelta(hours=2, minutes=30)).strftime("%Y-%m-%d %H:%M")}, "T")
        loss1 = c.execute("SELECT COALESCE(SUM(minutes),0) FROM pp_loss WHERE arbpl='WC-MACH' AND reason='MACH'").fetchone()[0]
        self.assertEqual(loss1 - loss0, 150)                              # downtime on the production line
        err(self, lambda: pm.confirm(c, a, {"minutes": "10"}, "T"), "909")
        rel = {r["equnr"]: r for r in pm.reliability(c, (T - datetime.timedelta(days=30)).isoformat(), TODAY)}["LAS-01"]
        self.assertEqual((rel["breakdowns"], rel["downtime"], rel["mttr"]), (1, 150, 150))
        self.assertLess(rel["availability"], 100)

    def test_preventive_plan_scheduling_and_next_due(self):
        from mm import util as clock
        from qm import maintenance as pm
        c = system()
        pm.save_equipment(c, {"equnr": "FAN-01", "eqktx": "Exhaust fan", "kostl": "4100"}, "T")
        w = pm.save_plan(c, {"equnr": "FAN-01", "text": "Clean filter", "interval_days": "14", "next_due": TODAY}, "T")["warpl"]
        made = [a for a in pm.schedule(c, "T")["orders"]
                if c.execute("SELECT warpl FROM pm_order WHERE aufnr=?", (a,)).fetchone()[0] == w]
        self.assertEqual(len(made), 1)
        self.assertEqual(pm.schedule(c, "T")["orders"], [])               # not twice
        pm.complete(c, made[0], {}, "T")
        p = c.execute("SELECT * FROM pm_plan WHERE warpl=?", (w,)).fetchone()
        self.assertEqual(p["next_due"], (clock.today() + datetime.timedelta(days=14)).isoformat())
        k = pm.cockpit(c, (T - datetime.timedelta(days=30)).isoformat(), TODAY)
        self.assertGreaterEqual(k["breakdowns"], 1)                        # demo breakdown of CNC-01
        self.assertIsNotNone(k["planned_share"])


if __name__ == "__main__":
    unittest.main()
