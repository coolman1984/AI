"""End-to-end process tests (UAT scripts).

Each test walks one business process through all modules on a freshly seeded
system - the same way a key user executes a test script - and checks the
integration points: document flow, stock, FI, CO and CO-PA. The test ids are
referenced by the QA catalog (qa/catalog.py) and shown in ZQA_TEST / ZLMS.
"""
import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mm import seed  # noqa: E402
from mm.db import connect  # noqa: E402
from mm.posting import post_goods_movement  # noqa: E402
from mm.util import MMError  # noqa: E402

U = "QA_TESTER"
T = datetime.date.today()
TODAY = T.isoformat()
_DB = {}


def demo():
    if "c" not in _DB:
        c = connect(":memory:")
        seed.seed(c)
        _DB["c"] = c
    return _DB["c"]


def books_ok(test, c):
    from co.reports import reconcile
    from fi.reports import statements, trial_balance
    from mm.reports import consistency_check
    test.assertTrue(statements(c, T.year, T.month, T.month)["balanced"], "balance sheet")
    tb = trial_balance(c, T.year, 1, T.month)
    test.assertAlmostEqual(sum(r["closing"] for r in tb), 0, 2, "trial balance")
    test.assertTrue(reconcile(c, T.year, T.month, T.month)["ok"], "FI = CO-PA")
    test.assertTrue(consistency_check(c)["ok"], "stock = G/L")


def stock(c, matnr, werks="1000"):
    return c.execute("SELECT COALESCE(SUM(qty),0) FROM quant WHERE matnr=? AND werks=? AND insmk='U'",
                     (matnr, werks)).fetchone()[0]


class E2E_P2P(unittest.TestCase):
    """Procure to pay: PO -> release -> GR -> 3-way match invoice -> payment."""

    def test_procure_to_pay_cycle(self):
        from fi import ap
        from pur import po
        c = demo()
        before = stock(c, "SP-4002")
        e = po.create_po(c, {"lifnr": "100005", "bedat": TODAY, "ekgrp": "001", "items": [
            {"matnr": "SP-4002", "menge": "20", "netpr": "58.00", "lgort": "0004"}]}, U)
        po.release_all(c, e, U)
        post_goods_movement(c, {"budat": TODAY, "xblnr": "QA-DN-1"},
                            [{"bwart": "101", "ebeln": e, "ebelp": 10, "qty": "20", "lgpla": "S-02"}], U)
        self.assertEqual(stock(c, "SP-4002") - before, 20000)
        with self.assertRaises(MMError):          # invoice above received quantity is blocked
            ap.miro(c, {"ebeln": e, "bldat": TODAY, "budat": TODAY, "xblnr": "QA-INV-0",
                        "mwskz": "V1"}, [{"ebelp": 10, "qty": "25"}], U)
        inv = ap.miro(c, {"ebeln": e, "bldat": TODAY, "budat": TODAY, "xblnr": "QA-INV-1",
                          "mwskz": "V1"}, [{"ebelp": 10, "qty": "20"}], U)
        belnr = inv["belnr"] if isinstance(inv, dict) else inv
        it = c.execute("SELECT belnr, gjahr, buzei FROM acc_doc_item WHERE belnr=? AND hkont IN "
                       "(SELECT hkont FROM acc_doc_item WHERE belnr=? AND koart='K') AND koart='K'",
                       (belnr, belnr)).fetchone()
        ap.pay(c, "K", "100005", TODAY, [(it["belnr"], it["gjahr"], it["buzei"])], U, tcode="F-53")
        self.assertFalse([x for x in ap.open_items(c, "K", "100005") if x["belnr"] == belnr])
        books_ok(self, c)


class E2E_PlanToProduce(unittest.TestCase):
    """Plan to produce: order -> release -> picking -> confirmation -> GR -> TECO -> settlement."""

    def test_production_order_cycle(self):
        from pp import order
        c = demo()
        before = stock(c, "FG-3001")
        a = order.create(c, {"auart": "PP01", "matnr": "FG-3001", "gamng": "2", "gstrp": TODAY,
                             "lgort": "0003", "ops": [dict(arbpl="WC-ASSY", ltxa1="Assemble cabinet",
                                                           vgw="1")]}, U)
        with self.assertRaises(MMError):          # no confirmation before release
            order.confirm(c, a, "0010", "2", budat=TODAY, user=U)
        order.release(c, a, U, TODAY)
        picks = [dict(rsnum=r["rsnum"], rspos=r["rspos"]) for r in order.picking_list(c) if r["aufnr"] == a]
        if picks:
            order.post_picking(c, picks, TODAY, U)
        ops = c.execute("SELECT vornr FROM pp_oper WHERE aufnr=? ORDER BY vornr", (a,)).fetchall()
        for i, op in enumerate(ops):
            order.confirm(c, a, op["vornr"], "2", budat=TODAY, final=(i == len(ops) - 1), user=U)
        o = c.execute("SELECT * FROM orders WHERE aufnr=?", (a,)).fetchone()
        if stock(c, "FG-3001") - before < 2000:   # no automatic GR -> post 101 against the order
            post_goods_movement(c, {"budat": TODAY, "bktxt": "QA GR"},
                                [{"bwart": "101", "aufnr": a, "qty": "2", "lgort": "0003", "lgpla": "F-03"}], U)
        self.assertEqual(stock(c, "FG-3001") - before, 2000)
        order.teco(c, a, U)
        self.assertIn("TECO", order.detail(c, a)["sysst"])
        from co import period_end            # month-end for this order: overhead, variance, settlement
        period_end.overhead(c, T.year, T.month, aufnr=a, user=U)
        period_end.variances(c, T.year, T.month, aufnr=a, user=U)
        period_end.settle(c, T.year, T.month, aufnr=a, user=U)
        self.assertTrue(o)
        books_ok(self, c)


