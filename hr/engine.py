"""HR master data, organization and time management.

PA40  personnel actions: hiring, organizational change, pay change, leaving
PA30 / PA20  maintain / display employee data (with change documents)
PPOME  organizational units and positions
PA61  absences (requests -> approval) and overtime; PT50 leave quota overview
"""
import datetime

from mm.db import atomic, next_number, rows
from mm.util import MMError, now_ts, parse_amount, parse_date
from mm import util as mmclock

from .config import ABSENCE_TYPES, EMPLOYEE_GROUPS, EMPLOYEE_SUBGROUPS, LEAVE_REASONS, OVERTIME_TYPES

MONEY = ("basic", "allow_transport", "allow_housing", "allow_other", "ins_wage")
FIELDS = ("name", "name_ar", "national_id", "birth_date", "gender", "orgeh", "plans", "kostl", "werks", "persg",
          "persk", "job", "iban", "si_no", "phone", "email", "bname") + MONEY


def cfg(conn, key):
    from .config import DEFAULTS
    r = conn.execute("SELECT value FROM hr_config WHERE key=?", (key,)).fetchone()
    return r[0] if r else DEFAULTS[key]


def cfg_int(conn, key):
    return int(cfg(conn, key))


@atomic
def save_config(conn, values, user=""):
    """ZHR_CONF: legal rates and ceilings (validated)."""
    from .config import CONFIG_TEXT
    from .payroll import annual_tax
    for k, v in (values or {}).items():
        if k not in CONFIG_TEXT:
            raise MMError("Unknown setting %s" % k, "PG", "070")
        v = str(v).strip()
        if k == "tax_brackets":
            try:
                parts = [tuple(int(x) for x in p.split(":")) for p in v.split(",")]
            except ValueError:
                raise MMError("Tax brackets: limit:rate, limit:rate, ...", "PG", "071")
            if not parts or [u for u, _ in parts] != sorted(u for u, _ in parts):
                raise MMError("Tax brackets must be in ascending order", "PG", "072")
        elif not v.isdigit():
            raise MMError("%s must be a whole number" % k, "PG", "073")
        conn.execute("INSERT OR REPLACE INTO hr_config VALUES (?,?)", (k, v))
    annual_tax(conn, 100000)      # the brackets must still be readable


def _emp(conn, pernr):
    e = conn.execute("SELECT * FROM hr_employee WHERE pernr=?", (str(pernr or "").strip(),)).fetchone()
    if not e:
        raise MMError("Personnel number %s does not exist" % pernr, "PG", "001")
    return e


def _check_national_id(nid, birth_date=None):
    """Egyptian national ID: 14 digits, century (2 = 1900s, 3 = 2000s) + YYMMDD + ..."""
    if not nid:
        return
    if not (len(nid) == 14 and nid.isdigit() and nid[0] in "23"):
        raise MMError("The national ID must have 14 digits and start with 2 or 3", "PG", "010")
    y = (1900 if nid[0] == "2" else 2000) + int(nid[1:3])
    try:
        d = datetime.date(y, int(nid[3:5]), int(nid[5:7]))
    except ValueError:
        raise MMError("The national ID contains no valid birth date", "PG", "011")
    if birth_date and d.isoformat() != birth_date:
        raise MMError("Birth date %s does not match the national ID (%s)" % (birth_date, d.isoformat()), "PG", "012")


