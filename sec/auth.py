"""Authorisation checks, the transaction catalogue, the audit log (SM20), the last
failed check (SU53) and the user information system (SUIM)."""
import fnmatch
import os
import re
import threading

from mm.db import atomic, rows
from mm.util import MMError, now_ts
from mm import util as mmclock

from .config import API_AREAS, MENU_AREAS, OBJECTS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MENU_JS = os.path.join(ROOT, "web", "static", "menu.js")

_LOCK = threading.Lock()
LAST_FAIL = {}          # SU53: user -> last refused check
_CATALOG = {}


# ------------------------------------------------------------------ transaction catalogue
def catalog():
    """tcode -> set of areas, read once from the Easy Access menu (web/static/menu.js),
    so a role can grant a whole menu area ('@SD') and stays in step with the menu."""
    if _CATALOG:
        return _CATALOG
    out = {}
    area = None
    try:
        with open(MENU_JS, encoding="utf-8") as f:
            for line in f:
                if line.startswith("const PROCESS"):
                    break
                m = re.match(r'^  \["([^"]+)", \[', line)
                if m and m.group(1) in MENU_AREAS:
                    area = MENU_AREAS[m.group(1)]
                if not area:
                    continue
                for t in re.findall(r'"([A-Z0-9_/.\-]{2,})"', line):
                    if t not in MENU_AREAS and not t.startswith("!"):
                        out.setdefault(t, set()).add(area)
    except OSError:
        pass
    for t in ("SU01", "PFCG", "SUIM", "SM04", "SM20"):
        out.setdefault(t, set()).add("BC")
    _CATALOG.update(out)
    return _CATALOG


def area_of_path(path):
    low = path.lower()                     # /api/forms/payslip/ must not bypass the HR area
    for prefix, area in API_AREAS:
        if low.startswith(prefix.lower()):
            return area
    return "MM"


# ------------------------------------------------------------------ permissions
def _valid_roles(conn, user):
    d = mmclock.today().isoformat()
    return [r[0] for r in conn.execute(
        "SELECT role FROM usr_role WHERE bname=? AND COALESCE(valid_from,'')<=? AND "
        "COALESCE(valid_to,'9999-12-31')>=?", (user, d, d))]


def profile(conn, user):
    """Everything the user may do: roles, transaction patterns and object values."""
    roles = _valid_roles(conn, user)
    q = ",".join("?" * len(roles)) or "''"
    tcodes = [r[0] for r in conn.execute(
        "SELECT DISTINCT tcode FROM role_tcode WHERE role IN (%s)" % q, roles)]
    auths = rows(conn.execute(
        "SELECT DISTINCT object, value, actvt FROM role_auth WHERE role IN (%s)" % q, roles))
    return {"roles": roles, "tcodes": tcodes, "auths": auths}


def tcode_allowed(prof, tcode):
    tcode = (tcode or "").upper()
    areas = catalog().get(tcode, set())
    for p in prof["tcodes"]:
        if p == "*" or p == tcode:
            return True
        if p.startswith("@") and p[1:] in areas:
            return True
        if "*" in p and fnmatch.fnmatchcase(tcode, p):
            return True
    return False


def _act_ok(have, need):
    return have == "*" or have == need or (have == "02" and need == "03")


def object_allowed(prof, obj, value="*", actvt="02"):
    for a in prof["auths"]:
        if a["object"] not in ("*", obj):
            continue
        if a["object"] == "*" and obj == "S_USER_GRP" and a["actvt"] != "*":
            continue        # user administration only when named explicitly (or full admin)
        if obj == "S_AREA" and value == "HR" and a["actvt"] != "*" and "HR" not in (a["value"],):
            continue        # personnel data and salaries: only with an explicit HR authorization
        if a["value"] not in ("*", value) and not (value == "*" and a["value"]):
            continue
        if _act_ok(a["actvt"], actvt):
            return True
    return False


def area_allowed(prof, area, actvt):
    if area == "BC":            # user administration: only through S_USER_GRP
        return object_allowed(prof, "S_USER_GRP", "*", actvt)
    return object_allowed(prof, "S_AREA", area, actvt)


def refuse(conn, user, kind, what, detail, tcode="", ip=""):
    """SU53 entry + audit line + the SAP message 00 077 / 00 078."""
    with _LOCK:
        LAST_FAIL[user] = dict(ts=now_ts(), kind=kind, what=what, detail=detail, tcode=tcode)
    try:
        audit(conn, user, "AUTH_FAIL", kind, what, detail, tcode=tcode, ip=ip)
    except Exception:      # noqa - the refusal itself must never fail
        pass
    if kind == "S_TCODE":
        return MMError("No authorization for transaction %s" % what, "00", "077")
    return MMError("No authorization: %s (%s) - see SU53" % (detail, what), "00", "078")


def check(conn, user, obj, value="*", actvt="02", tcode=""):
    """For engines and API layer: raise 00 078 if the user lacks the object."""
    if not object_allowed(profile(conn, user), obj, value, actvt):
        raise refuse(conn, user, obj, value, OBJECTS.get(obj, obj), tcode)


# ------------------------------------------------------------------ audit log
@atomic
def audit(conn, user, action, obj="", key="", detail="", tcode="", ip=""):
    conn.execute("INSERT INTO audit_log (ts,bname,ip,tcode,object,objkey,action,detail) "
                 "VALUES (?,?,?,?,?,?,?,?)", (now_ts(), user or "", ip or "", tcode or "",
                                              obj or "", str(key or "")[:80], action,
                                              str(detail or "")[:300]))


def audit_list(conn, user=None, d1=None, d2=None, action=None, limit=500):
    sql, args = "SELECT * FROM audit_log WHERE 1=1", []
    if user:
        sql += " AND bname=?"
        args.append(user.upper())
    if d1:
        sql += " AND ts>=?"
        args.append(d1)
    if d2:
        sql += " AND ts<=?"
        args.append(d2 + " 99")
    if action:
        sql += " AND action=?"
        args.append(action.upper())
    return rows(conn.execute(sql + " ORDER BY id DESC LIMIT ?", args + [int(limit)]))


# ------------------------------------------------------------------ SUIM
def users_for_tcode(conn, tcode):
    """SUIM: who may start a transaction (and through which role)."""
    tcode = (tcode or "").upper()
    out = []
    for u in conn.execute("SELECT bname, name, locked FROM usr ORDER BY bname").fetchall():
        prof = profile(conn, u["bname"])
        if not tcode_allowed(prof, tcode):
            continue
        via = [r for r in prof["roles"] if tcode_allowed(
            {"tcodes": [x[0] for x in conn.execute("SELECT tcode FROM role_tcode WHERE role=?", (r,))]},
            tcode)]
        change = any(area_allowed(prof, a, "02") for a in catalog().get(tcode, set())) \
            if catalog().get(tcode) else area_allowed(prof, "MM", "02")
        out.append(dict(bname=u["bname"], name=u["name"], locked=u["locked"],
                        roles=", ".join(via), change=change))
    return out


def tcodes_for_user(conn, user):
    """SUIM: which transactions a user may start, and with which activity."""
    prof = profile(conn, user)
    out = []
    for t, areas in sorted(catalog().items()):
        if tcode_allowed(prof, t):
            out.append(dict(tcode=t, areas=", ".join(sorted(areas)),
                            change=any(area_allowed(prof, a, "02") for a in areas)))
    return {"roles": prof["roles"], "auths": prof["auths"], "tcodes": out}
