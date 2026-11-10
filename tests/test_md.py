"""Master data tests on the full demo (material / customer / vendor)."""
import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fixture  # noqa: E402,F401  (fixed business date)

from co.seed import sample_period_start  # noqa: E402
from md import changes, checks, material as mat, partner as bp, reports  # noqa: E402
from mm import seed  # noqa: E402
from mm.db import connect  # noqa: E402
from mm.posting import post_goods_movement  # noqa: E402
from mm.util import MMError  # noqa: E402
from pur import po  # noqa: E402

_DB = {}
P = sample_period_start()
TODAY = fixture.T.isoformat()


def demo():
    if "c" not in _DB:
        c = connect(":memory:")
        seed.seed(c)
        _DB["c"] = c
    return _DB["c"]


def err(test, fn, msg_no):
    with test.assertRaises(MMError) as x:
        fn()
    test.assertEqual(x.exception.msg_no, msg_no, str(x.exception))
    return x.exception


class MaterialMaster(unittest.TestCase):
    def test_all_views_of_trading_good(self):
        m = mat.get_material(demo(), "TR-5001")
        self.assertEqual(m["vpsta"], "KVEDLSQBX")
        self.assertEqual(m["bklas"], "3100")
        self.assertEqual(m["uom"][0]["umrez"], 24)
        self.assertEqual([s["vtweg"] for s in m["sales"]], ["10", "20"])
        self.assertEqual(m["exim"]["impctl"], "L")

    def test_view_not_allowed_for_type(self):
        err(self, lambda: mat.create_material(demo(), dict(
            matnr="X-1", mtart="ROH", maktx="x", meins="KG", matkl="STEEL",
            plants=[dict(werks="1000", price="1")], sales=[dict(vtweg="10")]), "T"), "803")

    def test_valuation_class_and_price_control_rules(self):
        base = dict(mtart="FERT", maktx="x", meins="PC", matkl="CABINET")
        err(self, lambda: mat.create_material(demo(), dict(base, matnr="X-2", bklas="3000",
                                                           plants=[dict(werks="1000", price="1")]),
                                              "T"), "333")
        err(self, lambda: mat.create_material(demo(), dict(
            matnr="X-3", mtart="VERP", maktx="x", meins="PC", matkl="PACK",
            plants=[dict(werks="1000", vprsv="S", price="1")]), "T"), "331")
        err(self, lambda: mat.create_material(demo(), dict(base, matnr="X-4", ean11="6221234500017",
                                                           plants=[dict(werks="1000", price="1")]),
                                              "T"), "349")

    def test_mm02_rules_and_change_documents(self):
        c = demo()
        err(self, lambda: mat.change_material(c, "RM-1001", {"plants": [
            {"werks": "1000", "vprsv": "S"}]}, "T"), "160")       # stock exists
        err(self, lambda: mat.change_material(c, "RM-1001", {"plants": [
            {"werks": "1000", "price": "99"}]}, "T"), "161")      # prices only via MR21
        err(self, lambda: mat.change_material(c, "RM-1001", {"meins": "TO"}, "T"), "337")
        r = mat.change_material(c, "RM-1003", {"plants": [{"werks": "1000", "minbe": "460"}]}, "T")
        self.assertEqual(r["changed"], 1)
        ch = changes.changes(c, "MATERIAL", "RM-1003", fname="minbe")
        self.assertEqual((ch[0]["value_old"], ch[0]["value_new"]), ("450000", "460000"))

    def test_status_blocks_purchasing_and_inventory(self):
        c = demo()
        mat.change_material(c, "SP-4001", {"plants": [{"werks": "1000", "mmsta": "BP"}]}, "T")
        err(self, lambda: po.create_po(c, {"lifnr": "100005", "bedat": TODAY, "items": [
            {"matnr": "SP-4001", "menge": "5", "netpr": "85"}]}, "T"), "347")
        mat.change_material(c, "SP-4001", {"plants": [{"werks": "1000", "mmsta": "01"}]}, "T")
        err(self, lambda: post_goods_movement(c, {"budat": TODAY}, [
            {"bwart": "201", "matnr": "SP-4001", "werks": "1000", "lgort": "0004",
             "lgpla": "S-01", "qty": "1", "kostl": "4200"}], "T"), "121")
        mat.change_material(c, "SP-4001", {"plants": [{"werks": "1000", "mmsta": ""}]}, "T")
        w = []
        checks.material(c, "SP-4002", "1000", "purch", w)     # AV = warning only
        self.assertIn("Phase-out", w[0])

    def test_deletion_flag_blocks_receipts_and_orders(self):
        c = demo()
        self.assertTrue(c.execute("SELECT lvorm FROM material WHERE matnr='RM-1099'").fetchone()[0])
        err(self, lambda: post_goods_movement(c, {"budat": TODAY}, [
            {"bwart": "561", "matnr": "RM-1099", "werks": "1000", "lgort": "0002",
             "qty": "1", "amount": "1"}], "T"), "127")
        r = mat.flag_deletion(c, "FG-3002", "T")
        self.assertTrue(r["warnings"])                           # still has stock
        mat.flag_deletion(c, "FG-3002", "T", flag=False)

    def test_qm_inspection_stock_and_overdelivery_tolerance(self):
        c = demo()
        e = c.execute("SELECT ebeln FROM po_item WHERE matnr='TR-5001'").fetchone()["ebeln"]
        gr = c.execute("SELECT insmk, menge FROM mat_doc_item WHERE ebeln=? AND bwart='101'",
                       (e,)).fetchone()
        self.assertEqual((gr["insmk"], gr["menge"]), ("Q", 624000))   # 600 + 4 % tolerance
        self.assertEqual(c.execute("SELECT SUM(qty) FROM quant WHERE matnr='TR-5001' AND "
                                   "insmk='Q'").fetchone()[0] or 0, 0)  # released by 321
        auto = c.execute("SELECT auto FROM md_mard WHERE matnr='RM-1001' AND lgort='0001'"
                         ).fetchone()
        self.assertEqual(auto[0], 1)                          # OMB3 automatic creation

    def test_import_license_and_embargo(self):
        c = demo()
        it = {"matnr": "TR-5001", "menge": "10", "netpr": "45"}
        nxt = datetime.date(P.year + 3, 1, 5).isoformat()
        err(self, lambda: po.create_po(c, {"lifnr": "300003", "bedat": nxt, "items": [it]},
                                       "T"), "002")              # license expired by then
        c.execute("UPDATE md_exim SET impctl='B' WHERE matnr='TR-5001'")
        err(self, lambda: po.create_po(c, {"lifnr": "300003", "bedat": TODAY, "items": [it]},
                                       "T"), "001")
        po.create_po(c, {"lifnr": "100005", "bedat": TODAY, "items": [it]}, "T")  # domestic
        c.execute("UPDATE md_exim SET impctl='L' WHERE matnr='TR-5001'")

    def test_cin_and_brazil(self):
        self.assertEqual(mat.gstin_check_char("27AAACT2727Q1Z"), "W")
        err(self, lambda: mat.check_gstin("27AAACT2727Q1ZX"), "012")
        err(self, lambda: mat.check_gstin("27AAACT2727Q1ZW", "ABCDE1234F"), "013")
        err(self, lambda: mat.save_br_material(demo(), "FG-3001", "1000", "9403.40", "3", "0",
                                               "T"), "001")
        b = demo().execute("SELECT * FROM md_br_mat WHERE matnr='FG-3001'").fetchone()
        self.assertEqual((b["steuc"], b["mtuse"], b["mtorg"]), ("9403.40.00", "3", "1"))


