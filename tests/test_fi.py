"""FI tests on the full demo (MM + CO + FI)."""
import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from co.seed import sample_period_start  # noqa: E402
from fi import aa, ap, ar, gl, reports  # noqa: E402
from fi.document import signed  # noqa: E402
from mm import seed  # noqa: E402
from mm.db import connect  # noqa: E402
from mm.util import MMError  # noqa: E402

_DB = {}
P = sample_period_start()
Y, M = P.year, P.month
TODAY = datetime.date.today().isoformat()


def demo():
    if "c" not in _DB:
        c = connect(":memory:")
        seed.seed(c)
        _DB["c"] = c
    return _DB["c"]


def lines_of(c, belnr):
    return {r["hkont"]: signed(r) for r in c.execute(
        "SELECT hkont, shkzg, dmbtr FROM acc_doc_item WHERE belnr=?", (belnr,))}


class Ledger(unittest.TestCase):
    def test_balance_sheet_balances_every_month(self):
        for p in range(1, 13):
            st = reports.statements(demo(), Y, p, p)
            self.assertTrue(st["balanced"], "period %s" % p)

    def test_trial_balance_debit_equals_credit(self):
        tb = reports.trial_balance(demo(), Y, 1, 12)
        self.assertAlmostEqual(sum(r["debit"] for r in tb), sum(r["credit"] for r in tb), 2)

    def test_reconciliation_account_cannot_be_posted_directly(self):
        with self.assertRaises(MMError) as e:
            gl.general_posting(demo(), {"budat": TODAY}, [
                dict(bschl="40", account="113100", amount="10"),
                dict(bschl="50", account="160000", amount="10")], "T")
        self.assertEqual(e.exception.msg_no, "562")

    def test_closed_period_rejected(self):
        old = (P - datetime.timedelta(days=40)).isoformat()
        with self.assertRaises(MMError) as e:
            gl.general_posting(demo(), {"budat": old}, [
                dict(bschl="40", account="100000", amount="10"),
                dict(bschl="50", account="113100", amount="10")], "T")
        self.assertEqual(e.exception.msg_no, "201")

    def test_document_type_sa_does_not_allow_vendor(self):
        with self.assertRaises(MMError) as e:
            gl.general_posting(demo(), {"budat": TODAY, "blart": "SA"}, [
                dict(bschl="31", account="200001", amount="10"),
                dict(bschl="40", account="100000", amount="10")], "T")
        self.assertEqual(e.exception.msg_no, "101")


class Payables(unittest.TestCase):
    def test_fb60_tax_and_due_date(self):
        c = demo()
        b = ap.vendor_invoice(c, {"lifnr": "200005", "bldat": TODAY, "budat": TODAY,
                                  "mwskz": "V1"}, [dict(hkont="477000", amount="1000",
                                                        kostl="8100")], "T")
        l = lines_of(c, b)
        self.assertEqual(l["477000"], 100000)
        self.assertEqual(l["154000"], 14000)              # 14 % input VAT
        self.assertEqual(l["160000"], -114000)
        r = c.execute("SELECT netdt FROM acc_doc_item WHERE belnr=? AND koart='K'",
                      (b,)).fetchone()
        due = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
        self.assertEqual(r["netdt"], due)                 # NT30
        co = c.execute("SELECT COUNT(*) FROM co_item WHERE vrgng='COIN' AND objnr="
                       "'KS8100' AND sgtxt IS NOT NULL AND belnr IN (SELECT belnr FROM "
                       "co_doc WHERE refbn LIKE ?)", (b + "/%",)).fetchone()[0]
        self.assertEqual(co, 1)                           # cost flows to CO

    def test_expense_without_cost_center_rejected(self):
        with self.assertRaises(MMError) as e:
            ap.vendor_invoice(demo(), {"lifnr": "200005", "budat": TODAY, "mwskz": "V1"},
                              [dict(hkont="477000", amount="10")], "T")
        self.assertEqual(e.exception.msg_no, "235")

    def test_cash_discount_taken_in_payment_run(self):
        c = demo()
        disc = -c.execute("SELECT COALESCE(SUM(CASE WHEN shkzg='S' THEN dmbtr ELSE -dmbtr "
                          "END),0) FROM acc_doc_item i JOIN acc_doc h USING (belnr, gjahr) "
                          "WHERE i.hkont='276000' AND h.tcode='F110' AND h.budat=?",
                          (datetime.date(Y, M, 15).isoformat(),)).fetchone()[0]
        # Z210 invoices of the 10th paid on the 15th: 2 % of gross
        # services 10,000 + IT 11,200 net -> gross x 1.14 -> 2 %
        self.assertEqual(disc, round((10000 + 11200) * 1.14 * 0.02 * 100))

    def test_realized_exchange_loss(self):
        c = demo()
        fx = c.execute("SELECT SUM(dmbtr) FROM acc_doc_item WHERE hkont='721000'").fetchone()[0]
        self.assertEqual(fx, 20000 * (4920 - 4850))       # 20,000 USD x 0.70

    def test_fx_valuation_and_reversal(self):
        c = demo()
        docs = c.execute("SELECT belnr, stblg FROM acc_doc WHERE tcode='FAGL_FCV'").fetchall()
        self.assertEqual(len(docs), 1)
        self.assertTrue(docs[0]["stblg"])                # reversed by F.81
        l = lines_of(c, docs[0]["belnr"])
        self.assertEqual(l["722000"], 3000 * (4980 - 4850))

    def test_miro_price_difference_to_stock(self):
        c = demo()
        h = c.execute("SELECT belnr FROM acc_doc WHERE tcode='MIRO' AND xblnr='PP-9031'"
                      ).fetchone()
        l = lines_of(c, h["belnr"])
        self.assertEqual(l["191100"], 5850000)            # 300 L x 195 GR/IR
        self.assertEqual(l["300000"], 30000)              # 300 L x 1 to stock (MAP)
        self.assertEqual(l["160000"], -round(5880000 * 1.14))

    def test_miro_quantity_check(self):
        c = demo()
        e = c.execute("SELECT ebeln FROM po_item WHERE remng=wemng AND wemng>0 LIMIT 1"
                      ).fetchone()["ebeln"]
        with self.assertRaises(MMError):
            ap.miro(c, {"ebeln": e, "budat": TODAY}, [{"ebelp": 10, "qty": "1"}], "T")


