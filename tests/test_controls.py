"""Financial controls and reversals (review phase 2): invoice cancellation (MR8M),
reset clearing (FBRA), depreciation reversal, duplicate invoices, goods-receipt
reversal guard, limits for returns and credits, re-runnable period-end programs,
reservation-aware reversals, exact partial billing, foreign currency purchasing,
cross-year production orders and the data consistency checker."""
import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fixture  # noqa: E402,F401  (fixed business date)
from mm import seed, util  # noqa: E402
from mm.db import connect  # noqa: E402
from mm.posting import cancel_document, post_goods_movement  # noqa: E402
from mm.util import MMError  # noqa: E402

T = fixture.T
TODAY = fixture.TODAY
U = "QA1"
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


def books_ok(test, c):
    from qa.invariants import check
    test.assertEqual(check(c), [])


def po_gr(c, lifnr="100005", matnr="SP-4002", qty="10", price="58.00", lgort="0004", bin_="S-02"):
    from pur import po
    e = po.create_po(c, {"lifnr": lifnr, "bedat": TODAY, "items": [
        {"matnr": matnr, "menge": qty, "netpr": price, "lgort": lgort}]}, U)
    po.release_all(c, e, U)
    g = post_goods_movement(c, {"budat": TODAY}, [{"bwart": "101", "ebeln": e, "ebelp": 10, "qty": qty,
                                                    "lgpla": bin_}], U)
    return e, g


def valuation(c, matnr, werks="1000"):
    return dict(c.execute("SELECT * FROM valuation WHERE matnr=? AND bwkey=?", (matnr, werks)).fetchone())


class InvoiceCancel(unittest.TestCase):
    def test_mr8m_moving_price_with_stock_restores_everything(self):
        from fi import ap
        c = demo()
        e, _ = po_gr(c)
        before = valuation(c, "SP-4002")
        b = ap.miro(c, {"ebeln": e, "budat": TODAY, "xblnr": "MR8M-1"},
                    [{"ebelp": 10, "qty": "10", "amount": "600"}], U)       # 20.00 price difference
        self.assertNotEqual(valuation(c, "SP-4002")["salk3"], before["salk3"])
        ap.cancel_invoice(c, b, T.year, TODAY, U)
        after = valuation(c, "SP-4002")
        self.assertEqual((after["salk3"], after["lbkum"]), (before["salk3"], before["lbkum"]))
        self.assertEqual(c.execute("SELECT remng, reewr FROM po_item WHERE ebeln=?", (e,)).fetchone()[0], 0)
        err(self, lambda: ap.cancel_invoice(c, b, T.year, TODAY, U), "152")
        books_ok(self, c)

    def test_mr8m_after_stock_consumed_goes_to_price_difference(self):
        from fi import ap
        c = demo()
        e, _ = po_gr(c, matnr="SP-4003", qty="5", price="95.00", bin_="S-03")
        b = ap.miro(c, {"ebeln": e, "budat": TODAY, "xblnr": "MR8M-2"},
                    [{"ebelp": 10, "qty": "5", "amount": "500"}], U)
        stock = valuation(c, "SP-4003")["lbkum"]
        post_goods_movement(c, {"budat": TODAY}, [{"bwart": "201", "matnr": "SP-4003", "werks": "1000",
                                                   "lgort": "0004", "qty": "%.3f" % (stock / 1000.0),
                                                   "kostl": "4200"}], U)
        r = ap.cancel_invoice(c, b, T.year, TODAY, U)
        prd = c.execute("SELECT COUNT(*) FROM acc_doc_item WHERE belnr=? AND ktosl='PRD'",
                        (r["belnr"],)).fetchone()[0]
        self.assertGreaterEqual(prd, 1)
        self.assertEqual(valuation(c, "SP-4003")["salk3"], 0)
        books_ok(self, c)

    def test_paid_invoice_needs_fbra_then_cancels(self):
        from fi import ap, gl
        c = demo()
        e, _ = po_gr(c, qty="2")
        b = ap.miro(c, {"ebeln": e, "budat": TODAY, "xblnr": "MR8M-3"}, [{"ebelp": 10, "qty": "2"}], U)
        it = c.execute("SELECT belnr, gjahr, buzei FROM acc_doc_item WHERE belnr=? AND koart='K'",
                       (b,)).fetchone()
        p = ap.pay(c, "K", "100005", TODAY, [tuple(it)], U)
        err(self, lambda: ap.cancel_invoice(c, b, T.year, TODAY, U), "151")
        r = gl.reset_clearing(c, p["belnr"], T.year, U, reverse_doc=True)
        self.assertTrue(r["reversal"])
        ap.cancel_invoice(c, b, T.year, TODAY, U)
        books_ok(self, c)