class E2E_O2C(unittest.TestCase):
    """Order to cash: order -> delivery -> goods issue -> invoice -> e-invoice -> payment."""

    def test_order_to_cash_cycle(self):
        from fi.ap import open_items, pay
        from sd import billing, delivery, order
        c = demo()
        before = stock(c, "FG-3001")
        r = order.create(c, dict(auart="OR", kunnr="C1001", audat=TODAY, vdatu=TODAY, bstnk="QA-PO-1",
                                 items=[dict(matnr="FG-3001", qty="2")]), U)
        v = r["vbeln"]
        if c.execute("SELECT cmgst FROM sd_vbak WHERE vbeln=?", (v,)).fetchone()[0] == "B":
            with self.assertRaises(MMError):      # creator may not release his own block
                order.release_credit(c, v, U)
            order.release_credit(c, v, "CREDITMGR")
        lf = delivery.create(c, v, U, TODAY)["vbeln"]
        delivery.pick(c, lf)
        delivery.post_gi(c, lf, U, TODAY)
        self.assertEqual(before - stock(c, "FG-3001"), 2000)
        inv = billing.create(c, lf, U, TODAY)["vbeln"]
        e = billing.einvoice(c, inv, U)
        self.assertTrue(e)
        flow = {f["vbtyp"] for f in order.docflow(c, v)}
        for t in ("C", "J", "M"):
            self.assertIn(t, flow)
        b = c.execute("SELECT belnr FROM billing WHERE vbeln=?", (inv,)).fetchone()["belnr"]
        it = c.execute("SELECT belnr, gjahr, buzei FROM acc_doc_item WHERE belnr=? AND koart='D'",
                       (b,)).fetchone()
        pay(c, "D", "C1001", TODAY, [(it["belnr"], it["gjahr"], it["buzei"])], U, tcode="F-28")
        self.assertFalse([x for x in open_items(c, "D", "C1001") if x["belnr"] == b])
        books_ok(self, c)


class E2E_R2R(unittest.TestCase):
    """Record to report: journal entry -> period lock -> statements."""

    def test_record_to_report(self):
        from fi import document
        from fi.reports import statements
        c = demo()
        doc = document.write(c, "SA", TODAY, U, None, "QA accrual", [
            dict(hkont="475000", amount=100000, kostl="4200"), dict(hkont="113100", amount=-100000)])
        self.assertTrue(doc)
        with self.assertRaises(MMError):          # unbalanced document is rejected
            document.write(c, "SA", TODAY, U, None, "QA wrong", [
                dict(hkont="475000", amount=100, kostl="4200"), dict(hkont="113100", amount=-90)])
        with self.assertRaises(MMError):          # reconciliation account not directly
            document.write(c, "SA", TODAY, U, None, "QA recon", [
                dict(hkont="160000", amount=100), dict(hkont="113100", amount=-100)])
        self.assertTrue(statements(c, T.year, 1, T.month)["balanced"])
        books_ok(self, c)


class E2E_Control(unittest.TestCase):
    """Controlling: actuals on cost centers -> closing -> FI = CO -> CO-PA result."""

    def test_period_close_reconciles(self):
        from co.reports import cockpit, ke30, reconcile
        c = demo()
        y, p = (T.replace(day=1) - datetime.timedelta(days=1)).year, (T.replace(day=1) - datetime.timedelta(days=1)).month
        self.assertTrue(reconcile(c, y, p, p)["ok"])
        self.assertTrue(reconcile(c, T.year, T.month, T.month)["ok"])
        self.assertTrue(ke30(c, y, p, p))
        self.assertTrue(cockpit(c, y, p))


class E2E_MasterData(unittest.TestCase):
    """Master data: governance checks feed every process."""

    def test_master_data_quality(self):
        from md.reports import cockpit
        c = demo()
        k = cockpit(c)
        self.assertTrue(k)
        for m in ("FG-3001", "FG-3003", "RM-1001"):
            self.assertTrue(c.execute("SELECT 1 FROM material_plant WHERE matnr=? AND werks='1000'",
                                      (m,)).fetchone())


if __name__ == "__main__":
    unittest.main()