def _normalize(conn, data, old=None):
    v = {}
    for f in FIELDS:
        if f not in data:
            continue
        x = data.get(f)
        if f in MONEY:
            v[f] = parse_amount(x, allow_zero=True) if str(x or "").strip() != "" else 0
        elif f == "birth_date":
            v[f] = parse_date(x) if x else ""
        else:
            v[f] = str(x or "").strip()[:80]
    if "name" in v and not v["name"]:
        raise MMError("Enter the name of the employee", "PG", "002")
    if v.get("persg") and v["persg"] not in EMPLOYEE_GROUPS:
        raise MMError("Employee group %s does not exist" % v["persg"], "PG", "003")
    if v.get("persk") and v["persk"] not in EMPLOYEE_SUBGROUPS:
        raise MMError("Employee subgroup %s does not exist" % v["persk"], "PG", "004")
    if v.get("orgeh"):
        o = conn.execute("SELECT * FROM hr_orgunit WHERE orgeh=?", (v["orgeh"],)).fetchone()
        if not o:
            raise MMError("Organizational unit %s does not exist" % v["orgeh"], "PG", "005")
        if not v.get("kostl") and not (old and old["kostl"]):
            v["kostl"] = o["kostl"]
    if v.get("plans"):
        p = conn.execute("SELECT * FROM hr_position WHERE plans=?", (v["plans"],)).fetchone()
        if not p:
            raise MMError("Position %s does not exist" % v["plans"], "PG", "006")
        holder = conn.execute("SELECT pernr FROM hr_employee WHERE plans=? AND status='A' AND pernr<>?",
                              (v["plans"], old["pernr"] if old else "")).fetchone()
        if holder:
            raise MMError("Position %s is occupied by %s" % (v["plans"], holder[0]), "PG", "007")
        v.setdefault("orgeh", p["orgeh"])
    if v.get("kostl") and not conn.execute("SELECT 1 FROM cost_center WHERE kostl=?", (v["kostl"],)).fetchone():
        raise MMError("Cost center %s does not exist" % v["kostl"], "PG", "008")
    if "national_id" in v:
        _check_national_id(v["national_id"], v.get("birth_date") or (old["birth_date"] if old else None))
        if v["national_id"] and conn.execute("SELECT pernr FROM hr_employee WHERE national_id=? AND pernr<>?",
                                             (v["national_id"], old["pernr"] if old else "")).fetchone():
            raise MMError("National ID %s exists already" % v["national_id"], "PG", "013")
    if "basic" in v and v["basic"] <= 0 and not old:
        raise MMError("Enter the basic salary", "PG", "009")
    if "iban" in v and v["iban"] and not (v["iban"].startswith("EG") and len(v["iban"].replace(" ", "")) == 29):
        raise MMError("An Egyptian IBAN has 29 characters and starts with EG", "PG", "014")
    return v


def _log(conn, pernr, massn, begda, user, reason="", detail=""):
    conn.execute("INSERT INTO hr_action (pernr,massn,begda,reason,detail,usnam,ts) VALUES (?,?,?,?,?,?,?)",
                 (pernr, massn, begda, reason, detail[:200], user, now_ts()))


@atomic
def hire(conn, data, user):
    """PA40 action 01 Hiring."""
    begda = parse_date(data.get("hire_date"))
    for f in ("name", "orgeh", "basic"):
        if not str(data.get(f) or "").strip():
            raise MMError("Enter %s" % {"name": "the name", "orgeh": "the organizational unit",
                                         "basic": "the basic salary"}[f], "PG", "002")
    v = _normalize(conn, data)
    pernr = str(next_number(conn, "PERNR"))
    v.update(pernr=pernr, hire_date=begda, status="A", created=now_ts(), changed=now_ts(), changed_by=user)
    cols = ",".join(v)
    conn.execute("INSERT INTO hr_employee (%s) VALUES (%s)" % (cols, ",".join("?" * len(v))), list(v.values()))
    _log(conn, pernr, "01", begda, user, detail=v["name"])
    return pernr


@atomic
def change(conn, pernr, data, user, massn="02"):
    """PA30 / PA40 actions 02 org change, 03 pay change. Change documents per field."""
    e = _emp(conn, pernr)
    if e["status"] != "A":
        raise MMError("Employee %s has left - no changes possible" % pernr, "PG", "020")
    v = _normalize(conn, data, old=e)
    changed = {k: x for k, x in v.items() if str(e[k] if e[k] is not None else "") != str(x)}
    for k, x in changed.items():
        conn.execute("INSERT INTO hr_change (pernr,field,old,new,usnam,ts) VALUES (?,?,?,?,?,?)",
                     (e["pernr"], k, str(e[k] if e[k] is not None else ""), str(x), user, now_ts()))
    if changed:
        sets = ", ".join("%s=?" % k for k in changed)
        conn.execute("UPDATE hr_employee SET %s, changed=?, changed_by=? WHERE pernr=?" % sets,
                     list(changed.values()) + [now_ts(), user, e["pernr"]])
        pay = any(k in MONEY for k in changed)
        _log(conn, e["pernr"], "03" if pay and massn == "02" else massn, parse_date(data.get("begda")), user,
             detail=", ".join(changed))
    return sorted(changed)


