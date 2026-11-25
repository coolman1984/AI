"""Customs clearance (ZCUS): import declaration from an import file with ACID, duty and import VAT
on the CIF value at the customs rate, payment into the import file (landed cost) and the VAT return
(line 4a), steps only forward, days in port over the free days; export declaration from a delivery
with certificate of origin, bill of lading and expected export support; tariff checks."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fixture  # noqa: E402,F401
from mm.db import connect  # noqa: E402
from mm.util import MMError, rdiv  # noqa: E402

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


class Import(unittest.TestCase):
    def test_duty_and_vat_on_cif_at_the_customs_rate(self):
        from customs import engine as cu
        c = factory()
        d = cu.detail(c, c.execute("SELECT declno FROM cus_decl WHERE direction='IMP'").fetchone()[0])
        self.assertEqual(d["status"], "PAID")
        cif_fc = d["goods"] + d["freight"] + d["insurance"]
        self.assertEqual(d["cif"], rdiv(cif_fc * d["kurs"], 100000))          # customs value in EGP
        for i in d["items"]:
            self.assertEqual(i["duty"], rdiv(i["cif"] * i["duty_pct"], 10000))
            self.assertEqual(i["vat"], rdiv((i["cif"] + i["duty"]) * i["vat_pct"], 10000))
        # duty -> import file costs (landed cost later), VAT -> input tax code VI
        cost = c.execute("SELECT SUM(amount) FROM imp_cost WHERE impno=? AND typ='CUSTOMS'", (d["impno"],)).fetchone()[0]
        self.assertEqual(cost, d["duty"] + d["fees"])
        vat = c.execute("SELECT SUM(dmbtr) FROM acc_doc_item WHERE mwskz='VI' AND hkont='154000'").fetchone()[0]
        self.assertEqual(vat, d["vat"])
        from tax.returns import vat_return
        line = [x for x in vat_return(c, 2026, 11)["lines"] if x["no"] == "4a"][0]
        self.assertEqual(line["tax"], d["vat"])

    def test_steps_only_forward_and_acid_required(self):
        from customs import engine as cu
        c = fresh()
        imp = c.execute("SELECT impno FROM imp_file").fetchone()[0]
        c.execute("DELETE FROM cus_item WHERE declno IN (SELECT declno FROM cus_decl WHERE impno=?)", (imp,))
        c.execute("DELETE FROM cus_decl WHERE impno=?", (imp,))
        decl = cu.create_import(c, {"impno": imp, "freight": "100"}, "T")["declno"]
        with self.assertRaises(MMError) as e:
            cu.step(c, decl, "ARRIVED", None, "T")
        self.assertEqual(e.exception.msg_no, "024")                         # ACID first
        with self.assertRaises(MMError):
            cu.step(c, decl, "ACID", None, "T", {"acid": "123"})            # 19 digits
        cu.step(c, decl, "ACID", None, "T", {"acid": "1234567890123456789"})
        cu.step(c, decl, "ARRIVED", None, "T")
        with self.assertRaises(MMError):
            cu.step(c, decl, "ACID", None, "T")                             # never back
        with self.assertRaises(MMError):
            cu.step(c, decl, "RELEASED", "2099-01-01", "T")                 # no future dates
        with self.assertRaises(MMError):
            cu.create_import(c, {"impno": imp}, "T")                        # one declaration per file

    def test_missing_hs_code_stops_the_assessment(self):
        from customs import engine as cu
        c = fresh()
        imp = c.execute("SELECT impno FROM imp_file").fetchone()[0]
        c.execute("DELETE FROM cus_item WHERE declno IN (SELECT declno FROM cus_decl WHERE impno=?)", (imp,))
        c.execute("DELETE FROM cus_decl WHERE impno=?", (imp,))
        c.execute("DELETE FROM cus_tariff WHERE hs='3207.20'")
        decl = cu.create_import(c, {"impno": imp, "acid": "1234567890123456789"}, "T")["declno"]
        with self.assertRaises(MMError) as e:
            cu.step(c, decl, "ASSESSED", None, "T")
        self.assertEqual(e.exception.msg_no, "025")

    def test_days_in_port_over_the_free_days(self):
        from customs import engine as cu
        from mm import util
        c = fresh()
        decl = c.execute("SELECT declno FROM cus_decl WHERE direction='IMP'").fetchone()[0]
        c.execute("UPDATE cus_decl SET d_arrival='2026-11-01', free_days=4 WHERE declno=?", (decl,))
        d = cu.detail(c, decl)
        self.assertEqual(d["days_in_port"], (util.today() - __import__("datetime").date(2026, 11, 1)).days)
        self.assertEqual(d["over_days"], d["days_in_port"] - 4)
        self.assertEqual(d["storage"], d["over_days"] * 1500 * 100)
        self.assertTrue(any(a["kind"] == "PORT" for a in cu.cockpit(c)["alerts"]))
        self.assertIn("فاتت أيام السماح", cu.day_text(c))


class Export(unittest.TestCase):
    def test_export_declarations_and_support(self):
        from customs import engine as cu
        c = factory()
        rows = [r for r in cu.cockpit(c, "EXP")["rows"]]
        self.assertEqual(len(rows), 2)
        shipped = [r for r in rows if r["status"] == "SHIPPED"][0]
        self.assertTrue(shipped["coo_no"] and shipped["bl_no"])
        d = cu.detail(c, shipped["declno"])
        self.assertEqual(d["vat"], 0)
        self.assertEqual(d["export_support"], sum(rdiv(i["cif"] * i["export_support_pct"], 10000) for i in d["items"]))
        self.assertGreater(d["export_support"], 0)
        with self.assertRaises(MMError):                                    # ship needs a bill of lading
            other = [r for r in rows if r["status"] != "SHIPPED"][0]
            c2 = fresh()
            c2.execute("UPDATE cus_decl SET bl_no=NULL WHERE declno=?", (other["declno"],))
            cu.step(c2, other["declno"], "SHIPPED", None, "T")


class Tariff(unittest.TestCase):
    def test_tariff_and_material_hs(self):
        from customs import engine as cu
        c = fresh()
        with self.assertRaises(MMError):
            cu.save_tariff(c, "AB12", "x", "5")
        with self.assertRaises(MMError):
            cu.save_tariff(c, "3207.40", "x", "500")
        cu.save_tariff(c, "3207.40", "Glass frit", "3")
        self.assertEqual(c.execute("SELECT duty_pct FROM cus_tariff WHERE hs='3207.40'").fetchone()[0], 300)
        with self.assertRaises(MMError):
            cu.set_material_hs(c, "NOPE", "3207.40")
        self.assertEqual(cu.hs_of(c, "FG-P612"), "6907.21")                 # tiles: from the ISO group

    def test_briefing_line_only_for_purchasing(self):
        from notify.engine import customs_text
        c = factory()
        self.assertIn("الجمارك", customs_text(c))
        self.assertEqual(customs_text(c, lambda area: area != "PUR"), "")


if __name__ == "__main__":
    unittest.main()
