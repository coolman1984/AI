"""Data takeover with the Excel workbook (ZIMPORT): purchasing template, whole-workbook
simulation and posting in the right order, legacy vendor / purchase order numbers,
comparison file <-> system, and the real-data system that never gets demo data."""
import base64
import json
import os
import sys
import tempfile
import threading
import unittest
import http.client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fixture  # noqa: E402,F401
from mm.db import connect  # noqa: E402
from mm.util import MMError  # noqa: E402


def empty():
    return connect(":memory:")


class Xlsx(unittest.TestCase):
    def test_write_read_roundtrip_dates_and_codes(self):
        from mm import xlsx
        wb = xlsx.Workbook()
        s = wb.add("Data")
        s.row(0, ["werks", "price", "bedat", "text"])
        s.row(1, ["0001", 12.5, "2026-10-15", "صاج 2 مم"])
        s.set(2, 0, "1000", xlsx.TEXT)
        s.set(2, 1, 46000)                                 # Excel serial date typed as a number
        s.set(3, 1, "SUM(B2:B3)", kind="f")
        book = xlsx.read(wb.save())
        self.assertEqual(book["Data"][1], ["0001", "12.5", "2026-10-15", "صاج 2 مم"])
        self.assertEqual(xlsx.excel_date(book["Data"][2][1]), "2025-12-09")
        self.assertEqual(xlsx.excel_date("15.10.2026"), "2026-10-15")
        with self.assertRaises(xlsx.XlsxError):
            xlsx.read(b"not an excel file")


class PurchasingWorkbook(unittest.TestCase):
    def test_example_loads_verifies_and_detects_differences(self):
        from mm import dataimport, templates
        c = empty()
        book = templates.purchasing_workbook(example=True)
        r = dataimport.run_xlsx(c, book, "BUYER1", simulate=True)
        self.assertEqual(r["errors"], 0, [x for x in r["log"] if x["status"] == "E"])
        self.assertEqual(c.execute("SELECT COUNT(*) FROM vendor").fetchone()[0], 0)     # simulation keeps nothing
        r = dataimport.run_xlsx(c, book, "BUYER1", simulate=False)
        self.assertEqual((r["errors"], r["ok"]), (0, 21))
        # legacy numbers: vendor V-1001 got an NERP number, the old PO has two items and is released
        v = c.execute("SELECT * FROM vendor WHERE altkn='V-1001'").fetchone()
        self.assertTrue(v["lifnr"].startswith("1"))
        h = c.execute("SELECT * FROM po_header WHERE ihrez='PO-2026-0451'").fetchone()
        self.assertEqual((h["lifnr"], h["frgke"] in ("", "R")), (v["lifnr"], True))
        self.assertEqual(c.execute("SELECT COUNT(*) FROM po_item WHERE ebeln=?", (h["ebeln"],)).fetchone()[0], 2)
        res = dataimport.verify_xlsx(c, book)
        self.assertTrue(res["all_ok"], res["differences"])
        po = [s for s in res["summary"] if s["sheet"].startswith("08")][0]
        self.assertIn("file 249500.00 / NERP 249500.00", po["control"])
        c.execute("UPDATE info_record SET brutto=4900 WHERE matnr='RM-1001'")
        res = dataimport.verify_xlsx(c, book)
        self.assertEqual([(d["field"], d["file"], d["system"]) for d in res["differences"]], [("price", "48.50", "49.00")])
        again = dataimport.run_xlsx(c, book, "BUYER1", simulate=True)                  # loading twice is refused
        self.assertTrue(any("already" in x["message"] for x in again["log"] if x["sheet"].startswith("05")))
        self.assertTrue(any("already loaded" in x["message"] for x in again["log"] if x["sheet"].startswith("08")))

    def test_errors_point_to_sheet_and_excel_row(self):
        from mm import dataimport, templates, xlsx
        c = empty()
        book = xlsx.read(templates.purchasing_workbook(example=True))
        wb = xlsx.Workbook()
        for name in ("01 Plants", "05 Vendors"):
            s = wb.add(name)
            for r, row in enumerate(book[name]):
                s.row(r, row)
        s.set(4, 10, "12345")                              # second vendor: wrong tax number (col K = stcd1)
        r = dataimport.run_xlsx(c, wb.save(), "BUYER1", simulate=True)
        bad = [x for x in r["log"] if x["status"] == "E"]
        self.assertEqual([(x["sheet"], x["line"]) for x in bad], [("05 Vendors", 5)])
        self.assertIn("9 digits", bad[0]["message"])
        with self.assertRaises(MMError):
            dataimport.run_xlsx(c, b"PK-not-a-workbook", "BUYER1")

    def test_template_has_guide_dropdowns_and_control(self):
        from mm import templates, xlsx
        b = templates.purchasing_workbook()
        book = xlsx.read(b)
        self.assertEqual(list(book)[:2], ["00 Start here", "01 Plants"])
        self.assertIn("Control", book)
        self.assertEqual(book["05 Vendors"][1][0], "altkn")
        self.assertEqual(len([r for r in book["05 Vendors"] if any(r)]), 3)      # empty template: no data rows
        import zipfile, io
        z = zipfile.ZipFile(io.BytesIO(b))
        sheet = z.read("xl/worksheets/sheet6.xml").decode()                        # 05 Vendors
        self.assertIn("<dataValidation", sheet)
        self.assertIn("Lists!", sheet)


