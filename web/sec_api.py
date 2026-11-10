"""API of the user and authorisation administration: logon, AMS self-service,
SU01, PFCG, SUIM, SU53, SM04, SM20 and the approval inbox ZINBOX."""
from mm.util import MMError, parse_int, require

from sec import auth, inbox as sec_inbox, users
from sec.config import ACTIVITIES, ALWAYS, AREAS, COOKIE, IDLE_HOURS, OBJECTS

from web.server import db, route


def _cookie(req, value, age=None):
    ck = "%s=%s; HttpOnly; SameSite=Strict; Path=/" % (COOKIE, value)
    ck += "; Max-Age=%d" % (age if age is not None else IDLE_HOURS * 3600)
    if hasattr(req, "_cookies"):
        req._cookies.append(ck)


def _auth_on(req):
    return getattr(getattr(req, "server", None), "auth", False)


# ------------------------------------------------------------------ logon
@route("GET", "/api/sec/status")
def sec_status(req, q):
    c = db()
    return {"auth": _auth_on(req), "demo": users.demo_hint(c)}


@route("POST", "/api/sec/login")
def sec_login(req, q):
    b = req.body
    token, must = users.login(db(), b.get("bname"), b.get("password"), getattr(req, "ip", ""))
    _cookie(req, token)
    return {"user": (b.get("bname") or "").strip().upper(), "must_change": must,
            "message": "Welcome" + (" - please change your initial password" if must else "")}


@route("POST", "/api/sec/logout")
def sec_logout(req, q):
    users.logout(db(), getattr(req, "token", None), req.user)
    _cookie(req, "", 0)
    return {"message": "Logged off"}


@route("POST", "/api/sec/unlock-request")
def sec_unlock_request(req, q):
    users.unlock_request(db(), req.body.get("bname"), req.body.get("reason"))
    # same answer whether the user exists or not
    return {"message": "Request sent to the administrator. You will be informed when it is done."}


# ------------------------------------------------------------------ AMS (self-service)
@route("GET", "/api/sec/me")
def sec_me(req, q):
    c = db()
    if not _auth_on(req) and not c.execute("SELECT 1 FROM usr WHERE bname=?", (req.user,)).fetchone():
        return {"bname": req.user, "name": req.user, "dev": True, "roles": [], "requests": [],
                "recent": [], "allowed": None, "patterns": ["*"], "always": list(ALWAYS)}
    u = users.me(c, req.user)
    prof = u.pop("profile")
    u["allowed"] = sorted(t for t in auth.catalog() if auth.tcode_allowed(prof, t))
    u["patterns"] = [p for p in prof["tcodes"] if not p.startswith("@")]
    u["always"] = list(ALWAYS)
    u["admin"] = auth.object_allowed(prof, "S_USER_GRP", "*", "02")
    u["dev"] = not _auth_on(req)
    return u


@route("POST", "/api/sec/password")
def sec_password(req, q):
    require(req.body, "old", "new")
    if req.body.get("new") != req.body.get("repeat", req.body.get("new")):
        raise MMError("The two new passwords differ", "00", "183")
    users.change_password(db(), req.user, req.body["old"], req.body["new"])
    return {"message": "Password changed"}


@route("GET", "/api/sec/roles")
def sec_roles_short(req, q):
    return [dict(name=r[0], text=r[1]) for r in db().execute("SELECT name, text FROM role ORDER BY name")]


@route("POST", "/api/sec/request")
def sec_request(req, q):
    b = req.body
    n = users.request(db(), req.user, b.get("typ") or "ROLE", b.get("role"), b.get("valid_to"),
                      b.get("reason"))
    return {"reqid": n, "message": "Request %s sent for approval (ZINBOX of the administrator)" % n}


@route("GET", "/api/sec/inbox")
def sec_inbox_list(req, q):
    return sec_inbox.inbox(db(), req.user)


@route("GET", "/api/sec/su53")
def sec_su53(req, q):
    return auth.LAST_FAIL.get(req.user) or {}


# ------------------------------------------------------------------ SU01 users
@route("GET", "/api/sec/admin/users")
def sec_users(req, q):
    return users.users(db())


@route("GET", "/api/sec/admin/user/(?P<b>[^/]+)")
def sec_user(req, q, b):
    return users.user_detail(db(), b)


@route("POST", "/api/sec/admin/user")
def sec_user_save(req, q):
    pw = users.save_user(db(), req.body, req.user)
    b = (req.body.get("bname") or "").upper()
    if pw:
        return {"password": pw, "message": "User %s created - initial password %s "
                                           "(must be changed at the first logon)" % (b, pw)}
    return {"message": "User %s saved" % b}


@route("POST", "/api/sec/admin/user/(?P<b>[^/]+)/(?P<act>lock|unlock|reset|delete)")
def sec_user_action(req, q, b, act):
    c = db()
    if act == "reset":
        pw = users.reset_password(c, b, req.user)
        return {"password": pw, "message": "New initial password for %s: %s" % (b.upper(), pw)}
    if act == "delete":
        users.delete_user(c, b, req.user)
        return {"message": "User %s deleted" % b.upper()}
    users.lock(c, b, req.user, act == "lock")
    return {"message": "User %s %sed" % (b.upper(), act)}


# ------------------------------------------------------------------ PFCG roles
@route("GET", "/api/sec/admin/roles")
def sec_roles(req, q):
    return users.roles(db())


@route("POST", "/api/sec/admin/role")
def sec_role_save(req, q):
    n = users.save_role(db(), req.body, req.user)
    return {"message": "Role %s saved" % n}


@route("POST", "/api/sec/admin/role/(?P<r>[^/]+)/delete")
def sec_role_delete(req, q, r):
    users.delete_role(db(), r, req.user)
    return {"message": "Role %s deleted" % r.upper()}


@route("GET", "/api/sec/admin/catalog")
def sec_catalog(req, q):
    cat = auth.catalog()
    return {"areas": AREAS, "activities": ACTIVITIES, "objects": OBJECTS,
            "tcodes": [dict(tcode=t, areas=", ".join(sorted(a))) for t, a in sorted(cat.items())]}


# ------------------------------------------------------------------ requests (approval)
@route("POST", "/api/sec/admin/request/decide")
def sec_decide(req, q):
    b = req.body
    n = parse_int(b.get("reqid"), "request")
    pw = users.decide(db(), n, bool(b.get("approve")), req.user, b.get("note"))
    m = "Request %s %s" % (n, "approved" if b.get("approve") else "rejected")
    return {"password": pw, "message": m + (" - new initial password %s" % pw if pw else "")}


# ------------------------------------------------------------------ SUIM, SM04, SM20
@route("GET", "/api/sec/admin/suim")
def sec_suim(req, q):
    c = db()
    if q.get("tcode"):
        return {"by": "tcode", "rows": auth.users_for_tcode(c, q["tcode"])}
    if q.get("user"):
        users.user_detail(c, q["user"])           # message if unknown
        return {"by": "user", **auth.tcodes_for_user(c, q["user"].upper())}
    raise MMError("Enter a transaction code or a user name", "01", "120")


@route("GET", "/api/sec/admin/sessions")
def sec_sessions(req, q):
    return users.sessions(db())


@route("POST", "/api/sec/admin/session/end")
def sec_session_end(req, q):
    users.end_session(db(), req.body.get("id"), req.user)
    return {"message": "Session ended"}


@route("GET", "/api/sec/admin/audit")
def sec_audit(req, q):
    return auth.audit_list(db(), q.get("user"), q.get("d1"), q.get("d2"), q.get("action"),
                           parse_int(q.get("limit"), "limit", 1, 5000, default=500))
