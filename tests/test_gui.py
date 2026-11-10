"""Desktop client logic (MM Core Logon / Easy Access): system entries, command
field, favorites, session URL and the menu served for the client."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fixture  # noqa: E402,F401
from gui import client as C  # noqa: E402


class Client(unittest.TestCase):
    def test_system_entries_are_checked(self):
        systems = [dict(x) for x in C.DEFAULT_SYSTEMS]
        s = C.check_system(dict(name="Test", sid="tst", db="data/t.db", port="8090"), systems)
        self.assertEqual((s["sid"], s["port"]), ("TST", 8090))
        for bad in (dict(name="", sid="ABC", db="x.db", port=8090), dict(name="x", sid="AB", db="x.db", port=8090),
                    dict(name="x", sid="ABC", db="x.txt", port=8090), dict(name="x", sid="PRD", db="x.db", port=8090),
                    dict(name="x", sid="ABC", db="x.db", port=8080), dict(name="x", sid="ABC", db="x.db", port="z")):
            with self.assertRaises(C.ClientError):
                C.check_system(bad, systems)

    def test_command_field(self):
        self.assertEqual(C.parse_okcode("mm03"), ("same", "MM03"))
        self.assertEqual(C.parse_okcode("/oVA01"), ("new", "VA01"))
        self.assertEqual(C.parse_okcode("/nMIGO"), ("same", "MIGO"))
        self.assertEqual(C.parse_okcode("/nend"), ("logoff", None))
        self.assertEqual(C.parse_okcode("  "), (None, None))

    def test_favorites_per_system_and_session_url(self):
        d = tempfile.mkdtemp()
        old = C.FAV_FILE, C.DATA
        C.FAV_FILE, C.DATA = os.path.join(d, "f.json"), d
        try:
            self.assertTrue(C.load_favorites("PRD"))
            C.save_favorites("PRD", [dict(type="tx", tcode="MIGO")])
            self.assertEqual(C.load_favorites("PRD"), [dict(type="tx", tcode="MIGO")])
            self.assertNotEqual(C.load_favorites("TRN"), [dict(type="tx", tcode="MIGO")])
        finally:
            C.FAV_FILE, C.DATA = old
        u = C.session_url(dict(port=8080), "mb52", "SALES1", "tok")
        self.assertEqual(u, "http://localhost:8080/?session=1&user=SALES1&sso=tok#/MB52")

    def test_menu_for_the_client_has_every_transaction_with_a_title(self):
        from web import gui_api
        m = gui_api.menu_tree()
        codes = set()

        def walk(n):
            if isinstance(n, str):
                codes.add(n.lstrip("!"))
            else:
                for k in n[1]:
                    walk(k)
        for n in m["tree"]:
            walk(n)
        self.assertGreater(len(codes), 300)
        self.assertEqual(sorted(c for c in codes if c not in m["titles"]), [],
                         "run tools/gui/export_tcodes.js to refresh web/static/tcodes.json")


if __name__ == "__main__":
    unittest.main()
