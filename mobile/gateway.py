"""MM Core Mobile - the ERP dashboard on the phone, live.

A small separate server for the phone (same Wi-Fi as the PC). It can only READ the
dashboard: the database is opened read-only (PRAGMA query_only), and it has no other
routes - nothing can be posted or changed from the phone.

Live: a watcher checks every 2 seconds whether any program committed a change to the
database (PRAGMA data_version); then the dashboard is computed again and pushed to every
connected phone at once (Server-Sent Events, /m/api/stream).

Security: a phone must be paired once with the secret key of this PC (QR code on the
pairing page, which only opens on the PC itself). The key is kept in data/mobile_key.txt;
"New key" on the pairing page disconnects every paired phone. Wrong keys are counted per
address; after 20 the address is blocked for 10 minutes.
"""
import hmac
import json
import os
import secrets
import socket
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC = os.path.join(ROOT, "mobile", "static")
KEY_FILE = os.path.join(ROOT, "data", "mobile_key.txt")
COOKIE = "mmcore_mobile"
POLL = 2.0            # seconds between change checks
REFRESH = 60.0        # recompute at least every minute (business date, time-based figures)
CURRENCIES = ("EGP", "USD", "EUR")
FILES = {"/m/": ("index.html", "text/html; charset=utf-8"), "/m/index.html": ("index.html", "text/html; charset=utf-8"),
         "/m/m.js": ("m.js", "text/javascript; charset=utf-8"), "/m/m.css": ("m.css", "text/css; charset=utf-8"),
         "/m/manifest.webmanifest": ("manifest.webmanifest", "application/manifest+json"),
         "/m/pair": ("pair.html", "text/html; charset=utf-8"), "/m/pair.js": ("pair.js", "text/javascript; charset=utf-8")}
ICON = os.path.join(ROOT, "icons", "mm_dashboard.png")


# ------------------------------------------------------------------ key
def load_key(renew=False):
    os.makedirs(os.path.dirname(KEY_FILE), exist_ok=True)
    if not renew:
        try:
            with open(KEY_FILE, encoding="utf-8") as f:
                k = f.read().strip()
                if len(k) >= 32:
                    return k
        except OSError:
            pass
    k = secrets.token_urlsafe(32)
    with open(KEY_FILE, "w", encoding="utf-8") as f:
        f.write(k)
    return k


