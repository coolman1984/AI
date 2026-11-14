"""Purchasing in depth: import file with letter of credit and landed cost (ZIMP01 / ZLC01 /
ZIMP_COST / ZIMP_LAND / ZLC_REL), service entry sheets with acceptance by a second person
(ML81N), delivery reminders (ME91F), purchase price history (ZPUR_PRICE), configuration
(ZPUR_CONF) and the purchasing month-end (ZPUR_CLOSE)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fixture  # noqa: E402,F401
from mm import seed  # noqa: E402
from mm.db import connect  # noqa: E402
from mm.posting import post_goods_movement  # noqa: E402
from mm.util import MMError  # noqa: E402

T = fixture.T
TODAY = T.isoformat()
Y = T.year
U = "BUYER1"


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


def released_po(c, data):
    from pur import po
    e = po.create_po(c, dict(data, bedat=TODAY, angnr=data.get("angnr")), U)
    po.release_all(c, e, "MGR1")
    return e


class ImportAndLandedCost(unittest.TestCase):
    def test_lc_costs_landed_into_stock_value(self):
        from pur import importfile as imp
        c = system()
        e = released_po(c, {"lifnr": "300004", "waers": "USD", "rfq_reason": "single source",
                            "items": [{"matnr": "RM-1001", "menge": "1000", "netpr": "1.00", "lgort": "0001"}]})
        f = imp.create(c, {"ebeln": e, "lcno": "LC-26-0042", "lcbank": "NBE", "margin_pct": "25",
                           "port": "Alexandria"}, U)["impno"]
        err(self, lambda: imp.create(c, {"ebeln": e}, U), "903")                    # one file per PO
        m0, b0 = bal(c, "116000"), bal(c, "113100")
        r = imp.open_lc(c, f, {"budat": TODAY}, U)
        self.assertGreater(r["margin"], 0)                                          # 25 % of the LC in EGP
        self.assertEqual((bal(c, "116000") - m0, b0 - bal(c, "113100")), (r["margin"], r["margin"]))
        imp.add_cost(c, f, {"typ": "CUSTOMS", "amount": "3000", "budat": TODAY}, U)
        imp.add_cost(c, f, {"typ": "CLEARING", "amount": "1000", "budat": TODAY, "lifnr": "200003"}, U)
        err(self, lambda: imp.add_cost(c, f, {"typ": "BRIBE", "amount": "1"}, U), "907")
        err(self, lambda: imp.land(c, f, {"budat": TODAY}, U), "911")             # no goods receipt yet
        err(self, lambda: imp.release_margin(c, f, {"budat": TODAY}, U), "913")   # costs not landed
        post_goods_movement(c, {"budat": TODAY}, [{"bwart": "101", "ebeln": e, "ebelp": 10, "qty": "1000",
                                                  "lgpla": "A-01-01"}], U)
        v0 = c.execute("SELECT salk3 FROM valuation WHERE matnr='RM-1001' AND bwkey='1000'").fetchone()[0]
        test = imp.land(c, f, {"budat": TODAY}, U, test=True)
        self.assertEqual(test["total"], 400000)
        self.assertEqual(c.execute("SELECT salk3 FROM valuation WHERE matnr='RM-1001' AND bwkey='1000'")
                         .fetchone()[0], v0)                                         # test run changes nothing
        res = imp.land(c, f, {"budat": TODAY}, U)
        v1 = c.execute("SELECT salk3 FROM valuation WHERE matnr='RM-1001' AND bwkey='1000'").fetchone()[0]
        self.assertEqual(v1 - v0, 400000)                                            # all of it into stock
        self.assertEqual(bal(c, "193500"), 0)                                        # clearing account empty
        err(self, lambda: imp.land(c, f, {"budat": TODAY}, U), "910")             # nothing left to land
        self.assertEqual(res["items"][0]["to_stock"], 400000)
        imp.release_margin(c, f, {"budat": TODAY}, U)
        self.assertEqual(bal(c, "116000"), m0)
        row = imp.files(c)[0]
        self.assertEqual((row["status"], row["costs"], row["landed"]), ("CLOSED", 400000, 400000))
        self.assertGreater(row["landed_pct"], 0)


class ServiceEntry(unittest.TestCase):
    def test_entry_sheet_accepted_by_second_person_posts_expense(self):
        from pur import service
        c = system()
        e = released_po(c, {"lifnr": "200003", "rfq_reason": "framework", "items": [
            {"knttp": "K", "kostl": "4200", "sakto": "475000", "txz01": "Office cleaning November",
             "menge": "1", "netpr": "12000"}]})
        err(self, lambda: service.create(c, {"ebeln": e, "ebelp": 10, "menge": "2", "text": "x"}, "CLERK1"), "925")
        err(self, lambda: service.create(c, {"ebeln": e, "ebelp": 10, "menge": "1"}, "CLERK1"), "922")
        s = service.create(c, {"ebeln": e, "ebelp": 10, "menge": "1", "text": "Cleaning done 1-30 Nov",
                               "budat": TODAY}, "CLERK1")["lblni"]
        self.assertEqual(c.execute("SELECT wemng FROM po_item WHERE ebeln=?", (e,)).fetchone()[0], 0)  # not posted
        err(self, lambda: service.create(c, {"ebeln": e, "ebelp": 10, "menge": "1", "text": "again"}, "CLERK1"),
            "925")                                                                   # pending sheet counts
        err(self, lambda: service.accept(c, s, "CLERK1"), "927")                    # two-person rule
        e0 = bal(c, "475000")
        service.accept(c, s, "CHIEF1")
        self.assertEqual(bal(c, "475000") - e0, 1200000)                             # expense posted
        self.assertEqual(c.execute("SELECT wemng FROM po_item WHERE ebeln=?", (e,)).fetchone()[0], 1000)
        err(self, lambda: service.accept(c, s, "CHIEF1"), "926")
        err(self, lambda: service.create(c, {"ebeln": e, "ebelp": 10, "menge": "0.5", "text": "extra"}, "CLERK1"),
            "925")                                                                   # fully accepted
        g = released_po(c, {"lifnr": "100001", "items": [{"matnr": "RM-1001", "menge": "10", "lgort": "0001"}]})
        err(self, lambda: service.create(c, {"ebeln": g, "ebelp": 10, "menge": "1", "text": "x"}, "CLERK1"), "924")
        self.assertEqual(service.sheets(c)[0]["status"], "A")


class FollowUp(unittest.TestCase):
    def test_delivery_reminders_levels_and_price_history(self):
        from pur import followup
        c = system()
        late = followup.overdue(c)
        self.assertTrue(late)
        self.assertTrue(all(r["days"] > 0 and r["open"] > 0 for r in late))
        self.assertEqual({r["level"] for r in late} - {1, 2, 3}, set())
        r = followup.send(c, [], U)
        self.assertEqual(r["sent"], len([x for x in late if x["due"]]))
        err(self, lambda: followup.send(c, [], U), "931")                         # same level not sent twice
        err(self, lambda: followup.send(c, [[]], U), "933")                       # bad selection: clean message
        err(self, lambda: followup.send(c, ["x"], U), "933")
        self.assertTrue(r["letters"][0]["text"])
        h = followup.price_history(c, "RM-1001")
        self.assertTrue(h["rows"] and h["info_records"])
        self.assertEqual(h["rows"][0]["change_pct"], None)
        st = h["stats"]["EGP"]
        self.assertTrue(st["min"] <= st["avg"] <= st["max"])
        err(self, lambda: followup.price_history(c, "NOPE"), "932")


class ConfigAndClosing(unittest.TestCase):
    def test_configuration_and_month_end_status(self):
        from pur import closing
        c = system()
        cf = closing.config(c)
        self.assertEqual(cf["ekorg"], "1000")
        self.assertTrue(cf["groups"] and cf["release"] and cf["import_costs"])
        st = closing.status(c, Y, T.month)
        names = [s["step"] for s in st["steps"]]
        self.assertEqual(names[0], "Requisitions waiting for release")
        self.assertIn("Import costs to land", names)
        self.assertEqual(st["done"], sum(1 for s in st["steps"] if s["status"] == "done"))


if __name__ == "__main__":
    unittest.main()
