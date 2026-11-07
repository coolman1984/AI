"""Engine tests. Run:  python -m unittest discover -s tests -v"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mm import master, posting, reports  # noqa: E402
from mm.db import connect  # noqa: E402
from mm.util import MMError  # noqa: E402

U = "tester"


def setup_db():
    c = connect(":memory:")
    master.create_plant(c, "1000", "Main plant")
    master.create_plant(c, "1100", "Second plant")
    master.create_sloc(c, "1000", "0001", "Raw materials", bin_managed=True)
    master.create_sloc(c, "1000", "0002", "Production")
    master.create_sloc(c, "1100", "0001", "Raw materials")
    for b in ("A-01", "A-02", "A-03"):
        master.create_bin(c, "1000", "0001", b)
    master.create_vendor(c, "V100", "Steel Co")
    master.create_cost_center(c, "CC100", "Maintenance")
    master.create_material(c, {"matnr": "MAP1", "maktx": "Moving avg", "mtart": "ROH",
                               "meins": "KG", "plants": [
                                   {"werks": "1000", "vprsv": "V", "price": "10"},
                                   {"werks": "1100", "vprsv": "V", "price": "20"}]}, U)
    master.create_material(c, {"matnr": "STD1", "maktx": "Standard", "mtart": "ROH",
                               "meins": "PC", "plants": [
                                   {"werks": "1000", "vprsv": "S", "price": "10"}]}, U)
    return c


def val(c, m, w):
    return c.execute("SELECT * FROM valuation WHERE matnr=? AND bwkey=?",
                     (m, w)).fetchone()


def po(c, matnr, qty, price, lgort="0001"):
    e = master.create_po(c, {"lifnr": "V100", "items": [
        {"matnr": matnr, "werks": "1000", "lgort": lgort, "menge": qty,
         "netpr": price}]}, U)
    return e


def gr(c, ebeln, qty, lgpla="A-01", budat="2026-01-10", lgort=""):
    return posting.post_goods_movement(c, {"budat": budat}, [
        {"bwart": "101", "ebeln": ebeln, "ebelp": 10, "qty": qty, "lgpla": lgpla,
         "lgort": lgort}], U)


def acc_lines(c, belnr):
    return {(r["ktosl"], r["shkzg"]): r["dmbtr"] for r in c.execute(
        "SELECT ktosl, shkzg, SUM(dmbtr) AS dmbtr FROM acc_doc_item WHERE belnr=? "
        "GROUP BY ktosl, shkzg", (belnr,))}


class MovingAveragePrice(unittest.TestCase):
    def test_map_recalculated_on_receipts_and_issues_at_map(self):
        c = setup_db()
        gr(c, po(c, "MAP1", "100", "10"), "100")
        v = val(c, "MAP1", "1000")
        self.assertEqual((v["lbkum"], v["salk3"], v["verpr"]), (100000, 100000, 1000))
        gr(c, po(c, "MAP1", "100", "12"), "100", budat="2026-01-11")
        v = val(c, "MAP1", "1000")
        self.assertEqual((v["salk3"], v["verpr"]), (220000, 1100))  # MAP 11.00
        r = posting.post_goods_movement(c, {"budat": "2026-01-12"}, [
            {"bwart": "201", "matnr": "MAP1", "werks": "1000", "lgort": "0001",
             "qty": "50", "kostl": "CC100"}], U)
        self.assertEqual(acc_lines(c, r["belnr"]),
                         {("BSX", "H"): 55000, ("VBR", "S"): 55000})
        v = val(c, "MAP1", "1000")
        self.assertEqual((v["lbkum"], v["salk3"], v["verpr"]), (150000, 165000, 1100))
        # issuing the very last piece takes exactly the remaining value
        posting.post_goods_movement(c, {"budat": "2026-01-12"}, [
            {"bwart": "201", "matnr": "MAP1", "werks": "1000", "lgort": "0001",
             "qty": "150", "kostl": "CC100"}], U)
        v = val(c, "MAP1", "1000")
        self.assertEqual((v["lbkum"], v["salk3"]), (0, 0))
        self.assertTrue(reports.consistency_check(c)["ok"])

    def test_rounding_last_issue_clears_value(self):
        c = setup_db()
        gr(c, po(c, "MAP1", "3", "10"), "3")          # 30.00
        gr(c, po(c, "MAP1", "3", "10.01"), "3")       # 30.03 -> MAP 10.005 -> 10.01
        for _ in range(5):
            posting.post_goods_movement(c, {"budat": "2026-01-12"}, [
                {"bwart": "201", "matnr": "MAP1", "werks": "1000",
                 "lgort": "0001", "qty": "1", "kostl": "CC100"}], U)
        self.assertEqual(val(c, "MAP1", "1000")["salk3"], 6003 - 5 * 1001)
        posting.post_goods_movement(c, {"budat": "2026-01-12"}, [
            {"bwart": "201", "matnr": "MAP1", "werks": "1000",
             "lgort": "0001", "qty": "1", "kostl": "CC100"}], U)
        self.assertEqual(val(c, "MAP1", "1000")["salk3"], 0)
        self.assertTrue(reports.consistency_check(c)["ok"])


class StandardPrice(unittest.TestCase):
    def test_gr_difference_goes_to_price_difference_account(self):
        c = setup_db()
        r = gr(c, po(c, "STD1", "10", "12"), "10")
        self.assertEqual(acc_lines(c, r["belnr"]), {
            ("BSX", "S"): 10000, ("WRX", "H"): 12000, ("PRD", "S"): 2000})
        v = val(c, "STD1", "1000")
        self.assertEqual((v["salk3"], v["stprs"]), (10000, 1000))

    def test_price_change_revalues_stock(self):
        c = setup_db()
        gr(c, po(c, "STD1", "10", "10"), "10")
        res = posting.change_price(c, "STD1", "1000", "11", user=U)
        self.assertEqual(res["revaluation"], 1000)
        self.assertEqual(val(c, "STD1", "1000")["salk3"], 11000)
        self.assertTrue(reports.consistency_check(c)["ok"])


class Fifo(unittest.TestCase):
    def test_issue_takes_oldest_quant_first_across_bins(self):
        c = setup_db()
        gr(c, po(c, "MAP1", "10", "10"), "10", lgpla="A-02", budat="2026-01-05")
        gr(c, po(c, "MAP1", "10", "10"), "10", lgpla="A-01", budat="2026-01-06")
        r = posting.post_goods_movement(c, {"budat": "2026-01-07"}, [
            {"bwart": "201", "matnr": "MAP1", "werks": "1000", "lgort": "0001",
             "qty": "15", "kostl": "CC100"}], U)
        pieces = c.execute("SELECT lgpla, wdatu, qty FROM mat_doc_piece WHERE "
                           "mblnr=? ORDER BY rowid", (r["mblnr"],)).fetchall()
        self.assertEqual([tuple(p) for p in pieces],
                         [("A-02", "2026-01-05", 10000), ("A-01", "2026-01-06", 5000)])

    def test_transfer_keeps_goods_receipt_date(self):
        c = setup_db()
        gr(c, po(c, "MAP1", "10", "10"), "10", budat="2026-01-05")
        posting.post_goods_movement(c, {"budat": "2026-02-01"}, [
            {"bwart": "311", "matnr": "MAP1", "werks": "1000", "lgort": "0001",
             "umlgo": "0002", "qty": "4"}], U)
        q = c.execute("SELECT wdatu, qty FROM quant WHERE lgort='0002'").fetchone()
        self.assertEqual((q["wdatu"], q["qty"]), ("2026-01-05", 4000))


class Movements(unittest.TestCase):
    def test_deficit_is_rejected_and_nothing_is_posted(self):
        c = setup_db()
        gr(c, po(c, "MAP1", "5", "10"), "5")
        before = c.execute("SELECT COUNT(*) FROM mat_doc").fetchone()[0]
        with self.assertRaises(MMError) as e:
            posting.post_goods_movement(c, {}, [
                {"bwart": "201", "matnr": "MAP1", "werks": "1000", "lgort": "0001",
                 "qty": "6", "kostl": "CC100"}], U)
        self.assertIn("Deficit", e.exception.msg)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM mat_doc").fetchone()[0],
                         before)
        self.assertEqual(val(c, "MAP1", "1000")["lbkum"], 5000)

    def test_bin_required_in_bin_managed_location(self):
        c = setup_db()
        with self.assertRaises(MMError):
            gr(c, po(c, "MAP1", "5", "10"), "5", lgpla="")

    def test_po_over_delivery_rejected(self):
        c = setup_db()
        e = po(c, "MAP1", "5", "10")
        with self.assertRaises(MMError):
            gr(c, e, "6")

    def test_quality_release_321(self):
        c = setup_db()
        e = po(c, "MAP1", "10", "10")
        posting.post_goods_movement(c, {}, [{"bwart": "101", "ebeln": e, "ebelp": 10,
                                             "qty": "10", "lgpla": "A-01",
                                             "insmk": "Q"}], U)
        posting.post_goods_movement(c, {}, [{"bwart": "321", "matnr": "MAP1",
                                             "werks": "1000", "lgort": "0001",
                                             "qty": "7"}], U)
        st = reports.stock_overview(c, "MAP1")
        self.assertEqual((st["U"], st["Q"]), (7.0, 3.0))
        self.assertEqual(val(c, "MAP1", "1000")["salk3"], 10000)  # no value change

    def test_plant_to_plant_transfer_updates_receiving_map(self):
        c = setup_db()
        gr(c, po(c, "MAP1", "10", "10"), "10")
        posting.post_goods_movement(c, {}, [
            {"bwart": "561", "matnr": "MAP1", "werks": "1100", "lgort": "0001",
             "qty": "10", "amount": "200"}], U)          # 10 kg @ 20
        r = posting.post_goods_movement(c, {}, [
            {"bwart": "301", "matnr": "MAP1", "werks": "1000", "lgort": "0001",
             "umwrk": "1100", "umlgo": "0001", "qty": "10"}], U)
        v = val(c, "MAP1", "1100")
        self.assertEqual((v["lbkum"], v["salk3"], v["verpr"]), (20000, 30000, 1500))
        self.assertEqual(val(c, "MAP1", "1000")["salk3"], 0)
        self.assertEqual(acc_lines(c, r["belnr"]),
                         {("BSX", "H"): 10000, ("BSX", "S"): 10000})
        self.assertTrue(reports.consistency_check(c)["ok"])


class Reversal(unittest.TestCase):
    def test_cancel_gr_restores_stock_value_and_po(self):
        c = setup_db()
        e = po(c, "MAP1", "10", "10")
        r = gr(c, e, "10")
        posting.cancel_document(c, r["mblnr"], r["mjahr"], user=U)
        v = val(c, "MAP1", "1000")
        self.assertEqual((v["lbkum"], v["salk3"]), (0, 0))
        self.assertEqual(c.execute("SELECT wemng FROM po_item WHERE ebeln=?",
                                   (e,)).fetchone()[0], 0)
        with self.assertRaises(MMError):
            posting.cancel_document(c, r["mblnr"], r["mjahr"], user=U)
        self.assertTrue(reports.consistency_check(c)["ok"])

    def test_cancel_issue_puts_stock_back_in_same_bins_and_dates(self):
        c = setup_db()
        gr(c, po(c, "MAP1", "10", "10"), "10", lgpla="A-02", budat="2026-01-05")
        r = posting.post_goods_movement(c, {}, [
            {"bwart": "201", "matnr": "MAP1", "werks": "1000", "lgort": "0001",
             "qty": "4", "kostl": "CC100"}], U)
        posting.cancel_document(c, r["mblnr"], r["mjahr"], user=U)
        q = c.execute("SELECT lgpla, wdatu, SUM(qty) FROM quant GROUP BY lgpla, "
                      "wdatu").fetchall()
        self.assertEqual([tuple(x) for x in q], [("A-02", "2026-01-05", 10000)])
        self.assertEqual(val(c, "MAP1", "1000")["salk3"], 10000)
        self.assertTrue(reports.consistency_check(c)["ok"])

    def test_cancel_gr_after_price_moved_posts_difference(self):
        """GR 10@10, GR 10@20 (MAP 15), issue 15 at MAP, cancel 2nd GR:
        only 5 kg left worth 75 but the GR was 200 -> stock to 0? No: 5 kg
        remain wanted -10 kg -> deficit. So cancel the first GR of 5 kg."""
        c = setup_db()
        r1 = gr(c, po(c, "MAP1", "5", "10"), "5")
        gr(c, po(c, "MAP1", "10", "40"), "10")       # value 450, MAP 30
        posting.post_goods_movement(c, {}, [
            {"bwart": "201", "matnr": "MAP1", "werks": "1000", "lgort": "0001",
             "qty": "10", "kostl": "CC100"}], U)     # out 300 -> 5 kg / 150
        posting.cancel_document(c, r1["mblnr"], r1["mjahr"], user=U)
        v = val(c, "MAP1", "1000")
        self.assertEqual((v["lbkum"], v["salk3"]), (0, 0))   # value cleared
        self.assertTrue(reports.consistency_check(c)["ok"])


if __name__ == "__main__":
    unittest.main()
