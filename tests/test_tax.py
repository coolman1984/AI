"""Egyptian taxes module (ZTAX_*): law register with dated rules, salary tax of Law 7/2024
including the high-income rule, VAT return (form 10), withholding tax form 41, salary tax
return, tax calendar, e-invoice manual mode (export, results, cancellation window, received
documents matching), simplified regime (Law 6/2025) and the tax month-end."""
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
EGP = 100


def system():
    c = connect(":memory:")
    seed.seed(c)
    return c


def err(test, fn, no):
    with test.assertRaises(MMError) as x:
        fn()
    test.assertEqual(x.exception.msg_no, no, str(x.exception))


class SalaryTaxHighIncome(unittest.TestCase):
    """Law 7/2024: above 600,000 EGP annual taxable income the lower brackets fall away;
    above 1,200,000 the first 1,200,000 are taxed at 25 %."""
    def test_lower_brackets_fall_away_for_high_incomes(self):
        from hr.payroll import annual_tax
        c = system()
        self.assertEqual(annual_tax(c, 100000 * EGP), 9750 * EGP)          # normal scale: 1,500 + 2,250 + 6,000
        self.assertEqual(annual_tax(c, 650000 * EGP), 141250 * EGP)        # 0 % band removed: 55,000 at 10 %
        self.assertEqual(annual_tax(c, 1300000 * EGP), 327500 * EGP)       # 1,200,000 x 25 % + 100,000 x 27.5 %


class LawRegister(unittest.TestCase):
    def test_dated_rules_new_versions_and_sync_to_payroll_and_wht(self):
        from tax import rules
        c = system()
        self.assertEqual(rules.get(c, "SI_MAX", "2025-06-30")["value"], "14500")
        self.assertEqual(rules.get(c, "SI_MAX", "2026-02-01")["value"], "16700")      # yearly increase
        self.assertEqual(rules.num(c, "VAT_STD", TODAY), 14)
        err(self, lambda: rules.new_version(c, {"key": "WHT_SERVICES", "value": "4", "valid_from": "2027-01-01"}, "T"),
            "903")                                                                    # legal reference required
        err(self, lambda: rules.new_version(c, {"key": "WHT_SERVICES", "value": "4", "valid_from": "2020-01-01",
                                                "legal_ref": "x"}, "T"), "905")       # must be after the latest
        err(self, lambda: rules.new_version(c, {"key": "NOPE", "value": "1", "valid_from": "2027-01-01",
                                                "legal_ref": "x"}, "T"), "904")
        rules.new_version(c, {"key": "WHT_SERVICES", "value": "4", "valid_from": "2027-01-01",
                              "legal_ref": "Decree 1/2027"}, "T")
        self.assertEqual(rules.num(c, "WHT_SERVICES", "2026-12-31"), 3)               # old version closed
        self.assertEqual(rules.num(c, "WHT_SERVICES", "2027-01-01"), 4)
        self.assertEqual(rules.wht_check(c, TODAY)["differences"], [])
        self.assertEqual([d["code"] for d in rules.wht_check(c, "2027-01-02")["differences"]], ["W3"])
        rules.apply_wht(c, "2027-01-02", "T")
        self.assertEqual(c.execute("SELECT pct FROM wht_code WHERE code='W3'").fetchone()[0], 400)
        diffs = {d["key"] for d in rules.payroll_check(c, "2026-02-01")["differences"]}
        self.assertEqual(diffs, {"si_min", "si_max"})                                 # 2026 caps not yet in payroll
        rules.apply_payroll(c, "2026-02-01", "T")
        self.assertEqual(rules.payroll_check(c, "2026-02-01")["differences"], [])


class Returns(unittest.TestCase):
    def test_vat_form10_filing_credit_carry_and_calendar(self):
        from fi.gl import vat_report
        from tax import returns
        c = system()
        v = returns.vat_return(c, T.year, 10)
        rep = vat_report(c, v["d1"], v["d2"])
        self.assertEqual(v["payable"], rep["output"] - rep["input"])
        err(self, lambda: returns.mark(c, {"typ": "VAT", "period": "2026-10", "filed_on": TODAY}, "T"), "914")
        err(self, lambda: returns.mark(c, {"typ": "VAT", "period": "2026-10", "paid_on": TODAY}, "T"), "915")
        returns.mark(c, {"typ": "VAT", "period": "2026-10", "filed_on": TODAY, "ref_no": "ETA-10",
                         "amount": "%.2f" % (v["payable"] / 100.0)}, "T")
        nov = returns.vat_return(c, T.year, 11)
        carried = [l for l in nov["lines"] if l["no"] == "7"][0]["tax"]
        self.assertEqual(carried, -v["payable"] if v["payable"] < 0 else 0)             # credit carried forward
        cal = returns.calendar_year(c, T.year, TODAY)
        vat10 = [r for r in cal["rows"] if r["typ"] == "VAT" and r["period"] == "2026-10"][0]
        self.assertEqual((vat10["status"], vat10["due"]), ("filed", "2026-11-30"))
        sal = [r for r in cal["rows"] if r["typ"] == "SAL" and r["period"] == "2026-10"][0]
        self.assertEqual(sal["due"], "2026-11-15")
        self.assertEqual(sal["amount"], returns.salary_return(c, T.year, 10)["tax"])

    def test_form41_simplified_regime_and_cit(self):
        from fi.wht import report
        from tax import returns
        c = system()
        f = returns.form41(c, T.year, 4)
        self.assertEqual(f["amount"], sum(r["amount"] for r in report(c, f["d1"], f["d2"])))
        s = returns.simplified(c, "1500000")
        self.assertEqual((s["eligible"], s["rate"], s["tax"]), (True, 0.5, 7500 * EGP))
        big = returns.simplified(c, "23000000")
        self.assertEqual((big["eligible"], big["within_tolerance"]), (False, True))
        self.assertEqual(returns.cit_estimate(c, T.year)["rate"], 22.5)


