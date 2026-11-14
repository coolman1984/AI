"""API for the desktop client (NERP Logon / Easy Access, folder gui/):
system information, the Easy Access menu tree with transaction texts, and the
single sign-on of session windows."""
import json
import os
import re

from mm.util import MMError

from web.server import STATIC, db, route

_MENU = {}


def _js_array(src):
    """The menu literals in menu.js are plain JSON except for trailing commas."""
    src = re.sub(r"//[^\n]*", "", src)
    src = re.sub(r",(\s*[\]\}])", r"\1", src)
    return json.loads(src)


def menu_tree():
    if _MENU:
        return _MENU
    with open(os.path.join(STATIC, "menu.js"), encoding="utf-8") as f:
        js = f.read()
    a = js.index("const MENU = [") + len("const MENU = ")
    b = js.index("\n];", a) + 2
    tree = _js_array(js[a:b])
    p = js.find("MENU.push(", b)
    if p >= 0:
        e = js.index("]]);", p) + 2
        tree += _js_array("[" + js[p + len("MENU.push("):e] + "]")
    top = re.search(r"const TOP = (\[[^\]]*\]);", js)
    if top:
        order = _js_array(top.group(1))
        tree.sort(key=lambda n: order.index(n[0]) if n[0] in order else 99)
    titles = {}
    tj = os.path.join(STATIC, "tcodes.json")        # exported from the app (tools/gui/export_tcodes.js)
    if os.path.exists(tj):
        with open(tj, encoding="utf-8") as f:
            titles.update(json.load(f))
    for fn in os.listdir(STATIC):
        if fn.endswith(".js"):
            with open(os.path.join(STATIC, fn), encoding="utf-8") as f:
                for m in re.finditer(r'register\(\s*"([^"]+)"\s*,\s*\{\s*title:\s*["\'`]([^"\'`]+)', f.read()):
                    titles.setdefault(m.group(1), m.group(2))
    _MENU.update(tree=tree, titles=titles)
    return _MENU


@route("GET", "/api/gui/info")
def gui_info(req, q):
    from mm.db import DEFAULT_DB
    path = os.path.abspath(os.environ.get("MM_DB") or DEFAULT_DB)
    c = db()
    demo = bool(c.execute("SELECT COUNT(*) FROM plant").fetchone()[0])
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # the program folder of this copy
    return {"product": "NERP", "db": path, "root": root, "auth": getattr(getattr(req, "server", None), "auth", False),
            "demo": demo, "port": req.server.server_address[1] if hasattr(req, "server") else None}


@route("GET", "/api/gui/menu")
def gui_menu(req, q):
    m = menu_tree()
    return {"tree": m["tree"], "titles": m["titles"]}


@route("POST", "/api/sec/sso")
def sec_sso(req, q):
    """A session window opened by the desktop client takes over its logon."""
    from sec import users
    from web.sec_api import _cookie
    token = str(req.body.get("token") or "")
    user = users.session_user(db(), token)
    if not user:
        raise MMError("The logon of the desktop client has expired - log on again", "00", "076")
    _cookie(req, token)
    return {"user": user}
