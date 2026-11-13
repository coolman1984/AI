"""Users, roles, logon and sessions (SU01, PFCG, SM04) and the AMS self-service:
my assignments, password change, access / unlock requests."""
import datetime
import hashlib
import hmac
import os
import secrets
import time

from mm.db import atomic, rows, transaction
from mm.util import MMError, now_ts
from mm import util as mmclock

from . import auth
from .config import (DEMO_ROLES, DEMO_USERS, IDLE_HOURS, MAX_FAILED, MIN_PW, UNUSED_DAYS)

LOCKS = {"": "Available", "F": "Locked: too many failed logons", "A": "Locked by administrator",
         "U": "Locked: long-term unused"}


# ------------------------------------------------------------------ passwords
ITER = 200000          # PBKDF2 rounds (the tests lower it for speed; stored with the hash)


def _hash(pw, salt, iters=None):
    n = iters or ITER
    return "%d$%s" % (n, hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), bytes.fromhex(salt), n).hex())


def _verify(pw, u):
    stored = u["pw_hash"] or ""
    n = int(stored.split("$", 1)[0]) if "$" in stored else 200000
    return hmac.compare_digest(_hash(pw or "", u["pw_salt"], n), stored)


def _set_pw(conn, bname, pw, must_change):
    salt = secrets.token_hex(16)
    conn.execute("UPDATE usr SET pw_salt=?, pw_hash=?, must_change=?, pw_changed=?, failed=0 "
                 "WHERE bname=?", (salt, _hash(pw, salt), 1 if must_change else 0, now_ts(), bname))


def _policy(pw):
    if len(pw or "") < MIN_PW:
        raise MMError("The password must have at least %d characters" % MIN_PW, "00", "180")
    if pw.isdigit() or pw.isalpha():
        raise MMError("The password must contain letters and digits", "00", "181")


def _initial_pw():
    return secrets.token_urlsafe(9)[:10] + str(secrets.randbelow(10))


def _key(bname):
    b = (bname or "").strip().upper()
    if not b or len(b) > 12 or not all(ch.isalnum() or ch in "._-" for ch in b):
        raise MMError("Enter a user name (max. 12 letters / digits)", "01", "100")
    return b


def _user(conn, bname):
    u = conn.execute("SELECT * FROM usr WHERE bname=?", (_key(bname),)).fetchone()
    if not u:
        raise MMError("User %s does not exist" % bname, "01", "124")
    return u


def _date(text, default):
    if not text:
        return default
    try:
        return datetime.date.fromisoformat(str(text)[:10]).isoformat()
    except ValueError:
        raise MMError("Date %s is not valid (YYYY-MM-DD)" % text, "00", "100")


# ------------------------------------------------------------------ status
def status(u):
    """Lock status with the long-term-unused rule applied on the fly."""
    if u["locked"]:
        return u["locked"]
    if u["valid_to"] and u["valid_to"] < mmclock.today().isoformat():
        return "V"
    last = (u["last_login"] or u["created"] or "")[:10]
    if last and last < (mmclock.today() - datetime.timedelta(days=UNUSED_DAYS)).isoformat():
        return "U"
    return ""


def status_text(st):
    return "Expired (validity)" if st == "V" else LOCKS.get(st, st)


# ------------------------------------------------------------------ logon / session
def login(conn, bname, pw, ip=""):
    b = (bname or "").strip().upper()
    u = conn.execute("SELECT * FROM usr WHERE bname=?", (b,)).fetchone()
    if not u or not u["pw_hash"]:
        auth.audit(conn, b, "LOGON_FAIL", "USR", b, "unknown user", ip=ip)
        raise MMError("Name or password is incorrect (repeat logon)", "00", "152")
    st = status(u)
    if st:
        if st == "U" and not u["locked"]:
            with transaction(conn):
                conn.execute("UPDATE usr SET locked='U' WHERE bname=?", (b,))
        auth.audit(conn, b, "LOGON_FAIL", "USR", b, status_text(st), ip=ip)
        raise MMError("User %s: %s - use 'Unlock / Change password' to ask the administrator"
                      % (b, status_text(st)), "00", "158")
    if not _verify(pw, u):
        with transaction(conn):
            n = (u["failed"] or 0) + 1
            conn.execute("UPDATE usr SET failed=?, locked=? WHERE bname=?",
                         (n, "F" if n >= MAX_FAILED else "", b))
        auth.audit(conn, b, "LOGON_FAIL", "USR", b, "wrong password (%d)" % n, ip=ip)
        raise MMError("Name or password is incorrect (repeat logon)" +
                      (" - user is now locked" if n >= MAX_FAILED else ""), "00", "152")
    token = secrets.token_hex(32)
    with transaction(conn):
        conn.execute("UPDATE usr SET failed=0, last_login=? WHERE bname=?", (now_ts(), b))
        conn.execute("INSERT INTO usr_session VALUES (?,?,?,?,?)",
                     (token, b, now_ts(), time.time(), ip or ""))
    auth.audit(conn, b, "LOGON", "USR", b, "", ip=ip)
    return token, bool(u["must_change"])


