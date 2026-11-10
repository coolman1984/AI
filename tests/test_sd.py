"""Sales & distribution tests on the full demo (current month)."""
import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fixture  # noqa: E402,F401  (fixed business date)

from mm import seed  # noqa: E402
from mm.db import connect  # noqa: E402
from mm.util import MMError  # noqa: E402
from sd import billing, delivery, order, pricing, reports, service  # noqa: E402

_DB = {}
T = fixture.T
TODAY = T.isoformat()
D1 = T.replace(day=1).isoformat()


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


def first(c, auart, kunnr):
    return c.execute("SELECT * FROM sd_vbak WHERE auart=? AND kunnr=? ORDER BY vbeln LIMIT 1",
                     (auart, kunnr)).fetchone()


class Pricing(unittest.TestCase):
    def test_access_sequence_customer_price_before_list_price(self):
        c = demo()
        cust = c.execute("SELECT * FROM customer WHERE kunnr='C1004'").fetchone()
        area = order.area_of(c, "C1004")
        r = pricing.price_item(c, cust, area, "FG-3003", 1000, TODAY)
        self.assertEqual(r["conds"][0]["kbetr"], 760000)            # A305 7,600 instead of A304 7,900
        other = pricing.price_item(c, c.execute("SELECT * FROM customer WHERE kunnr='C1001'").fetchone(),
                                   order.area_of(c, "C1001"), "FG-3003", 1000, TODAY)
        self.assertEqual(other["conds"][0]["kbetr"], 790000)

    def test_scale_discounts_freight_and_tax(self):
        c = demo()
        o = first(c, "OR", "C1002")
        p = c.execute("SELECT * FROM sd_vbap WHERE vbeln=? AND matnr='FG-3001'", (o["vbeln"],)).fetchone()
        self.assertEqual(p["kzwi1"], 25 * 415000)                    # scale 20+ = 4,150
        self.assertEqual(p["kzwi2"], 25 * 415000 * 5 // 100)        # K007 5 %
        q = c.execute("SELECT * FROM sd_konv WHERE knumv=? AND kschl='ZDEA'", (o["vbeln"],)).fetchone()
        self.assertEqual(q["kbetr"], -300)                           # promotion 3 % on FG-3002
        o1 = first(c, "OR", "C1004")
        it = c.execute("SELECT * FROM sd_vbap WHERE vbeln=? AND matnr='FG-3003'", (o1["vbeln"],)).fetchone()
        self.assertEqual(it["freight"], it["netwr"] * 150 // 10000)  # DAP 1.5 %
        self.assertEqual(it["mwsbp"], (it["netwr"] + it["freight"]) * 14 // 100)

    def test_export_procedure_has_no_tax(self):
        c = demo()
        cust = c.execute("SELECT * FROM customer WHERE kunnr='C1003'").fetchone()
        r = pricing.price_item(c, cust, order.area_of(c, "C1003"), "FG-3001", 1000, TODAY)
        self.assertEqual((r["proc"][-1], r["tax"]), ("VPRS", 0))


class Orders(unittest.TestCase):
    def test_quotation_to_order_flow(self):
        c = demo()
        qt = first(c, "QT", "C1004")
        self.assertEqual(qt["gbstk"], "B")            # 10 of 12 ordered: partly referenced
        r = order.create(c, dict(auart="OR", vgbel=qt["vbeln"], audat=TODAY), "T")
        self.assertEqual(c.execute("SELECT kwmeng FROM sd_vbap WHERE vbeln=?", (r["vbeln"],)).fetchone()[0],
                         2000)                        # only the open 2 are proposed
        self.assertEqual(first(c, "QT", "C1004")["gbstk"], "C")
        err(self, lambda: order.create(c, dict(auart="OR", vgbel=qt["vbeln"], audat=TODAY), "T"), "017")
        flow = [f["vbtyp"] for f in order.docflow(c, first(c, "OR", "C1004")["vbeln"])]
        for t in ("A", "B", "C", "J", "M", "H", "O"):
            self.assertIn(t, flow)

    def test_credit_block_and_release_rules(self):
        c = demo()
        o2 = c.execute("SELECT * FROM sd_vbak WHERE kunnr='C1004' AND auart='OR' ORDER BY vbeln").fetchall()[1]
        self.assertEqual(o2["cmgst"], "D")                            # blocked, then released
        r = order.create(c, dict(auart="OR", kunnr="C1004", audat=TODAY, bstnk="X",
                                 items=[dict(matnr="FG-3003", qty="20")]), "CLERK")
        self.assertTrue(any("Credit block" in m for m in r["messages"]))
        err(self, lambda: delivery.create(c, r["vbeln"], "T", TODAY), "460")
        err(self, lambda: order.release_credit(c, r["vbeln"], "CLERK"), "071")   # not by creator
        order.change(c, r["vbeln"], {"items": [{"posnr": 10, "abgru": "05"}]}, "CLERK")

    def test_partial_confirmation_backorder(self):
        c = demo()
        o3 = first(c, "OR", "C1001")
        sl = c.execute("SELECT * FROM sd_vbep WHERE vbeln=? ORDER BY etenr", (o3["vbeln"],)).fetchall()
        self.assertEqual(len(sl), 2)
        self.assertEqual(sum(s["bmeng"] for s in sl), 6000)
        self.assertGreater(sl[1]["edatu"], sl[0]["edatu"])            # rest from production order

    def test_exclusion_incompletion_and_references(self):
        c = demo()
        err(self, lambda: order.create(c, dict(auart="OR", kunnr="C1003", audat=TODAY, bstnk="X",
                                               items=[dict(matnr="FG-3003", qty="1")]), "T"), "022")
        r = order.create(c, dict(auart="OR", kunnr="C1001", audat=TODAY, items=[dict(matnr="TR-5001", qty="1")]), "T")
        self.assertIn("Customer purchase order number", r["incomplete"])
        err(self, lambda: delivery.create(c, r["vbeln"], "T", TODAY), "462")
        err(self, lambda: order.create(c, dict(auart="RE", kunnr="C1001", audat=TODAY, augru="101",
                                               items=[dict(matnr="TR-5001", qty="1")]), "T"), "012")


class ShippingBilling(unittest.TestCase):
    def test_goods_issue_cogs_and_equipment(self):
        c = demo()
        o1 = first(c, "OR", "C1004")
        h = c.execute("SELECT * FROM sd_likp WHERE vgbel=?", (o1["vbeln"],)).fetchone()
        self.assertEqual((h["wbstk"], h["fkstk"]), ("C", "C"))
        n = c.execute("SELECT COUNT(*) FROM sd_equi WHERE lieferung=?", (h["vbeln"],)).fetchone()[0]
        self.assertEqual(n, 10)                                         # serialised FG-3003
        e = c.execute("SELECT * FROM sd_equi WHERE lieferung=?", (h["vbeln"],)).fetchone()
        self.assertEqual(int(e["gwlen"][:4]) * 12 + int(e["gwlen"][5:7]),
                         int(e["inbdt"][:4]) * 12 + int(e["inbdt"][5:7]) + 24)

    def test_invoice_fi_and_copa(self):
        c = demo()
        o1 = first(c, "OR", "C1004")
        b = c.execute("SELECT * FROM billing WHERE aubel=? AND fkart='F2'", (o1["vbeln"],)).fetchone()
        lines = {r["hkont"]: r["dmbtr"] * (1 if r["shkzg"] == "S" else -1)
                 for r in c.execute("SELECT hkont, SUM(dmbtr) dmbtr, shkzg FROM acc_doc_item WHERE belnr=? "
                                    "GROUP BY hkont, shkzg", (b["belnr"],))}
        self.assertEqual(lines["140000"], b["netwr"] + b["mwsbk"])
        self.assertEqual(-lines["805000"], sum(r["freight"] for r in c.execute(
            "SELECT freight FROM billing_item WHERE vbeln=?", (b["vbeln"],))))
        cogs = c.execute("SELECT SUM(cogs) FROM billing_item WHERE vbeln=?", (b["vbeln"],)).fetchone()[0]
        copa = c.execute("SELECT SUM(vv030+vv040+vv050+vv051+vv060+vv061+vv070) FROM copa_item WHERE refdoc=?",
                         (b["vbeln"],)).fetchone()[0]
        self.assertEqual(copa, cogs)                                    # CO-PA cost = real COGS

    def test_cancellation_and_rebilling(self):
        c = demo()
        s1 = c.execute("SELECT * FROM billing WHERE fkart='S1'").fetchone()
        orig = c.execute("SELECT * FROM billing WHERE vbeln=?", (s1["sfakn"],)).fetchone()
        self.assertEqual(orig["cancelled"], 1)
        self.assertEqual(s1["netwr"], -orig["netwr"])
        n = c.execute("SELECT COUNT(*) FROM billing WHERE vgbel=? AND fkart='F2' AND cancelled=0",
                      (orig["vgbel"],)).fetchone()[0]
        self.assertEqual(n, 1)
        err(self, lambda: billing.cancel(c, orig["vbeln"], "T", TODAY), "045")

    def test_returns_credit_memo_and_debit_memo(self):
        c = demo()
        re_ = c.execute("SELECT * FROM billing WHERE fkart='RE'").fetchone()
        self.assertEqual(re_["netwr"], -760000)                         # no freight credited
        cost = c.execute("SELECT SUM(vv030+vv040+vv050+vv051+vv060+vv061+vv070) FROM copa_item WHERE refdoc=?",
                         (re_["vbeln"],)).fetchone()[0]
        self.assertLess(cost, 0)                                         # cost of sales reversed
        g2 = c.execute("SELECT netwr FROM billing WHERE fkart='G2'").fetchone()[0]
        l2 = c.execute("SELECT netwr FROM billing WHERE fkart='L2'").fetchone()[0]
        self.assertEqual((g2, l2), (-50000, 15000))
        cr = order.create(c, dict(auart="CR", vgbel=c.execute("SELECT vbeln FROM billing WHERE fkart='F2' AND "
                                                               "kunnr='C1002'").fetchone()[0], audat=TODAY,
                                  augru="201", items=[dict(matnr="FG-3001", qty="1", price="10")]), "T")
        err(self, lambda: billing.create(c, cr["vbeln"], "T", TODAY), "020")   # block 08
        err(self, lambda: order.change(c, cr["vbeln"], {"faksk": ""}, "T"), "060")

    def test_einvoice_hash(self):
        c = demo()
        e = c.execute("SELECT * FROM sd_einv LIMIT 1").fetchone()
        import hashlib
        import json
        doc = json.loads(e["payload"])
        self.assertEqual(hashlib.sha256(billing._ser("document", doc).encode()).hexdigest(), e["uuid"])
        self.assertTrue(e["status"].startswith("Valid"))


class Service(unittest.TestCase):
    def test_warranty_vs_paid_repair(self):
        c = demo()
        w, p = c.execute("SELECT * FROM sd_qmel ORDER BY qmnum").fetchall()
        self.assertEqual((w["warranty"], p["warranty"]), (1, 0))
        err(self, lambda: service.dp90(c, w["qmnum"], "T", TODAY), "002")
        b = c.execute("SELECT * FROM billing WHERE vbeln=?", (p["billed"],)).fetchone()
        self.assertEqual(b["netwr"], 2 * 35000 + 11000)                 # 2 h x 350 + part 110
        settled = c.execute("SELECT SUM(vv100) FROM copa_item WHERE aufnr=?", (w["aufnr"],)).fetchone()[0]
        self.assertGreater(settled, 0)                                   # warranty cost in CO-PA

    def test_samples_cost_to_copa(self):
        c = demo()
        fd = first(c, "FD", "C1002")
        h = c.execute("SELECT * FROM sd_likp WHERE vgbel=?", (fd["vbeln"],)).fetchone()
        cogs = c.execute("SELECT SUM(cogs) FROM sd_lips WHERE vbeln=?", (h["vbeln"],)).fetchone()[0]
        copa = c.execute("SELECT SUM(vv030+vv040+vv050+vv051+vv060+vv061+vv070), SUM(vv010) FROM copa_item WHERE "
                         "refdoc=?", (h["vbeln"],)).fetchone()
        self.assertEqual((copa[0], copa[1]), (cogs, 0))


class Reports(unittest.TestCase):
    def test_cockpit_and_books(self):
        c = demo()
        k = reports.cockpit(c, D1, TODAY)["kpi"]
        self.assertGreater(k["revenue"], 0)
        self.assertIsNotNone(k["otif"])
        from co.reports import reconcile
        from fi.reports import statements
        self.assertTrue(statements(c, T.year, T.month, T.month)["balanced"])
        self.assertTrue(reconcile(c, T.year, T.month, T.month)["ok"])


if __name__ == "__main__":
    unittest.main()