class Duplicates(unittest.TestCase):
    def test_same_vendor_reference_rejected(self):
        from fi import ap
        c = demo()
        e, _ = po_gr(c, qty="4")
        b = ap.miro(c, {"ebeln": e, "budat": TODAY, "xblnr": "DUP-9"}, [{"ebelp": 10, "qty": "2"}], U)
        err(self, lambda: ap.miro(c, {"ebeln": e, "budat": TODAY, "xblnr": " dup-9 "},
                                  [{"ebelp": 10, "qty": "2"}], U), "117")
        ap.cancel_invoice(c, b, T.year, TODAY, U)
        ap.miro(c, {"ebeln": e, "budat": TODAY, "xblnr": "DUP-9"}, [{"ebelp": 10, "qty": "2"}], U)
        err(self, lambda: ap.miro(c, {"ebeln": e, "budat": TODAY}, [{"ebelp": 10, "qty": "1"}], U), "116")

    def test_goods_receipt_reversal_blocked_after_invoice(self):
        from fi import ap
        c = demo()
        e, g = po_gr(c, qty="3")
        b = ap.miro(c, {"ebeln": e, "budat": TODAY, "xblnr": "GRG-1"}, [{"ebelp": 10, "qty": "3"}], U)
        err(self, lambda: cancel_document(c, g["mblnr"], g["mjahr"], TODAY, U), "033")
        ap.cancel_invoice(c, b, T.year, TODAY, U)
        cancel_document(c, g["mblnr"], g["mjahr"], TODAY, U)
        books_ok(self, c)


class Tolerance(unittest.TestCase):
    def test_price_variance_blocks_payment_until_mrbr(self):
        from fi import ap
        c = demo()
        e, _ = po_gr(c, qty="10")
        b = ap.miro(c, {"ebeln": e, "budat": TODAY, "xblnr": "TOL-1"},
                    [{"ebelp": 10, "qty": "10", "amount": "800"}], U)       # +38 %
        self.assertTrue(b.blocked)
        it = c.execute("SELECT belnr, gjahr, buzei FROM acc_doc_item WHERE belnr=? AND koart='K'",
                       (b,)).fetchone()
        err(self, lambda: ap.pay(c, "K", "100005", TODAY, [tuple(it)], U), "267")
        err(self, lambda: ap.release_blocked(c, b, T.year, U), "161")      # not the poster
        ap.release_blocked(c, b, T.year, "BOSS")
        ap.pay(c, "K", "100005", TODAY, [tuple(it)], U)
        books_ok(self, c)


class Depreciation(unittest.TestCase):
    def test_reverse_last_period_then_repost(self):
        from fi import aa
        c = demo()
        r = aa.depreciation_run(c, T.year, T.month, U, test=False)
        aa.reverse_depreciation(c, T.year, T.month, U)
        again = aa.depreciation_run(c, T.year, T.month, U, test=True)
        self.assertEqual(again["total"], r["total"])
        aa.depreciation_run(c, T.year, T.month, U, test=False)
        books_ok(self, c)


