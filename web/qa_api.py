"""JSON API for quality assurance and e-Learning (ZQA_TEST, ZLMS)."""
import datetime
import json
import os
import threading

from qa import catalog, runner

from .server import STATIC, db, route
from mm import util as mmclock  # noqa: E402

_LOCK = threading.Lock()
MANUALS = os.path.join(STATIC, "manuals")


def _manuals():
    try:
        return sorted(f for f in os.listdir(MANUALS) if f.endswith(".pptx"))
    except OSError:
        return []


@route("GET", "/api/qa/catalog")
def api_catalog(req, q):
    d = catalog.as_json()
    d["run"] = runner.last()
    d["files"] = _manuals()
    return d


@route("POST", "/api/qa/run")
def api_run(req, q):
    if not _LOCK.acquire(blocking=False):
        return {"type": "W", "text": "A test run is already in progress"}
    try:
        r = runner.run(req.user)
    finally:
        _LOCK.release()
    r["type"] = "S" if not r["failed"] else "E"
    r["text"] = "Test run finished: %d of %d test cases passed (%d automated tests, %.1f s)" % (
        r["passed"], r["cases"], r["unit_tests"], r["seconds"])
    return r


# ------------------------------------------------------------------ LMS ID (request -> register -> connect)
def _lms_get(c, user):
    row = c.execute("SELECT value FROM settings WHERE key=?", ("lms_" + user,)).fetchone()
    return json.loads(row[0]) if row else {"user": user, "status": "NONE"}


def _lms_set(c, user, d):
    c.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", ("lms_" + user, json.dumps(d)))
    c.commit()


@route("GET", "/api/qa/lms")
def api_lms(req, q):
    return _lms_get(db(), req.user)


@route("POST", "/api/qa/lms/(?P<step>request|register|connect|reset)")
def api_lms_step(req, q, step):
    c, user = db(), req.user
    d = _lms_get(c, user)
    now = mmclock.now().isoformat(timespec="seconds")
    order = {"request": ("NONE", "REQUESTED"), "register": ("REQUESTED", "REGISTERED"),
             "connect": ("REGISTERED", "CONNECTED")}
    if step == "reset":
        d = {"user": user, "status": "NONE"}
    else:
        need, new = order[step]
        if d["status"] != need:
            return {"type": "E", "text": "Step not possible in status %s" % d["status"], **d}
        d["status"] = new
        d[step + "_at"] = now
        if step == "register":
            d["lms_id"] = "LMS-%s-%04d" % (user.upper()[:8], sum(map(ord, user)) % 10000)
    _lms_set(c, user, d)
    d["type"] = "S"
    d["text"] = {"request": "LMS ID requested - waiting for registration by HQ",
                 "register": "LMS ID %s registered" % d.get("lms_id", ""),
                 "connect": "Connected to the LMS - manuals are open for you",
                 "reset": "LMS registration reset"}[step]
    return d
