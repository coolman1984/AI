"""NERP Mobile: QR code, pairing with the secret key, read-only gateway and the live
stream (a change committed by NERP reaches the phone without reloading)."""
import http.client
import json
import os
import socket
import sqlite3
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fixture  # noqa: E402,F401
from mm import seed  # noqa: E402
from mm.db import connect  # noqa: E402


class QrCode(unittest.TestCase):
    def test_reed_solomon_and_matrix(self):
        from mobile import qr
        # ISO 18004 example "HELLO WORLD" 1-M: data codewords -> error correction codewords
        self.assertEqual(qr.rs_ecc([32, 91, 11, 120, 209, 114, 220, 77, 67, 64, 236, 17, 236, 17, 236, 17], 10),
                         [196, 35, 39, 119, 235, 215, 231, 226, 93, 23])
        m = qr.matrix("http://192.168.1.25:8090/m/#k=" + "x" * 43)
        n = len(m)
        self.assertEqual((n - 17) % 4, 0)
        for x0, y0 in ((0, 0), (n - 7, 0), (0, n - 7)):                 # three finder patterns
            self.assertEqual([m[y0][x0 + i] for i in range(7)], [1] * 7)
            self.assertEqual(m[y0 + 3][x0 + 3], 1)
            self.assertEqual(m[y0 + 1][x0 + 1], 0)
        self.assertEqual(m[n - 8][8], 1)                                 # dark module
        self.assertIn("<svg", qr.svg("NERP"))
        with self.assertRaises(ValueError):
            qr.matrix("x" * 300)


class Gateway(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from mobile import gateway
        cls.dir = tempfile.mkdtemp()
        cls.db = os.path.join(cls.dir, "mob.db")
        c = connect(cls.db)
        seed.seed(c, fixture.FIXED)
        c.close()
        gateway.KEY_FILE = os.path.join(cls.dir, "mobile_key.txt")
        gateway.POLL = 0.3
        cls.srv = gateway.Gateway(("127.0.0.1", 0), cls.db, local_free=False)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def call(self, path, body=None, cookie=None):
        h = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        hd = {"Cookie": cookie} if cookie else {}
        if body is not None:
            hd["Content-Type"] = "application/json"
            h.request("POST", path, json.dumps(body), hd)
        else:
            h.request("GET", path, headers=hd)
        r = h.getresponse()
        raw = r.read()
        ck = r.getheader("Set-Cookie")
        h.close()
        try:
            data = json.loads(raw or b"{}")
        except ValueError:
            data = raw
        return r.status, data, ck

    def pair(self):
        st, d, ck = self.call("/m/api/pair", {"key": self.srv.key})
        self.assertEqual(st, 200, d)
        self.assertIn("HttpOnly", ck)
        return ck.split(";")[0]

    def test_pairing_read_only_and_routes(self):
        self.assertEqual(self.call("/m/api/overview")[0], 401)            # not paired
        st, d, _ = self.call("/m/api/pair", {"key": "wrong-key-wrong-key-wrong-key-123"})
        self.assertEqual(st, 401)
        ck = self.pair()
        st, d, _ = self.call("/m/api/overview?currency=USD", cookie=ck)
        self.assertEqual((st, d["currency"]), (200, "USD"))
        self.assertIn("finance", d)
        self.assertEqual(self.call("/m/api/overview?currency=XYZ", cookie=ck)[0], 400)
        self.assertEqual(self.call("/api/meta", cookie=ck)[0], 404)          # nothing of NERP itself
        self.assertEqual(self.call("/m/", cookie=ck)[0], 200)
        st, info, _ = self.call("/m/api/pairinfo")
        self.assertTrue(info["links"][0].endswith(self.srv.key))
        self.assertEqual(self.call("/m/api/qr.svg")[0], 200)
        with self.assertRaises(sqlite3.OperationalError):                   # the gateway never writes
            self.srv.hub.conn.execute("UPDATE material SET maktx='x'")
        old = self.srv.key
        self.call("/m/api/renew", {})
        self.assertNotEqual(self.srv.key, old)
        self.assertEqual(self.call("/m/api/overview", cookie=ck)[0], 401)  # old phones are out

    def test_live_update_reaches_the_phone(self):
        ck = self.pair()
        s = socket.create_connection(("127.0.0.1", self.port), timeout=20)
        s.sendall(("GET /m/api/stream?currency=EGP HTTP/1.1\r\nHost: x\r\nCookie: %s\r\n\r\n" % ck).encode())
        f = s.makefile("rb")

        def next_event():
            data = None
            while True:
                line = f.readline()
                if not line:
                    return None
                if line.startswith(b"data: "):
                    data = json.loads(line[6:])
                elif line == b"\n" and data is not None:
                    return data
        first = next_event()
        self.assertIn("finance", first)
        t0 = time.time()
        w = connect(self.db)                                                # NERP saves something
        w.execute("UPDATE material SET maktx=maktx || ' ' WHERE matnr='FG-3001'")
        w.close()
        second = next_event()
        s.close()
        self.assertGreater(second["version"], first["version"])
        self.assertGreater(second["changes"], first["changes"])
        self.assertLess(time.time() - t0, 10)

    def test_wrong_keys_are_blocked(self):
        from mobile import gateway
        srv = gateway.Gateway(("127.0.0.1", 0), self.db, local_free=False)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        port, self.port = self.port, srv.server_address[1]
        try:
            for _ in range(20):
                self.call("/m/api/pair", {"key": "x" * 40})
            self.assertEqual(self.call("/m/api/pair", {"key": srv.key})[0], 429)
        finally:
            self.port = port
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    unittest.main()
