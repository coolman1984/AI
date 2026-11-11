"""MM Core desktop client: "MM Core Logon" (system list) and "MM Core Easy Access"
(menu tree with favorites, command field, menus), like the classic SAP GUI.
Transactions open in their own window (application mode, no address bar).

Start: double-click "MM Core Logon.bat" (Windows) or  python gui/main.py
Needs Python with Tkinter (standard in the python.org installer)."""
import os
import sys
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gui import client as C  # noqa: E402

VERSION = "800"
BLUE, GOLD, GREY = "#0a3d8f", "#f0b400", "#e9edf2"


# ------------------------------------------------------------------ icons drawn in code (no image files)
def _icon(root, kind):
    img = tk.PhotoImage(master=root, width=16, height=16)
    if kind == "folder":
        img.put("#e0a800", to=(1, 4, 7, 6))
        img.put("#f6c445", to=(1, 6, 15, 14))
        img.put("#c98f00", to=(1, 13, 15, 14))
    elif kind == "open":
        img.put("#e0a800", to=(1, 4, 7, 6))
        img.put("#f6c445", to=(1, 6, 15, 8))
        img.put("#ffd65c", to=(3, 8, 15, 14))
    elif kind == "star":
        pts = [(7, 1), (8, 1), (7, 2), (8, 2), (6, 3), (9, 3), (6, 4), (9, 4)]
        for x, y in pts:
            img.put("#f08c00", to=(x, y, x + 1, y + 1))
        img.put("#f5a300", to=(1, 5, 15, 7))
        img.put("#f5a300", to=(4, 7, 12, 10))
        img.put("#f5a300", to=(3, 10, 7, 13))
        img.put("#f5a300", to=(9, 10, 13, 13))
        img.put("#f08c00", to=(2, 13, 5, 15))
        img.put("#f08c00", to=(11, 13, 14, 15))
    elif kind == "tx":
        img.put("#5b6b7c", to=(3, 3, 13, 13))
        img.put("#ffffff", to=(4, 4, 12, 12))
        img.put("#0a5bc4", to=(5, 6, 11, 7))
        img.put("#0a5bc4", to=(5, 9, 11, 10))
    elif kind == "system":
        img.put("#7a8796", to=(2, 3, 14, 12))
        img.put("#dfe8f3", to=(3, 4, 13, 11))
        img.put("#7a8796", to=(6, 12, 10, 14))
        img.put("#4a5664", to=(4, 14, 12, 15))
    return img


def _bg(widget, fn, done=None, fail=None, tick=None):
    """Run fn in a worker thread; done / fail / tick run in the Tk thread (Tk is not
    thread-safe, so the worker only fills a queue that the Tk thread polls)."""
    import queue
    q = queue.Queue()

    def work():
        try:
            q.put(("ok", fn(lambda x: q.put(("tick", x)))))
        except Exception as e:  # noqa - shown to the user
            q.put(("err", e))
    threading.Thread(target=work, daemon=True).start()

    def poll():
        try:
            while True:
                k, v = q.get_nowait()
                if k == "tick":
                    if tick:
                        tick(v)
                    continue
                if k == "ok" and done:
                    done(v)
                if k == "err":
                    (fail or (lambda e: messagebox.showerror("MM Core", str(e))))(v)
                return
        except queue.Empty:
            pass
        try:
            widget.after(100, poll)
        except tk.TclError:
            pass
    widget.after(100, poll)


