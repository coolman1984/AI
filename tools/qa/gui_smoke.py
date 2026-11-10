"""Smoke test of the desktop client (needs Tkinter and a display, e.g. xvfb-run):
logon pad, system start, logon, Easy Access menu, command field, favorites,
session URL. Exit code 1 on any problem.   python tools/qa/gui_smoke.py"""
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from gui import client as C  # noqa: E402

tmp = tempfile.mkdtemp()
C.SYSTEMS_FILE = os.path.join(tmp, "systems.json")
C.FAV_FILE = os.path.join(tmp, "favs.json")
port = int(os.environ.get("MM_GUI_PORT", "8120"))
C.save_systems([dict(name="01. Smoke test (TST)", sid="TST", db=os.path.join(tmp, "tst.db"), port=port, empty=False,
                     text="smoke")])
opened = []
C.open_session = lambda s, t, u, tok=None: opened.append(C.session_url(s, t, u, tok))

import tkinter as tk  # noqa: E402
from gui import main as M  # noqa: E402

problems = []


def check(cond, text):
    if not cond:
        problems.append(text)
        print("FAIL", text)


root = tk.Tk()
M._style(root)
pad = M.LogonPad(root)
s = pad.systems[0]
try:
    C.start(s, wait=240)
    check(C.status(s) == "running", "system starts")
    token, st = C.logon(s, "SMOKE", "")
    ea = M.EasyAccess(pad, s, "SMOKE", token)
    for _ in range(300):
        root.update()
        time.sleep(0.1)
        if ea.menu_data:
            break
    check(bool(ea.menu_data), "menu loaded")
    check(len(ea.titles) > 300, "transaction texts loaded")
    ea.okv.set("/oMIGO")
    ea._okcode()
    check(opened and opened[-1].endswith("#/MIGO"), "command field starts MIGO")
    ea.okv.set("NOPE")
    ea._okcode()
    check("does not exist" in ea.status.get(), "unknown transaction is refused")
    n = [k for k, (kind, v) in ea.node.items() if kind == "tx" and v == "ME2N"][0]
    ea.tv.focus(n)
    ea.fav_add()
    check(any(f.get("tcode") == "ME2N" for f in C.load_favorites("TST")), "favorite saved")
    n = [k for k, (kind, v) in ea.node.items() if kind == "fav" and v.get("tcode") == "ME2N"][0]
    ea.tv.focus(n)
    ea.fav_delete()
    check(not any(f.get("tcode") == "ME2N" for f in C.load_favorites("TST")), "favorite deleted")
    check(any(kind == "tx" and v == "ZBI" for kind, v in ea.node.values()), "menu has ZBI")
finally:
    C.stop(s)
    root.destroy()
print("GUI smoke test:", "OK" if not problems else "%d problem(s)" % len(problems))
sys.exit(1 if problems else 0)
