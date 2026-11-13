"""NERP Dashboard - the ERP dashboard in its own window (no menus, no address bar).

Started by "NERP Dashboard.bat" (or the desktop icon made by tools/Create desktop
icons.bat). Uses the first system of NERP Logon (default: data/mm.db, port 8080),
starts it when it is not running, and opens http://localhost:PORT/dashboard.html."""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from gui import client as C  # noqa: E402


def _message(text):
    try:
        import tkinter as tk
        from tkinter import messagebox
        r = tk.Tk()
        r.withdraw()
        messagebox.showerror("NERP Dashboard", text)
        r.destroy()
    except Exception:  # noqa - no Tk: the console is all we have
        print(text)


def main():
    systems = C.load_systems()
    sid = (sys.argv[1] if len(sys.argv) > 1 else "").upper()
    system = next((s for s in systems if s["sid"] == sid), systems[0])
    try:
        C.start(system, wait=180, keep_running=False)   # stops when the window closes
    except C.ClientError as e:
        _message(str(e))
        return 1
    C.open_app(system, C.dashboard_url(system), size="1560,960")
    return 0


if __name__ == "__main__":
    sys.exit(main())
