"""MM Core Mobile - the ERP dashboard on the phone, updated live.

Started by "MM Core Mobile.bat". Opens the pairing page with the QR code on this PC;
the phone (same Wi-Fi) scans it once and then has the dashboard as an icon on its home
screen. Read-only: nothing can be changed from the phone.

    python mobile.py [--port 8090] [--db data/mm.db] [--no-browser]
"""
import argparse
import json
import os
import sys
import urllib.request
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)


def _message(text):
    try:
        import tkinter as tk
        from tkinter import messagebox
        r = tk.Tk()
        r.withdraw()
        messagebox.showerror("MM Core Mobile", text)
        r.destroy()
    except Exception:  # noqa - no Tk: the console is all we have
        print(text)


def _running(port):
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d/m/api/pairinfo" % port, timeout=2) as r:
            return "ips" in json.loads(r.read() or b"{}")
    except Exception:  # noqa - not running / something else on the port
        return False


def main(argv=None):
    ap = argparse.ArgumentParser(description="MM Core Mobile - live dashboard for the phone")
    ap.add_argument("--port", type=int, default=int(os.environ.get("MM_MOBILE_PORT") or 8090))
    ap.add_argument("--db", default=None, help="database (default: the first system of MM Core Logon)")
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args(argv)
    pair = "http://localhost:%d/m/pair" % a.port
    if _running(a.port):                                  # already on: show the QR code again
        if not a.no_browser:
            webbrowser.open(pair)
        return 0
    db = a.db or os.environ.get("MM_DB")
    if not db:
        from gui import client as C
        s = C.load_systems()[0]
        db = s["db"] if os.path.isabs(s["db"]) else os.path.join(ROOT, s["db"])
    if not os.path.exists(db):
        _message("No MM Core database yet (%s).\nStart MM Core once (Start MM Core.bat), then MM Core Mobile." % db)
        return 1
    from mobile.gateway import serve
    try:
        srv = serve(db, port=a.port)
    except OSError as e:
        _message("Port %d is in use by another program (%s).\nStart with another port: mobile.py --port 8091" % (a.port, e))
        return 1
    print("MM Core Mobile on port %d - pairing page %s" % (a.port, pair))
    if not a.no_browser:
        webbrowser.open(pair)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