class SalesLimits(unittest.TestCase):
    def _invoice(self, c, qty="2"):
        from sd import billing, delivery, order
        v = order.create(c, dict(auart="OR", kunnr="C1001", audat=TODAY, vdatu=TODAY, bstnk="QA",
                                 items=[dict(matnr="FG-3001", qty=qty)]), U)["vbeln"]
        if c.execute("SELECT cmgst FROM sd_vbak WHERE vbeln=?", (v,)).fetchone()[0] == "B":
            order.release_credit(c, v, "CM")
        lf = delivery.create(c, v, U, TODAY)["vbeln"]
        delivery.post_gi(c, lf, U, TODAY)
        return v, billing.create(c, lf, U, TODAY)["vbeln"]

    def test_return_and_credit_limits(self):
        from sd import order
        c = demo()
        _, inv = self._invoice(c)
        mk = lambda auart, q, reason, price=None: order.create(c, dict(  # noqa: E731
            auart=auart, vgbel=inv, audat=TODAY, augru=reason,
            items=[dict(matnr="FG-3001", qty=q, vgbel=inv, vgpos=10, price=price)]), U)
        mk("RE", "1", "101")
        mk("RE", "1", "101")
        err(self, lambda: mk("RE", "1", "101"), "019")
        err(self, lambda: mk("CR", "1", "201", "1"), "023")                 # all returned already

    def test_reject_with_delivery_refused_then_delete_delivery(self):
        from sd import delivery, order
        c = demo()
        v = order.create(c, dict(auart="OR", kunnr="C1001", audat=TODAY, vdatu=TODAY, bstnk="QA",
                                 items=[dict(matnr="FG-3001", qty="3")]), U)["vbeln"]
        if c.execute("SELECT cmgst FROM sd_vbak WHERE vbeln=?", (v,)).fetchone()[0] == "B":
            order.release_credit(c, v, "CM")
        lf = delivery.create(c, v, U, TODAY)["vbeln"]
        err(self, lambda: order.change(c, v, {"items": [{"posnr": 10, "abgru": "02"}]}, U), "306")
        delivery.change(c, lf, {10: "1"}, U)
        self.assertEqual(c.execute("SELECT lfimg FROM sd_lips WHERE vbeln=?", (lf,)).fetchone()[0], 1000)
        delivery.delete(c, lf, U)
        order.change(c, v, {"items": [{"posnr": 10, "abgru": "02"}]}, U)

    def test_partial_billing_adds_up_exactly(self):
        from sd import billing, delivery, order
        c = demo()
        v = order.create(c, dict(auart="OR", kunnr="C1001", audat=TODAY, vdatu=TODAY, bstnk="QA",
                                 items=[dict(matnr="FG-3001", qty="3", price="100.01", disc="3.33")]),
                         U)["vbeln"]
        if c.execute("SELECT cmgst FROM sd_vbak WHERE vbeln=?", (v,)).fetchone()[0] == "B":
            order.release_credit(c, v, "CM")
        p = c.execute("SELECT kzwi1, kzwi2, freight FROM sd_vbap WHERE vbeln=?", (v,)).fetchone()
        tot = [0, 0, 0]
        for _ in range(3):
            lf = delivery.create(c, v, U, TODAY, items={10: "1"})["vbeln"]
            delivery.post_gi(c, lf, U, TODAY)
            inv = billing.create(c, lf, U, TODAY)["vbeln"]
            b = c.execute("SELECT gross, disc, freight FROM billing_item WHERE vbeln=?", (inv,)).fetchone()
            tot = [tot[0] + b[0], tot[1] + b[1], tot[2] + b[2]]
        self.assertEqual(tot, [p[0], p[1], p[2]])


class PeriodEnd(unittest.TestCase):
    def test_vat_settlement_once_and_payment_run_status(self):
        from fi import ap, gl
        c = demo()
        d1 = T.replace(day=1).isoformat()
        gl.vat_settlement(c, d1, TODAY, TODAY, U)
        err(self, lambda: gl.vat_settlement(c, d1, TODAY, TODAY, U), "010")
        nxt = (T + datetime.timedelta(days=40)).isoformat()
        ap.payment_run(c, TODAY, "QA9", nxt, U)
        ap.payment_run(c, TODAY, "QA9", nxt, U, execute=True)
        err(self, lambda: ap.payment_run(c, TODAY, "QA9", nxt, U), "002")
        books_ok(self, c)

    def test_carry_forward_and_trial_balance(self):
        from fi import gl
        from fi.reports import trial_balance
        c = demo()
        err(self, lambda: gl.carry_forward(c, T.year, U), "210")
        r = gl.carry_forward(c, T.year - 1, U, test=True)
        self.assertEqual(r["to_year"], T.year)
        self.assertAlmostEqual(sum(x["closing"] for x in trial_balance(c, T.year, 1, T.month)), 0, 2)