def _center(win, w, h):
    win.update_idletasks()
    x = max(0, (win.winfo_screenwidth() - w) // 2)
    y = max(0, (win.winfo_screenheight() - h) // 3)
    win.geometry("%dx%d+%d+%d" % (w, h, x, y))


def _style(root):
    st = ttk.Style(root)
    try:
        st.theme_use("vista" if os.name == "nt" else "clam")
    except tk.TclError:
        st.theme_use("clam")
    st.configure("Treeview", rowheight=22, font=("Segoe UI", 10))
    st.configure("Treeview.Heading", font=("Segoe UI", 10))
    st.configure("Tool.TButton", padding=(6, 2))
    return st


# ------------------------------------------------------------------ system entry dialog
class SystemDialog(tk.Toplevel):
    def __init__(self, master, title, system):
        super().__init__(master)
        self.title(title)
        self.transient(master)
        self.resizable(False, False)
        self.result = None
        s = system or dict(name="", sid="", db="data/new.db", port=8083, empty=False, text="")
        self.v = {k: tk.StringVar(self, str(s.get(k, ""))) for k in ("name", "sid", "db", "port", "text")}
        self.empty = tk.BooleanVar(self, bool(s.get("empty")))
        f = ttk.Frame(self, padding=14)
        f.pack(fill="both", expand=True)
        rows = [("Description", "name", 42), ("System ID", "sid", 6), ("Database file", "db", 42),
                ("Port", "port", 8), ("Comment", "text", 42)]
        for i, (lab, key, w) in enumerate(rows):
            ttk.Label(f, text=lab).grid(row=i, column=0, sticky="w", pady=3)
            e = ttk.Entry(f, textvariable=self.v[key], width=w)
            e.grid(row=i, column=1, sticky="w", pady=3)
            if i == 0:
                e.focus_set()
        ttk.Checkbutton(f, text="Start without demo data (empty system) when the database is new",
                        variable=self.empty).grid(row=len(rows), column=0, columnspan=2, sticky="w", pady=6)
        b = ttk.Frame(f)
        b.grid(row=len(rows) + 1, column=0, columnspan=2, sticky="e", pady=(8, 0))
        ttk.Button(b, text="Cancel", command=self.destroy).pack(side="right", padx=4)
        ttk.Button(b, text="Save", command=self._ok).pack(side="right")
        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())
        self.grab_set()

    def _ok(self):
        self.result = dict({k: v.get() for k, v in self.v.items()}, empty=self.empty.get())
        self.destroy()


# ------------------------------------------------------------------ logon screen (client / user / password)
class LogonDialog(tk.Toplevel):
    def __init__(self, master, system, need_password, last_user):
        super().__init__(master)
        self.title("%s - Log On" % system["sid"])
        self.transient(master)
        self.resizable(False, False)
        self.result = None
        f = ttk.Frame(self, padding=16)
        f.pack(fill="both", expand=True)
        tk.Label(f, text="MM Core", font=("Segoe UI", 18, "bold italic"), fg=BLUE).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(f, text=system["name"]).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 10))
        self.client, self.user, self.pw, self.lang = (tk.StringVar(self, "800"), tk.StringVar(self, last_user or ""),
                                                      tk.StringVar(self), tk.StringVar(self, "EN"))
        for i, (lab, var, show) in enumerate((("Client", self.client, None), ("User", self.user, None),
                                              ("Password", self.pw, "*"), ("Language", self.lang, None))):
            ttk.Label(f, text=lab).grid(row=2 + i, column=0, sticky="w", pady=3, padx=(0, 10))
            e = ttk.Entry(f, textvariable=var, width=24, show=show or "")
            e.grid(row=2 + i, column=1, sticky="w", pady=3)
            if lab == ("Password" if last_user else "User"):
                e.focus_set()
        msg = ("The user logon of this system is switched OFF - enter only your name." if not need_password
               else "Demo users: ADMIN / admin, SALES1 / sales1 ... (password = user name in small letters)")
        ttk.Label(f, text=msg, foreground="#5a6470", wraplength=320).grid(row=6, column=0, columnspan=2, sticky="w", pady=8)
        b = ttk.Frame(f)
        b.grid(row=7, column=0, columnspan=2, sticky="e")
        ttk.Button(b, text="Cancel", command=self.destroy).pack(side="right", padx=4)
        ttk.Button(b, text="Log On", command=self._ok).pack(side="right")
        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())
        self.grab_set()

    def _ok(self):
        if not self.user.get().strip():
            messagebox.showerror("Log On", "Enter a user name", parent=self)
            return
        self.result = (self.user.get().strip().upper(), self.pw.get())
        self.destroy()


