"""Desktop client logic (no user interface): system list (logon pad entries),
starting / stopping the local MM Core server of a system, logon, Easy Access
menu, favorites and opening transaction sessions in their own window."""
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
SYSTEMS_FILE = os.path.join(DATA, "logon_systems.json")
FAV_FILE = os.path.join(DATA, "gui_favorites.json")

DEFAULT_SYSTEMS = [
    dict(name="01. MM Core ERP (PRD)", sid="PRD", db="data/mm.db", port=8080, empty=False,
         text="Production / demo data - the database of 'Start MM Core.bat'"),
    dict(name="02. MM Core Training (TRN)", sid="TRN", db="data/training.db", port=8081, empty=False,
         text="Training system with fresh demo data"),
    dict(name="03. MM Core Sandbox - empty (SBX)", sid="SBX", db="data/sandbox.db", port=8082, empty=True,
         text="Empty system for your own tests and the data import (ZIMPORT)"),
]
DEFAULT_FAVORITES = [
    dict(type="tx", tcode="ZBI"), dict(type="tx", tcode="ZBI_DASH"), dict(type="tx", tcode="MMBE"),
    dict(type="folder", name="MM", items=[dict(type="tx", tcode="MIGO"), dict(type="tx", tcode="MB52"),
                                         dict(type="tx", tcode="MB51"), dict(type="tx", tcode="MI01")]),
    dict(type="folder", name="SD", items=[dict(type="tx", tcode="VA01"), dict(type="tx", tcode="VA05"),
                                         dict(type="tx", tcode="VL01N"), dict(type="tx", tcode="VF01")]),
    dict(type="folder", name="CO Check", items=[dict(type="tx", tcode="KSB1"), dict(type="tx", tcode="KE30"),
                                               dict(type="tx", tcode="ZCO_RECON")]),
    dict(type="tx", tcode="F.01"), dict(type="tx", tcode="ZAMS"),
]


class ClientError(Exception):
    pass


# ------------------------------------------------------------------ systems (logon pad)
def _abs(p):
    return p if os.path.isabs(p) else os.path.join(ROOT, p)


def load_systems():
    try:
        with open(SYSTEMS_FILE, encoding="utf-8") as f:
            s = json.load(f)
            if isinstance(s, list) and s:
                return s
    except (OSError, ValueError):
        pass
    return [dict(x) for x in DEFAULT_SYSTEMS]


def save_systems(systems):
    os.makedirs(DATA, exist_ok=True)
    with open(SYSTEMS_FILE, "w", encoding="utf-8") as f:
        json.dump(systems, f, indent=1, ensure_ascii=False)


def check_system(s, systems, old=None):
    if not (s.get("name") or "").strip():
        raise ClientError("Enter a description")
    sid = (s.get("sid") or "").strip().upper()
    if not (len(sid) == 3 and sid.isalnum()):
        raise ClientError("The system ID has 3 letters or digits (e.g. PRD)")
    try:
        port = int(s.get("port"))
    except (TypeError, ValueError):
        raise ClientError("The port must be a number (e.g. 8080)")
    if not 1024 <= port <= 65000:
        raise ClientError("The port must be between 1024 and 65000")
    if not (s.get("db") or "").strip().lower().endswith(".db"):
        raise ClientError("The database file must end with .db")
    for o in systems:
        if o is old:
            continue
        if o["sid"] == sid:
            raise ClientError("System ID %s is used by '%s'" % (sid, o["name"]))
        if int(o["port"]) == port:
            raise ClientError("Port %d is used by '%s'" % (port, o["name"]))
    return dict(s, sid=sid, port=port, name=s["name"].strip(), db=s["db"].strip())


# ------------------------------------------------------------------ HTTP
def _req(port, path, body=None, token=None, timeout=10):
    url = "http://127.0.0.1:%d%s" % (port, path)
    data = None if body is None else json.dumps(body).encode("utf-8")
    r = urllib.request.Request(url, data=data, method="POST" if body is not None else "GET")
    if body is not None:
        r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Cookie", "mmcore_session=" + token)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            raw = resp.read()
            ck = resp.headers.get("Set-Cookie") or ""
            return json.loads(raw or b"{}"), ck
    except urllib.error.HTTPError as e:
        try:
            d = json.loads(e.read() or b"{}")
        except ValueError:
            d = {}
        raise ClientError(d.get("text") or "Server answered %s" % e.code)
    except (urllib.error.URLError, OSError) as e:
        raise ClientError("No connection to the system on port %d (%s)" % (port, e))


def info(port, timeout=2):
    try:
        return _req(port, "/api/gui/info", timeout=timeout)[0]
    except ClientError:
        return None


def status(system):
    i = info(int(system["port"]), 1)
    if not i:
        return "stopped"
    if os.path.normcase(i.get("db") or "") != os.path.normcase(os.path.abspath(_abs(system["db"]))):
        return "port used by another system"
    return "running"


