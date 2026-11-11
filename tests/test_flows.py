"""Process links (review phase 4): customer orders in MRP, PIR consumption, operation
sequence and scrap reasons, full sales-order change, commitments, foreign-currency
customer invoices."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fixture  # noqa: E402,F401  (fixed business date)
from mm import seed  # noqa: E402
from mm.db import connect  # noqa: E402
from mm.posting import post_goods_movement  # noqa: E402
from mm.util import MMError  # noqa: E402

T, TODAY, U = fixture.T, fixture.TODAY, "QA2"
_DB = {}


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


def stock(c, m):
    return c.execute("SELECT COALESCE(SUM(qty),0) FROM quant WHERE matnr=? AND werks='1000' AND insmk='U'",
                     (m,)).fetchone()[0]


def sales_order(c, matnr, qty, kunnr="C1001"):
    from sd import order
    v = order.create(c, dict(auart="OR", kunnr=kunnr, audat=TODAY, vdatu=TODAY, bstnk="QA",
                             items=[dict(matnr=matnr, qty=qty)]), U)["vbeln"]
    if c.execute("SELECT cmgst FROM sd_vbak WHERE vbeln=?", (v,)).fetchone()[0] == "B":
        order.release_credit(c, v, "CM")
    return v


class SalesInMrp(unittest.TestCase):
    def test_backorder_creates_planned_order_and_consumes_pir(self):
        from pp import planning
        c = demo()
        pir_before = sum(p["open"] for p in planning.pirs(c, "FG-3001") if p["month"] == TODAY[:7])
        need = stock(c, "FG-3001") // 1000 + 50
        v = sales_order(c, "FG-3001", str(need))
        md = planning.stock_requirements(c, "FG-3001", today=TODAY)
        self.assertTrue(any(l["typ"] == "VC" and l["ref"] == v for l in md["lines"]))
        pir_after = sum(p["open"] for p in planning.pirs(c, "FG-3001") if p["month"] == TODAY[:7])
        self.assertEqual(pir_before - pir_after, min(pir_before, need * 1000))   # strategy 40
        planning.mrp_run(c, U, today=TODAY)
        planned = c.execute("SELECT COALESCE(SUM(gsmng),0) FROM pp_plaf WHERE matnr='FG-3001' AND conv='' "
                            "AND pedtr<=?", (TODAY,)).fetchone()[0]
        self.assertGreaterEqual(planned, 50000)


class ShopFloor(unittest.TestCase):
    def _order(self, c):
        from pp import order
        a = order.create(c, {"auart": "PP01", "matnr": "FG-3003", "gamng": "4", "gstrp": TODAY,
                             "lgort": "0003"}, U)
        order.release(c, a, U, TODAY)
        return a

    def test_operation_sequence_and_scrap_reason(self):
        from pp import order
        c = demo()
        a = self._order(c)
        ops = [r["vornr"] for r in c.execute("SELECT vornr FROM pp_oper WHERE aufnr=? ORDER BY vornr", (a,))]
        err(self, lambda: order.confirm(c, a, ops[-1], "1", budat=TODAY, user=U), "006")
        err(self, lambda: order.confirm(c, a, ops[0], "2", "1", budat=TODAY, user=U), "007")
        order.confirm(c, a, ops[0], "2", "1", budat=TODAY, user=U, grund="01")
        err(self, lambda: order.confirm(c, a, ops[-1], "3", budat=TODAY, user=U), "006")

    def test_picking_cannot_exceed_reservation(self):
        from pp import order
        c = demo()
        a = self._order(c)
        r = [x for x in order.picking_list(c) if x["aufnr"] == a]
        if not r:
            self.skipTest("no picking components")
        err(self, lambda: order.post_picking(c, [dict(rsnum=r[0]["rsnum"], rspos=r[0]["rspos"],
                                                      qty="%.3f" % (r[0]["open"] / 1000.0 + 1))], TODAY, U), "102")


class SalesOrderChange(unittest.TestCase):
    def test_va02_quantity_price_add_delete(self):
        from sd import order
        c = connect(":memory:")            # own system: other tests consume the free stock
        seed.seed(c)
        v = sales_order(c, "FG-3001", "2")
        order.change(c, v, {"items": [{"posnr": 10, "qty": "3", "price": "2600"}],
                            "new_items": [{"matnr": "FG-3002", "qty": "1"}]}, U)
        it = c.execute("SELECT kwmeng, netpr FROM sd_vbap WHERE vbeln=? AND posnr=10", (v,)).fetchone()
        self.assertEqual((it[0], it[1]), (3000, 260000))
        self.assertEqual(c.execute("SELECT COUNT(*) FROM sd_vbap WHERE vbeln=?", (v,)).fetchone()[0], 2)
        order.change(c, v, {"items": [{"posnr": 20, "delete": True}]}, U)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM sd_vbap WHERE vbeln=?", (v,)).fetchone()[0], 1)
        from sd import delivery
        lf = delivery.create(c, v, U, TODAY)["vbeln"]
        delivery.post_gi(c, lf, U, TODAY)
        err(self, lambda: order.change(c, v, {"items": [{"posnr": 10, "qty": "1"}]}, U), "308")
        err(self, lambda: order.change(c, v, {"items": [{"posnr": 10, "delete": True}]}, U), "307")


class Commitments(unittest.TestCase):
    def test_account_assigned_po_is_committed_until_receipt(self):
        from co.reports import commitments
        from pur import po
        c = demo()
        e = po.create_po(c, {"lifnr": "100005", "bedat": TODAY, "items": [
            {"txz01": "Gearbox inspection", "matkl": "SERVICE", "meins": "AU", "menge": "1",
             "knttp": "K", "kostl": "4200", "sakto": "475000", "netpr": "1500"}]}, U)
        po.release_all(c, e, U)
        cm = [x for x in commitments(c, "KS4200") if x["refbn"] == e]
        self.assertEqual(cm[0]["amount"], 150000)
        post_goods_movement(c, {"budat": TODAY}, [{"bwart": "101", "ebeln": e, "ebelp": 10, "qty": "1"}], U)
        self.assertEqual([x for x in commitments(c, "KS4200") if x["refbn"] == e], [])


class CustomerCurrency(unittest.TestCase):
    def test_usd_customer_invoice_and_payment(self):
        from fi import gl
        from fi.ap import pay
        from md import partner
        from qa.invariants import check
        from sd import billing, delivery
        c = demo()
        gl.set_rate(c, "USD", TODAY, "50.00")
        partner.change_customer(c, "C1003", {"waers": "USD"}, U)
        v = sales_order(c, "FG-3001", "1", kunnr="C1003")
        lf = delivery.create(c, v, U, TODAY)["vbeln"]
        delivery.post_gi(c, lf, U, TODAY)
        inv = billing.create(c, lf, U, TODAY)["vbeln"]
        b = c.execute("SELECT belnr, waerk FROM billing WHERE vbeln=?", (inv,)).fetchone()
        self.assertEqual(b["waerk"], "USD")
        it = c.execute("SELECT belnr, gjahr, buzei, wrbtr, dmbtr FROM acc_doc_item WHERE belnr=? AND koart='D'",
                       (b["belnr"],)).fetchone()
        self.assertEqual(it["wrbtr"] * 50, it["dmbtr"])          # exact at rate 50 (export, no tax)
        pay(c, "D", "C1003", TODAY, [(it["belnr"], it["gjahr"], it["buzei"])], U, tcode="F-28")
        self.assertEqual(check(c), [])

    def test_usd_price_is_kept_exactly_from_order_to_invoice(self):
        """BUG-010: a dollar price (VK11 in USD) stays the same dollar amount on the invoice,
        the local amount follows the exchange rate of the billing date."""
        from fi import gl
        from md import partner
        from qa.invariants import check
        from sd import billing, delivery, order, pricing
        c = demo()
        gl.set_rate(c, "USD", TODAY, "50.00")
        partner.change_customer(c, "C1002", {"waers": "USD"}, U)
        pricing.save_condition(c, "PR00", "A305", dict(kunnr="C1002", matnr="FG-3002", kbetr="123.45",
                                                       konwa="USD", datab=TODAY), U)
        err = None
        try:
            pricing.save_condition(c, "PR00", "A305", dict(kunnr="C1002", matnr="FG-3002", kbetr="1",
                                                           konwa="XYZ", datab=TODAY), U)
        except MMError as e:
            err = e.msg_no
        self.assertEqual(err, "011")
        v = sales_order(c, "FG-3002", "3", kunnr="C1002")
        k = order.detail(c, v)
        self.assertEqual((k["waerk"], k["kursk"]), ("USD", 5000000))
        p = k["items"][0]
        self.assertEqual(p["kzwi1_fc"], 3 * 12345)                       # USD price x quantity, exact
        self.assertEqual(p["kzwi1"], 3 * 12345 * 50)                     # local value at the order rate
        net_fc = p["kzwi1_fc"] - p["kzwi2_fc"] + p["freight_fc"]
        gl.set_rate(c, "USD", TODAY, "51.37")                            # the rate moves before billing
        lf = delivery.create(c, v, U, TODAY)["vbeln"]
        delivery.post_gi(c, lf, U, TODAY)
        inv = billing.create(c, lf, U, TODAY)["vbeln"]
        b = c.execute("SELECT * FROM billing WHERE vbeln=?", (inv,)).fetchone()
        self.assertEqual((b["waerk"], b["kurrf"], b["netwr_fc"]), ("USD", 5137000, net_fc))
        it = c.execute("SELECT wrbtr, dmbtr FROM acc_doc_item WHERE belnr=? AND koart='D'", (b["belnr"],)).fetchone()
        self.assertEqual(it["wrbtr"], net_fc + p["mwsbp_fc"])            # the customer owes the order dollars
        self.assertEqual(it["dmbtr"], round((net_fc + p["mwsbp_fc"]) * 51.37))
        from mm import forms
        html = forms.render(c, "INVOICE", inv)                           # the printed invoice shows the dollars
        self.assertIn("<b>Total %s USD</b>" % "{:,.2f}".format((net_fc + p["mwsbp_fc"]) / 100.0), html)
        self.assertEqual(check(c), [])


if __name__ == "__main__":
    unittest.main()