class Receivables(unittest.TestCase):
    def test_partial_payment_residual_is_dunned(self):
        c = demo()
        res = [r for r in ap.open_items(c, "D", "C1002") if r["rebzg"]]
        self.assertEqual(len(res), 1)
        self.assertEqual(signed(res[0]), round((20 * 4200 + 30 * 2600) * 0.92 * 1.14 * 100)
                         - 12000000)
        self.assertEqual(res[0]["manst"], 1)              # dunning level 1

    def test_credit_limit_blocks_billing(self):
        from co import copa
        with self.assertRaises(MMError) as e:
            copa.create_billing(demo(), {"kunnr": "C1003", "fkdat": TODAY, "items": [
                dict(matnr="FG-3002", qty="400", price="2500", lgort="0003")]}, "T")
        self.assertEqual(e.exception.msg_no, "035")

    def test_fb70_revenue_goes_to_copa(self):
        c = demo()
        b = ar.customer_invoice(c, {"kunnr": "C1001", "budat": TODAY, "mwskz": "A1"},
                                [dict(hkont="800000", amount="500", matnr="FG-3001")], "T")
        r = c.execute("SELECT vrgar, vv010 FROM copa_item WHERE refdoc=?", (b,)).fetchone()
        self.assertEqual((r["vrgar"], r["vv010"]), ("B", 50000))


class Assets(unittest.TestCase):
    def test_depreciation_to_cost_center(self):
        c = demo()
        r = c.execute("SELECT SUM(wtg) FROM co_item WHERE objnr='KS4100' AND kstar='470000'"
                      " AND gjahr=? AND perio=? AND wrttp='04'", (Y, M)).fetchone()[0]
        self.assertEqual(r, 6000000)                      # CNC 7.2 M / 120 months

    def test_scrapping_loss_equals_book_value(self):
        c = demo()
        a = c.execute("SELECT anln1 FROM asset WHERE txt='Old laptop pool'").fetchone()
        apc, dep, nbv = aa.values(c, a["anln1"])
        self.assertEqual((apc, dep, nbv), (0, 0, 0))
        loss = c.execute("SELECT SUM(dmbtr) FROM acc_doc_item WHERE hkont='821000'"
                         ).fetchone()[0]
        self.assertGreater(loss, 0)

    def test_new_asset_depreciation_starts_next_month(self):
        c = demo()
        a = c.execute("SELECT * FROM asset WHERE txt LIKE 'Fiber laser%'").fetchone()
        self.assertEqual(aa.planned_dep(c, a, Y, M), 0)
        nm, ny = (M % 12) + 1, Y + (1 if M == 12 else 0)
        self.assertGreater(aa.planned_dep(c, a, ny, nm), 0)


class Closing(unittest.TestCase):
    def test_vat_settled(self):
        c = demo()
        d1, d2 = P.isoformat(), reports.eop(Y, M)
        rep = gl.vat_report(c, d1, d2)
        fb41 = c.execute("SELECT belnr FROM acc_doc WHERE tcode='FB41' AND budat=?",
                         (d2,)).fetchone()
        self.assertEqual(-lines_of(c, fb41["belnr"])["179000"], rep["payable"])

    def test_grir_cleared_for_invoiced_po(self):
        c = demo()
        n = c.execute("SELECT COUNT(*) FROM acc_doc_item WHERE hkont='191100' AND augbl IS "
                      "NOT NULL").fetchone()[0]
        self.assertGreater(n, 0)

    def test_reverse_vendor_invoice(self):
        c = demo()
        b = ap.vendor_invoice(c, {"lifnr": "200006", "budat": TODAY, "mwskz": "V1"},
                              [dict(hkont="478000", amount="200", kostl="8100")], "T")
        new = gl.reverse(c, b, int(TODAY[:4]), TODAY, "01", "T")
        self.assertTrue(new)
        self.assertFalse([r for r in ap.open_items(c, "K", "200006") if r["belnr"] in (b, new)])


if __name__ == "__main__":
    unittest.main()