class EInvoice(unittest.TestCase):
    def test_manual_mode_export_results_cancel_window_and_api_check(self):
        from tax import eta
        c = system()
        out = eta.outbound(c, "%d-01-01" % T.year, TODAY)
        todo = [r["vbeln"] for r in out["rows"] if r["eta_status"] == "Not generated"]
        eta.generate(c, todo, "T")
        ready = [r["vbeln"] for r in eta.outbound(c, "%d-01-01" % T.year, TODAY)["rows"]
                 if r["eta_status"] == "Ready to submit"]
        self.assertTrue(ready)
        ex = eta.export(c, ready)
        self.assertEqual(ex["count"], len(ready))
        self.assertIn('"documents"', ex["json"])
        err(self, lambda: eta.record(c, ready[0], {"status": "Valid", "uuid": "?"}, "T"), "925")
        csv_text = "internal_id,uuid,status,date\n" + "\n".join(
            "%s,UUID%s0000000,Valid,%s" % (v, v, TODAY) for v in ready) + "\nNOPE,UUIDX000000000,Valid,%s\n" % TODAY
        r = eta.import_results(c, csv_text, "T")
        self.assertEqual((r["ok"], r["errors"]), (len(ready), 1))
        eta.request_cancel(c, ready[0], "wrong customer", "T", TODAY)
        err(self, lambda: eta.request_cancel(c, ready[0], "again", "T", TODAY), "929")    # not valid any more
        err(self, lambda: eta.request_cancel(c, ready[1], "late", "T", "2099-01-01"), "930")  # window over
        err(self, lambda: eta.submit_api(c, ready, "T"), "931")
        err(self, lambda: eta.save_settings(c, {"mode": "API"}, "T"), "922")
        self.assertEqual(eta.settings(c)["mode"], "MANUAL")

    def test_received_documents_matching_and_input_vat_at_risk(self):
        from tax import eta
        c = system()
        d1 = "%d-01-01" % T.year
        before = eta.input_vat_at_risk(c, d1, TODAY)
        doc = before["rows"][0]
        c.execute("UPDATE vendor SET stcd1='123-456-789' WHERE lifnr=?", (doc["lifnr"],))
        c.execute("UPDATE acc_doc SET xblnr='B-4711' WHERE belnr=? AND gjahr=?", (doc["belnr"], doc["gjahr"]))
        text = ("uuid,issuer_id,issuer_name,internal_id,issued,net,tax,total,status\n"
                "U1AAAAAAAAAA,123456789,Vendor,B-4711,%s,100,14,114,Valid\n"
                "U2AAAAAAAAAA,999999999,Unknown,X-1,%s,10,1.4,11.4,Valid\n" % (doc["budat"], doc["budat"]))
        r = eta.import_received(c, text, "T")
        self.assertEqual(r["ok"], 2)
        rec = eta.received(c, d1, TODAY)
        self.assertEqual(sorted(d["match"] for d in rec["rows"]), ["matched", "vendor unknown"])
        after = eta.input_vat_at_risk(c, d1, TODAY)
        self.assertEqual(after["count"], before["count"] - 1)
        self.assertEqual(after["amount"], before["amount"] - doc["vat"])


class Audit(unittest.TestCase):
    def test_checklist_reconciliation_audit_file_and_month_end(self):
        from mm import xlsx
        from tax import audit
        c = system()
        ch = audit.checklist(c, T.year)
        self.assertEqual(ch["items"][0]["status"], "ok")                               # ledger balanced
        self.assertTrue(all(i["status"] in ("ok", "issue", "manual") for i in ch["items"]))
        rec = audit.revenue_reconciliation(c, T.year)
        for r in rec["rows"]:
            self.assertEqual(r["diff_books"], r["books"] - r["invoices"])
        book = xlsx.read(audit.audit_file(c, T.year))
        self.assertEqual(list(book)[:3], ["01 Trial balance", "02 Journal", "03 Sales VAT register"])
        self.assertIn("10 Audit checklist", book)
        st = audit.close_status(c, T.year, 10)
        self.assertEqual(st["steps"][0]["tcode"], "ZTAX_EINV")
        self.assertEqual(st["done"], sum(1 for s in st["steps"] if s["status"] == "done"))