class RealDataSystem(unittest.TestCase):
    def test_empty_system_never_gets_demo_data(self):
        from mm import seed
        d = tempfile.mkdtemp()
        path = os.path.join(d, "company.db")
        c = connect(path)
        seed.mark_no_demo(c)
        c.close()
        c = connect(path)
        self.assertIsNone(seed.seed(c))                                            # still empty
        self.assertEqual(c.execute("SELECT COUNT(*) FROM plant").fetchone()[0], 0)
        from gui import client
        self.assertTrue(any(s["sid"] == "LIV" and s["empty"] for s in client.DEFAULT_SYSTEMS))


class Http(unittest.TestCase):
    def test_upload_and_compare_over_http(self):
        import web.server as S
        from mm import templates
        d = tempfile.mkdtemp()
        old = os.environ.get("MM_DB")
        os.environ["MM_DB"] = os.path.join(d, "t.db")
        connect().close()
        httpd = S.serve("127.0.0.1", 0, auto_stop=False, auth=False)
        port = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()

        def call(path, body=None):
            h = http.client.HTTPConnection("127.0.0.1", port, timeout=60)
            hd = {"Host": "127.0.0.1:%d" % port, "X-User": "BUYER1"}
            if body is None:
                h.request("GET", path, headers=hd)
            else:
                hd["Content-Type"] = "application/json"
                h.request("POST", path, json.dumps(body), hd)
            r = h.getresponse()
            out = (r.status, json.loads(r.read()))
            h.close()
            return out
        try:
            st, t = call("/api/import/workbook/PUR?example=1")
            self.assertEqual(st, 200)
            self.assertEqual(base64.b64decode(t["xlsx"]), templates.purchasing_workbook(example=True))
            st, r = call("/api/import/xlsx", {"obj": "ALL", "xlsx": t["xlsx"], "simulate": False})
            self.assertEqual((st, r["errors"]), (200, 0))
            st, v = call("/api/import/verify", {"obj": "ALL", "xlsx": t["xlsx"]})
            self.assertTrue(v["all_ok"])
            st, e = call("/api/import/xlsx", {"obj": "ALL", "xlsx": "@@@"})
            self.assertEqual(st, 422)
        finally:
            httpd.shutdown()
            httpd.server_close()
            if old is None:
                os.environ.pop("MM_DB", None)
            else:
                os.environ["MM_DB"] = old


if __name__ == "__main__":
    unittest.main()
