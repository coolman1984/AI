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


if __name__ == "__main__":
    unittest.main()


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
