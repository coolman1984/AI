"""Ceramic tiles (on the ceramic factory demo): sorting into grade / shade / caliber lots, one shade +
caliber per delivery item, lab tests by ISO 13006 group, first-choice rate, gas and power per m2,
and the lines in the morning briefing."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fixture  # noqa: E402,F401
from mm.db import connect  # noqa: E402
from mm.util import MMError  # noqa: E402

_C = {}


def factory():
    if "c" not in _C:
        from mm import demo_ceramic
        c = connect(":memory:")
        demo_ceramic.load(c)
        _C["c"] = c
    return _C["c"]


def fresh():
    from mm import demo_ceramic
    c = connect(":memory:")
    demo_ceramic.load(c)
    return c


def _new_order(c, matnr="FG-F60", qty="2000"):
    from pp import order
    a = order.create(c, {"auart": "PP01", "matnr": matnr, "gamng": qty, "lgort": "0003"}, "T")
    order.release(c, a, "T")
    return a


class Sorting(unittest.TestCase):
    def test_sorting_posts_stock_and_creates_lots(self):
        from tile import lots
        c = fresh()
        a = _new_order(c)
        before = {m: c.execute("SELECT COALESCE(SUM(qty),0) FROM quant WHERE matnr=?", (m,)).fetchone()[0]
                  for m in ("FG-F60", "FG-F60B")}
        r = lots.sort(c, a, dict(lots=[dict(shade="Z1", caliber="9.7", qty="1500"), dict(shade="Z2", caliber="9.7", qty="200")],
                                 grade2=[dict(shade="Z1", caliber="9.7", qty="150")], grade3="100", broken="50",
                                 defects={"GLZ": "200", "CHP": "100"}), "T")
        self.assertEqual(len(r["lots"]), 3)
        self.assertEqual(r["first_choice"], 85.0)
        after = {m: c.execute("SELECT COALESCE(SUM(qty),0) FROM quant WHERE matnr=?", (m,)).fetchone()[0]
                 for m in ("FG-F60", "FG-F60B")}
        self.assertEqual(after["FG-F60"] - before["FG-F60"], 1700000)
        self.assertEqual(after["FG-F60B"] - before["FG-F60B"], 150000)
        self.assertTrue(all(x["difference"] == 0 for x in lots.reconcile(c)))

    def test_wrong_sorting_input_is_refused(self):
        from tile import lots
        c = factory()
        a = conn_order = c.execute("SELECT aufnr FROM orders WHERE matnr='FG-W36'").fetchone()[0]
        self.assertTrue(conn_order)
        with self.assertRaises(MMError):                     # wall tile has no grade 2 material
            lots.sort(c, a, dict(grade2=[dict(shade="B", caliber="1", qty="10")]), "T")
        with self.assertRaises(MMError):
            lots.sort(c, a, dict(lots=[dict(shade="", caliber="1", qty="10")]), "T")
        with self.assertRaises(MMError):
            lots.sort(c, a, dict(grade3="10", defects={"XXX": "5"}), "T")
        with self.assertRaises(MMError):
            lots.sort(c, a, dict(grade3="10", defects={"CRK": "50"}), "T")    # more defects than rejects
        with self.assertRaises(MMError):
            lots.sort(c, a, {}, "T")


class Deliveries(unittest.TestCase):
    def test_demo_deliveries_took_one_shade_per_item(self):
        c = factory()
        rows = c.execute("SELECT p.vbeln, p.posnr, COUNT(DISTINCT l.shade || '/' || l.caliber) n FROM tile_pick p "
                         "JOIN tile_lot l USING (lot) GROUP BY p.vbeln, p.posnr").fetchall()
        self.assertGreaterEqual(len(rows), 5)
        self.assertTrue(all(r["n"] == 1 for r in rows))

    def test_mixed_shades_are_refused_and_proposal_is_one_shade(self):
        from sd import delivery as dl, order as so
        from tile import lots
        c = fresh()
        v = so.create(c, dict(auart="OR", kunnr="C1003", bstnk="T-1", items=[dict(matnr="FG-F60", qty="8500")]), "T")["vbeln"]
        if c.execute("SELECT cmgst FROM sd_vbak WHERE vbeln=?", (v,)).fetchone()[0] == "B":
            so.release_credit(c, v, "CREDITMGR")
        dn = dl.create(c, v, "T", "2026-12-31")["vbeln"]
        two = c.execute("SELECT lot, shade, caliber FROM tile_lot WHERE matnr='FG-F60' AND status='OK' AND qty>issued "
                        "ORDER BY lot").fetchall()
        a, b = next((x, y) for x in two for y in two if (x["shade"], x["caliber"]) != (y["shade"], y["caliber"]))
        with self.assertRaises(MMError) as e:
            lots.assign(c, dn, 10, [dict(lot=a["lot"], qty="4000"), dict(lot=b["lot"], qty="4500")])
        self.assertEqual(e.exception.msg_no, "021")
        p = lots.picks(c, dn)[0]
        self.assertEqual(len({(x["shade"], x["caliber"]) for x in p["lots"]}), 1)
        need = c.execute("SELECT lfimg FROM sd_lips WHERE vbeln=?", (dn,)).fetchone()[0]
        self.assertEqual(need, 8500320)                        # rounded up to full boxes (5903 x 1.44 m2)
        self.assertEqual(sum(x["qty"] for x in p["lots"]), need)
        dl.pick(c, dn)
        dl.post_gi(c, dn, "T")
        self.assertTrue(all(x["difference"] == 0 for x in lots.reconcile(c)))

    def test_no_single_shade_big_enough(self):
        from sd import delivery as dl, order as so
        from tile import lots
        c = fresh()
        free = max(g["qty"] for g in lots.lots(c, "FG-F60")["groups"])
        v = so.create(c, dict(auart="OR", kunnr="C1001", bstnk="T-2", items=[dict(matnr="FG-F60", qty="%.3f" % (free / 1000 + 100))]),
                      "T")["vbeln"]
        if c.execute("SELECT cmgst FROM sd_vbak WHERE vbeln=?", (v,)).fetchone()[0] == "B":
            so.release_credit(c, v, "CREDITMGR")
        r = dl.create(c, v, "T", "2026-12-31")
        dn = r["vbeln"]
        need = c.execute("SELECT lfimg FROM sd_lips WHERE vbeln=?", (dn,)).fetchone()[0]
        if need <= free:
            self.skipTest("delivery limited by stock")
        with self.assertRaises(MMError) as e:
            dl.post_gi(c, dn, "T")
        self.assertEqual(e.exception.msg_no, "014")


class Packing(unittest.TestCase):
    def test_boxes_pallets_and_rounding(self):
        from tile import pack
        c = factory()
        self.assertEqual(pack.sales_qty(c, "FG-F60", 100000), (100800, "FG-F60: rounded up to full boxes - 70 boxes = "
                                                                       "100.8 m2"))
        self.assertEqual(pack.sales_qty(c, "FG-F60", 2000, "PAL")[0], 2 * 40 * 1440)
        self.assertEqual(pack.sales_qty(c, "FG-F60", 10000, "BOX")[0], 14400)
        self.assertEqual(pack.sales_qty(c, "FG-F60B", 1440, "")[0], 1440)          # grade 2 uses the grade 1 box
        self.assertEqual(pack.sales_qty(c, "RM-CLR", 1234, ""), (1234, None))        # not a tile: unchanged
        with self.assertRaises(MMError):
            pack.sales_qty(c, "FG-F60", 1000, "KG")
        with self.assertRaises(MMError):
            pack.sales_qty(c, "RM-CLR", 1000, "PAL")
        p = pack.packing(c, "FG-F60", 2 * 40 * 1440 + 3 * 1440)
        self.assertEqual((p["boxes"], p["full_pallets"], p["loose_boxes"], p["pallets"]), (83, 2, 3, 3))

    def test_order_in_pallets_and_packing_list(self):
        from mm import forms
        from tile import pack
        c = factory()
        dn = c.execute("SELECT vbeln FROM sd_likp WHERE kunnr='C1007'").fetchone()[0]
        d = pack.delivery(c, dn)
        self.assertEqual(d["total"]["pallets"], 8)                     # 8 pallets ordered
        self.assertEqual(d["total"]["boxes"], 8 * 48)
        html = forms.render(c, "PACKLIST", dn)
        self.assertIn("6907.23", html)                                # wall tile: water absorption > 10 %
        self.assertIn("B1/29.7", html)


class Export(unittest.TestCase):
    def test_export_channel_report_and_origin(self):
        from mm import forms
        from tile import export
        c = factory()
        r = export.report(c, "2026-01-01", "2026-12-31")
        self.assertEqual({x["land"] for x in r["countries"]}, {"SA", "JO"})
        self.assertTrue(all(x["vtweg"] == "20" for x in r["invoices"]))
        self.assertTrue(all(x["mwsbk"] == 0 for x in r["invoices"]))  # exports zero-rated
        self.assertGreater(r["share"], 0)
        dn = c.execute("SELECT vbeln FROM sd_likp WHERE kunnr='C1006'").fetchone()[0]
        html = forms.render(c, "ORIGIN", dn)
        self.assertIn("6907.22", html)
        self.assertIn("USD", html)

    def test_takeover_material_line_adds_the_export_channel(self):
        from mm import dataimport
        c = factory()
        self.assertEqual(c.execute("SELECT COUNT(*) FROM md_mvke WHERE matnr='FG-F60'").fetchone()[0], 2)
        r = dataimport.run(c, "MATERIAL", "matnr,sales.vkorg,sales.vtweg\nFG-F60,1000,20\n", "T", simulate=True)
        self.assertEqual(r["errors"], 1)                               # channel 20 exists already
        r = dataimport.run(c, "MATERIAL", "matnr\nFG-F60\n", "T", simulate=True)
        self.assertEqual(r["errors"], 1)                               # nothing to add: already exists


class Lab(unittest.TestCase):
    def test_failed_test_blocks_the_lot_and_it_is_not_proposed(self):
        from tile import lots
        c = fresh()
        lot = c.execute("SELECT lot FROM tile_lot WHERE matnr='FG-P612' AND status='OK'").fetchone()[0]
        r = lots.test(c, lot, dict(water_abs="1.2", strength="1500", planarity="0.2", size_dev="0.1"), "QM1")
        self.assertEqual(r["result"], "FAIL")                  # porcelain BIa: water absorption max 0.5 %
        self.assertEqual(c.execute("SELECT status FROM tile_lot WHERE lot=?", (lot,)).fetchone()[0], "BLOCK")
        with self.assertRaises(MMError):
            lots.propose(c, "FG-P612", "1000", 100)
        ok = lots.test(c, lot, dict(water_abs="0.3", strength="1500"), "QM1")
        self.assertEqual(ok["result"], "PASS")
        self.assertEqual(c.execute("SELECT status FROM tile_lot WHERE lot=?", (lot,)).fetchone()[0], "BLOCK")

    def test_demo_has_one_blocked_lot(self):
        c = factory()
        self.assertEqual(c.execute("SELECT COUNT(*) FROM tile_lot WHERE status='BLOCK'").fetchone()[0], 1)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM tile_test WHERE result='FAIL'").fetchone()[0], 1)


class Kpi(unittest.TestCase):
    def test_first_choice_rate_and_defects(self):
        from tile import lots
        c = factory()
        k = lots.kpi(c, "2026-01-01", "2026-12-31")
        t = k["total"]
        self.assertEqual(t["total"], t["grade1"] + t["grade2"] + t["grade3"] + t["broken"])
        self.assertAlmostEqual(t["first_choice"], round(100.0 * t["grade1"] / t["total"], 1))
        self.assertTrue(k["defects"])
        self.assertEqual(k["defects"], sorted(k["defects"], key=lambda d: -d["qty"]))


class Energy(unittest.TestCase):
    def test_gas_per_m2_and_readings(self):
        from tile import energy
        c = fresh()
        r = energy.report(c, "2026-01-01", "2026-11-09")
        days = [x for x in r["rows"] if x["gas_m2"]]
        self.assertTrue(days)
        x = days[0]
        self.assertAlmostEqual(x["gas_m2"], round(x["gas"] / x["m2"], 3))
        with self.assertRaises(MMError):                       # a meter does not run backwards
            energy.save_reading(c, "GAS-KILN", "2026-11-09", "1", "T")
        with self.assertRaises(MMError):
            energy.save_reading(c, "GAS-KILN", "2026-12-31", "99999999", "T")
        with self.assertRaises(MMError):
            energy.save_reading(c, "NOPE", "2026-11-09", "1", "T")

    def test_high_day_is_flagged(self):
        from tile import energy, lots
        c = fresh()
        a = _new_order(c, "FG-F60", "5000")
        for day in ("2026-11-02", "2026-11-03", "2026-11-04", "2026-11-05"):
            lots.sort(c, a, dict(day=day, lots=[dict(shade="T1", caliber="9.8", qty="1000")]), "T")
        energy.save_meter(c, "TST", "Test meter", "GAS", "", "8.5")
        for day, r in (("2026-11-01", "0"), ("2026-11-02", "1000"), ("2026-11-03", "2000"), ("2026-11-04", "3000"),
                       ("2026-11-05", "5000")):
            energy.save_reading(c, "TST", day, r, "T")
        rows = {x["day"]: x for x in energy.report(c, "2026-11-02", "2026-11-05")["rows"]}
        self.assertFalse(rows["2026-11-04"]["high"])
        self.assertTrue(rows["2026-11-05"]["high"])           # 2 m3 / m2 more than the days before


class Briefing(unittest.TestCase):
    def test_lines_in_the_morning_briefing(self):
        from notify.engine import tile_text
        c = factory()
        t = tile_text(c, day=fixture.TODAY)
        self.assertIn("الفرز الأول", t)
        self.assertIn("م3 لكل م2", t)
        self.assertEqual(tile_text(c, lambda area: area != "PP", day=fixture.TODAY), "")

    def test_standard_demo_has_no_tile_lines(self):
        from mm import seed
        from notify.engine import tile_text
        c = connect(":memory:")
        seed.seed(c)
        self.assertEqual(tile_text(c), "")


if __name__ == "__main__":
    unittest.main()