class Partners(unittest.TestCase):
    def test_number_ranges_and_field_status(self):
        c = demo()
        self.assertEqual(c.execute("SELECT lifnr FROM vendor WHERE name LIKE 'Ningbo%'"
                                   ).fetchone()[0], "300003")      # internal number
        full = dict(ktokk="0001", name="x", city="Cairo", stcd1="123-456-789",
                    akont="160000", zterm="NT30", bankn="1")
        err(self, lambda: bp.create_vendor(c, dict(full, lifnr="100050"), "T"), "011")
        err(self, lambda: bp.create_customer(c, dict(ktokd="0002", kunnr="C9500", name="x", street="s", city="Giza"), "T"), "010")
        err(self, lambda: bp.create_vendor(c, dict(ktokk="0001", name="New Co", city="Cairo",
                                                   stcd1="123-456-789", akont="160000",
                                                   zterm="NT30"), "T"), "055")  # no bank
        err(self, lambda: bp.create_vendor(c, dict(ktokk="0001", name="New Co", city="Cairo",
                                                   stcd1="123-456-789", akont="160000",
                                                   zterm="NT30", bankn="1",
                                                   iban="EG380019000500000000263180003"),
                                           "T"), "191")              # IBAN check digits

    def test_duplicate_warning(self):
        c = demo()
        r = bp.create_vendor(c, dict(ktokk="0001", name="Copy Paints", city="Giza",
                                     stcd1=c.execute("SELECT stcd1 FROM vendor WHERE lifnr="
                                                     "'100003'").fetchone()[0],
                                     akont="160000", zterm="NT30", bankn="999"), "T")
        self.assertTrue(any("100003" in w for w in r["warnings"]))

    def test_partner_functions_and_ship_to(self):
        c = demo()
        we = {r["kunn2"] for r in c.execute("SELECT kunn2 FROM md_knvp WHERE kunnr='C1004' AND "
                                            "parvw='WE'")}
        self.assertEqual(we, {"C1004", "S0001"})
        err(self, lambda: bp.create_customer(c, dict(
            ktokd="0001", kunnr="C1007", name="x", city="Cairo", stcd1="111-222-333",
            akont="140000", zterm="NT30",
            sales=[dict(vtweg="10", kalks="1", vsbed="01", ktgrd="01", zterm="NT30",
                        waers="EGP")], partners=[dict(parvw="RG", kunn2="S0001")]), "T"), "004")
        from fi.ar import customer_invoice
        err(self, lambda: customer_invoice(c, {"kunnr": "S0001", "budat": TODAY, "mwskz": "A0"},
                                           [{"hkont": "800000", "amount": "10"}], "T"), "352")

    def test_billing_blocks_and_sales_view(self):
        from co import copa
        c = demo()
        err(self, lambda: copa.create_billing(c, {"kunnr": "C1005", "fkdat": TODAY, "items": [
            dict(matnr="FG-3001", qty="1", price="1")]}, "T"), "011")   # deletion flag
        err(self, lambda: copa.create_billing(c, {"kunnr": "C1001", "fkdat": TODAY, "items": [
            dict(matnr="RM-1001", qty="1", price="1")]}, "T"), "320")   # no sales view
        b = c.execute("SELECT b.netwr FROM billing b JOIN billing_item i USING (vbeln) WHERE "
                      "i.matnr='TR-5001'").fetchone()
        self.assertEqual(b["netwr"], 1140000)                # 120 x 95.00

    def test_purchasing_block(self):
        err(self, lambda: po.create_po(demo(), {"lifnr": "100004", "bedat": TODAY, "items": [
            {"matnr": "PK-2001", "menge": "100", "netpr": "12.5", "peinh": "100"}]}, "T"), "302")

    def test_sensitive_change_dual_control(self):
        from fi.ap import payment_run
        c = demo()
        nxt = (fixture.T + datetime.timedelta(days=400)).isoformat()
        r = payment_run(c, TODAY, "MDT1", nxt, "T")
        self.assertIn("100006", [e["lifnr"] for e in r["exceptions"]])
        self.assertNotIn("100006", [p["lifnr"] for p in r["payments"]])
        err(self, lambda: bp.confirm_sensitive(c, "K", "100006", "MDADMIN"), "061")
        old = c.execute("SELECT bankn FROM vendor WHERE lifnr='100006'").fetchone()[0]
        bp.change_vendor(c, "100005", {"bankn": "000011112222"}, "CLERK")
        before = c.execute("SELECT value_old FROM md_cdpos p JOIN md_cdhdr h USING (changenr) "
                           "WHERE h.objectid='100005' AND p.fname='bankn' ORDER BY changenr DESC"
                           ).fetchone()[0]
        bp.confirm_sensitive(c, "K", "100005", "FINMGR", reject=True)
        self.assertEqual(c.execute("SELECT bankn FROM vendor WHERE lifnr='100005'").fetchone()[0],
                         before)                              # rejected -> old value back
        self.assertTrue(old)
        self.assertEqual(c.execute("SELECT status FROM md_sensitive WHERE objectid='100003'"
                                   ).fetchone()[0], "C")


class Governance(unittest.TestCase):
    def test_cockpit(self):
        k = reports.cockpit(demo())["kpi"]
        self.assertGreaterEqual(k["pending"], 1)
        self.assertGreater(k["held"], 0)
        self.assertGreaterEqual(k["blocked_vendors"], 1)
        self.assertGreater(k["quality"], 50)

    def test_books_still_balanced(self):
        from co.reports import reconcile
        from fi.reports import statements
        self.assertTrue(statements(demo(), P.year, P.month, P.month)["balanced"])
        self.assertTrue(reconcile(demo(), P.year, P.month, P.month)["ok"])


if __name__ == "__main__":
    unittest.main()
