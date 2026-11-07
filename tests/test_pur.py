"""Procurement tests on the full demo."""
import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from co.seed import sample_period_start  # noqa: E402
from fi.document import signed  # noqa: E402
from mm import seed  # noqa: E402
from mm.db import connect  # noqa: E402
from mm.posting import post_goods_movement  # noqa: E402
from mm.util import MMError  # noqa: E402
from pur import analytics, po, pr, sourcing  # noqa: E402

_DB = {}
P = sample_period_start()
TODAY = datetime.date.today().isoformat()


def demo():
    if "c" not in _DB:
        c = connect(":memory:")
        seed.seed(c)
        _DB["c"] = c
    return _DB["c"]


def d(day):
    return datetime.date(P.year, P.month, day).isoformat()


class Requisitions(unittest.TestCase):
    def test_mrp_creates_requisition_to_max_stock(self):
        r = demo().execute("SELECT * FROM pr_item WHERE estkz='B'").fetchone()
        self.assertEqual(r["matnr"], "RM-1003")
        self.assertEqual(r["menge"], 1200000 - 366000)      # max 1,200 - available 366
        self.assertEqual(r["statu"], "A")                  # released and ordered

    def test_requisition_above_limit_needs_release(self):
        c = demo()
        r = pr.create_pr(c, [{"matnr": "RM-1001", "menge": "1000"}], "T", badat=TODAY)
        self.assertEqual(r["release"], ["R1"])
        self.assertFalse(pr.assign_sources(c, r["banfn"]))   # blocked: not assignable
        pr.release_pr(c, r["banfn"], "R1", "T")
        self.assertEqual(len(pr.assign_sources(c, r["banfn"])), 1)

    def test_quota_arrangement_picks_vendor(self):
        c = demo()
        row = c.execute("SELECT h.lifnr FROM pr_item p JOIN po_header h ON h.ebeln=p.ebeln "
                        "WHERE p.matnr='RM-1001'").fetchone()
        self.assertEqual(row["lifnr"], "100007")            # 40 % quota vendor


class Orders(unittest.TestCase):
    def test_goods_receipt_blocked_until_released(self):
        c = demo()
        e = po.create_po(c, {"lifnr": "100001", "bedat": TODAY, "items": [
            {"matnr": "RM-1001", "menge": "3000", "lgort": "0001"}]}, "T")
        with self.assertRaises(MMError) as x:
            post_goods_movement(c, {"budat": TODAY}, [{"bwart": "101", "ebeln": e, "ebelp": 10,
                                                       "qty": "10", "lgpla": "A-01-01"}], "T")
        self.assertEqual(x.exception.msg_no, "390")
        with self.assertRaises(MMError) as y:
            po.release_po(c, e, "R2", "T")                   # wrong sequence
        self.assertEqual(y.exception.msg_no, "181")
        po.release_po(c, e, "R1", "T")
        post_goods_movement(c, {"budat": TODAY}, [{"bwart": "101", "ebeln": e, "ebelp": 10,
                                                   "qty": "10", "lgpla": "A-01-01"}], "T")

    def test_two_level_release_for_large_order(self):
        h = demo().execute("SELECT * FROM po_header WHERE lifnr='100007'").fetchone()
        self.assertEqual((h["frgst"], h["frgzu"], h["frgke"]), ("R1,R2", "R1,R2", "R"))

    def test_contract_call_off_and_target_check(self):
        c = demo()
        st = sourcing.contract_status(c)[0]
        self.assertEqual(st["released_qty"], 2000000)
        with self.assertRaises(MMError) as x:
            po.create_po(c, {"lifnr": "100002", "bedat": TODAY, "items": [
                {"matnr": "RM-1002", "menge": "19000", "konnr": st["konnr"], "ktpnr": 10}]}, "T")
        self.assertEqual(x.exception.msg_no, "322")

    def test_blocked_vendor(self):
        c = demo()
        c.execute("UPDATE vendor SET sperr=1 WHERE lifnr='100009'")
        with self.assertRaises(MMError):
            po.create_po(c, {"lifnr": "100009", "bedat": TODAY, "items": [
                {"matnr": "RM-1004", "menge": "1", "netpr": "500"}]}, "T")
        c.execute("UPDATE vendor SET sperr=0 WHERE lifnr='100009'")


class Sourcing(unittest.TestCase):
    def test_price_comparison_and_award(self):
        c = demo()
        sub = c.execute("SELECT submi FROM rfq LIMIT 1").fetchone()["submi"]
        cmp = sourcing.price_comparison(c, sub)
        self.assertEqual([x["lifnr"] for x in cmp["items"]], ["100008", "100009", "100006"])
        self.assertEqual(cmp["items"][0]["statu"], "A")
        ir = c.execute("SELECT brutto FROM info_record WHERE lifnr='100008' AND "
                       "matnr='RM-1004'").fetchone()
        self.assertEqual(ir["brutto"], 54800)               # info record from quotation


class Postings(unittest.TestCase):
    def test_freight_capitalized_and_cleared(self):
        c = demo()
        e = c.execute("SELECT ebeln FROM po_header WHERE lifnr='100007'").fetchone()["ebeln"]
        fre = c.execute("SELECT SUM(CASE WHEN shkzg='S' THEN dmbtr ELSE -dmbtr END) FROM "
                        "acc_doc_item WHERE hkont='193000' AND ebeln=?", (e,)).fetchone()[0]
        self.assertEqual(fre, 0)                             # GR credit = MIRO debit
        gr = c.execute("SELECT SUM(dmbtr) FROM acc_doc_item i JOIN acc_doc h USING (belnr, "
                       "gjahr) WHERE i.hkont='193000' AND i.ebeln=? AND h.blart='WE'",
                       (e,)).fetchone()[0]
        self.assertEqual(gr, 300000)                         # freight 3,000 at GR

    def test_service_goes_to_cost_center(self):
        c = demo()
        e = c.execute("SELECT ebeln FROM po_item WHERE txz01='Gearbox overhaul CNC line'"
                      ).fetchone()["ebeln"]
        docs = [r["belnr"] for r in c.execute("SELECT DISTINCT belnr FROM acc_doc_item WHERE "
                                              "ebeln=? AND hkont='475000'", (e,))]
        self.assertEqual(len(docs), 2)                       # GR + MIRO difference
        v = sum(c.execute("SELECT COALESCE(SUM(i.wtg),0) FROM co_item i JOIN co_doc d ON "
                          "d.belnr=i.belnr WHERE d.refbn LIKE ? AND i.objnr='KS4200'",
                          (b + "/%",)).fetchone()[0] for b in docs)
        self.assertEqual(v, 2850000)                         # 28,000 GR + 500 invoice diff

    def test_return_and_delivery_completed(self):
        c = demo()
        it = c.execute("SELECT * FROM po_item i JOIN po_header h USING (ebeln) WHERE "
                       "h.lifnr='100008'").fetchone()
        self.assertEqual((it["wemng"], it["elikz"]), (280000, 1))
        ev = {e["lifnr"]: e for e in analytics.vendor_evaluation(c)}
        self.assertLess(ev["100008"]["quality"], 100)
        self.assertLess(ev["100008"]["quantity"], 100)
        self.assertLess(ev["100007"]["ontime"], 100)        # late deliveries

    def test_books_still_balanced(self):
        from co.reports import reconcile
        from fi.reports import statements
        self.assertTrue(statements(demo(), P.year, P.month, P.month)["balanced"])
        self.assertTrue(reconcile(demo(), P.year, P.month, P.month)["ok"])


if __name__ == "__main__":
    unittest.main()