class AdviserReview(unittest.TestCase):
    """ZTAX_REVIEW: the sheet for the tax adviser and loading the answers back"""
    def _answer(self, data, answers, adviser="Dr. Adviser"):
        """fill the adviser columns of the sheet like Excel would (re-written workbook)"""
        from mm.xlsx import Workbook, read
        from tax.review import HEAD_ROW, SHEET
        book = read(data)
        wb = Workbook()
        s = wb.add(SHEET)
        rows = book[SHEET]
        for n, r in enumerate(rows):
            s.row(n, list(r))
        s.set(1, 3, adviser)
        s.set(2, 3, "46340")                                   # Excel serial date
        for n in range(HEAD_ROW + 1, len(rows)):
            a = answers.get(rows[n][2])
            if a:
                for i, v in enumerate(a):
                    s.set(n, 11 + i, v)
        return wb.save()

    def test_sheet_answers_simulate_verify_correct_and_new_version(self):
        from mm.xlsx import read
        from tax import review, rules
        c = system()
        before = review.summary(c)
        self.assertEqual(before["to_verify"], 30)               # 28 rules, SI_MIN / SI_MAX in 2 versions
        data = review.review_sheet(c, "Test Co")
        book = read(data)
        self.assertEqual(set(book), {"Guide", "Rules to verify", "Verified rules"})
        sheet = book["Rules to verify"]
        keys = [r[2] for r in sheet[review.HEAD_ROW + 1:] if len(r) > 2]
        self.assertEqual(len(keys), 30)
        brackets = [r for r in sheet if len(r) > 2 and r[2] == "SAL_BRACKETS"][0]
        self.assertEqual(brackets[6], "40000:0, 55000:10, 70000:15, 200000:20, 400000:22.5, 1200000:25, above:27.5")
        self.assertTrue(brackets[5])                           # Arabic description
        # answers: confirm, correct in place, new version, one bad value, one bad decision
        bad = self._answer(data, {"WHT_SUPPLIES": ["OK"], "WHT_SERVICES": ["CHANGE", "x%", "", "Decree 1"],
                                  "WHT_MIN": ["MAYBE"]})
        r = review.import_review(c, bad, "T", simulate=False)
        self.assertEqual(r["errors"], 2)
        self.assertEqual(review.summary(c)["to_verify"], 30)    # nothing changed with errors
        err(self, lambda: review.import_review(c, self._answer(data, {"WHT_MIN": ["OK"]}, adviser=""), "T"), "942")
        err(self, lambda: review.import_review(c, b"not excel", "T"), "940")
        good = self._answer(data, {
            "WHT_SUPPLIES": ["OK"],
            "SIMP_BANDS": ["CHANGE", "500000:0.4, 2000000:0.5, 3000000:0.75, 10000000:1, 20000000:1.5", "",
                           "Law 6/2025 art. 7", "confirmed bands"],
            "SAL_EXEMPTION": ["CHANGE", "25000", "2027-01-01", "Law 1/2027"]})
        sim = review.import_review(c, good, "T", simulate=True)
        self.assertEqual((sim["errors"], sim["answered"]), (0, 3))
        self.assertEqual(review.summary(c)["to_verify"], 30)    # simulation writes nothing
        res = review.import_review(c, good, "T", simulate=False)
        self.assertEqual(res["errors"], 0)
        self.assertEqual(res["adviser"], "Dr. Adviser")
        self.assertEqual(res["date"], "2026-11-14")
        self.assertEqual(rules.get(c, "WHT_SUPPLIES")["status"], "VERIFIED")
        self.assertIn("Adviser Dr. Adviser", rules.get(c, "WHT_SUPPLIES")["note"])
        simp = rules.get(c, "SIMP_BANDS")
        self.assertEqual((simp["status"], simp["legal_ref"]), ("VERIFIED", "Law 6/2025 art. 7"))
        self.assertEqual(rules.num(c, "SAL_EXEMPTION", "2026-12-31"), 20000)    # old version kept until then
        new = rules.get(c, "SAL_EXEMPTION", "2027-01-01")
        self.assertEqual((new["value"], new["status"]), ("25000", "VERIFIED"))
        self.assertEqual(review.summary(c)["to_verify"], 28)    # SAL_EXEMPTION 2024 version still to verify
        # the same sheet again: the confirmed rows are skipped, changed rule detected
        again = review.import_review(c, good, "T", simulate=True)
        self.assertTrue(any("already verified" in o["result"] for o in again["rows"]))
        # brackets written by the adviser go back to the payroll format
        self.assertEqual(review.to_register("SAL_BRACKETS", "hr format", "40000:0, 55000:10, above:27.5", 1),
                         "4000000:0,5500000:1000,999999999999:2750")
        self.assertEqual(review.to_register("SAL_HIGH_INCOME", "hr format", "600000:55000:10", 1), "60000000:5500000:1000")


if __name__ == "__main__":
    unittest.main()