class Reservations(unittest.TestCase):
    def test_picking_reversal_reopens_reservation(self):
        from pp import order
        c = demo()
        a = order.create(c, {"auart": "PP01", "matnr": "FG-3001", "gamng": "2", "gstrp": TODAY,
                             "lgort": "0003", "ops": [dict(arbpl="WC-ASSY", ltxa1="x", vgw="1")]}, U)
        order.release(c, a, U, TODAY)
        picks = [dict(rsnum=r["rsnum"], rspos=r["rspos"]) for r in order.picking_list(c) if r["aufnr"] == a]
        g = order.post_picking(c, picks, TODAY, U)
        cancel_document(c, g["mblnr"], g["mjahr"], TODAY, U)
        self.assertEqual(c.execute("SELECT SUM(enmng) FROM pp_resb WHERE aufnr=?", (a,)).fetchone()[0], 0)
        self.assertEqual(len([r for r in order.picking_list(c) if r["aufnr"] == a]), len(picks))
        books_ok(self, c)


class ForeignCurrency(unittest.TestCase):
    def test_usd_po_receipt_invoice_payment(self):
        from fi import ap, gl
        c = demo()
        gl.set_rate(c, "USD", TODAY, "50.00")
        e, g = po_gr(c, lifnr="300001", matnr="RM-1004", qty="10", price="10.00", lgort="0001",
                     bin_="C-02-02")
        self.assertEqual(c.execute("SELECT waers FROM po_header WHERE ebeln=?", (e,)).fetchone()[0], "USD")
        gr = c.execute("SELECT dmbtr FROM acc_doc_item WHERE belnr=? AND hkont='191100'",
                       (g["belnr"],)).fetchone()[0]
        self.assertEqual(gr, 500000)                                         # 100 USD x 50
        b = ap.miro(c, {"ebeln": e, "budat": TODAY, "xblnr": "USD-1"}, [{"ebelp": 10, "qty": "10"}], U)
        h = c.execute("SELECT waers FROM acc_doc WHERE belnr=?", (b,)).fetchone()
        self.assertEqual(h[0], "USD")
        v = c.execute("SELECT wrbtr, dmbtr FROM acc_doc_item WHERE belnr=? AND koart='K'", (b,)).fetchone()
        self.assertEqual(v[0], 11400)                                        # 114.00 USD incl. VAT
        it = c.execute("SELECT belnr, gjahr, buzei FROM acc_doc_item WHERE belnr=? AND koart='K'",
                       (b,)).fetchone()
        ap.pay(c, "K", "300001", TODAY, [tuple(it)], U)
        books_ok(self, c)


class CrossYear(unittest.TestCase):
    def test_order_released_in_december_closed_in_january(self):
        from co import period_end
        from pp import order
        old = util.set_clock(datetime.date(2026, 12, 15))
        try:
            c = connect(":memory:")
            seed.seed(c)
            from fi import gl
            gl.set_periods(c, 2026, 11, 2027, 12)
            a = order.create(c, {"auart": "PP01", "matnr": "FG-3001", "gamng": "2", "gstrp": "2026-12-15",
                                 "lgort": "0003", "ops": [dict(arbpl="WC-ASSY", ltxa1="x", vgw="1")]}, U)
            order.release(c, a, U, "2026-12-15")
            picks = [dict(rsnum=r["rsnum"], rspos=r["rspos"]) for r in order.picking_list(c)
                     if r["aufnr"] == a]
            order.post_picking(c, picks, "2026-12-15", U)
            util.set_clock(datetime.date(2027, 1, 10))
            post_goods_movement(c, {"budat": "2027-01-10"}, [{"bwart": "101", "aufnr": a, "qty": "2",
                                                              "lgort": "0003", "lgpla": "F-03"}], U)
            order.teco(c, a, U)
            period_end.variances(c, 2027, 1, aufnr=a, user=U)
            period_end.settle(c, 2027, 1, aufnr=a, user=U)
            bal = c.execute("SELECT COALESCE(SUM(wtg),0) FROM co_item WHERE objnr=? AND wrttp='04'",
                            ("OR" + a,)).fetchone()[0]
            self.assertEqual(bal, 0)                    # December material included
            from qa.invariants import check
            self.assertEqual(check(c), [])
        finally:
            util.set_clock(old)


class Consistency(unittest.TestCase):
    def test_demo_data_is_consistent(self):
        from qa.invariants import check
        self.assertEqual(check(demo(), TODAY), [])


if __name__ == "__main__":
    unittest.main()