def session_user(conn, token):
    """User of a valid session (idle timeout), or None."""
    if not token:
        return None
    s = conn.execute("SELECT * FROM usr_session WHERE token=?", (token,)).fetchone()
    if not s:
        return None
    if time.time() - float(s["last_seen"] or 0) > IDLE_HOURS * 3600:
        with transaction(conn):
            conn.execute("DELETE FROM usr_session WHERE token=?", (token,))
        return None
    if time.time() - float(s["last_seen"] or 0) > 60:     # write at most once a minute
        with transaction(conn):
            conn.execute("UPDATE usr_session SET last_seen=? WHERE token=?", (time.time(), token))
    return s["bname"]


def logout(conn, token, user=""):
    with transaction(conn):
        conn.execute("DELETE FROM usr_session WHERE token=?", (token or "",))
    auth.audit(conn, user, "LOGOFF", "USR", user)


def sessions(conn):
    out = rows(conn.execute("SELECT token, bname, created, last_seen, ip FROM usr_session "
                            "ORDER BY bname"))
    for r in out:
        r["id"] = r.pop("token")[:12]
        r["idle_min"] = int((time.time() - float(r["last_seen"] or 0)) // 60)
        del r["last_seen"]
    return out


def end_session(conn, sid, admin):
    with transaction(conn):
        n = conn.execute("DELETE FROM usr_session WHERE substr(token,1,12)=?", (sid or "",)).rowcount
    if not n:
        raise MMError("Session %s does not exist" % sid, "00", "001")
    auth.audit(conn, admin, "SESSION_END", "USR", sid, tcode="SM04")


def must_change(conn, bname):
    u = conn.execute("SELECT must_change FROM usr WHERE bname=?", (bname,)).fetchone()
    return bool(u and u["must_change"])


def change_password(conn, bname, old, new):
    u = _user(conn, bname)
    if not _verify(old, u):
        raise MMError("The current password is incorrect", "00", "152")
    _policy(new)
    if new == old:
        raise MMError("Choose a new password that differs from the current one", "00", "182")
    with transaction(conn):
        _set_pw(conn, u["bname"], new, False)
    auth.audit(conn, u["bname"], "PW_CHANGE", "USR", u["bname"], tcode="ZAMS")
    if u["bname"] == "ADMIN":       # the one-time password note is no longer needed
        from mm.db import DEFAULT_DB
        note = os.path.join(os.path.dirname(os.path.abspath(os.environ.get("MM_DB") or DEFAULT_DB)),
                            "first_login.txt")
        if os.path.exists(note):
            os.remove(note)


# ------------------------------------------------------------------ SU01
def users(conn):
    out = rows(conn.execute("SELECT bname, name, company, busarea, kostl, email, locked, valid_from, "
                            "valid_to, last_login, created, must_change, failed FROM usr ORDER BY bname"))
    for r in out:
        r["status"] = status(r)
        r["status_text"] = status_text(r["status"])
        r["roles"] = ", ".join(x[0] for x in conn.execute(
            "SELECT role FROM usr_role WHERE bname=? ORDER BY role", (r["bname"],)))
    return out


def user_detail(conn, bname):
    u = dict(_user(conn, bname))
    for k in ("pw_salt", "pw_hash"):
        u.pop(k, None)
    u["status"] = status(u)
    u["status_text"] = status_text(u["status"])
    u["roles"] = rows(conn.execute(
        "SELECT ur.role, r.text, ur.valid_from, ur.valid_to FROM usr_role ur LEFT JOIN role r "
        "ON r.name=ur.role WHERE ur.bname=? ORDER BY ur.role", (u["bname"],)))
    return u


@atomic
def save_user(conn, data, admin):
    """SU01 create / change. Returns the initial password for a new user."""
    b = _key(data.get("bname"))
    if not (data.get("name") or "").strip():
        raise MMError("Enter the full name of the user", "01", "101")
    vf = _date(data.get("valid_from"), mmclock.today().isoformat())
    vt = _date(data.get("valid_to"), "9999-12-31")
    if vt < vf:
        raise MMError("Valid to is before valid from", "01", "102")
    exists = conn.execute("SELECT 1 FROM usr WHERE bname=?", (b,)).fetchone()
    vals = (data["name"].strip()[:60], (data.get("company") or "")[:30], (data.get("busarea") or "")[:30],
            (data.get("kostl") or "")[:10], (data.get("email") or "")[:80], vf, vt)
    pw = None
    if exists:
        if data.get("create"):
            raise MMError("User %s already exists" % b, "01", "224")
        conn.execute("UPDATE usr SET name=?, company=?, busarea=?, kostl=?, email=?, valid_from=?, "
                     "valid_to=? WHERE bname=?", vals + (b,))
    else:
        conn.execute("INSERT INTO usr (name,company,busarea,kostl,email,valid_from,valid_to,bname,"
                     "created,created_by) VALUES (?,?,?,?,?,?,?,?,?,?)", vals + (b, now_ts(), admin))
        pw = data.get("password") or _initial_pw()
        _set_pw(conn, b, pw, True)
    if "roles" in data:
        set_roles(conn, b, data.get("roles") or [], admin)
    auth.audit(conn, admin, "USER_CHANGE" if exists else "USER_CREATE", "USR", b, vals[0], tcode="SU01")
    return pw


@atomic
def set_roles(conn, bname, roles, admin):
    """roles: [{role, valid_from, valid_to}] or role names."""
    b = _key(bname)
    conn.execute("DELETE FROM usr_role WHERE bname=?", (b,))
    for r in roles:
        r = r if isinstance(r, dict) else {"role": r}
        name = (r.get("role") or "").strip().upper()
        if not name:
            continue
        if not conn.execute("SELECT 1 FROM role WHERE name=?", (name,)).fetchone():
            raise MMError("Role %s does not exist" % name, "S#", "010")
        conn.execute("INSERT OR REPLACE INTO usr_role VALUES (?,?,?,?)",
                     (b, name, _date(r.get("valid_from"), mmclock.today().isoformat()),
                      _date(r.get("valid_to"), "9999-12-31")))
    auth.audit(conn, admin, "ROLE_ASSIGN", "USR", b,
               ",".join((r if isinstance(r, str) else r.get("role", "")) for r in roles), tcode="SU01")


@atomic
def lock(conn, bname, admin, on=True):
    b = _user(conn, bname)["bname"]
    if on and b == admin:
        raise MMError("You cannot lock your own user", "01", "110")
    if on:
        conn.execute("UPDATE usr SET locked='A' WHERE bname=?", (b,))
        conn.execute("DELETE FROM usr_session WHERE bname=?", (b,))
    else:       # unlocking restarts the "long-term unused" clock
        conn.execute("UPDATE usr SET locked='', failed=0, last_login=? WHERE bname=?", (now_ts(), b))
    auth.audit(conn, admin, "USER_LOCK" if on else "USER_UNLOCK", "USR", b, tcode="SU01")


@atomic
def reset_password(conn, bname, admin):
    """New initial password (must be changed at the next logon); unlocks the user."""
    b = _user(conn, bname)["bname"]
    pw = _initial_pw()
    _set_pw(conn, b, pw, True)
    conn.execute("UPDATE usr SET locked='', last_login=? WHERE bname=?", (now_ts(), b))
    conn.execute("DELETE FROM usr_session WHERE bname=?", (b,))
    auth.audit(conn, admin, "PW_RESET", "USR", b, tcode="SU01")
    return pw


@atomic
def delete_user(conn, bname, admin):
    b = _user(conn, bname)["bname"]
    if b == admin:
        raise MMError("You cannot delete your own user", "01", "111")
    for t in ("usr_role", "usr_session"):
        conn.execute("DELETE FROM %s WHERE bname=?" % t, (b,))
    conn.execute("DELETE FROM usr WHERE bname=?", (b,))
    auth.audit(conn, admin, "USER_DELETE", "USR", b, tcode="SU01")


# ------------------------------------------------------------------ PFCG
def roles(conn):
    out = rows(conn.execute("SELECT * FROM role ORDER BY name"))
    for r in out:
        r["tcodes"] = [x[0] for x in conn.execute(
            "SELECT tcode FROM role_tcode WHERE role=? ORDER BY tcode", (r["name"],))]
        r["auths"] = rows(conn.execute("SELECT object, value, actvt FROM role_auth WHERE role=? "
                                       "ORDER BY object, value", (r["name"],)))
        r["users"] = conn.execute("SELECT COUNT(*) FROM usr_role WHERE role=?", (r["name"],)).fetchone()[0]
    return out


@atomic
def save_role(conn, data, admin):
    name = (data.get("name") or "").strip().upper()
    if not name or len(name) > 30 or not all(ch.isalnum() or ch in "_-" for ch in name):
        raise MMError("Enter a role name (letters, digits, _)", "S#", "001")
    conn.execute("INSERT INTO role (name,text,changed,changed_by) VALUES (?,?,?,?) ON CONFLICT(name) "
                 "DO UPDATE SET text=excluded.text, changed=excluded.changed, changed_by=excluded.changed_by",
                 (name, (data.get("text") or name)[:60], now_ts(), admin))
    if "tcodes" in data:
        conn.execute("DELETE FROM role_tcode WHERE role=?", (name,))
        for t in data.get("tcodes") or []:
            t = str(t).strip().upper()
            if t:
                conn.execute("INSERT OR IGNORE INTO role_tcode VALUES (?,?)", (name, t))
    if "auths" in data:
        conn.execute("DELETE FROM role_auth WHERE role=?", (name,))
        for a in data.get("auths") or []:
            obj = (a.get("object") or "").strip().upper()
            act = (a.get("actvt") or "03").strip()
            if not obj:
                continue
            if act not in ("02", "03", "*"):
                raise MMError("Activity must be 02 (change), 03 (display) or *", "S#", "002")
            conn.execute("INSERT OR IGNORE INTO role_auth VALUES (?,?,?,?)",
                         (name, obj, (a.get("value") or "*").strip().upper(), act))
    auth.audit(conn, admin, "ROLE_CHANGE", "ROLE", name, tcode="PFCG")
    return name


@atomic
def delete_role(conn, name, admin):
    name = (name or "").upper()
    if conn.execute("SELECT COUNT(*) FROM usr_role WHERE role=?", (name,)).fetchone()[0]:
        raise MMError("Role %s is still assigned to users" % name, "S#", "003")
    for t, k in (("role_tcode", "role"), ("role_auth", "role"), ("role", "name")):
        conn.execute("DELETE FROM %s WHERE %s=?" % (t, k), (name,))
    auth.audit(conn, admin, "ROLE_DELETE", "ROLE", name, tcode="PFCG")


# ------------------------------------------------------------------ AMS self-service
def me(conn, bname):
    u = user_detail(conn, bname)
    prof = auth.profile(conn, bname)
    u["profile"] = prof
    u["requests"] = rows(conn.execute("SELECT * FROM access_request WHERE bname=? ORDER BY reqid DESC "
                                      "LIMIT 20", (u["bname"],)))
    u["recent"] = [r["tcode"] for r in conn.execute(
        "SELECT tcode, MAX(id) AS m FROM audit_log WHERE bname=? AND tcode<>'' GROUP BY tcode "
        "ORDER BY m DESC LIMIT 6", (u["bname"],))]
    return u


@atomic
def request(conn, bname, typ, role="", valid_to="", reason=""):
    """Access request (role) or unlock / password reset request."""
    typ = (typ or "").upper()
    if typ not in ("ROLE", "UNLOCK", "PWRESET"):
        raise MMError("Request type must be ROLE, UNLOCK or PWRESET", "S#", "020")
    b = _user(conn, bname)["bname"]
    role = (role or "").upper()
    if typ == "ROLE":
        if not conn.execute("SELECT 1 FROM role WHERE name=?", (role,)).fetchone():
            raise MMError("Role %s does not exist" % role, "S#", "010")
        if not (reason or "").strip():
            raise MMError("Enter the business reason for the access", "S#", "021")
    if conn.execute("SELECT 1 FROM access_request WHERE bname=? AND typ=? AND role=? AND status='O'",
                    (b, typ, role)).fetchone():
        raise MMError("The same request is already waiting for approval", "S#", "022")
    cur = conn.execute("INSERT INTO access_request (bname,typ,role,valid_to,reason,created) "
                       "VALUES (?,?,?,?,?,?)", (b, typ, role, _date(valid_to, "9999-12-31"),
                                                (reason or "")[:200], now_ts()))
    auth.audit(conn, b, "REQUEST_" + typ, "REQ", cur.lastrowid, role, tcode="ZAMS")
    return cur.lastrowid


def open_requests(conn):
    out = rows(conn.execute("SELECT r.*, u.name FROM access_request r LEFT JOIN usr u USING (bname) "
                            "WHERE r.status='O' ORDER BY r.reqid"))
    for r in out:
        u = conn.execute("SELECT * FROM usr WHERE bname=?", (r["bname"],)).fetchone()
        r["user_status"] = status_text(status(u)) if u else ""
    return out


@atomic
def decide(conn, reqid, approve, admin, note=""):
    r = conn.execute("SELECT * FROM access_request WHERE reqid=?", (reqid,)).fetchone()
    if not r or r["status"] != "O":
        raise MMError("Request %s is not open" % reqid, "S#", "023")
    if r["bname"] == admin:
        raise MMError("You cannot approve your own request (two-person rule)", "S#", "024")
    pw = None
    if approve:
        if r["typ"] == "ROLE":
            conn.execute("INSERT OR REPLACE INTO usr_role VALUES (?,?,?,?)",
                         (r["bname"], r["role"], mmclock.today().isoformat(), r["valid_to"] or "9999-12-31"))
        elif r["typ"] == "UNLOCK":
            conn.execute("UPDATE usr SET locked='', failed=0, last_login=? WHERE bname=?",
                         (now_ts(), r["bname"]))
        else:
            pw = reset_password(conn, r["bname"], admin)
    conn.execute("UPDATE access_request SET status=?, decided_by=?, decided=?, note=? WHERE reqid=?",
                 ("A" if approve else "R", admin, now_ts(), (note or "")[:200], reqid))
    auth.audit(conn, admin, "REQUEST_" + ("APPROVE" if approve else "REJECT"), "REQ", reqid,
               "%s %s %s" % (r["bname"], r["typ"], r["role"]), tcode="ZINBOX")
    return pw


@atomic
def unlock_request(conn, bname, reason=""):
    """From the logon screen (no session): only for an existing, locked user."""
    b = (bname or "").strip().upper()
    u = conn.execute("SELECT * FROM usr WHERE bname=?", (b,)).fetchone()
    if not u:          # do not reveal which user names exist
        return None
    typ = "UNLOCK" if status(u) else "PWRESET"
    if conn.execute("SELECT 1 FROM access_request WHERE bname=? AND typ=? AND status='O'",
                    (b, typ)).fetchone():
        return None
    return request(conn, b, typ, "", "", reason or "Self-service request from the logon screen")


# ------------------------------------------------------------------ installation
@atomic
def bootstrap(conn, demo):
    """First start: demo users (password = user name in lower case) in a demo
    database, otherwise one ADMIN with a one-time password. Returns that password."""
    if conn.execute("SELECT COUNT(*) FROM usr").fetchone()[0]:
        return None
    for name, (text, tcodes, auths) in DEMO_ROLES.items():
        save_role(conn, {"name": name, "text": text, "tcodes": tcodes,
                         "auths": [dict(object=o if o != "*" else "*", value=v, actvt=a)
                                   for o, v, a in auths]}, "SYSTEM")
    vf = (mmclock.today() - datetime.timedelta(days=365)).isoformat()
    if not demo:
        pw = _initial_pw()
        save_user(conn, {"bname": "ADMIN", "name": "System administrator", "valid_from": vf,
                         "password": pw, "roles": ["ADMIN"], "create": True}, "SYSTEM")
        return pw
    for b, (name, rls, area, kostl) in DEMO_USERS.items():
        save_user(conn, {"bname": b, "name": name, "company": "NERP Demo", "busarea": area,
                         "kostl": kostl, "valid_from": vf, "password": b.lower(),
                         "roles": [{"role": r, "valid_from": vf} for r in rls], "create": True}, "SYSTEM")
        conn.execute("UPDATE usr SET must_change=0 WHERE bname=?", (b,))
    # one user who has not logged on for half a year -> shows "Locked: long-term unused"
    save_user(conn, {"bname": "TEMP01", "name": "Temporary staff", "company": "NERP Demo",
                     "busarea": "Sales", "valid_from": vf, "password": "temp01",
                     "roles": [{"role": "SALES_CLERK", "valid_from": vf}], "create": True}, "SYSTEM")
    old = (mmclock.today() - datetime.timedelta(days=180)).isoformat() + " 09:00:00"
    conn.execute("UPDATE usr SET must_change=0, last_login=?, created=? WHERE bname='TEMP01'", (old, old))
    conn.execute("INSERT OR REPLACE INTO settings VALUES ('sec_demo', '1')")
    return None


def demo_hint(conn):
    r = conn.execute("SELECT value FROM settings WHERE key='sec_demo'").fetchone()
    return bool(r and r[0] == "1")
