"""Skills matrix and certifications (qualification catalog): which employee may do which work, at which
level (1 = trained, 2 = independent, 3 = can train others), until when. Used by the shop floor (GMES):
an operator may only book at a station whose skill he holds and is still valid."""
import datetime

from mm import util as clock
from mm.db import transaction
from mm.util import MMError, now_ts, parse_date, parse_int

LEVELS = {1: "Trained (under supervision)", 2: "Independent", 3: "Trainer / expert"}


def save_skill(conn, code, text, valid_months=24, kind="SKILL"):
    code = (code or "").strip().upper()
    if not code or not (text or "").strip():
        raise MMError("Enter the skill code and text", "PQ", "901")
    m = parse_int(valid_months, "validity in months", 1, 240)
    with transaction(conn):
        conn.execute("INSERT OR REPLACE INTO hr_skill (code, text, valid_months, kind) VALUES (?,?,?,?)",
                     (code[:12], text.strip()[:80], m, (kind or "SKILL")[:10]))
    return {"message": "Skill %s saved" % code}


def skills(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM hr_skill ORDER BY code")]


def qualify(conn, pernr, skill, level=1, valid_from=None, user="", trainer="", note="", valid_to=None):
    e = conn.execute("SELECT pernr, status FROM hr_employee WHERE pernr=?", (str(pernr),)).fetchone()
    if not e:
        raise MMError("Employee %s does not exist" % pernr, "PQ", "902")
    s = conn.execute("SELECT * FROM hr_skill WHERE code=?", ((skill or "").upper(),)).fetchone()
    if not s:
        raise MMError("Skill %s does not exist" % skill, "PQ", "903")
    lv = parse_int(level, "level", 1, 3)
    vf = parse_date(valid_from) if valid_from else clock.today().isoformat()
    if valid_to:
        vt = parse_date(valid_to)
    else:
        d = datetime.date.fromisoformat(vf)
        y, m = divmod(d.month - 1 + s["valid_months"], 12)
        vt = datetime.date(d.year + y, m + 1, min(d.day, 28)).isoformat()
    if vt < vf:
        raise MMError("Valid to is before valid from", "PQ", "904")
    with transaction(conn):
        conn.execute("INSERT OR REPLACE INTO hr_qual (pernr, skill, level, valid_from, valid_to, trainer, note, usnam, ts) "
                     "VALUES (?,?,?,?,?,?,?,?,?)", (e["pernr"], s["code"], lv, vf, vt, (trainer or "")[:40], (note or "")[:200],
                                                    user, now_ts()))
    return {"message": "%s qualified for %s (level %d) until %s" % (e["pernr"], s["code"], lv, vt)}


def certified(conn, pernr, skill, day=None):
    """None when the employee may do the work, otherwise the reason (text)"""
    day = day or clock.today().isoformat()
    e = conn.execute("SELECT pernr, name, status, leave_date FROM hr_employee WHERE pernr=?", (str(pernr),)).fetchone()
    if not e or (e["leave_date"] and e["leave_date"] <= day):
        return "Operator %s is not an active employee" % pernr
    if not skill:
        return None
    q = conn.execute("SELECT * FROM hr_qual WHERE pernr=? AND skill=?", (e["pernr"], skill)).fetchone()
    if not q:
        return "%s is not certified for %s" % (e["name"], skill)
    if not q["valid_from"] <= day <= q["valid_to"]:
        return "The certification of %s for %s expired on %s" % (e["name"], skill, q["valid_to"])
    return None


def matrix(conn, day=None, warn_days=30):
    """skills matrix: employees x skills with level and validity (expired / expiring soon)"""
    day = day or clock.today().isoformat()
    soon = (datetime.date.fromisoformat(day) + datetime.timedelta(days=warn_days)).isoformat()
    sk = skills(conn)
    rows = []
    for e in conn.execute("SELECT pernr, name, job, orgeh FROM hr_employee WHERE COALESCE(leave_date,'')='' OR leave_date>? "
                          "ORDER BY pernr", (day,)):
        cells = {}
        for q in conn.execute("SELECT * FROM hr_qual WHERE pernr=?", (e["pernr"],)):
            state = "expired" if q["valid_to"] < day else "expiring" if q["valid_to"] <= soon else "valid"
            cells[q["skill"]] = dict(level=q["level"], valid_to=q["valid_to"], state=state)
        rows.append(dict(e, skills=cells))
    cover = {s["code"]: sum(1 for r in rows if r["skills"].get(s["code"], {}).get("state") in ("valid", "expiring"))
             for s in sk}
    return {"skills": sk, "rows": rows, "coverage": cover,
            "expired": sum(1 for r in rows for c in r["skills"].values() if c["state"] == "expired"),
            "expiring": sum(1 for r in rows for c in r["skills"].values() if c["state"] == "expiring")}
