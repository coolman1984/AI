"""Accounting in depth: cheques received / issued (notes receivable / payable), petty cash
journal (FBCJ), recurring entries (FBD1 / F.14), parked documents with approval
(FV50 / FBV0), statement of account (F.27) and the FI closing management (ZFI_CLOSE)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fixture  # noqa: E402,F401
from mm import seed  # noqa: E402
from mm.db import connect  # noqa: E402
from mm.util import MMError  # noqa: E402

T = fixture.T
TODAY = T.isoformat()
Y = T.year
U = "FIQA"


def system():
    c = connect(":memory:")
    seed.seed(c)
    return c


def err(test, fn, no):
    with test.assertRaises(MMError) as x:
        fn()
    test.assertEqual(x.exception.msg_no, no, str(x.exception))


def bal(c, hkont):
    from fi.reports import gl_balance
    return gl_balance(c, hkont, "9999-12-31")


def item(c, koart, partner):
    from fi import ap
    i = ap.open_items(c, koart, partner)[0]
    return i["belnr"], i["gjahr"], i["buzei"], i["dmbtr"]


class Cheques(unittest.TestCase):
    def test_receive_collect_bounce_and_issue(self):
        from fi import ap, cheque
        c = system()
        b, g, z, amt = item(c, "D", "C1001")
        n_open = len(ap.open_items(c, "D", "C1001"))
        nr0, bank0 = bal(c, "115000"), bal(c, "113100")
        cid = cheque.receive(c, {"kunnr": "C1001", "chqno": "000123", "bank": "CIB", "due": "2026-12-15",
                                 "budat": TODAY, "items": [[b, g, z]]}, U)["id"]
        self.assertEqual(len(ap.open_items(c, "D", "C1001")), n_open - 1)               # invoice cleared
        self.assertEqual(bal(c, "115000") - nr0, amt)                                    # in notes receivable
        err(self, lambda: cheque.receive(c, {"kunnr": "C1001", "chqno": "000123", "bank": "CIB", "amount": "10",
                                             "due": "2026-12-15", "budat": TODAY}, U), "802")  # same cheque twice
        cheque.collect(c, cid, TODAY, U)
        self.assertEqual((bal(c, "115000"), bal(c, "113100") - bank0), (nr0, amt))
        err(self, lambda: cheque.collect(c, cid, TODAY, U), "805")                        # already collected
        cid2 = cheque.receive(c, {"kunnr": "C1004", "chqno": "777", "bank": "NBE", "amount": "5000",
                                  "due": TODAY, "budat": TODAY}, U)["id"]                   # on account
        before = len(ap.open_items(c, "D", "C1004"))
        cheque.bounce(c, cid2, TODAY, U, "insufficient funds")
        self.assertEqual(bal(c, "115000"), nr0)
        self.assertEqual(len(ap.open_items(c, "D", "C1004")), before + 1)               # customer owes again
        vb, vg, vz, vamt = item(c, "K", "100005")
        np0 = bal(c, "165000")
        oid = cheque.issue(c, {"lifnr": "100005", "chqno": "900001", "bank": "NBE", "due": "2026-12-20",
                               "budat": TODAY, "items": [[vb, vg, vz]]}, U)["id"]
        self.assertEqual(bal(c, "165000") - np0, -vamt)                                  # notes payable (credit)
        cheque.collect(c, oid, TODAY, U)                                                 # cashed by the vendor
        self.assertEqual(bal(c, "165000"), np0)
        reg = cheque.register(c)
        self.assertEqual({r["id"]: r["status"] for r in reg}[cid2], "BNC")
        self.assertTrue(all(k in reg[0] for k in ("chqno", "partner", "amount", "due", "status")))


class CashJournal(unittest.TestCase):
    def test_cash_in_expense_balance_never_negative(self):
        from fi import cashbook
        c = system()
        start = cashbook.book(c, "2026-01-01", "2026-12-31")["closing"]
        cashbook.post(c, {"typ": "BANK_IN", "budat": TODAY, "amount": "5000", "text": "Cash from bank"}, U)
        cashbook.post(c, {"typ": "EXPENSE", "budat": TODAY, "amount": "1200", "hkont": "477000", "kostl": "8100",
                          "text": "Printing of flyers"}, U)
        err(self, lambda: cashbook.post(c, {"typ": "EXPENSE", "budat": TODAY, "amount": "999999",
                                            "hkont": "477000", "kostl": "8100", "text": "x"}, U), "811")
        bk = cashbook.book(c, "2026-01-01", "2026-12-31")
        self.assertEqual(bk["closing"], start + 500000 - 120000)
        self.assertEqual(bk["lines"][-1]["balance"], bk["closing"])
        err(self, lambda: cashbook.post(c, {"typ": "EXPENSE", "budat": TODAY, "amount": "10", "hkont": "113100",
                                            "text": "x"}, U), "813")                       # not an expense account


class Recurring(unittest.TestCase):
    def test_monthly_rent_runs_once_per_period(self):
        from fi import recurring
        c = system()
        rid = recurring.save(c, {"text": "Warehouse rent", "first": "2026-01-01", "last": "2026-12-31", "lines": [
            {"bschl": "40", "account": "475000", "amount": "20000", "kostl": "4400"},
            {"bschl": "50", "account": "113100", "amount": "20000"}]}, U)
        r = recurring.run(c, Y, T.month, U)
        self.assertEqual((r["posted"], r["docs"][0]["id"]), (1, rid))
        err(self, lambda: recurring.run(c, Y, T.month, U), "822")                         # once per period
        self.assertEqual(recurring.run(c, 2027, 1, U)["posted"], 0)                       # outside validity
        err(self, lambda: recurring.save(c, {"text": "x", "first": "2026-01-01", "lines": [
            {"bschl": "40", "account": "475000", "amount": "1", "kostl": "4400"},
            {"bschl": "50", "account": "113100", "amount": "2"}]}, U), "821")             # not balanced


class Parked(unittest.TestCase):
    def test_park_and_post_by_another_person(self):
        from fi import parked
        c = system()
        doc = {"budat": TODAY, "bktxt": "Consulting fee", "lines": [
            {"bschl": "40", "account": "475000", "amount": "3000", "kostl": "9100"},
            {"bschl": "50", "account": "113100", "amount": "3000"}]}
        pid = parked.park(c, doc, "CLERK1")
        err(self, lambda: parked.post(c, pid, "CLERK1"), "832")                           # two-person rule
        r = parked.post(c, pid, "CHIEF1")
        self.assertTrue(r["belnr"])
        err(self, lambda: parked.post(c, pid, "CHIEF1"), "833")                           # already posted
        bad = dict(doc, lines=[dict(doc["lines"][0]), dict(doc["lines"][1], amount="1")])
        err(self, lambda: parked.park(c, bad, "CLERK1"), "702")                           # checked when parked
        pid2 = parked.park(c, doc, "CLERK1")
        parked.delete(c, pid2, "CLERK1")
        self.assertEqual([p["status"] for p in parked.listing(c) if p["id"] == pid2], ["D"])


class StatementAndClosing(unittest.TestCase):
    def test_statement_of_account_and_closing_status(self):
        from fi import closing, reports
        c = system()
        s = reports.statement(c, "D", "C1001", "%d-01-01" % Y, TODAY)
        self.assertEqual(s["opening"] + sum(x["debit"] - x["credit"] for x in s["lines"]), s["closing"])
        fd = [p for p in reports.partner_balances(c, "D", Y) if p["partner"] == "C1001"][0]
        self.assertAlmostEqual(s["closing"] / 100.0, fd["balance"], 2)
        err(self, lambda: reports.statement(c, "D", "NOPE", "%d-01-01" % Y, TODAY), "841")
        st = closing.status(c, Y, T.month)
        names = [x["step"] for x in st["steps"]]
        self.assertEqual(names[0], "Recurring entries")
        self.assertIn("Parked documents", names)
        self.assertIn("Posting period", names)


if __name__ == "__main__":
    unittest.main()