# ------------------------------------------------------------------ MM Core Logon (system list)
class LogonPad:
    def __init__(self, root):
        self.root = root
        self.systems = C.load_systems()
        self.open_windows = []
        self.started = {}
        root.title("MM Core Logon %s" % VERSION)
        _center(root, 860, 520)
        self.ic = {k: _icon(root, k) for k in ("folder", "open", "system")}
        bar = ttk.Frame(root, padding=(6, 4))
        bar.pack(fill="x")
        for text, cmd in (("Log On", self.logon), ("Variable Logon", self.variable_logon)):
            ttk.Button(bar, text=text, command=cmd, style="Tool.TButton").pack(side="left", padx=1)
        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=6)
        for text, tip, cmd in (("New", "New system entry", self.new), ("Change", "Change entry", self.change),
                               ("Delete", "Delete entry", self.delete), ("Start", "Start server only", self.start_only),
                               ("Stop", "Stop server", self.stop_only)):
            ttk.Button(bar, text=text, command=cmd, style="Tool.TButton").pack(side="left", padx=1)
        self.flt = tk.StringVar(root)
        self.flt.trace_add("write", lambda *a: self.fill())
        ttk.Entry(bar, textvariable=self.flt, width=18).pack(side="right")
        ttk.Label(bar, text="Filter ").pack(side="right")
        body = ttk.PanedWindow(root, orient="horizontal")
        body.pack(fill="both", expand=True, padx=6, pady=(0, 4))
        left = ttk.Treeview(body, show="tree", selectmode="browse")
        ws = left.insert("", "end", text=" Workspaces", image=self.ic["open"], open=True)
        left.insert(ws, "end", text=" Local", image=self.ic["folder"])
        left.selection_set(left.get_children(ws)[0])
        body.add(left, weight=1)
        right = ttk.Frame(body)
        self.tv = ttk.Treeview(right, columns=("sid", "port", "st"), show="tree headings", selectmode="browse")
        self.tv.heading("#0", text="Name")
        self.tv.heading("sid", text="SID")
        self.tv.heading("port", text="Port")
        self.tv.heading("st", text="Status")
        self.tv.column("#0", width=300)
        self.tv.column("sid", width=50, anchor="center")
        self.tv.column("port", width=60, anchor="center")
        self.tv.column("st", width=140)
        self.tv.pack(fill="both", expand=True)
        self.tv.bind("<Double-1>", lambda e: self.logon())
        self.tv.bind("<Return>", lambda e: self.logon())
        self.tv.bind("<<TreeviewSelect>>", lambda e: self._detail())
        body.add(right, weight=4)
        self.detail = tk.StringVar(root)
        ttk.Label(root, textvariable=self.detail, relief="sunken", anchor="w", padding=(6, 2)).pack(fill="x", side="bottom")
        self.fill()
        root.protocol("WM_DELETE_WINDOW", self.quit)
        root.after(300, self.refresh_status)

    # ---------------- list
    def fill(self):
        sel = self._sel_index()
        self.tv.delete(*self.tv.get_children())
        f = self.flt.get().lower()
        for i, s in enumerate(self.systems):
            if f and f not in s["name"].lower() and f not in s["sid"].lower():
                continue
            self.tv.insert("", "end", iid=str(i), text=" " + s["name"], image=self.ic["system"],
                           values=(s["sid"], s["port"], s.get("_st", "")))
        if self.tv.get_children():
            self.tv.selection_set(str(sel) if sel is not None and self.tv.exists(str(sel)) else self.tv.get_children()[0])
            self.tv.focus(self.tv.selection()[0])

    def refresh_status(self):
        def work(tick):
            for s in self.systems:
                s["_st"] = C.status(s)
        _bg(self.root, work, lambda r: self.fill())

    def _sel_index(self):
        sel = self.tv.selection() if hasattr(self, "tv") else ()
        return int(sel[0]) if sel else None

    def _sel(self):
        i = self._sel_index()
        return self.systems[i] if i is not None else None

    def _detail(self):
        s = self._sel()
        if s:
            self.detail.set("%s  ·  %s  ·  database %s  ·  port %s" % (s["sid"], s.get("text", ""), s["db"], s["port"]))

    # ---------------- entries
    def _save(self):
        C.save_systems([{k: v for k, v in s.items() if not k.startswith("_")} for s in self.systems])

    def new(self):
        d = SystemDialog(self.root, "Create New System Entry", None)
        self.root.wait_window(d)
        if d.result:
            try:
                s = C.check_system(d.result, self.systems)
            except C.ClientError as e:
                return messagebox.showerror("New entry", str(e), parent=self.root)
            self.systems.append(s)
            self._save()
            self.fill()

    def change(self):
        s = self._sel()
        if not s:
            return
        d = SystemDialog(self.root, "Change System Entry", s)
        self.root.wait_window(d)
        if d.result:
            try:
                n = C.check_system(d.result, self.systems, old=s)
            except C.ClientError as e:
                return messagebox.showerror("Change entry", str(e), parent=self.root)
            s.clear()
            s.update(n)
            self._save()
            self.refresh_status()

    def delete(self):
        s = self._sel()
        if s and messagebox.askyesno("Delete entry", "Delete the entry '%s'?\nThe database file is NOT deleted."
                                     % s["name"], parent=self.root):
            self.systems.remove(s)
            self._save()
            self.fill()

    def start_only(self):
        s = self._sel()
        if s:
            self._start(s, lambda: messagebox.showinfo("Start", "%s is running on port %s" % (s["name"], s["port"]),
                                                       parent=self.root))

    def stop_only(self):
        s = self._sel()
        if s and messagebox.askyesno("Stop", "Stop the server of %s?\nOpen windows of this system stop working."
                                     % s["name"], parent=self.root):
            C.stop(s, self.started.get(s["sid"]))
            self.started.pop(s["sid"], None)
            self.root.after(1500, self.refresh_status)

    # ---------------- logon
    def _start(self, s, then):
        win = tk.Toplevel(self.root)
        win.title("Connecting")
        win.transient(self.root)
        txt = tk.StringVar(win, "Starting %s ..." % s["name"])
        ttk.Label(win, textvariable=txt, padding=18).pack()
        pb = ttk.Progressbar(win, mode="indeterminate", length=260)
        pb.pack(padx=18, pady=(0, 18))
        pb.start(12)
        _center(win, 340, 110)

        def ok(started):
            if started:
                self.started[s["sid"]] = None
            win.destroy()
            self.refresh_status()
            then()

        def fail(e):
            win.destroy()
            messagebox.showerror("Log On", str(e), parent=self.root)
        _bg(self.root, lambda tick: C.start(s, progress=tick), ok, fail,
            lambda sec: txt.set("Starting %s ... %d s (the first start loads the data)" % (s["sid"], sec)))

    def logon(self, system=None):
        s = system or self._sel()
        if not s:
            return messagebox.showinfo("Log On", "Select a system", parent=self.root)
        self._start(s, lambda: self._logon_dialog(s))

    def _logon_dialog(self, s):
        try:
            st = C._req(int(s["port"]), "/api/sec/status")[0]
        except C.ClientError as e:
            return messagebox.showerror("Log On", str(e), parent=self.root)
        last = s.get("_user") or os.environ.get("USERNAME", "OWNER").upper()[:12]
        d = LogonDialog(self.root, s, bool(st.get("auth")), last)
        self.root.wait_window(d)
        if not d.result:
            return
        user, pw = d.result
        try:
            token, _ = C.logon(s, user, pw)
        except C.ClientError as e:
            messagebox.showerror("Log On", str(e), parent=self.root)
            return self._logon_dialog(s)
        s["_user"] = user
        self.open_windows.append(EasyAccess(self, s, user, token))

    def variable_logon(self):
        port = simpledialog.askinteger("Variable Logon", "Port of a running MM Core system:", parent=self.root,
                                       minvalue=1024, maxvalue=65000)
        if not port:
            return
        i = C.info(port)
        if not i:
            return messagebox.showerror("Variable Logon", "No MM Core system on port %d" % port, parent=self.root)
        s = dict(name="Variable logon (port %d)" % port, sid="VAR", db=i["db"], port=port, empty=False, text=i["db"])
        self._logon_dialog(s)

    def quit(self):
        running = [s for s in self.systems if s["sid"] in self.started]
        if running and messagebox.askyesno("Exit", "Stop the systems started by MM Core Logon (%s)?"
                                           % ", ".join(s["sid"] for s in running), parent=self.root):
            for s in running:
                C.stop(s)
        self.root.destroy()


