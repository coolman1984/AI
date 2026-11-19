"""External audit area (ZAUD_*): engagement and materiality, the PBC list with the auditor-only steps,
queries and answers, proposed adjustments (posted or left uncorrected) against materiality, the audit
analytics and the Excel audit pack for the audit firm (Egyptian Accounting Standards)."""
import io
import os
import re
import sys
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fixture  # noqa: E402,F401
from mm import seed  # noqa: E402
from mm import util as clock  # noqa: E402
from mm.db import connect  # noqa: E402
from mm.util import MMError  # noqa: E402


def system():
    c = connect(":memory:")
    seed.seed(c)
    return c


def err(test, fn, no):
    with test.assertRaises(MMError) as x:
        fn()
    test.assertEqual(x.exception.msg_no, no, str(x.exception))


def engage(c, y, **kw):
    from extaudit import engagement as E
    E.save_engagement(c, dict(dict(gjahr=y, firm="Audit Firm One", partner="Partner A", basis="REV", pct="1", pm_pct="75",
                                   trivial_pct="5"), **kw), "OWNER")


class Engagement(unittest.TestCase):
    def test_materiality_and_pbc_list(self):
        from extaudit import engagement as E
        from extaudit.standards import PBC
        c = system()
        y = clock.today().year
        err(self, lambda: E.save_engagement(c, {"gjahr": y, "firm": "X", "basis": "XX"}, "OWNER"), "901")
        err(self, lambda: E.save_engagement(c, {"gjahr": y, "firm": "X", "pct": "50"}, "OWNER"), "902")
        err(self, lambda: E.save_engagement(c, {"gjahr": y}, "OWNER"), "903")
        engage(c, y)
        e = E.engagement(c, y)
        self.assertTrue(e["exists"])
        self.assertGreater(e["base"], 0)
        self.assertAlmostEqual(e["overall"], round(e["base"] * 0.01, 2), places=2)
        self.assertAlmostEqual(e["performance"], round(e["overall"] * 0.75, 2), places=2)
        self.assertAlmostEqual(e["trivial"], round(e["overall"] * 0.05, 2), places=2)
        items = E.pbc(c, y)
        self.assertEqual(len(items), len(PBC))
        engage(c, y)                                                           # saving again keeps the list
        self.assertEqual(len(E.pbc(c, y)), len(PBC))
        inv = next(i for i in items if i["code"] == "INV")
        self.assertIn("EAS 2 (verify)", inv["eas_text"])                        # unconfirmed number flagged
        ecl = next(i for i in items if i["code"] == "ECL")
        self.assertEqual(ecl["eas_text"], "EAS 47")

    def test_pbc_workflow_auditor_only_steps_and_queries(self):
        from extaudit import engagement as E
        c = system()
        y = clock.today().year
        engage(c, y)
        err(self, lambda: E.update_pbc(c, y, "NOPE", {"status": "SUB"}, "ACC", False), "904")
        err(self, lambda: E.update_pbc(c, y, "TB", {"status": "XX"}, "ACC", False), "905")
        E.update_pbc(c, y, "TB", {"status": "SUB", "owner": "ACC"}, "ACC", False)
        err(self, lambda: E.update_pbc(c, y, "TB", {"status": "OK"}, "ACC", False), "906")   # company cannot accept
        err(self, lambda: E.update_pbc(c, y, "TB", {"status": "RET"}, "AUD", True), "907")   # return needs a reason
        E.update_pbc(c, y, "TB", {"status": "RET", "comment": "opening balances missing"}, "AUD", True)
        E.update_pbc(c, y, "TB", {"status": "OK"}, "AUD", True)
        tb = next(i for i in E.pbc(c, y) if i["code"] == "TB")
        self.assertEqual((tb["status"], tb["owner"], tb["comment"]), ("OK", "ACC", "opening balances missing"))
        err(self, lambda: E.ask(c, y, {"question": " "}, "AUD"), "908")
        qid = E.ask(c, y, {"pbc": "inv", "question": "Basis of the slow-moving provision?"}, "AUD")["id"]
        self.assertEqual(next(i for i in E.pbc(c, y) if i["code"] == "INV")["queries"], 1)
        err(self, lambda: E.answer(c, 999, {"answer": "x"}, "ACC", False), "909")
        err(self, lambda: E.answer(c, qid, {"answer": ""}, "ACC", False), "911")
        E.answer(c, qid, {"answer": "Items idle more than 180 days at 50 %"}, "ACC", False)
        err(self, lambda: E.answer(c, qid, {"close": True}, "ACC", False), "910")
        E.answer(c, qid, {"close": True}, "AUD", True)
        self.assertEqual(E.queries(c, y)[0]["status"], "CLOSED")
        self.assertEqual(next(i for i in E.pbc(c, y) if i["code"] == "INV")["queries"], 0)
        ck = E.cockpit(c, y)
        self.assertEqual(ck["pbc_by_status"]["OK"], 1)
        self.assertTrue(ck["statements_balanced"])