def _python():
    """pythonw on Windows (no black window), else the current interpreter."""
    exe = sys.executable
    if os.name == "nt":
        w = os.path.join(os.path.dirname(exe), "pythonw.exe")
        if os.path.exists(w):
            return w
    return exe


def start(system, wait=120, progress=None):
    """Start the server of a system (if needed). Returns True when this call started it."""
    port = int(system["port"])
    st = status(system)
    if st == "running":
        return False
    if st != "stopped":
        raise ClientError("Port %d is used by another MM Core system - change the port of '%s'"
                          % (port, system["name"]))
    db = _abs(system["db"])
    os.makedirs(os.path.dirname(db), exist_ok=True)
    env = dict(os.environ, MM_DB=db)
    args = [_python(), os.path.join(ROOT, "run.py"), "--no-browser", "--keep-running", "--port", str(port)]
    if system.get("empty") and not os.path.exists(db):
        args.append("--empty")
    log = open(os.path.join(DATA, "server_%s.log" % system["sid"]), "a", encoding="utf-8")
    flags = 0x08000000 if os.name == "nt" else 0           # CREATE_NO_WINDOW
    subprocess.Popen(args, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                     stdin=subprocess.DEVNULL, creationflags=flags)
    t0 = time.time()
    while time.time() - t0 < wait:
        if progress:
            progress(int(time.time() - t0))
        if status(system) == "running":
            return True
        time.sleep(0.5)
    raise ClientError("The system did not start within %d seconds - see data/server_%s.log"
                      % (wait, system["sid"]))


def stop(system, token=None):
    try:
        _req(int(system["port"]), "/api/shutdown", {}, token=token, timeout=3)
    except ClientError:
        pass


def logon(system, user, password):
    """Returns (token or None, info). With the logon switched off no password is needed."""
    port = int(system["port"])
    st, _ = _req(port, "/api/sec/status")
    if not st.get("auth"):
        return None, st
    d, ck = _req(port, "/api/sec/login", {"bname": user, "password": password})
    token = ""
    for part in ck.split(";"):
        k, _, v = part.strip().partition("=")
        if k == "mmcore_session":
            token = v
    if not token:
        raise ClientError("Logon failed")
    return token, dict(st, must_change=d.get("must_change"))


def logoff(system, token):
    if token:
        try:
            _req(int(system["port"]), "/api/sec/logout", {}, token=token, timeout=3)
        except ClientError:
            pass


def menu(system, token=None):
    return _req(int(system["port"]), "/api/gui/menu", token=token, timeout=20)[0]


def me(system, token=None):
    try:
        return _req(int(system["port"]), "/api/sec/me", token=token)[0]
    except ClientError:
        return {}


# ------------------------------------------------------------------ favorites (per system)
def load_favorites(sid):
    try:
        with open(FAV_FILE, encoding="utf-8") as f:
            d = json.load(f)
            if sid in d:
                return d[sid]
    except (OSError, ValueError):
        pass
    return json.loads(json.dumps(DEFAULT_FAVORITES))


def save_favorites(sid, favs):
    d = {}
    try:
        with open(FAV_FILE, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        pass
    d[sid] = favs
    os.makedirs(DATA, exist_ok=True)
    with open(FAV_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=1, ensure_ascii=False)


# ------------------------------------------------------------------ session windows
def _browser():
    """Edge or Chrome in app mode = a window without address bar or tabs."""
    cands = []
    if os.name == "nt":
        for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"),
                     os.environ.get("LOCALAPPDATA")):
            if base:
                cands += [os.path.join(base, "Microsoft", "Edge", "Application", "msedge.exe"),
                          os.path.join(base, "Google", "Chrome", "Application", "chrome.exe")]
    else:
        cands += [shutil.which(x) for x in ("microsoft-edge", "google-chrome", "chromium", "chromium-browser")]
        cands.append("/opt/pw-browsers/chromium")
    for c in cands:
        if c and os.path.isfile(c):
            return c
    return None


def session_url(system, tcode, user, token=None):
    from urllib.parse import quote
    u = "http://localhost:%d/?session=1&user=%s" % (int(system["port"]), quote(user or ""))
    if token:
        u += "&sso=" + quote(token)
    return u + "#/" + quote((tcode or "HOME").upper())


def open_session(system, tcode, user, token=None):
    url = session_url(system, tcode, user, token)
    exe = _browser()
    if exe:
        prof = os.path.join(DATA, "gui_profile_%s" % system["sid"])
        subprocess.Popen([exe, "--app=" + url, "--user-data-dir=" + prof, "--no-first-run",
                          "--window-size=1400,900"], stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        import webbrowser
        webbrowser.open(url)
    return url


def parse_okcode(text):
    """SAP command field: TCODE, /nTCODE (same session), /oTCODE (new session), /nend, /i ..."""
    t = (text or "").strip().upper()
    if not t:
        return None, None
    if t in ("/NEND", "/NEX"):
        return "logoff", None
    if t.startswith("/O"):
        return "new", t[2:].strip() or "HOME"
    if t.startswith("/N"):
        return "same", t[2:].strip() or "HOME"
    return "same", t.split()[0]
