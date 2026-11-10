"""Users, roles and authorisations (review SEC-001, phase 5): logon, lock rules,
transaction and area authorisation, business objects, two-person rule, audit
log, AMS self-service requests and the approval inbox - engine and HTTP."""
import http.client
import json
import os
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fixture  # noqa: E402,F401  (fixed business date, fast hashing)
from mm import seed  # noqa: E402
from mm.db import connect  # noqa: E402
from mm.util import MMError  # noqa: E402
from sec import auth, inbox, users  # noqa: E402

_DB = {}


def demo():
    if "c" not in _DB:
        c = connect(":memory:")
        seed.seed(c)
        _DB["c"] = c
    return _DB["c"]


def err(test, fn, no):
    with test.assertRaises(MMError) as x:
        fn()
    test.assertEqual(x.exception.msg_no, no, str(x.exception))


class Logon(unittest.TestCase):
    def test_demo_users_logon_and_failed_logons_lock(self):
        c = demo()
        tok, must = users.login(c, "sales1", "sales1")
        self.assertFalse(must)
        self.assertEqual(users.session_user(c, tok), "SALES1")
        users.logout(c, tok, "SALES1")
        self.assertIsNone(users.session_user(c, tok))
        for _ in range(5):
            err(self, lambda: users.login(c, "AR1", "wrong"), "152")
        err(self, lambda: users.login(c, "AR1", "ar1"), "158")          # locked now
        self.assertEqual(c.execute("SELECT locked FROM usr WHERE bname='AR1'").fetchone()[0], "F")
        users.lock(c, "AR1", "ADMIN", on=False)
        users.login(c, "AR1", "ar1")

    def test_long_term_unused_self_service_unlock(self):
        c = demo()
        err(self, lambda: users.login(c, "TEMP01", "temp01"), "158")
        u = [x for x in users.users(c) if x["bname"] == "TEMP01"][0]
        self.assertEqual(u["status_text"], "Locked: long-term unused")
        n = users.unlock_request(c, "TEMP01", "back from leave")
        self.assertIsNone(users.unlock_request(c, "NOBODY"))           # no user enumeration
        err(self, lambda: users.decide(c, n, True, "TEMP01"), "024")
        users.decide(c, n, True, "ADMIN")
        users.login(c, "TEMP01", "temp01")

    def test_new_user_initial_password_must_change(self):
        c = demo()
        pw = users.save_user(c, {"bname": "NEW1", "name": "New colleague", "roles": ["BUYER"],
                                 "create": True}, "ADMIN")
        tok, must = users.login(c, "NEW1", pw)
        self.assertTrue(must)
        err(self, lambda: users.change_password(c, "NEW1", pw, "short"), "180")
        err(self, lambda: users.change_password(c, "NEW1", pw, "onlyletters"), "181")
        users.change_password(c, "NEW1", pw, "Buyer2026x")
        self.assertFalse(users.must_change(c, "NEW1"))
        err(self, lambda: users.save_user(c, {"bname": "NEW1", "name": "x", "create": True}, "ADMIN"), "224")


class Authorisation(unittest.TestCase):
    def test_tcode_area_and_objects_per_role(self):
        c = demo()
        p = auth.profile(c, "SALES1")
        self.assertTrue(auth.tcode_allowed(p, "VA01"))
        self.assertFalse(auth.tcode_allowed(p, "FB01"))
        self.assertTrue(auth.area_allowed(p, "SD", "02"))
        self.assertFalse(auth.area_allowed(p, "FI", "02"))
        self.assertTrue(auth.area_allowed(p, "FI", "03"))                 # display everywhere
        self.assertFalse(auth.object_allowed(p, "V_KNKK_FRE"))
        self.assertTrue(auth.object_allowed(auth.profile(c, "CREDIT1"), "V_KNKK_FRE"))
        a = auth.profile(c, "AUDIT1")
        self.assertTrue(auth.tcode_allowed(a, "FB01"))
        self.assertFalse(any(auth.area_allowed(a, x, "02") for x in ("SD", "FI", "MM", "BC")))
        err(self, lambda: auth.check(c, "SALES1", "F_REGU_BUK"), "078")
        self.assertEqual(auth.LAST_FAIL["SALES1"]["what"], "*")

    def test_access_request_inbox_and_suim(self):
        c = demo()
        req = [r for r in inbox.inbox(c, "ADMIN") if r["typ"] == "Access request"]
        self.assertTrue(any("CREDIT_MANAGER" in r["text"] for r in req))
        self.assertEqual(inbox.inbox(c, "SALES1"), [])                    # nothing to approve
        rid = int([r for r in req if "SALES1" in r["text"]][0]["key"])
        err(self, lambda: users.decide(c, rid, True, "SALES1"), "024")     # own request
        users.decide(c, rid, True, "ADMIN")
        self.assertTrue(auth.object_allowed(auth.profile(c, "SALES1"), "V_KNKK_FRE"))
        who = {r["bname"] for r in auth.users_for_tcode(c, "VKM1")}
        self.assertTrue({"SALES1", "CREDIT1", "ADMIN"} <= who)
        self.assertTrue(any(t["tcode"] == "VA01" for t in auth.tcodes_for_user(c, "SALES1")["tcodes"]))
        users.set_roles(c, "SALES1", ["SALES_CLERK"], "ADMIN")          # back to the demo state
        acts = {r["action"] for r in auth.audit_list(c)}
        self.assertIn("REQUEST_APPROVE", acts)

    def test_pfcg_role_maintenance(self):
        c = demo()
        users.save_role(c, {"name": "Z_TEST", "text": "Test", "tcodes": ["MM03", "MB*"],
                            "auths": [{"object": "S_AREA", "value": "MM", "actvt": "03"}]}, "ADMIN")
        users.set_roles(c, "WH1", ["WAREHOUSE", "Z_TEST"], "ADMIN")
        err(self, lambda: users.delete_role(c, "Z_TEST", "ADMIN"), "003")
        users.set_roles(c, "WH1", ["WAREHOUSE"], "ADMIN")
        users.delete_role(c, "Z_TEST", "ADMIN")
        err(self, lambda: users.save_role(c, {"name": "Z2", "auths": [{"object": "X", "actvt": "9"}]},
                                          "ADMIN"), "002")