class Adjustments(unittest.TestCase):
    def test_propose_post_or_leave_uncorrected_against_materiality(self):
        from extaudit import engagement as E
        from fi.reports import statements
        c = system()
        y = clock.today().year
        engage(c, y)
        err(self, lambda: E.propose(c, y, {"text": "x", "lines": [{"hkont": "999999", "debit": "1"}]}, "AUD"), "912")
        err(self, lambda: E.propose(c, y, {"text": "x", "lines": [{"hkont": "400000", "debit": "1", "credit": "1"},
                                                                    {"hkont": "140099", "credit": "1"}]}, "AUD"), "913")
        err(self, lambda: E.propose(c, y, {"text": "x", "lines": [{"hkont": "400000", "debit": "1"}]}, "AUD"), "914")
        err(self, lambda: E.propose(c, y, {"text": "x", "lines": [{"hkont": "400000", "debit": "1"},
                                                                    {"hkont": "140000", "credit": "1"}]}, "AUD"), "924")
        err(self, lambda: E.propose(c, y, {"text": "x", "lines": [{"hkont": "400000", "debit": "10"},
                                                                    {"hkont": "140099", "credit": "9"}]}, "AUD"), "915")
        err(self, lambda: E.propose(c, y, {"text": "", "lines": [{"hkont": "400000", "debit": "10"},
                                                                   {"hkont": "140099", "credit": "10"}]}, "AUD"), "916")
        e = E.engagement(c, y)
        big = "%.2f" % (e["overall"] * 1.2)                                     # above overall materiality
        a1 = E.propose(c, y, {"text": "Expected credit loss not booked", "eas": "47",
                              "lines": [{"hkont": "400000", "debit": big}, {"hkont": "140099", "credit": big}]}, "AUD")["id"]
        err(self, lambda: E.propose(c, y, {"text": "x", "lines": [{"hkont": "400000", "debit": "1", "kostl": "XX"},
                                                                    {"hkont": "190000", "credit": "1"}]}, "AUD"), "925")
        a2 = E.propose(c, y, {"text": "Small accrual", "lines": [{"hkont": "400000", "debit": "100", "kostl": "4100"},
                                                                 {"hkont": "190000", "credit": "100"}]}, "AUD")["id"]
        aj = E.adjustments(c, y)
        self.assertAlmostEqual(aj["rows"][0]["pl_effect"], -float(big), places=2)  # an expense lowers profit
        err(self, lambda: E.decide(c, a1, {"reason": ""}, "OWNER"), "919")
        E.decide(c, a1, {"reason": "management disagrees"}, "OWNER")
        err(self, lambda: E.decide(c, a1, {"reason": "x"}, "OWNER"), "918")
        aj = E.adjustments(c, y)
        self.assertGreaterEqual(aj["uncorrected_gross"], aj["overall"])
        self.assertIn("material", aj["conclusion"].lower())
        err(self, lambda: E.post(c, a2, {"budat": "%d-01-01" % (y + 1)}, "OWNER"), "920")
        before = statements(c, y, 1, 12)["result"]
        belnr = E.post(c, a2, {"budat": clock.today().isoformat()}, "OWNER")["belnr"]
        self.assertEqual(c.execute("SELECT blart, tcode FROM acc_doc WHERE belnr=?", (belnr,)).fetchone()[:], ("SA", "ZAUD_AJE"))
        self.assertAlmostEqual(statements(c, y, 1, 12)["result"] - before, -100.0, places=2)   # result down by 100
        err(self, lambda: E.post(c, a2, {}, "OWNER"), "918")
        aj = E.adjustments(c, y)
        self.assertAlmostEqual(aj["corrected"], -100.0, places=2)


