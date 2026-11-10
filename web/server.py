"""HTTP server + JSON API (standard library only).

Start with:  python run.py      then open http://localhost:8080
"""
import datetime
import json
import mimetypes
import os
import re
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from mm import master, posting, reports
from mm.config import (GL_ACCOUNTS, MATERIAL_TYPES, MOVEMENT_TYPES, STOCK_TYPES,
                       UNITS)
from mm.db import connect, rows
from mm.util import CURRENCY, MMError, amt_out, qty_out
from office import com_bridge
from mm import util as mmclock  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC = os.path.join(ROOT, "web", "static")
EXPORTS = os.path.join(ROOT, "exports")

_local = threading.local()


def db():
    if not hasattr(_local, "conn"):
        _local.conn = connect()
    return _local.conn


ROUTES = []


def route(method, pattern):
    def deco(fn):
        ROUTES.append((method, re.compile("^" + pattern + "$"), fn))
        return fn
    return deco


# ====================================================================== meta
@route("GET", "/api/meta")
def api_meta(req, q):
    c = db()
    return {
        "user": req.user, "currency": CURRENCY, "today": mmclock.today()
        .isoformat(),
        "plants": rows(c.execute("SELECT * FROM plant ORDER BY werks")),
        "slocs": rows(c.execute("SELECT * FROM sloc ORDER BY werks, lgort")),
        "vendors": rows(c.execute("SELECT * FROM vendor ORDER BY lifnr")),
        "cost_centers": rows(c.execute("SELECT * FROM cost_center ORDER BY kostl")),
        "movement_types": reports.movement_types(),
        "stock_types": STOCK_TYPES,
        "material_types": {k: v[0] for k, v in MATERIAL_TYPES.items()},
        "units": UNITS,
        "gl_accounts": GL_ACCOUNTS,
        "com": dict(zip(("available", "reason"), com_bridge.available())),
    }


@route("GET", "/api/dashboard")
def api_dashboard(req, q):
    return reports.dashboard(db(), int(q.get("days", 30)))


# ====================================================================== master
@route("GET", "/api/materials")
def api_materials(req, q):
    return reports_materials(q.get("q", ""))


def reports_materials(text):
    c = db()
    out = master.search_materials(c, text)
    for m in out:
        m["plants"] = [r["werks"] for r in c.execute(
            "SELECT werks FROM material_plant WHERE matnr=?", (m["matnr"],))]
    return out


@route("GET", "/api/material/(?P<matnr>[^/]+)")
def api_material(req, q, matnr):
    m = master.get_material(db(), matnr.upper())
    for p in m["plants"]:
        for k in ("minbe", "eisbe", "lbkum"):
            p[k] = qty_out(p[k])
        for k in ("verpr", "stprs", "salk3"):
            p[k] = amt_out(p[k])
    return m


@route("POST", "/api/material")
def api_material_create(req, q):
    matnr = master.create_material(db(), req.body, req.user)
    return {"matnr": matnr, "message": "Material %s created" % matnr}


@route("POST", "/api/material/(?P<matnr>[^/]+)/change")
def api_material_change(req, q, matnr):
    master.change_material(db(), matnr.upper(), req.body)
    return {"message": "Material %s changed" % matnr.upper()}


@route("POST", "/api/material/(?P<matnr>[^/]+)/extend")
def api_material_extend(req, q, matnr):
    master.extend_material(db(), matnr.upper(), req.body)
    return {"message": "Material %s extended to plant %s"
            % (matnr.upper(), req.body.get("werks"))}


@route("POST", "/api/plant")
def api_plant(req, q):
    b = req.body
    master.create_plant(db(), b.get("werks"), b.get("name") or "", b.get("city"))
    return {"message": "Plant %s created" % b.get("werks")}


@route("POST", "/api/sloc")
def api_sloc(req, q):
    b = req.body
    master.create_sloc(db(), b.get("werks"), b.get("lgort"), b.get("name") or "",
                       bool(b.get("bin_managed")))
    return {"message": "Storage location %s %s created" % (b.get("werks"),
                                                           b.get("lgort"))}


@route("POST", "/api/bin")
def api_bin(req, q):
    b = req.body
    names = b.get("lgpla_list") or [b.get("lgpla")]
    for n in names:
        master.create_bin(db(), b.get("werks"), b.get("lgort"), n,
                          b.get("bin_type") or "")
    return {"message": "%d storage bin(s) created" % len(names)}