class Http(unittest.TestCase):
    """The real server with logon on: 401 without session, 00 077 / 00 078 refusals."""

    @classmethod
    def setUpClass(cls):
        import web.server as S
        cls.dir = tempfile.mkdtemp()
        cls.old = os.environ.get("MM_DB")
        os.environ["MM_DB"] = os.path.join(cls.dir, "sec.db")
        c = connect()
        seed.seed(c, fixture.FIXED)
        c.close()
        cls.httpd = S.serve("127.0.0.1", 0, auto_stop=False, auth=True)
        cls.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        if cls.old is None:
            os.environ.pop("MM_DB", None)
        else:
            os.environ["MM_DB"] = cls.old

    def call(self, path, body=None, cookie=None, tcode=None):
        h = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        hd = {"Host": "127.0.0.1:%d" % self.port}
        if cookie:
            hd["Cookie"] = cookie
        if tcode:
            hd["X-Tcode"] = tcode
        if body is not None:
            hd["Content-Type"] = "application/json"
            h.request("POST", path, json.dumps(body), hd)
        else:
            h.request("GET", path, headers=hd)
        r = h.getresponse()
        data = json.loads(r.read() or b"{}")
        ck = r.getheader("Set-Cookie")
        h.close()
        return r.status, data, ck

    def logon(self, user):
        st, d, ck = self.call("/api/sec/login", {"bname": user, "password": user.lower()})
        self.assertEqual(st, 200, d)
        self.assertIn("HttpOnly", ck)
        self.assertIn("SameSite=Strict", ck)
        return ck.split(";")[0]

    def test_session_and_refusals(self):
        st, d, _ = self.call("/api/meta")
        self.assertEqual((st, d.get("number")), (401, "076"))
        st, d, _ = self.call("/api/sec/status")
        self.assertEqual((st, d["auth"], d["demo"]), (200, True, True))
        ck = self.logon("SALES1")
        self.assertEqual(self.call("/api/meta", cookie=ck)[0], 200)
        st, d, _ = self.call("/api/fi/ob52", {}, cookie=ck)                # FI change: no
        self.assertEqual((st, d["number"]), (403, "078"))
        st, d, _ = self.call("/api/sd/orders", cookie=ck, tcode="FB01")     # transaction: no
        self.assertEqual((st, d["number"]), (403, "077"))
        st, d, _ = self.call("/api/sec/su53", cookie=ck)
        self.assertEqual(d["kind"], "S_TCODE")
        st, d, _ = self.call("/api/sec/admin/users", cookie=ck)
        self.assertEqual(st, 403)
        me = self.call("/api/sec/me", cookie=ck)[1]
        self.assertIn("VA01", me["allowed"])
        self.assertNotIn("FB01", me["allowed"])
        ad = self.logon("ADMIN")
        st, d, _ = self.call("/api/sec/admin/users", cookie=ad)
        self.assertEqual(st, 200)
        st, d, _ = self.call("/api/sec/admin/audit?action=AUTH_FAIL", cookie=ad)
        self.assertTrue(any(r["bname"] == "SALES1" for r in d))
        self.call("/api/sec/logout", {}, cookie=ck)
        self.assertEqual(self.call("/api/meta", cookie=ck)[0], 401)

    def test_object_route_is_audited(self):
        ck = self.logon("CREDIT1")
        st, d, _ = self.call("/api/sd/order/999999/release", {}, cookie=ck)
        self.assertEqual(st, 422)                    # authorised; the order does not exist
        sl = self.logon("SALES1")
        st, d, _ = self.call("/api/sd/order/999999/release", {}, cookie=sl)
        self.assertEqual((st, d["number"]), (403, "078"))


if __name__ == "__main__":
    unittest.main()
