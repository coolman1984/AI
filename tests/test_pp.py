"""Production planning tests on the full demo (current month)."""
import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mm import seed  # noqa: E402
from mm.db import connect  # noqa: E402
from mm.posting import post_goods_movement  # noqa: E402
from mm.util import MMError  # noqa: E402
from pp import master, order, planning, service, subcon  # noqa: E402

_DB = {}
T = datetime.date.today()
TODAY = T.isoformat()


def demo():
    if "c" not in _DB:
        c = connect(":memory:")
        seed.seed(c)
        _DB["c"] = c
    return _DB["c"]


def err(test, fn, no):
    with test.assertRaises(MMError) as x:
        fn()
    test.assertEqual(x.exception.msg_no, no, str(x.exception))


def order_of(c, matnr, auart="PP01", stat=None):
    sql = "SELECT * FROM orders WHERE matnr=? AND auart=? AND erdat>=?"
    args = [matnr, auart, T.replace(day=1).isoformat()]
    if stat:
        sql += " AND stat=?"
        args.append(stat)
    return c.execute(sql + " ORDER BY aufnr", args).fetchall()


class MasterData(unittest.TestCase):
    def test_multilevel_explosion_and_low_level_codes(self):
        c = demo()
        ex = master.explode(c, "FG-3003", "1000", "1")
        steel = sum(x["menge"] for x in ex if x["idnrk"] == "RM-1001")
        self.assertEqual(steel, 25200 + 3000)       # 24 kg + 5 % scrap, 2 doors x 1.5 kg
        llc = master.low_level_codes(c)
        self.assertEqual((llc["FG-3003"], llc["SF-3101"], llc["RM-1005"]), (0, 1, 2))

    def test_bom_recursion_and_routing_rules(self):
        c = demo()
        err(self, lambda: master.save_bom(c, "SF-3101", "1000", "1", [dict(idnrk="FG-3003", menge="1")]),
            "012")
        err(self, lambda: master.save_routing(c, "SF-3101", "1000", "1", [
            dict(vornr="0010", arbpl="WC-MACH", steus="PP03", vgw="1"),
            dict(vornr="0020", arbpl="WC-MACH", vgw="1")]), "005")   # auto GR only last op
        err(self, lambda: master.save_routing(c, "SF-3101", "1000", "1", [
            dict(vornr="0010", steus="PP02", ltxa1="x")]), "006")    # external needs vendor

    def test_cost_estimate_contains_external_and_subcontracting(self):
        c = demo()
        kinds = {r["kstar"]: r["wert"] for r in c.execute(
            "SELECT i.kstar, i.wert FROM cost_estimate e JOIN cost_estimate_item i ON i.id=e.id "
            "WHERE e.matnr='SF-3102' ORDER BY e.id DESC")}
        self.assertEqual(kinds["417000"], 550000)          # fee 55.00 x lot 100
        ext = c.execute("SELECT i.wert FROM cost_estimate e JOIN cost_estimate_item i ON i.id=e.id "
                        "WHERE e.matnr='SF-3101' AND i.kstar='417000'").fetchone()[0]
        self.assertEqual(ext, 1400000)                       # coating 140.00 x 100

    def test_production_version_required(self):
        c = demo()
        err(self, lambda: order.create(c, {"matnr": "FG-3003", "gamng": "600", "gstrp": TODAY}, "T"),
            "004")                                         # lot size above 500