@route("POST", "/api/bin/block")
def api_bin_block(req, q):
    b = req.body
    master.set_bin_blocked(db(), b["werks"], b["lgort"], b["lgpla"],
                           bool(b.get("blocked")))
    return {"message": "Storage bin %s %s" % (b["lgpla"], "blocked" if
                                               b.get("blocked") else "unblocked")}


@route("POST", "/api/vendor")
def api_vendor(req, q):
    b = req.body
    master.create_vendor(db(), b.get("lifnr"), b.get("name") or "", b.get("city"))
    return {"message": "Vendor %s created" % b.get("lifnr")}


@route("POST", "/api/costcenter")
def api_kostl(req, q):
    b = req.body
    master.create_cost_center(db(), b.get("kostl"), b.get("name") or "")
    return {"message": "Cost center %s created" % b.get("kostl")}


# ====================================================================== purchasing
@route("POST", "/api/po")
def api_po_create(req, q):
    e = master.create_po(db(), req.body, req.user)
    return {"ebeln": e, "message": "Standard PO created under the number %s" % e}


@route("GET", "/api/po/(?P<ebeln>[0-9]+)")
def api_po(req, q, ebeln):
    po = master.get_po(db(), ebeln)
    for it in po["items"]:
        for k in ("menge", "wemng", "open"):
            it[k] = qty_out(it[k])
        it["netpr"] = amt_out(it["netpr"])
        it["value"] = amt_out(it["value"])
    po["history"] = [r for r in reports.document_list(db()) if r["ebeln"] == ebeln]
    return po


@route("GET", "/api/pos")
def api_pos(req, q):
    out = master.list_pos(db(), q.get("open") == "1")
    for r in out:
        for k in ("menge", "wemng", "open"):
            r[k] = qty_out(r[k])
        r["netpr"] = amt_out(r["netpr"])
    return out


# ====================================================================== stock
@route("GET", "/api/stock/overview/(?P<matnr>[^/]+)")
def api_mmbe(req, q, matnr):
    return reports.stock_overview(db(), matnr.upper())


@route("GET", "/api/stock/warehouse")
def api_mb52(req, q):
    return reports.warehouse_stock(db(), q.get("matnr", "").upper(),
                                   q.get("werks", ""), q.get("lgort", ""),
                                   q.get("mtart", ""), q.get("zero") != "1")


@route("GET", "/api/docs")
def api_mb51(req, q):
    return reports.document_list(db(), q.get("matnr", "").upper(),
                                 q.get("werks", ""), q.get("lgort", ""),
                                 q.get("bwart", ""), q.get("from", ""),
                                 q.get("to", ""), q.get("usnam", ""))


@route("GET", "/api/doc/(?P<mjahr>[0-9]{4})/(?P<mblnr>[0-9]+)")
def api_mb03(req, q, mjahr, mblnr):
    return reports.get_document(db(), mblnr, int(mjahr))


@route("GET", "/api/doc/(?P<mblnr>[0-9]+)")
def api_mb03_any_year(req, q, mblnr):
    r = db().execute("SELECT mjahr FROM mat_doc WHERE mblnr=? ORDER BY mjahr DESC",
                     (mblnr,)).fetchone()
    if not r:
        raise MMError("Document %s does not exist" % mblnr, "M7", "060")
    return reports.get_document(db(), mblnr, r["mjahr"])


@route("GET", "/api/accdoc/(?P<gjahr>[0-9]{4})/(?P<belnr>[0-9]+)")
def api_fb03(req, q, gjahr, belnr):
    return reports.get_acc_document(db(), belnr, int(gjahr))


@route("POST", "/api/goodsmovement")
def api_migo(req, q):
    b = req.body
    return posting.post_goods_movement(db(), b.get("header") or {},
                                       b.get("items") or [], req.user,
                                       b.get("tcode") or "MIGO",
                                       check_only=bool(b.get("check")))


@route("POST", "/api/doc/cancel")
def api_mbst(req, q):
    b = req.body
    return posting.cancel_document(db(), b.get("mblnr"), int(b.get("mjahr")),
                                   b.get("budat"), req.user, b.get("reason") or "")