# ------------------------------------------------------------------ Easy Access
class EasyAccess(tk.Toplevel):
    def __init__(self, pad, system, user, token):
        super().__init__(pad.root)
        self.pad, self.s, self.user, self.token = pad, system, user, token
        self.title("MM Core Easy Access  -  %s (%s) - %s" % (system["name"], system["sid"], user))
        _center(self, 1000, 760)
        self.ic = {k: _icon(self, k) for k in ("folder", "open", "star", "tx")}
        self.tech = tk.BooleanVar(self, True)
        self.favs = C.load_favorites(system["sid"])
        self.history = []
        self._menubar()
        self._toolbar()
        band = tk.Frame(self, bg="#dfe3e8")
        band.pack(fill="x")
        tk.Label(band, text="MM Core Easy Access", font=("Segoe UI", 16, "bold italic"), bg="#dfe3e8",
                 fg="#1d2a3a").pack(side="left", padx=10, pady=6)
        tb2 = ttk.Frame(self, padding=(6, 2))
        tb2.pack(fill="x")
        for text, cmd in (("★ Add to favorites", self.fav_add), ("★ Delete favorite", self.fav_delete),
                          ("✎ Change favorite", self.fav_rename), ("▼ Expand", lambda: self._expand(True)),
                          ("▲ Collapse", lambda: self._expand(False))):
            ttk.Button(tb2, text=text, command=cmd, style="Tool.TButton").pack(side="left", padx=1)
        frm = ttk.Frame(self)
        frm.pack(fill="both", expand=True, padx=4)
        self.tv = ttk.Treeview(frm, show="tree", selectmode="browse")
        sb = ttk.Scrollbar(frm, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=sb.set)
        self.tv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tv.tag_configure("tx", foreground="#0a3d8f")
        self.tv.bind("<Double-1>", self._activate)
        self.tv.bind("<Return>", self._activate)
        self.tv.bind("<Button-3>", self._context)
        self.tv.bind("<<TreeviewOpen>>", self._icon_toggle)
        self.tv.bind("<<TreeviewClose>>", self._icon_toggle)
        self.status = tk.StringVar(self)
        st = ttk.Frame(self)
        st.pack(fill="x", side="bottom")
        ttk.Label(st, textvariable=self.status, anchor="w", padding=(6, 2), relief="sunken").pack(side="left", fill="x", expand=True)
        ttk.Label(st, text="  %s (%s)  |  %s  |  port %s  " % (system["sid"], "800", user, system["port"]),
                  relief="sunken", padding=(6, 2)).pack(side="right")
        self.menu_data = None
        self.titles = {}
        self.protocol("WM_DELETE_WINDOW", self.logoff)
        self.bind("<F3>", lambda e: self.ok.focus_set())
        self.bind("<Control-slash>", lambda e: self.ok.focus_set())
        self.load_menu()

    # ---------------- menus and toolbar
    def _menubar(self):
        mb = tk.Menu(self)
        m = tk.Menu(mb, tearoff=0)
        m.add_command(label="Execute", accelerator="Enter", command=lambda: self._activate(None))
        m.add_command(label="Create session", command=lambda: self.run("HOME"))
        m.add_separator()
        m.add_command(label="Log off", command=self.logoff)
        mb.add_cascade(label="Menu", menu=m)
        e = tk.Menu(mb, tearoff=0)
        e.add_command(label="Find in menu ...", accelerator="Ctrl+F", command=self.find)
        e.add_command(label="Refresh menu", command=self.load_menu)
        mb.add_cascade(label="Edit", menu=e)
        f = tk.Menu(mb, tearoff=0)
        f.add_command(label="Insert transaction ...", command=self.fav_insert)
        f.add_command(label="Add selected to favorites", command=self.fav_add)
        f.add_command(label="Insert folder ...", command=self.fav_folder)
        f.add_command(label="Change ...", command=self.fav_rename)
        f.add_command(label="Delete", command=self.fav_delete)
        f.add_separator()
        f.add_command(label="Move up", command=lambda: self.fav_move(-1))
        f.add_command(label="Move down", command=lambda: self.fav_move(1))
        f.add_command(label="Reset to default favorites", command=self.fav_reset)
        mb.add_cascade(label="Favorites", menu=f)
        x = tk.Menu(mb, tearoff=0)
        x.add_checkbutton(label="Show technical names", variable=self.tech, command=self.build_tree)
        mb.add_cascade(label="Extras", menu=x)
        s = tk.Menu(mb, tearoff=0)
        s.add_command(label="New session", command=lambda: self.run("HOME"))
        s.add_command(label="ERP Dashboard", command=lambda: C.open_app(self.s, C.dashboard_url(self.s), "1560,960"))
        s.add_command(label="User profile (AMS)", command=lambda: self.run("ZAMS"))
        s.add_command(label="Status", command=self.sys_status)
        mb.add_cascade(label="System", menu=s)
        h = tk.Menu(mb, tearoff=0)
        h.add_command(label="e-Learning (ZLMS)", command=lambda: self.run("ZLMS"))
        h.add_command(label="About MM Core", command=lambda: messagebox.showinfo(
            "About", "MM Core desktop client %s\nSystem %s on port %s\nDatabase %s"
            % (VERSION, self.s["sid"], self.s["port"], self.s["db"]), parent=self))
        mb.add_cascade(label="Help", menu=h)
        self.config(menu=mb)
        self.bind("<Control-f>", lambda e: self.find())

    def _toolbar(self):
        bar = ttk.Frame(self, padding=(6, 4))
        bar.pack(fill="x")
        ttk.Button(bar, text="✔", width=3, command=self._okcode).pack(side="left")
        self.okv = tk.StringVar(self)
        self.ok = ttk.Combobox(bar, textvariable=self.okv, width=26, values=self.history)
        self.ok.pack(side="left", padx=4)
        self.ok.bind("<Return>", lambda e: self._okcode())
        for text, cmd in (("New session", lambda: self.run("HOME")), ("Log off", self.logoff),
                          ("Find", self.find), ("Help", lambda: self.run("ZLMS"))):
            ttk.Button(bar, text=text, command=cmd, style="Tool.TButton").pack(side="left", padx=1)
        self.ok.focus_set()

    # ---------------- menu tree
    def load_menu(self):
        self.status.set("Reading the menu ...")

        _bg(self, lambda tick: C.menu(self.s, self.token), self._menu_loaded, lambda e: self.status.set(str(e)))

    def _menu_loaded(self, d):
        self.menu_data, self.titles = d["tree"], d["titles"]
        self.build_tree()
        self.status.set("Ready - double-click a transaction or enter a code (e.g. MIGO, /oVA01)")

    def _label(self, tcode):
        t = self.titles.get(tcode, "")
        return ("%s - %s" % (tcode, t) if t else tcode) if self.tech.get() else (t or tcode)

    def build_tree(self):
        self.tv.delete(*self.tv.get_children())
        self.node = {}
        fav = self.tv.insert("", "end", text=" Favorites", image=self.ic["open"], open=True)
        self.node[fav] = ("favroot", self.favs)

        def add_fav(parent, items):
            for it in items:
                if it["type"] == "folder":
                    n = self.tv.insert(parent, "end", text=" " + it["name"], image=self.ic["folder"])
                    self.node[n] = ("favfolder", it)
                    add_fav(n, it.setdefault("items", []))
                else:
                    n = self.tv.insert(parent, "end", text=" " + self._label(it["tcode"]), image=self.ic["star"], tags=("tx",))
                    self.node[n] = ("fav", it)
        add_fav(fav, self.favs)
        root = self.tv.insert("", "end", text=" MM Core Menu", image=self.ic["open"], open=True)
        self.node[root] = ("menuroot", None)

        def add_menu(parent, items):
            for it in items or []:
                if isinstance(it, str):
                    if it.startswith("!"):
                        continue
                    n = self.tv.insert(parent, "end", text=" " + self._label(it), image=self.ic["tx"], tags=("tx",))
                    self.node[n] = ("tx", it)
                else:
                    name = it[0].lstrip("!")
                    n = self.tv.insert(parent, "end", text=" " + name, image=self.ic["folder"])
                    self.node[n] = ("folder", name)
                    add_menu(n, it[1])
        add_menu(root, self.menu_data or [])

    def _icon_toggle(self, e):
        n = self.tv.focus()
        k = self.node.get(n, ("",))[0]
        if k in ("folder", "favfolder", "favroot", "menuroot"):
            self.tv.item(n, image=self.ic["open"] if self.tv.item(n, "open") else self.ic["folder"])

    def _expand(self, on):
        def rec(n):
            for c in self.tv.get_children(n):
                if self.tv.get_children(c):
                    self.tv.item(c, open=on, image=self.ic["open"] if on else self.ic["folder"])
                    rec(c)
        for top in self.tv.get_children(""):
            rec(top)

    def _tcode_of(self, n):
        k, v = self.node.get(n, (None, None))
        if k == "tx":
            return v
        if k == "fav":
            return v["tcode"]
        return None

    def _activate(self, e):
        n = self.tv.focus()
        t = self._tcode_of(n)
        if t:
            self.run(t)
        return "break" if t else None

    def _context(self, e):
        n = self.tv.identify_row(e.y)
        if not n:
            return
        self.tv.selection_set(n)
        self.tv.focus(n)
        k = self.node.get(n, ("",))[0]
        m = tk.Menu(self, tearoff=0)
        if self._tcode_of(n):
            m.add_command(label="Execute", command=lambda: self._activate(None))
            m.add_command(label="Execute in new window", command=lambda: self._activate(None))
        if k == "tx":
            m.add_command(label="Add to favorites", command=self.fav_add)
        if k in ("fav", "favfolder", "favroot"):
            m.add_command(label="Insert transaction ...", command=self.fav_insert)
            m.add_command(label="Insert folder ...", command=self.fav_folder)
        if k in ("fav", "favfolder"):
            m.add_command(label="Change ...", command=self.fav_rename)
            m.add_command(label="Delete favorite", command=self.fav_delete)
            m.add_command(label="Move up", command=lambda: self.fav_move(-1))
            m.add_command(label="Move down", command=lambda: self.fav_move(1))
        m.tk_popup(e.x_root, e.y_root)

    # ---------------- run transactions
    def _okcode(self):
        mode, t = C.parse_okcode(self.okv.get())
        self.okv.set("")
        if not mode:
            return
        if mode == "logoff":
            return self.logoff()
        if t not in self.titles and t != "HOME":
            self.status.set("Transaction %s does not exist" % t)
            self.bell()
            return
        if t in self.history:
            self.history.remove(t)
        self.history.insert(0, t)
        self.ok.configure(values=self.history[:20])
        self.run(t)

    def run(self, tcode):
        try:
            C.open_session(self.s, tcode, self.user, self.token)
            self.status.set("Transaction %s started in its own window" % tcode)
        except OSError as e:
            messagebox.showerror("Start transaction", str(e), parent=self)

    # ---------------- favorites
    def _fav_container(self, n):
        """(list, index) where to insert next to node n."""
        k, v = self.node.get(n, (None, None))
        if k == "favroot":
            return self.favs, len(self.favs)
        if k == "favfolder":
            return v.setdefault("items", []), len(v["items"])
        if k == "fav":
            parent = self.tv.parent(n)
            pk, pv = self.node.get(parent)
            lst = self.favs if pk == "favroot" else pv["items"]
            return lst, lst.index(v) + 1
        return self.favs, len(self.favs)

    def _fav_changed(self):
        C.save_favorites(self.s["sid"], self.favs)
        self.build_tree()

    def fav_add(self):
        n = self.tv.focus()
        t = self._tcode_of(n)
        if not t:
            return self.status.set("Select a transaction in the menu first")
        if any(f.get("tcode") == t for f in self.favs):
            return self.status.set("%s is already in the favorites" % t)
        self.favs.append(dict(type="tx", tcode=t))
        self._fav_changed()
        self.status.set("%s added to the favorites" % t)

    def fav_insert(self):
        t = simpledialog.askstring("Insert transaction", "Transaction code:", parent=self)
        if not t:
            return
        t = t.strip().upper()
        if t not in self.titles:
            return messagebox.showerror("Insert transaction", "Transaction %s does not exist" % t, parent=self)
        lst, i = self._fav_container(self.tv.focus())
        lst.insert(i, dict(type="tx", tcode=t))
        self._fav_changed()

    def fav_folder(self):
        name = simpledialog.askstring("Insert folder", "Folder name:", parent=self)
        if not name:
            return
        lst, i = self._fav_container(self.tv.focus())
        lst.insert(i, dict(type="folder", name=name.strip()[:40], items=[]))
        self._fav_changed()

    def _fav_parent_list(self, n):
        parent = self.tv.parent(n)
        pk, pv = self.node.get(parent, (None, None))
        return self.favs if pk == "favroot" else pv["items"]

    def fav_delete(self):
        n = self.tv.focus()
        k, v = self.node.get(n, (None, None))
        if k not in ("fav", "favfolder"):
            return self.status.set("Select a favorite or a favorites folder")
        if k == "favfolder" and v.get("items") and not messagebox.askyesno(
                "Delete folder", "Delete the folder '%s' with its %d entries?" % (v["name"], len(v["items"])), parent=self):
            return
        self._fav_parent_list(n).remove(v)
        self._fav_changed()

    def fav_rename(self):
        n = self.tv.focus()
        k, v = self.node.get(n, (None, None))
        if k == "favfolder":
            name = simpledialog.askstring("Change folder", "Folder name:", initialvalue=v["name"], parent=self)
            if name:
                v["name"] = name.strip()[:40]
                self._fav_changed()
        elif k == "fav":
            t = simpledialog.askstring("Change favorite", "Transaction code:", initialvalue=v["tcode"], parent=self)
            if t and t.strip().upper() in self.titles:
                v["tcode"] = t.strip().upper()
                self._fav_changed()
        else:
            self.status.set("Select a favorite or a favorites folder")

    def fav_move(self, d):
        n = self.tv.focus()
        k, v = self.node.get(n, (None, None))
        if k not in ("fav", "favfolder"):
            return
        lst = self._fav_parent_list(n)
        i = lst.index(v)
        j = i + d
        if 0 <= j < len(lst):
            lst[i], lst[j] = lst[j], lst[i]
            self._fav_changed()

    def fav_reset(self):
        if messagebox.askyesno("Favorites", "Replace your favorites by the default favorites?", parent=self):
            self.favs = C.load_favorites("__default__")
            self._fav_changed()

    # ---------------- other
    def find(self):
        t = simpledialog.askstring("Find", "Transaction code or text:", parent=self)
        if not t:
            return
        t = t.strip().lower()
        for n, (k, v) in self.node.items():
            if k == "tx" and (t in v.lower() or t in self.titles.get(v, "").lower()):
                p = self.tv.parent(n)
                while p:
                    self.tv.item(p, open=True)
                    p = self.tv.parent(p)
                self.tv.selection_set(n)
                self.tv.focus(n)
                self.tv.see(n)
                self.status.set("Found %s - press Enter to start it" % v)
                return
        self.status.set("Nothing found for '%s'" % t)

    def sys_status(self):
        i = C.info(int(self.s["port"])) or {}
        me = C.me(self.s, self.token)
        roles = ", ".join(r.get("role", "") for r in me.get("roles", [])) or "-"
        messagebox.showinfo("Status", "System: %s (%s)\nPort: %s\nDatabase: %s\nUser: %s %s\nRoles: %s\nUser logon: %s"
                            % (self.s["name"], self.s["sid"], self.s["port"], i.get("db", self.s["db"]), self.user,
                               me.get("name", ""), roles, "ON" if i.get("auth") else "OFF"), parent=self)

    def logoff(self):
        if not messagebox.askyesno("Log Off", "Do you really want to log off from %s?\nUnsaved data in open "
                                   "transaction windows will be lost." % self.s["sid"], parent=self):
            return
        C.logoff(self.s, self.token)
        if self in self.pad.open_windows:
            self.pad.open_windows.remove(self)
        self.destroy()


def main():
    root = tk.Tk()
    _style(root)
    LogonPad(root)
    root.mainloop()


if __name__ == "__main__":
    main()