class Planning(unittest.TestCase):
    def test_sop_disaggregation_to_pirs(self):
        c = demo()
        plan = planning.sop_get(c, "PG-CAB")
        p = {r["matnr"]: r["plnmg"] for r in planning.pirs(c) if r["month"] == plan[1]["month"]}
        self.assertEqual(sum(p.values()), plan[1]["production"])
        self.assertEqual(p["FG-3003"], (plan[1]["production"] * 25 // 100 + 500) // 1000 * 1000)

    def test_mrp_explodes_to_semi_finished_and_subcontracting(self):
        c = demo()
        fg = [p["gsmng"] for p in planning.planned_orders(c, "FG-3003", open_only=False)]
        sf = [p["gsmng"] for p in planning.planned_orders(c, "SF-3102", open_only=False)]
        self.assertEqual(sorted(sf), sorted(2 * q for q in fg))   # 2 doors per pantry unit
        self.assertTrue(all(p["paart"] == "NB" for p in planning.planned_orders(c, "SF-3102")))
        self.assertTrue(c.execute("SELECT 1 FROM pp_mrp_msg WHERE ausk='06'").fetchone())

    def test_stock_requirements_list_balances(self):
        d = planning.stock_requirements(demo(), "FG-3003")
        self.assertEqual(d["lines"][-1]["avail"], d["material"]["final_avail"])
        self.assertGreaterEqual(d["material"]["final_avail"], 0)


class Execution(unittest.TestCase):
    def test_subcontracting_value(self):
        c = demo()
        gr = c.execute("SELECT * FROM mat_doc_item WHERE matnr='SF-3102' AND bwart='101'").fetchone()
        comps = c.execute("SELECT SUM(dmbtr) FROM mat_doc_item WHERE mblnr=? AND bwart='543'",
                          (gr["mblnr"],)).fetchone()[0]
        fee = gr["menge"] * 5500 // 1000
        self.assertEqual(gr["dmbtr"], fee + comps)        # product value = fee + components
        self.assertEqual(subcon.vendor_stock(c, c.execute(
            "SELECT lifnr FROM po_item i JOIN po_header USING (ebeln) WHERE pstyp='L'"
        ).fetchone()[0]), 0)

    def test_external_operation_cost_on_order(self):
        c = demo()
        o = order_of(c, "SF-3101")[0]
        ext = c.execute("SELECT SUM(wtg) FROM co_item WHERE objnr=? AND kstar='417000'",
                        ("OR" + o["aufnr"],)).fetchone()[0]
        self.assertEqual(ext, o["gamng"] * 14000 // 1000)  # 140.00 per unit

    def test_backflush_scrap_and_auto_gr(self):
        c = demo()
        o = order_of(c, "FG-3003", stat="TECO")[0]
        self.assertEqual((o["wemng"], o["iasmg"]), (o["gamng"] - 2000, 2000))
        h = c.execute("SELECT SUM(menge) FROM mat_doc_item WHERE aufnr=? AND matnr='TR-5001' AND "
                      "bwart='261'", (o["aufnr"],)).fetchone()[0]
        self.assertEqual(h, 2 * o["gamng"])                 # handles backflushed for yield + scrap
        v = c.execute("SELECT SUM(qty_var) FROM order_variance WHERE aufnr=?", (o["aufnr"],)).fetchone()[0]
        self.assertGreater(v, 0)                           # scrap -> quantity variance

    def test_missing_parts_and_wip(self):
        c = demo()
        o = c.execute("SELECT * FROM orders WHERE sysst LIKE '%MSPT%' AND stat='REL'").fetchone()
        w = c.execute("SELECT wip FROM pp_wip WHERE aufnr=?", (o["aufnr"],)).fetchone()[0]
        bal = c.execute("SELECT SUM(wtg) FROM co_item WHERE objnr=?", ("OR" + o["aufnr"],)).fetchone()[0]
        self.assertEqual(w, bal)

    def test_confirmation_rules(self):
        c = demo()
        o = order_of(c, "SF-3101")[0]
        err(self, lambda: order.confirm(c, o["aufnr"], "0020", "1", budat=TODAY), "102")  # external
        err(self, lambda: order.confirm(c, o["aufnr"], "0010", "1", budat=TODAY), "103")  # final

    def test_rework_and_refurbishment_settlement(self):
        c = demo()
        rw = order_of(c, "FG-3001", "ZP03")[0]
        st = c.execute("SELECT SUM(wtg) FROM co_item WHERE objnr='KS4300' AND parob=?",
                       ("OR" + rw["aufnr"],)).fetchone()[0]
        lab = c.execute("SELECT SUM(wtg) FROM co_item WHERE objnr=? AND kstar='616000'",
                        ("OR" + rw["aufnr"],)).fetchone()[0]
        self.assertGreaterEqual(st, lab)                   # rework labour (+overhead) to QC
        ref = order_of(c, "SP-4001", "ZREF")[0]
        self.assertEqual(c.execute("SELECT COALESCE(SUM(wtg),0) FROM co_item WHERE objnr=?",
                                   ("OR" + ref["aufnr"],)).fetchone()[0], 0)
        doc = c.execute("SELECT i.dmbtr FROM acc_doc_item i JOIN acc_doc h USING (belnr, gjahr) WHERE "
                        "h.awkey=? AND i.hkont='303000'", ("KO88" + ref["aufnr"],)).fetchone()
        self.assertGreater(doc["dmbtr"], 0)                # refurbishment cost into stock

    def test_cancel_confirmation(self):
        c = demo()
        a = order.create(c, {"matnr": "FG-3003", "gamng": "5", "gstrp": TODAY, "lgort": "0003"}, "T")
        order.release(c, a, "T", TODAY)
        r = order.confirm(c, a, "0010", "2", budat=TODAY, user="T")
        order.cancel_confirmation(c, r["rueck"], "T", TODAY)
        op = c.execute("SELECT * FROM pp_oper WHERE aufnr=? AND vornr='0010'", (a,)).fetchone()
        self.assertEqual((op["lmnga"], op["ism"], op["status"]), (0, 0, "REL"))
        self.assertEqual(c.execute("SELECT COALESCE(SUM(wtg),0) FROM co_item WHERE objnr=?",
                                   ("OR" + a,)).fetchone()[0], 0)


class ServiceParts(unittest.TestCase):
    def test_forecast_and_safety_stock(self):
        c = demo()
        r = service.forecast(c, "SP-4003", model="D", service=99, today=TODAY)
        self.assertEqual(len(r["forecast"]), 6)
        self.assertGreaterEqual(r["reorder_point"], r["safety_stock"])
        err(self, lambda: service.forecast(c, "SP-4003", service=93), "002")

    def test_reservation_partial_issue(self):
        r = demo().execute("SELECT bdmng, enmng FROM pp_resb WHERE kostl='4200'").fetchone()
        self.assertEqual((r["bdmng"], r["enmng"]), (20000, 15000))


class Books(unittest.TestCase):
    def test_balanced_and_reconciled(self):
        from co.reports import reconcile
        from fi.reports import statements
        self.assertTrue(statements(demo(), T.year, T.month, T.month)["balanced"])
        self.assertTrue(reconcile(demo(), T.year, T.month, T.month)["ok"])


if __name__ == "__main__":
    unittest.main()