@atomic
def terminate(conn, pernr, leave_date, reason, user):
    """PA40 action 10 Leaving: the position becomes vacant, payroll stops after the leave date."""
    e = _emp(conn, pernr)
    if e["status"] != "A":
        raise MMError("Employee %s has already left" % pernr, "PG", "021")
    if reason not in LEAVE_REASONS:
        raise MMError("Reason for leaving %s does not exist" % reason, "PG", "022")
    d = parse_date(leave_date)
    if d < e["hire_date"]:
        raise MMError("The leaving date is before the hiring date", "PG", "023")
    conn.execute("UPDATE hr_employee SET status='W', leave_date=?, leave_reason=?, plans='', changed=?, changed_by=? "
                 "WHERE pernr=?", (d, reason, now_ts(), user, e["pernr"]))
    _log(conn, e["pernr"], "10", d, user, reason=reason, detail=LEAVE_REASONS[reason])


def employee(conn, pernr):
    e = dict(_emp(conn, pernr))
    e["actions"] = rows(conn.execute("SELECT * FROM hr_action WHERE pernr=? ORDER BY begda DESC, id DESC", (e["pernr"],)))
    e["changes"] = rows(conn.execute("SELECT * FROM hr_change WHERE pernr=? ORDER BY id DESC LIMIT 50", (e["pernr"],)))
    e["quota"] = quota(conn, e["pernr"])
    o = conn.execute("SELECT text FROM hr_orgunit WHERE orgeh=?", (e["orgeh"],)).fetchone()
    e["org_text"] = o[0] if o else ""
    p = conn.execute("SELECT text FROM hr_position WHERE plans=?", (e["plans"],)).fetchone()
    e["position_text"] = p[0] if p else ""
    e["service_years"] = _years(e["hire_date"], e["leave_date"] or mmclock.today().isoformat())
    return e


def employees(conn, status="A", orgeh=None, text=None):
    sql = ("SELECT e.*, o.text AS org_text, p.text AS position_text FROM hr_employee e LEFT JOIN hr_orgunit o "
           "USING (orgeh) LEFT JOIN hr_position p ON p.plans=e.plans WHERE 1=1")
    a = []
    if status:
        sql += " AND e.status=?"
        a.append(status)
    if orgeh:
        sql += " AND e.orgeh=?"
        a.append(orgeh)
    if text:
        sql += " AND (e.name LIKE ? OR e.name_ar LIKE ? OR e.pernr LIKE ?)"
        a += ["%" + text + "%"] * 3
    return rows(conn.execute(sql + " ORDER BY e.pernr", a))


def _years(d1, d2):
    a, b = datetime.date.fromisoformat(d1[:10]), datetime.date.fromisoformat(d2[:10])
    return b.year - a.year - ((b.month, b.day) < (a.month, a.day))


# ------------------------------------------------------------------ organization (PPOME)
@atomic
def save_orgunit(conn, orgeh, text, parent="", kostl="", manager=""):
    orgeh = (orgeh or "").strip()
    if not orgeh or not (text or "").strip():
        raise MMError("Enter number and name of the organizational unit", "PG", "030")
    if parent and not conn.execute("SELECT 1 FROM hr_orgunit WHERE orgeh=?", (parent,)).fetchone():
        raise MMError("Superior unit %s does not exist" % parent, "PG", "031")
    if parent == orgeh:
        raise MMError("A unit cannot be its own superior", "PG", "032")
    if kostl and not conn.execute("SELECT 1 FROM cost_center WHERE kostl=?", (kostl,)).fetchone():
        raise MMError("Cost center %s does not exist" % kostl, "PG", "008")
    conn.execute("INSERT OR REPLACE INTO hr_orgunit VALUES (?,?,?,?,?)", (orgeh, text.strip()[:60], parent or "",
                                                                          kostl or "", manager or ""))


@atomic
def save_position(conn, plans, text, orgeh, kostl="", persk="S"):
    plans = (plans or "").strip()
    if not plans or not (text or "").strip():
        raise MMError("Enter number and name of the position", "PG", "033")
    if not conn.execute("SELECT 1 FROM hr_orgunit WHERE orgeh=?", (orgeh,)).fetchone():
        raise MMError("Organizational unit %s does not exist" % orgeh, "PG", "005")
    conn.execute("INSERT OR REPLACE INTO hr_position VALUES (?,?,?,?,?)", (plans, text.strip()[:60], orgeh,
                                                                           kostl or "", persk or "S"))


