"""Start MM Core:   python run.py   [options]

Normally started by double-clicking "Start MM Core.bat" (Windows): the server
runs hidden in the background, the browser opens, and the server stops by
itself a few seconds after the last browser tab is closed.

Options:
  --reset          delete the database and load fresh demo data
  --empty          with --reset: start with an empty system (no demo data)
  --port N         port (default 8080)
  --no-browser     do not open the browser
  --keep-running   do not stop when the browser tabs are closed
  --backup         copy the database to data/backup (also done daily and before --reset)
  --restore FILE   restore a backup copy
"""
import argparse
import json
import os
import sys
import threading
import urllib.request
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

# Started with pythonw (no console window): send all output to a log file.
if sys.stdout is None or sys.stderr is None:
    os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)
    _log = open(os.path.join(ROOT, "data", "server.log"), "a", encoding="utf-8",
                buffering=1)
    sys.stdout = sys.stderr = _log

from mm import seed  # noqa: E402
from mm.db import DEFAULT_DB, backup, connect, integrity_ok, restore  # noqa: E402
from web.server import serve  # noqa: E402


def _daily_backup(db_path):
    """One automatic backup per day at the first start (the last 14 are kept)."""
    import glob
    import time
    d = os.path.join(os.path.dirname(db_path), "backup")
    today = time.strftime("%Y%m%d")
    if not glob.glob(os.path.join(d, "mm_%s_*.db" % today)):
        try:
            backup(db_path)
        except Exception:       # a failed backup must not stop the start
            pass


def setup_log():
    from mm.log import setup
    return setup()


def show_startup_error(host, port, err):
    """Serve one page that explains the problem (the server runs without a console)."""
    import html
    from http.server import BaseHTTPRequestHandler, HTTPServer
    page = ("<!doctype html><meta charset='utf-8'><title>MM Core</title><body style='font-family:"
            "Arial;margin:40px'><h2>MM Core could not start</h2><p>%s</p><p>Details are in "
            "<code>data/mm_core.log</code>. Restore a backup with <code>run.py --restore</code> or "
            "load fresh demo data with <code>tools\\Reset - fresh demo data.bat</code>.</p>"
            % html.escape(str(err))).encode("utf-8")

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(500)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
            self.end_headers()
            self.wfile.write(page)

        def log_message(self, *a):
            pass
    try:
        srv = HTTPServer((host, port), H)
    except OSError:
        return
    threading.Timer(0.5, lambda: webbrowser.open("http://localhost:%d" % port)).start()
    threading.Timer(120, srv.shutdown).start()     # do not stay forever
    srv.serve_forever()


def already_running(port):
    """True if MM Core already answers on this port."""
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d/api/office/status" % port,
                                    timeout=2) as r:
            return "available" in json.loads(r.read().decode("utf-8"))
    except Exception:
        return False


def stop_running(port):
    """Ask a running MM Core to stop and wait until the port is free."""
    import time
    try:
        req = urllib.request.Request("http://127.0.0.1:%d/api/shutdown" % port,
                                     data=b"{}", method="POST")
        urllib.request.urlopen(req, timeout=3).read()
    except Exception:
        pass
    for _ in range(40):
        if not already_running(port):
            time.sleep(0.5)
            return
        time.sleep(0.25)


def _first_users(conn, db_path):
    """A database without users (older version or --empty): demo users when it holds
    the demo data, otherwise ADMIN with a one-time password in data/first_login.txt."""
    from sec import users
    demo = bool(conn.execute("SELECT COUNT(*) FROM plant").fetchone()[0]) and \
        bool(conn.execute("SELECT COUNT(*) FROM customer WHERE kunnr='C1001'").fetchone()[0])
    pw = users.bootstrap(conn, demo)
    note = os.path.join(os.path.dirname(os.path.abspath(db_path)), "first_login.txt")
    if pw:
        with open(note, "w", encoding="utf-8") as f:
            f.write("MM Core - first logon\n\nUser: ADMIN\nOne-time password: %s\n\n"
                    "You must choose a new password at the first logon. Delete this file "
                    "afterwards.\n" % pw)
        print("First logon: user ADMIN, one-time password in", note)
    elif demo and conn.execute("SELECT COUNT(*) FROM usr").fetchone()[0]:
        print("Demo users: ADMIN / admin, SALES1 / sales1, BUYER1 / buyer1 ... (password = user name)")


def main():
    ap = argparse.ArgumentParser(description="MM Core - inventory management")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--empty", action="store_true")
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--keep-running", action="store_true")
    ap.add_argument("--backup", action="store_true", help="copy the database to data/backup and exit")
    ap.add_argument("--restore", metavar="FILE", help="restore a backup (stops a running server)")
    ap.add_argument("--dev", action="store_true",
                    help="developer mode: no logon, the X-User header names the user (tests, tools)")
    a = ap.parse_args()
    db_path = os.environ.get("MM_DB") or DEFAULT_DB
    if a.host not in ("127.0.0.1", "localhost", "::1") and not os.environ.get("MM_ALLOW_REMOTE"):
        print("Remote access is refused: MM Core has no network-grade login yet. "
              "Use the default host 127.0.0.1 (or set MM_ALLOW_REMOTE=1 at your own risk).")
        sys.exit(2)
    if a.backup:
        print("Backup written:", backup(db_path))
        return
    if a.restore:
        if already_running(a.port):
            stop_running(a.port)
        backup(db_path)                      # keep the current state, just in case
        print("Database restored from", a.restore, "->", restore(a.restore, db_path))
        return

    # Second click while it is already running: just open the browser again.
    if not a.reset and already_running(a.port):
        print("MM Core is already running - opening the browser.")
        if not a.no_browser:
            webbrowser.open("http://localhost:%d" % a.port)
        return

    if a.reset and already_running(a.port):
        stop_running(a.port)

    if a.reset and os.path.exists(db_path):
        print("Backup before reset:", backup(db_path))
        os.remove(db_path)
        for ext in ("-wal", "-shm"):
            if os.path.exists(db_path + ext):
                os.remove(db_path + ext)
        print("Database deleted:", db_path)
    elif os.path.exists(db_path):
        _daily_backup(db_path)
    log = setup_log()
    try:
        conn = connect(db_path)
        if not integrity_ok(conn):
            raise RuntimeError("The database file %s is damaged - restore a backup "
                               "(run.py --restore data/backup/...)" % db_path)
        if not a.empty and seed.seed(conn) is not None:
            print("Demo data loaded.")
        _first_users(conn, db_path)
        conn.close()
    except Exception as e:      # the server would start on a broken database: show why
        log.exception("start-up failed")
        print("MM Core could not start:", e)
        if a.no_browser:
            sys.exit(1)
        show_startup_error(a.host, a.port, e)
        return

    auto_stop = not (a.keep_running or a.no_browser)
    httpd, port = None, a.port
    for port in range(a.port, a.port + 20):
        try:
            httpd = serve(a.host, port, auto_stop=auto_stop, auth=not a.dev)
            break
        except OSError:
            continue
    if httpd is None:
        print("No free port found between %d and %d." % (a.port, a.port + 19))
        sys.exit(1)
    url = "http://localhost:%d" % port
    print("MM Core is running: %s" % url)
    print("It stops automatically when you close the browser tab."
          if auto_stop else "Press Ctrl+C to stop.")
    if not a.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    print("MM Core stopped.")


if __name__ == "__main__":
    main()