@route("POST", "/api/pricechange")
def api_mr21(req, q):
    b = req.body
    res = posting.change_price(db(), b.get("matnr", "").upper(), b.get("werks"),
                               b.get("price"), b.get("budat"), req.user,
                               b.get("peinh"))
    res["revaluation"] = amt_out(res["revaluation"])
    res["old_price"] = amt_out(res["old_price"])
    res["new_price"] = amt_out(res["new_price"])
    res["message"] = "Price changed" + (", document %s posted" % res["belnr"]
                                        if res["belnr"] else "")
    return res


@route("GET", "/api/pricehistory")
def api_price_hist(req, q):
    return reports.price_history(db(), q.get("matnr", "").upper(), q.get("werks"))


@route("GET", "/api/quants")
def api_lx02(req, q):
    return reports.quant_list(db(), q.get("werks", ""), q.get("lgort", ""),
                              q.get("matnr", "").upper(), q.get("lgpla", ""))


@route("GET", "/api/bins")
def api_lx03(req, q):
    return reports.bin_status(db(), q.get("werks", ""), q.get("lgort", ""))


@route("GET", "/api/bin/propose")
def api_bin_propose(req, q):
    return posting.propose_bin(db(), q.get("matnr", "").upper(), q.get("werks"),
                               q.get("lgort"), q.get("insmk", "U")) or {}


@route("GET", "/api/check")
def api_check(req, q):
    return reports.consistency_check(db())


# ====================================================================== office
@route("GET", "/api/office/status")
def api_office_status(req, q):
    ok, why = com_bridge.available()
    return {"available": ok, "reason": why, "exports": EXPORTS}


@route("POST", "/api/office/excel-export")
def api_excel_export(req, q):
    b = req.body
    os.makedirs(EXPORTS, exist_ok=True)
    name = re.sub(r"[^A-Za-z0-9_-]+", "_", b.get("title") or "export")
    path = os.path.join(EXPORTS, "%s_%s.xlsx" % (
        name, mmclock.now().strftime("%Y%m%d_%H%M%S")))
    com_bridge.excel_write(path, [{"name": (b.get("title") or "Data")[:31],
                                   "header": b.get("header") or [],
                                   "rows": b.get("rows") or []}], visible=True)
    return {"path": path, "message": "Exported to Excel: %s" % path}


@route("POST", "/api/office/excel-read")
def api_excel_read(req, q):
    b = req.body
    return com_bridge.excel_read(b.get("path", "").strip().strip('"'),
                                 b.get("sheet") or None)


@route("POST", "/api/office/pdf-read")
def api_pdf_read(req, q):
    return com_bridge.pdf_read_text(req.body.get("path", "").strip().strip('"'))


@route("POST", "/api/office/ppt-read")
def api_ppt_read(req, q):
    return com_bridge.powerpoint_read_text(req.body.get("path", "").strip()
                                           .strip('"'))


@route("GET", "/api/office/inbox")
def api_inbox(req, q):
    return com_bridge.outlook_inbox(int(q.get("count", 10)))


@route("POST", "/api/office/outlook-draft")
def api_outlook(req, q):
    b = req.body
    com_bridge.outlook_draft(b.get("to", ""), b.get("subject", ""),
                             b.get("html", ""), b.get("cc", ""))
    return {"message": "Mail opened in Outlook - check it and press Send"}