class Analytics(unittest.TestCase):
    def test_tests_reconcile_and_pack_for_the_audit_firm(self):
        from extaudit import analytics as A, engagement as E, pack
        c = system()
        y = clock.today().year
        engage(c, y)
        j = A.jet(c, y)
        self.assertEqual(j["flagged"], len(j["rows"]))
        self.assertLess(j["flagged"], j["documents"])
        self.assertTrue(all(r["flags"] for r in j["rows"]))
        ar = A.partners(c, y, "D")
        tot = sum(abs(r["total"]) for r in ar["rows"])
        cov = sum(abs(r["total"]) for r in ar["rows"] if r["sample"])
        self.assertAlmostEqual(ar["coverage_pct"], round(100.0 * cov / tot, 1), places=1)
        self.assertGreaterEqual(ar["coverage_pct"], 70)
        ecl = A.ecl(c, y)
        self.assertAlmostEqual(ecl["allowance"], round(sum(r["allowance"] for r in ecl["lines"]), 2), places=1)
        inv = A.inventory(c, y)
        self.assertAlmostEqual(inv["total"], round(sum(r["value"] for r in inv["rows"]), 2), places=1)
        for r in A.payroll(c, y)["rows"]:                                     # every difference is explained
            self.assertTrue(abs(r["difference"]) < 1 or r["note"], r)
        fa = A.fixed_assets(c, y)
        for r in fa["rows"]:
            self.assertAlmostEqual(r["cost_close"] + r["dep_close"], r["nbv"], places=1)
        self.assertTrue(E.cockpit(c, y)["statements_balanced"])
        data = pack.build(c, y)
        names = re.findall(r'<sheet name="([^"]+)"', zipfile.ZipFile(io.BytesIO(data)).read("xl/workbook.xml").decode("utf-8"))
        self.assertEqual(len(names), 21)
        for n in ("00", "01", "06", "08", "11", "18", "19", "20"):
            self.assertTrue(any(x.startswith(n) for x in names), n)

    def test_auditor_access_and_area(self):
        from extaudit import engagement as E
        from sec import config
        c = system()
        err(self, lambda: E.grant_access(c, {"bname": "", "valid_to": "2099-01-01"}, "ADMIN"), "921")
        err(self, lambda: E.grant_access(c, {"bname": "AUD1", "valid_to": "2000-01-01"}, "ADMIN"), "922")
        r = E.grant_access(c, {"bname": "aud1", "name": "Auditor", "valid_to": "2099-01-01", "firm": "Audit Firm One"}, "ADMIN")
        self.assertTrue(r["password"])
        roles = [x[0] for x in c.execute("SELECT role FROM usr_role WHERE bname='AUD1'")]
        self.assertEqual(roles, ["AUDITOR"])
        self.assertIn(("S_AREA", "AU", "02"), config.DEMO_ROLES["AUDITOR"][2])
        area = next(a for p, a in config.API_AREAS if "/api/audit/aje".startswith(p))
        self.assertEqual(area, "AU")
        self.assertEqual(next(a for p, a in config.API_AREAS if "/api/audit/aje/post".startswith(p)), "FI")


if __name__ == "__main__":
    unittest.main()