def org_structure(conn):
    units = rows(conn.execute("SELECT * FROM hr_orgunit ORDER BY orgeh"))
    for u in units:
        u["positions"] = rows(conn.execute(
            "SELECT p.*, e.pernr, e.name FROM hr_position p LEFT JOIN hr_employee e ON e.plans=p.plans AND "
            "e.status='A' WHERE p.orgeh=? ORDER BY p.plans", (u["orgeh"],)))
        u["headcount"] = conn.execute("SELECT COUNT(*) FROM hr_employee WHERE orgeh=? AND status='A'",
                                      (u["orgeh"],)).fetchone()[0]
    return units


# ------------------------------------------------------------------ time management (PA61 / PT50)
def _workdays(begda, endda):
    """Working days between two dates (factory calendar: Friday off)."""
    from pp.config import WORKDAYS
    d = datetime.date.fromisoformat(begda)
    e = datetime.date.fromisoformat(endda)
    n = 0
    while d <= e:
        if d.weekday() in WORKDAYS:
            n += 1
        d += datetime.timedelta(days=1)
    return n


def quota(conn, pernr, year=None):
    """PT50: annual leave entitlement, taken, requested, remaining (calendar year)."""
    e = _emp(conn, pernr)
    y = int(year or mmclock.today().year)
    end = "%04d-12-31" % y
    senior = _years(e["hire_date"], end) >= 10 or (e["birth_date"] and _years(e["birth_date"], end) >= 50)
    ent = cfg_int(conn, "leave_days_senior" if senior else "leave_days")
    if e["hire_date"][:4] == str(y):                    # pro rata in the hiring year
        ent = ent * (13 - int(e["hire_date"][5:7])) // 12
    taken = requested = casual = 0
    for a in conn.execute("SELECT * FROM hr_absence WHERE pernr=? AND substr(begda,1,4)=? AND status IN ('A','R')",
                          (e["pernr"], str(y))):
        if ABSENCE_TYPES.get(a["awart"], {}).get("quota") != "ANN":
            continue
        if a["status"] == "A":
            taken += a["days"]
            if a["awart"] == "CAS":
                casual += a["days"]
        else:
            requested += a["days"]
    return dict(year=y, entitlement=ent, taken=taken, requested=requested, remaining=ent - taken - requested,
                casual_taken=casual, casual_max=cfg_int(conn, "casual_days"))


@atomic
def request_absence(conn, pernr, awart, begda, endda, user, reason="", approve=False):
    """Absence (request). Annual and casual leave are checked against the quota."""
    e = _emp(conn, pernr)
    if e["status"] != "A":
        raise MMError("Employee %s has left" % pernr, "PG", "020")
    t = ABSENCE_TYPES.get((awart or "").upper())
    if not t:
        raise MMError("Absence type %s does not exist" % awart, "PG", "040")
    b, en = parse_date(begda), parse_date(endda or begda)
    if en < b:
        raise MMError("The end date is before the start date", "PG", "041")
    if b[:4] != en[:4]:
        raise MMError("Enter one absence per calendar year", "PG", "042")
    if b < e["hire_date"]:
        raise MMError("The absence starts before the hiring date", "PG", "043")
    if conn.execute("SELECT 1 FROM hr_absence WHERE pernr=? AND status IN ('A','R') AND begda<=? AND endda>=?",
                    (e["pernr"], en, b)).fetchone():
        raise MMError("There is already an absence in this period", "PG", "044")
    days = _workdays(b, en)
    if days == 0:
        raise MMError("The period contains no working day", "PG", "045")
    if t["quota"]:
        q = quota(conn, e["pernr"], b[:4])
        if days > q["remaining"]:
            raise MMError("Only %d leave day(s) left in %s (entitlement %d, taken %d, requested %d)"
                          % (q["remaining"], b[:4], q["entitlement"], q["taken"], q["requested"]), "PG", "046")
        if awart.upper() == "CAS" and q["casual_taken"] + days > q["casual_max"]:
            raise MMError("Casual leave is limited to %d days a year" % q["casual_max"], "PG", "047")
    cur = conn.execute("INSERT INTO hr_absence (pernr,awart,begda,endda,days,status,reason,created,created_by) "
                       "VALUES (?,?,?,?,?,?,?,?,?)", (e["pernr"], awart.upper(), b, en, days, "R", (reason or "")[:80],
                                                      now_ts(), user))
    if approve:
        decide_absence(conn, cur.lastrowid, True, user, _self_ok=True)
    return cur.lastrowid


