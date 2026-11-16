"""Excel data takeover for every business area (ZIMPORT): the six workbooks (purchasing,
sales, warehouse, finance, production, HR) load their examples one after the other into an
empty system without an error, the takeover account 399999 ends at zero, "Compare file with
system" finds every value and reports a changed one, and loading twice is refused."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fixture  # noqa: E402,F401
from mm.db import connect  # noqa: E402

ORDER = ("PUR", "SD", "MM", "FI", "PP", "HR")
_C = {}


def loaded():
    """an empty system with all six example workbooks posted"""
    if "c" not in _C:
        from mm import dataimport, templates
        c = connect(":memory:")
        _C["log"] = {}
        for a in ORDER:
            r = dataimport.run_xlsx(c, templates.workbook(a, example=True), "ADMIN", simulate=False)
            _C["log"][a] = r
        _C["c"] = c
    return _C["c"]


class AllAreas(unittest.TestCase):
    def test_examples_load_in_order_and_balance(self):
        from mm import dataimport
        c = loaded()
        for a in ORDER:
            r = _C["log"][a]
            self.assertEqual(r["errors"], 0, (a, [x for x in r["log"] if x["status"] == "E"]))
            self.assertGreater(r["ok"], 0, a)
        self.assertEqual(dataimport.takeover_balance(c), 0)                          # opening balances complete
        self.assertEqual(c.execute("SELECT COUNT(*) FROM customer").fetchone()[0], 2)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM hr_employee").fetchone()[0], 3)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM sd_vbak WHERE vbtyp='C'").fetchone()[0], 2)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM bom WHERE matnr='FG-100'").fetchone()[0], 2)
        # open loan of the old system: deducted by the payroll from its first month
        self.assertEqual(c.execute("SELECT amount FROM hr_loan").fetchone()[0], 300000)

    def test_asset_accounts_equal_the_asset_register(self):
        from fi.reports import gl_balance
        c = loaded()
        apc = c.execute("SELECT COALESCE(SUM(apc),0) FROM asset_item i JOIN asset a ON a.anln1=i.anln1 "
                        "WHERE a.anlkl='2000'").fetchone()[0]
        self.assertEqual(apc, 50000000)                                             # 500,000.00 - not converted twice
        self.assertEqual(gl_balance(c, "020000", "9999-12-31"), apc)
        self.assertEqual(gl_balance(c, "020100", "9999-12-31"), -19000000)

    def test_compare_finds_everything_and_reports_a_change(self):
        from mm import dataimport, templates
        c = loaded()
        for a in ORDER:
            v = dataimport.verify_xlsx(c, templates.workbook(a, example=True))
            self.assertTrue(v["all_ok"], (a, v["differences"][:5]))
            self.assertGreater(v["checked"], 0, a)
        c.execute("UPDATE hr_employee SET basic=950000 WHERE old_pernr='E-101'")
        c.execute("UPDATE customer SET klimk=1 WHERE altkn='CU-501'")
        hr = dataimport.verify_xlsx(c, templates.workbook("HR", example=True))
        self.assertEqual([(d["field"], d["file"], d["system"]) for d in hr["differences"]],
                         [("basic", "9000.00", "9500.00")])
        sd = dataimport.verify_xlsx(c, templates.workbook("SD", example=True))
        self.assertIn(("klimk", "500000.00", "0.01"), [(d["field"], d["file"], d["system"]) for d in sd["differences"]])
        c.execute("UPDATE hr_employee SET basic=900000 WHERE old_pernr='E-101'")
        c.execute("UPDATE customer SET klimk=50000000 WHERE altkn='CU-501'")

    def test_loading_twice_is_refused(self):
        from mm import dataimport, templates
        c = loaded()
        for a, sheet in (("SD", "S1 Customers"), ("SD", "S4 Open sales orders"), ("HR", "H2 Employees"),
                         ("PP", "P3 Bills of material")):
            r = dataimport.run_xlsx(c, templates.workbook(a, example=True), "ADMIN", simulate=True)
            bad = [x for x in r["log"] if x["sheet"] == sheet and x["status"] == "E"]
            self.assertTrue(bad and all("already" in x["message"] for x in bad), (a, sheet, bad))


class Templates(unittest.TestCase):
    def test_every_area_has_guide_sheets_control_and_lists(self):
        from mm import templates, xlsx
        for a in ORDER:
            book = xlsx.read(templates.workbook(a))
            names = list(book)
            self.assertEqual(names[0], "00 Start here", a)
            self.assertIn("Control", names)
            self.assertIn("Lists", names)
            for n in names[1:-2]:
                self.assertEqual(len([r for r in book[n] if any(r)]), 3, (a, n))   # empty template: header rows only
        with self.assertRaises(Exception):
            templates.workbook("XX")

    def test_wrong_national_id_points_to_the_excel_row(self):
        from mm import dataimport, templates, xlsx
        c = connect(":memory:")
        for a in ("PUR", "SD", "MM", "FI"):
            dataimport.run_xlsx(c, templates.workbook(a, example=True), "ADMIN", simulate=False)
        book = xlsx.read(templates.workbook("HR", example=True))
        wb = xlsx.Workbook()
        for name in ("H1 Org units", "H2 Employees"):
            s = wb.add(name)
            for r, row in enumerate(book[name]):
                s.row(r, row)
        s.set(4, 3, "29912310101022")                     # second employee: ID with another birth date
        r = dataimport.run_xlsx(c, wb.save(), "ADMIN", simulate=True)
        bad = [x for x in r["log"] if x["status"] == "E"]
        self.assertEqual([(x["sheet"], x["line"]) for x in bad], [("H2 Employees", 5)])
        self.assertIn("national ID", bad[0]["message"])


if __name__ == "__main__":
    unittest.main()