# ====================================================================== handler
class Handler(BaseHTTPRequestHandler):
    server_version = "MMCore/1.0"

    def log_message(self, fmt, *args):  # quieter console
        if os.environ.get("MM_LOG"):
            super().log_message(fmt, *args)

    @property
    def user(self):
        return (self.headers.get("X-User") or "OWNER").upper()[:12]

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def _dispatch(self, method):
        u = urlparse(self.path)
        if not u.path.startswith("/api/"):
            return self._static(u.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        self.body = {}
        if method == "POST":
            n = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(n) if n else b"{}"
            try:
                self.body = json.loads(raw.decode("utf-8") or "{}")
            except ValueError:
                return self._json(400, {"type": "E", "text": "Invalid JSON"})
        for m, rx, fn in ROUTES:
            if m != method:
                continue
            mt = rx.match(u.path)
            if mt:
                try:
                    return self._json(200, fn(self, q, **mt.groupdict()))
                except MMError as e:
                    return self._json(422, e.as_dict())
                except com_bridge.ComError as e:
                    return self._json(422, {"type": "E", "class": "COM",
                                            "number": "001", "text": str(e)})
                except Exception:  # noqa - details go to the log, not to the browser
                    import secrets
                    from mm.log import LOG
                    ref = "%s-%s" % (time.strftime("%Y%m%d%H%M%S"), secrets.token_hex(3))
                    LOG.exception("internal error %s on %s %s", ref, method, u.path)
                    traceback.print_exc()
                    return self._json(500, {"type": "E", "ref": ref, "text": "Internal error - "
                                            "reference %s (details in data/mm_core.log)" % ref})
        self._json(404, {"type": "E", "text": "Unknown function %s" % u.path})

    def _json(self, code, obj):
        data = json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _static(self, path):
        if path in ("", "/"):
            path = "/index.html"
        full = os.path.normpath(os.path.join(STATIC, path.lstrip("/")))
        if not full.startswith(STATIC) or not os.path.isfile(full):
            full = os.path.join(STATIC, "index.html")
        with open(full, "rb") as f:
            data = f.read()
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype.endswith("javascript"):
            ctype += "; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)


# ====================================================================== lifecycle
class Lifecycle:
    """Stops the server automatically when the last browser tab is closed.

    Every open tab sends a heartbeat ("ping") every 10 seconds and a
    goodbye ("bye") when it is closed. When no tab is left, the server
    waits a few seconds (a page reload says bye and hello again) and then
    stops. Browsers slow down timers in hidden tabs to about once a minute,
    so a tab only counts as gone after IDLE seconds without a heartbeat.
    """
    IDLE = 150          # seconds without heartbeat -> tab counts as closed
    GRACE = 8           # seconds with no open tab -> stop
    FIRST_CONTACT = 600  # stop if no browser ever connects

    def __init__(self, httpd, enabled=True):
        self.httpd = httpd
        self.enabled = enabled
        self.tabs = {}
        self.lock = threading.Lock()
        self.started = time.time()
        self.seen = False
        self.empty_since = None
        self.stopping = False

    def ping(self, tab):
        with self.lock:
            self.tabs[tab] = time.time()
            self.seen = True
            self.empty_since = None

    def bye(self, tab):
        with self.lock:
            self.tabs.pop(tab, None)

    def stop(self, delay=0.5):
        if self.stopping:
            return
        self.stopping = True
        threading.Timer(delay, self.httpd.shutdown).start()

    def watch(self):
        while not self.stopping:
            time.sleep(2)
            if not self.enabled:
                continue
            now = time.time()
            with self.lock:
                for t, last in list(self.tabs.items()):
                    if now - last > self.IDLE:
                        del self.tabs[t]
                if not self.seen:
                    if now - self.started > self.FIRST_CONTACT:
                        self.stop(0)
                    continue
                if self.tabs:
                    self.empty_since = None
                elif self.empty_since is None:
                    self.empty_since = now
                elif now - self.empty_since > self.GRACE:
                    print("All browser tabs closed - server stopped.")
                    self.stop(0)


LIFE = None


@route("POST", "/api/ping")
def api_ping(req, q):
    if LIFE:
        LIFE.ping(str(req.body.get("tab") or "?"))
    return {"ok": True}


@route("POST", "/api/bye")
def api_bye(req, q):
    if LIFE:
        LIFE.bye(str(req.body.get("tab") or "?"))
    return {"ok": True}


@route("POST", "/api/shutdown")
def api_shutdown(req, q):
    if LIFE:
        LIFE.stop()
    return {"message": "Server stopped. You can close this tab."}


class _Server(ThreadingHTTPServer):
    # On Windows, address reuse would let two servers share one port silently.
    allow_reuse_address = os.name != "nt"
    daemon_threads = True


def serve(host="127.0.0.1", port=8080, auto_stop=True):
    global LIFE
    httpd = _Server((host, port), Handler)
    LIFE = Lifecycle(httpd, enabled=auto_stop)
    threading.Thread(target=LIFE.watch, daemon=True).start()
    return httpd


# CO module API (registers its routes on import)
from web import co_api  # noqa: E402,F401
from web import fi_api  # noqa: E402,F401
from web import pur_api  # noqa: E402,F401
from web import md_api  # noqa: E402,F401
from web import pp_api  # noqa: E402,F401
from web import sd_api  # noqa: E402,F401
from web import qa_api  # noqa: E402,F401
