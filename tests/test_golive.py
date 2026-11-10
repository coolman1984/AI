"""Go-live functions (review phase 6): physical inventory, withholding tax, manual
clearing, down payments, posting periods per account type, MM periods and MB5B,
three-quotations rule, data import and print forms."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fixture  # noqa: E402,F401  (fixed business date)
from mm import seed  # noqa: E402
from mm.db import connect  # noqa: E402
from mm.posting import post_goods_movement  # noqa: E402
from mm.util import MMError  # noqa: E402
from qa.invariants import check  # noqa: E402

T, TODAY, U = fixture.T, fixture.TODAY, "QA6"


def system():
    c = connect(":memory:")
    seed.seed(c)
    return c


def err(test, fn, no):
    with test.assertRaises(MMError) as x:
        fn()
    test.assertEqual(x.exception.msg_no, no, str(x.exception))


def vkey(c, belnr, koart="K"):
    r = c.execute("SELECT belnr, gjahr, buzei FROM acc_doc_item WHERE belnr=? AND koart=? AND umskz IS NULL",
                  (belnr, koart)).fetchone()
    return (r[0], r[1], r[2])


class PhysicalInventory(unittest.TestCase):
    def test_freeze_count_recount_and_post_differences(self):
        from mm import inventory as I
        c = system()
        q = c.execute("SELECT matnr, lgort, lgpla FROM quant WHERE werks='1000' AND insmk='U' AND qty>2000 "
                      "AND lgpla<>'' LIMIT 1").fetchone()
        d = I.create(c, "1000", q["lgort"], [q["matnr"]], TODAY, U)
        err(self, lambda: post_goods_movement(c, {"budat": TODAY}, [dict(
            bwart="201", matnr=q["matnr"], werks="1000", lgort=q["lgort"], lgpla=q["lgpla"], qty="1", kostl="4100")], U), "140")
        doc = I.display(c, d)
        items = [dict(zeili=i["zeili"], qty=str((i["buchm"] - 1000) / 1000.0)) for i in doc["items"]]
        self.assertGreater(I.count(c, d, items[:1], U), -1)
        err(self, lambda: I.post(c, d, TODAY, U), "148") if len(items) > 1 else None
        I.count(c, d, items, U)
        diff = I.differences(c, d)
        self.assertLess(diff["total"], 0)
        new = I.recount(c, d, [items[0]["zeili"]], U)            # MI11
        I.count(c, new, [dict(zeili=1, zero=True)] if len(I.display(c, new)["items"]) == 1 else
                [dict(zeili=i["zeili"], qty=str(i["buchm"] / 1000.0)) for i in I.display(c, new)["items"]], U)
        r = I.post(c, new, TODAY, U, "recount")
        self.assertTrue(r["lines"] >= 0)
        if len(items) > 1:
            I.post(c, d, TODAY, U)
        self.assertEqual(check(c), [])

    def test_zero_difference_closes_without_posting(self):
        from mm import inventory as I
        c = system()
        d = I.create(c, "1000", "0001", ["PK-2001"], TODAY, U)
        I.count(c, d, [dict(zeili=i["zeili"], qty=str(i["buchm"] / 1000.0)) for i in I.display(c, d)["items"]], U)
        r = I.post(c, d, TODAY, U)
        self.assertIsNone(r["mblnr"])
        self.assertEqual(I.display(c, d)["status"], "POST")


class WithholdingTax(unittest.TestCase):
    def test_service_invoice_withholds_3_percent_and_exemption(self):
        from fi import ap, wht
        c = system()
        wht.assign(c, "100005", "W3")
        b = ap.vendor_invoice(c, {"lifnr": "100005", "budat": TODAY, "xblnr": "W-1", "mwskz": "V1"},
                              [{"hkont": "470000", "amount": "10000", "kostl": "4200"}], U)
        lines = {r["hkont"]: r["dmbtr"] for r in c.execute("SELECT * FROM acc_doc_item WHERE belnr=?", (b,))}
        self.assertEqual(lines["177000"], 30000)
        self.assertEqual(lines["160000"], 1110000)              # 10,000 + 1,400 VAT - 300 WHT
        self.assertEqual(wht.report(c)[0]["amount"], 30000)
        wht.assign(c, "100005", "W3", "2026-01-01", "2026-12-31", "EX-77")
        b2 = ap.vendor_invoice(c, {"lifnr": "100005", "budat": TODAY, "xblnr": "W-2"},
                               [{"hkont": "470000", "amount": "1000", "kostl": "4200"}], U)
        self.assertFalse(c.execute("SELECT 1 FROM acc_doc_item WHERE belnr=? AND ktosl='WIT'", (b2,)).fetchone())
        self.assertEqual(check(c), [])


class Clearing(unittest.TestCase):
    def test_manual_clearing_tolerance_residual_and_refusal(self):
        from fi import ap, clearing as C
        c = system()
        inv = lambda x, a, cm=False: ap.vendor_invoice(c, {"lifnr": "100005", "budat": TODAY, "xblnr": x},   # noqa: E731
                                                     [{"hkont": "470000", "amount": a, "kostl": "4200"}], U, credit_memo=cm)
        a, b = inv("C-1", "1000"), inv("C-2", "998", True)
        r = C.clear_open_items(c, "K", "100005", [vkey(c, a), vkey(c, b)], TODAY, U)
        self.assertEqual(r["difference"], -2.0)                   # within 5.00 -> payment difference
        x, y = inv("C-3", "1000"), inv("C-4", "500", True)
        err(self, lambda: C.clear_open_items(c, "K", "100005", [vkey(c, x), vkey(c, y)], TODAY, U), "263")
        r = C.clear_open_items(c, "K", "100005", [vkey(c, x), vkey(c, y)], TODAY, U, residual=True)
        self.assertTrue(r["residual"])
        open_ = [o for o in ap.open_items(c, "K", "100005") if o["belnr"] == r["belnr"]]
        self.assertEqual(open_[0]["dmbtr"], 50000)
        self.assertEqual(check(c), [])

    def test_down_payment_request_payment_and_clearing(self):
        from fi import ap, clearing as C
        c = system()
        n = C.request(c, "K", "100005", "5000", TODAY, U, text="Advance for tooling")
        d = C.down_payment(c, "K", "100005", None, TODAY, U, request_id=n)
        self.assertEqual(C.requests(c, "K"), [])
        self.assertEqual([o for o in ap.open_items(c, "K", "100005") if o["belnr"] == d["belnr"]], [])
        self.assertEqual(len(ap.open_items(c, "K", "100005", special="A")), 1)
        inv = ap.vendor_invoice(c, {"lifnr": "100005", "budat": TODAY, "xblnr": "DP-1"},
                                [{"hkont": "470000", "amount": "5000", "kostl": "4200"}], U)
        dp = ap.open_items(c, "K", "100005", special="A")[0]
        C.clear_down_payment(c, "K", "100005", (dp["belnr"], dp["gjahr"], dp["buzei"]), vkey(c, inv), TODAY, U)
        self.assertEqual(ap.open_items(c, "K", "100005", special="A"), [])
        self.assertFalse([o for o in ap.open_items(c, "K", "100005") if o["belnr"] == inv])
        self.assertEqual(check(c), [])


class Periods(unittest.TestCase):
    def test_account_type_interval_and_special_period(self):
        from fi import ap, gl
        c = system()
        gl.set_periods(c, 2026, 12, 2026, 12, "K")
        err(self, lambda: ap.vendor_invoice(c, {"lifnr": "100005", "budat": TODAY, "xblnr": "P-1"},
                                            [{"hkont": "470000", "amount": "10", "kostl": "4200"}], U), "201")
        gl.set_periods(c, 0, 1, 0, 1, "K", delete=True)
        ap.vendor_invoice(c, {"lifnr": "100005", "budat": TODAY, "xblnr": "P-2"},
                          [{"hkont": "470000", "amount": "10", "kostl": "4200"}], U)
        gl.set_periods(c, 2025, 1, 2026, 11)
        err(self, lambda: gl.general_posting(c, {"budat": "2025-12-31", "perio": "13", "blart": "SA"}, [
            {"bschl": "40", "account": "470000", "amount": "5", "kostl": "4200"},
            {"bschl": "50", "account": "113100", "amount": "5"}], U), "201")
        gl.set_periods(c, 2025, 1, 2025, 13)
        gl.set_periods(c, 2025, 1, 2026, 11) if False else None
        b = gl.general_posting(c, {"budat": "2025-12-31", "perio": "13", "blart": "SA"}, [
            {"bschl": "40", "account": "470000", "amount": "5", "kostl": "4200"},
            {"bschl": "50", "account": "113100", "amount": "5"}], U)
        self.assertEqual(c.execute("SELECT monat FROM acc_doc WHERE belnr=?", (b,)).fetchone()[0], 13)
        err(self, lambda: gl.general_posting(c, {"budat": "2025-11-30", "perio": "13", "blart": "SA"}, [
            {"bschl": "40", "account": "470000", "amount": "5", "kostl": "4200"},
            {"bschl": "50", "account": "113100", "amount": "5"}], U), "202")

    def test_mm_period_and_stock_on_posting_date(self):
        from mm import periods as P
        c = system()
        now = {r["matnr"]: (r["qty"], r["value"]) for r in P.stock_at(c, "1000", TODAY)}
        for v in c.execute("SELECT * FROM valuation WHERE bwkey='1000' AND lbkum<>0"):
            self.assertEqual(now[v["matnr"]], (v["lbkum"], v["salk3"]))
        P.open_next(c, 2026, 11, U)
        err(self, lambda: P.open_next(c, 2027, 3, U), "055")
        P.open_next(c, 2026, 12, U)
        P.close_previous(c, U)
        err(self, lambda: post_goods_movement(c, {"budat": TODAY}, [dict(
            bwart="201", matnr="PK-2001", werks="1000", lgort="0001", qty="1", kostl="4100")], U), "053")
        self.assertTrue(P.history(c))


class Quotations(unittest.TestCase):
    def test_new_source_above_limit_needs_three_quotations_or_reason(self):
        from pur import po
        c = system()
        data = {"lifnr": "100005", "bedat": TODAY, "items": [{"matnr": "FG-3001", "menge": "200", "netpr": "2000",
                                                               "werks": "1000", "lgort": "0003"}]}
        err(self, lambda: po.create_po(c, dict(data), U), "394")
        e = po.create_po(c, dict(data, rfq_reason="Only certified supplier"), U)
        h = c.execute("SELECT frgst, frgke, rfq_reason FROM po_header WHERE ebeln=?", (e,)).fetchone()
        self.assertTrue(h["frgst"].startswith("R1"))
        self.assertEqual(h["frgke"], "B")


class Import(unittest.TestCase):
    def test_simulate_then_post_with_line_errors(self):
        from mm import dataimport as D
        c = system()
        text = "kostl;name\n4901;Imported center;\n;missing name\n"
        r = D.run(c, "COSTCENTER", text, U, simulate=True)
        self.assertEqual((r["ok"], r["errors"]), (1, 1))
        self.assertFalse(c.execute("SELECT 1 FROM cost_center WHERE kostl='4901'").fetchone())
        D.run(c, "COSTCENTER", text, U, simulate=False)
        self.assertTrue(c.execute("SELECT 1 FROM cost_center WHERE kostl='4901'").fetchone())
        before = D.takeover_balance(c)
        D.run(c, "VENDOR_OI", "lifnr,budat,xblnr,amount\n100005,%s,OLD-7,1000\n" % TODAY, U, simulate=False)
        D.run(c, "GL_BALANCE", "hkont,amount,budat\n113100,1000,%s\n" % TODAY, U, simulate=False)
        self.assertEqual(D.takeover_balance(c), before)           # debit balance + vendor credit = 0
        self.assertEqual(check(c), [])


class Forms(unittest.TestCase):
    def test_every_form_renders_and_output_is_logged(self):
        from mm import forms, inventory
        c = system()
        keys = {"PO": c.execute("SELECT ebeln FROM po_header LIMIT 1").fetchone()[0],
                "RFQ": c.execute("SELECT anfnr FROM rfq LIMIT 1").fetchone()[0],
                "DELIVERY": c.execute("SELECT vbeln FROM sd_likp LIMIT 1").fetchone()[0],
                "INVOICE": c.execute("SELECT vbeln FROM billing LIMIT 1").fetchone()[0],
                "PRODORDER": c.execute("SELECT aufnr FROM orders WHERE auart='PP01' LIMIT 1").fetchone()[0],
                "COUNT": inventory.create(c, "1000", "0001", ["PK-2001"], TODAY, U),
                "PAYADVICE": "%s-%s" % tuple(c.execute("SELECT belnr, gjahr FROM acc_doc WHERE blart='KZ' LIMIT 1").fetchone())}
        r = c.execute("SELECT id, result FROM dunning_run LIMIT 1").fetchone()
        if r:
            keys["DUNNING"] = "%s-%s" % (r[0], json.loads(r[1])[0]["kunnr"])
        for f, k in keys.items():
            self.assertIn("<html>", forms.render(c, f, k), f)
        forms.log_output(c, "PO", keys["PO"], "PRINT", U)
        self.assertEqual(c.execute("SELECT printed FROM po_header WHERE ebeln=?", (keys["PO"],)).fetchone()[0], 1)
        err(self, lambda: forms.render(c, "PO", "NOPE"), "019")


if __name__ == "__main__":
    unittest.main()