@atomic
def decide_absence(conn, aid, approve, user, _self_ok=False):
    a = conn.execute("SELECT a.*, e.bname FROM hr_absence a JOIN hr_employee e USING (pernr) WHERE a.id=?",
                     (int(aid),)).fetchone()
    if not a or a["status"] != "R":
        raise MMError("Leave request %s is not open" % aid, "PG", "048")
    if not _self_ok and a["bname"] and a["bname"] == user:
        raise MMError("You cannot approve your own leave request", "PG", "049")
    conn.execute("UPDATE hr_absence SET status=?, decided_by=?, decided=? WHERE id=?",
                 ("A" if approve else "X", user, now_ts(), int(aid)))


@atomic
def cancel_absence(conn, aid, user):
    a = conn.execute("SELECT * FROM hr_absence WHERE id=?", (int(aid),)).fetchone()
    if not a or a["status"] not in ("A", "R"):
        raise MMError("Absence %s cannot be cancelled" % aid, "PG", "050")
    r = conn.execute("SELECT status FROM hr_payroll_run WHERE gjahr=? AND perio=?",
                     (int(a["begda"][:4]), int(a["begda"][5:7]))).fetchone()
    if r and r["status"] in ("POST", "PAID"):
        raise MMError("Payroll %s is already posted - the absence cannot be cancelled" % a["begda"][:7], "PG", "051")
    conn.execute("UPDATE hr_absence SET status='C', decided_by=?, decided=? WHERE id=?", (user, now_ts(), int(aid)))


def absences(conn, pernr=None, status=None, year=None):
    sql = ("SELECT a.*, e.name FROM hr_absence a JOIN hr_employee e USING (pernr) WHERE 1=1")
    p = []
    if pernr:
        sql += " AND a.pernr=?"
        p.append(pernr)
    if status:
        sql += " AND a.status=?"
        p.append(status)
    if year:
        sql += " AND substr(a.begda,1,4)=?"
        p.append(str(year))
    out = rows(conn.execute(sql + " ORDER BY a.begda DESC, a.id DESC", p))
    for r in out:
        r["type_text"] = ABSENCE_TYPES.get(r["awart"], {}).get("text", r["awart"])
    return out


@atomic
def add_overtime(conn, pernr, datum, ottype, hours, user):
    e = _emp(conn, pernr)
    if e["status"] != "A":
        raise MMError("Employee %s has left" % pernr, "PG", "020")
    if ottype not in OVERTIME_TYPES:
        raise MMError("Overtime type must be D (day), N (night) or R (rest day)", "PG", "060")
    from mm.util import parse_qty
    h = parse_qty(hours)
    if h > 12000:
        raise MMError("More than 12 overtime hours in one day are not allowed", "PG", "061")
    d = parse_date(datum)
    r = conn.execute("SELECT status FROM hr_payroll_run WHERE gjahr=? AND perio=?", (int(d[:4]), int(d[5:7]))).fetchone()
    if r and r["status"] in ("POST", "PAID"):
        raise MMError("Payroll %s is already posted" % d[:7], "PG", "051")
    cur = conn.execute("INSERT INTO hr_overtime (pernr,datum,ottype,hours,created,created_by) VALUES (?,?,?,?,?,?)",
                       (e["pernr"], d, ottype, h, now_ts(), user))
    return cur.lastrowid


def overtime(conn, pernr=None, month=None):
    sql, p = "SELECT o.*, e.name FROM hr_overtime o JOIN hr_employee e USING (pernr) WHERE 1=1", []
    if pernr:
        sql += " AND o.pernr=?"
        p.append(pernr)
    if month:
        sql += " AND substr(o.datum,1,7)=?"
        p.append(month)
    return rows(conn.execute(sql + " ORDER BY o.datum DESC", p))