def lan_addresses():
    """IPv4 addresses of this PC in the local network (the phone uses one of them)."""
    ips = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))          # no packet is sent; picks the LAN interface
        ips.append(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.append(info[4][0])
    except OSError:
        pass
    out = []
    for ip in ips:
        if ip not in out and not ip.startswith("127."):
            out.append(ip)
    return out or ["127.0.0.1"]


# ------------------------------------------------------------------ live data
class Hub:
    """Computes the dashboard when the database changed and wakes up the streams."""

    def __init__(self, db_path):
        self.db_path = db_path
        self.cond = threading.Condition()
        self.version = 0
        self.cache = {}                     # currency -> (version, json)
        self.lock = threading.Lock()
        self.stop = False
        self.conn = self._open()
        self.data_version = self._dv()
        self.last = time.time()
        self.changes = 0

    def _open(self):
        from mm.db import open_db
        c = open_db(self.db_path)
        c.execute("PRAGMA query_only = ON")             # this process never writes
        return c

    def _dv(self):
        return self.conn.execute("PRAGMA data_version").fetchone()[0]

    def payload(self, currency):
        """dashboard JSON in the currency (computed once per change)"""
        with self.lock:
            hit = self.cache.get(currency)
            if hit and hit[0] == self.version:
                return hit[1]
            from bi import overview
            d = overview.overview(self.conn, "MOBILE", everything=True, currency=currency)
            d["version"] = self.version
            d["changes"] = self.changes
            d["server_time"] = time.strftime("%H:%M:%S")
            s = json.dumps(d, default=str)
            self.cache[currency] = (self.version, s)
            return s

    def bump(self, changed):
        with self.lock:
            self.version += 1
            if changed:
                self.changes += 1
        with self.cond:
            self.cond.notify_all()

    def watch(self):
        while not self.stop:
            time.sleep(POLL)
            try:
                with self.lock:
                    dv = self._dv()
            except sqlite3.Error:
                continue
            if dv != self.data_version:
                self.data_version = dv
                self.last = time.time()
                self.bump(True)
            elif time.time() - self.last > REFRESH:
                self.last = time.time()
                self.bump(False)

    def wait(self, version, timeout):
        with self.cond:
            if self.version == version:
                self.cond.wait(timeout)
            return self.version


# ------------------------------------------------------------------ HTTP
class Handler(BaseHTTPRequestHandler):
    server_version = "MMCoreMobile/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):         # quiet
        pass

    @property
    def hub(self):
        return self.server.hub

    def _local(self):
        return self.client_address[0] in ("127.0.0.1", "::1", "::ffff:127.0.0.1")

    def _cookie(self):
        for part in (self.headers.get("Cookie") or "").split(";"):
            k, _, v = part.strip().partition("=")
            if k == COOKIE:
                return v
        return ""

    def _key_ok(self, key):
        return bool(key) and hmac.compare_digest(key.encode(), self.server.key.encode())

    def _blocked(self):
        ip = self.client_address[0]
        b = self.server.bad.get(ip)
        return b and b[0] >= 20 and time.time() - b[1] < 600

    def _bad(self):
        ip = self.client_address[0]
        n, t = self.server.bad.get(ip, (0, time.time()))
        self.server.bad[ip] = (n + 1, time.time())

    def _send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; "
                         "style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'")
        for k, v in (extra or []):
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def _err(self, code, text):
        self._send(code, json.dumps({"type": "E", "text": text}))

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        u = urlparse(self.path)
        p, q = u.path, {k: v[0] for k, v in parse_qs(u.query).items()}
        if p in ("/", "/m"):
            return self._send(302, b"", extra=[("Location", "/m/")])
        if p in ("/m/pair", "/m/pair.js", "/m/api/pairinfo", "/m/api/qr.svg") and not self._local():
            return self._err(403, "The pairing page opens only on the PC itself")
        if p in FILES:
            name, ctype = FILES[p]
            with open(os.path.join(STATIC, name), "rb") as f:
                return self._send(200, f.read(), ctype)
        if p == "/m/icon.png":
            with open(ICON, "rb") as f:
                return self._send(200, f.read(), "image/png")
        if p == "/m/api/pairinfo":
            return self._send(200, json.dumps(self.server.pair_info()))
        if p == "/m/api/qr.svg":
            from .qr import svg
            ip = q.get("ip") or self.server.pair_info()["ips"][0]
            if ip not in self.server.pair_info()["ips"]:
                return self._err(400, "Unknown address")
            return self._send(200, svg(self.server.link(ip)), "image/svg+xml")
        if p in ("/m/api/overview", "/m/api/stream"):
            if self._blocked():
                return self._err(429, "Too many wrong keys - try again in 10 minutes")
            if not (self._key_ok(self._cookie()) or (self._local() and self.server.local_free)):
                return self._err(401, "This phone is not paired - scan the QR code on the PC (MM Core Mobile)")
            cur = (q.get("currency") or "EGP").upper()
            if cur not in CURRENCIES:
                return self._err(400, "Currency must be EGP, USD or EUR")
            if p == "/m/api/overview":
                try:
                    return self._send(200, self.hub.payload(cur))
                except Exception as e:  # noqa - shown on the phone
                    return self._err(500, "Dashboard error: %s" % e)
            return self._stream(cur)
        return self._err(404, "Not found")

    def do_POST(self):
        u = urlparse(self.path)
        n = int(self.headers.get("Content-Length") or 0)
        if n > 4096:
            return self._err(413, "Too large")
        try:
            body = json.loads((self.rfile.read(n) if n else b"{}").decode("utf-8") or "{}")
        except ValueError:
            return self._err(400, "Invalid JSON")
        if not (self.headers.get("Content-Type") or "").startswith("application/json"):
            return self._err(415, "JSON expected")
        if u.path == "/m/api/pair":
            if self._blocked():
                return self._err(429, "Too many wrong keys - try again in 10 minutes")
            key = str(body.get("key") or "")
            if not self._key_ok(key):
                self._bad()
                return self._err(401, "Wrong or old key - scan the QR code on the PC again")
            ck = "%s=%s; Path=/m/; Max-Age=31536000; HttpOnly; SameSite=Strict" % (COOKIE, key)
            return self._send(200, json.dumps({"ok": True}), extra=[("Set-Cookie", ck)])
        if u.path == "/m/api/renew":
            if not self._local():
                return self._err(403, "Only on the PC itself")
            self.server.key = load_key(renew=True)
            return self._send(200, json.dumps({"ok": True, "message": "New key - every paired phone must scan again"}))
        if u.path == "/m/api/stop":
            if not self._local():
                return self._err(403, "Only on the PC itself")
            self._send(200, json.dumps({"ok": True, "message": "Mobile access stopped"}))
            threading.Timer(0.5, self.server.shutdown).start()
            return None
        return self._err(404, "Not found")

    def _stream(self, cur):
        """Server-Sent Events: the dashboard now, then after every change."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        self.close_connection = True
        seen = -1
        self.server.streams += 1
        try:
            self.wfile.write(b"retry: 3000\n\n")
            while not self.hub.stop:
                v = self.hub.version
                if v != seen:
                    seen = v
                    self.wfile.write(b"event: dashboard\ndata: " + self.hub.payload(cur).encode("utf-8") + b"\n\n")
                    self.wfile.flush()
                if self.hub.wait(seen, 15) == seen:
                    self.wfile.write(b": keep-alive\n\n")            # keeps Wi-Fi / NAT connections open
                    self.wfile.flush()
        except (OSError, ValueError):
            pass
        finally:
            self.server.streams -= 1


class Gateway(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = os.name != "nt"

    def __init__(self, addr, db_path, local_free=False):
        super().__init__(addr, Handler)
        self.key = load_key()
        self.bad = {}
        self.streams = 0
        self.local_free = local_free           # the PC itself may look without pairing
        self.hub = Hub(db_path)
        self.db_path = db_path
        threading.Thread(target=self.hub.watch, daemon=True).start()

    def link(self, ip):
        return "http://%s:%d/m/#k=%s" % (ip, self.server_address[1], self.key)

    def pair_info(self):
        ips = lan_addresses()
        return {"ips": ips, "port": self.server_address[1], "links": [self.link(i) for i in ips],
                "db": self.db_path, "connected": self.streams}

    def server_close(self):
        self.hub.stop = True
        with self.hub.cond:
            self.hub.cond.notify_all()
        super().server_close()


def serve(db_path, host="0.0.0.0", port=8090, local_free=True):
    return Gateway((host, port), db_path, local_free=local_free)
