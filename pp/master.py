"""Production master data.

CS01/CS02/CS03  bill of material (component scrap, backflush, issue storage
                location, operation assignment); recursion check; status check
CS11/CS12       multi-level BOM explosion        CS15  where-used list
CR01/CR02/CR03  work center: cost center + activity type (costing), capacity
                (hours per shift, shifts, utilization), default control key
CA01/CA02/CA03  routing: operations with control key PP01 / PP02 (external:
                vendor, price, delivery days) / PP03 (auto goods receipt)
C223            production versions (validity, lot size range, consistency check)
SCAL            factory calendar (Friday off)
CM01            capacity load per work center and week
"""
import datetime
import math

from mm.db import rows, transaction
from mm.util import MMError, now_ts, parse_amount, parse_date, parse_qty

from .config import CONTROL_KEYS, WORKDAYS


# ------------------------------------------------------------------ calendar
def is_workday(d):
    return d.weekday() in WORKDAYS


def add_workdays(day, n):
    """day (iso) + n working days (n may be negative); n=0 moves to a workday."""
    d = datetime.date.fromisoformat(day)
    step = 1 if n >= 0 else -1
    while not is_workday(d):
        d += datetime.timedelta(days=step)
    for _ in range(abs(n)):
        d += datetime.timedelta(days=step)
        while not is_workday(d):
            d += datetime.timedelta(days=step)
    return d.isoformat()


def workdays_between(d1, d2):
    a, b = datetime.date.fromisoformat(d1), datetime.date.fromisoformat(d2)
    n = 0
    while a <= b:
        n += is_workday(a)
        a += datetime.timedelta(days=1)
    return n


def _log(conn, obj, key, tcode, user, items, ind="U"):
    from md.changes import log
    return log(conn, obj, key, tcode, user, items, ind)


# ------------------------------------------------------------------ BOM
def save_bom(conn, matnr, werks, basis, items, user="", tcode="CS01"):
    """items: [{idnrk, menge, ausch (scrap %), rgekz, lgort, vornr, postp}]"""
    matnr = (matnr or "").upper()
    b = parse_qty(basis)
    if not items:
        raise MMError("Enter at least one item", "29", "010")
    with transaction(conn):
        if not conn.execute("SELECT 1 FROM material_plant WHERE matnr=? AND werks=?",
                            (matnr, werks)).fetchone():
            raise MMError("Material %s is not maintained in plant %s" % (matnr, werks),
                          "29", "002")
        from md.checks import material as status_check
        status_check(conn, matnr, werks, "bom")
        old = {r["idnrk"]: r for r in conn.execute("SELECT * FROM bom WHERE matnr=? AND werks=?",
                                                   (matnr, werks))}
        conn.execute("DELETE FROM bom WHERE matnr=? AND werks=?", (matnr, werks))
        log = []
        for i, it in enumerate(items, start=1):
            comp = (it.get("idnrk") or "").upper()
            if comp == matnr:
                raise MMError("Item %d: component %s is the header material (recursion)"
                              % (i, comp), "29", "011")
            if not conn.execute("SELECT 1 FROM material_plant WHERE matnr=? AND werks=?",
                                (comp, werks)).fetchone():
                raise MMError("Item %d: component %s not maintained in plant %s"
                              % (i, comp, werks), "29", "001")
            status_check(conn, comp, werks, "bom")
            if matnr in [x["idnrk"] for x in explode(conn, comp, werks, "1")]:
                raise MMError("Item %d: component %s contains %s - recursive BOM"
                              % (i, comp, matnr), "29", "012")
            menge = parse_qty(it.get("menge"))
            ausch = int(round(float(it.get("ausch") or 0) * 100))
            if not 0 <= ausch < 10000:
                raise MMError("Component scrap must be between 0 and 99 %", "29", "013")
            lgort = (it.get("lgort") or "").upper()
            if lgort and not conn.execute("SELECT 1 FROM sloc WHERE werks=? AND lgort=?",
                                          (werks, lgort)).fetchone():
                raise MMError("Item %d: storage location %s does not exist" % (i, lgort),
                              "29", "014")
            conn.execute("INSERT INTO bom (matnr,werks,posnr,idnrk,menge,basis,ausch,rgekz,"
                         "lgort,vornr,postp) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                         (matnr, werks, i * 10, comp, menge, b, ausch,
                          1 if it.get("rgekz") in (1, "1", True, "X") else 0, lgort,
                          (it.get("vornr") or "").strip(), it.get("postp") or "L"))
            o = old.pop(comp, None)
            if not o:
                log.append(("STPO", "%s/%s" % (matnr, comp), "idnrk", "", comp))
            elif o["menge"] != menge:
                log.append(("STPO", "%s/%s" % (matnr, comp), "menge", o["menge"], menge))
        for comp in old:
            log.append(("STPO", "%s/%s" % (matnr, comp), "idnrk", comp, ""))
        _log(conn, "BOM", matnr, tcode, user, log, "I" if tcode == "CS01" else "U")


def bom(conn, matnr, werks):
    return rows(conn.execute(
        "SELECT b.*, m.maktx, m.meins, m.mtart FROM bom b JOIN material m ON m.matnr=b.idnrk "
        "WHERE b.matnr=? AND b.werks=? ORDER BY posnr", (matnr.upper(), werks)))


def explode(conn, matnr, werks, qty, level=1, path=None, out=None):
    """CS11/CS12: multi-level explosion. qty = header quantity (string)."""
    q = parse_qty(qty) if isinstance(qty, str) else qty
    out = [] if out is None else out
    path = path or [matnr]
    for b in conn.execute("SELECT b.*, m.maktx, m.meins, m.mtart, p.beskz, p.sobsl FROM bom b "
                          "JOIN material m ON m.matnr=b.idnrk LEFT JOIN material_plant p ON "
                          "p.matnr=b.idnrk AND p.werks=b.werks WHERE b.matnr=? AND b.werks=? "
                          "ORDER BY posnr", (matnr, werks)).fetchall():
        need = q * b["menge"] // b["basis"]
        need = need + need * (b["ausch"] or 0) // 10000
        out.append(dict(level=level, parent=matnr, posnr=b["posnr"], idnrk=b["idnrk"],
                        maktx=b["maktx"], meins=b["meins"], mtart=b["mtart"], menge=need,
                        ausch=b["ausch"], rgekz=b["rgekz"], beskz=b["beskz"],
                        sobsl=b["sobsl"], lgort=b["lgort"], vornr=b["vornr"]))
        if b["idnrk"] not in path:
            explode(conn, b["idnrk"], werks, need, level + 1, path + [b["idnrk"]], out)
    return out


def where_used(conn, idnrk, werks="1000"):
    return rows(conn.execute(
        "SELECT b.matnr, m.maktx, m.mtart, b.posnr, b.menge, b.basis, b.ausch FROM bom b "
        "JOIN material m ON m.matnr=b.matnr WHERE b.idnrk=? AND b.werks=? ORDER BY b.matnr",
        (idnrk.upper(), werks)))


def low_level_codes(conn, werks="1000"):
    """Lowest BOM level per material (0 = finished product) - MRP sequence."""
    llc = {}
    heads = [r[0] for r in conn.execute("SELECT DISTINCT matnr FROM bom WHERE werks=?", (werks,))]
    comps = {r[0] for r in conn.execute("SELECT DISTINCT idnrk FROM bom WHERE werks=?", (werks,))}
    for h in heads:
        if h not in comps:
            llc[h] = max(llc.get(h, 0), 0)
            for x in explode(conn, h, werks, 1000):
                llc[x["idnrk"]] = max(llc.get(x["idnrk"], 0), x["level"])
    return llc


# ------------------------------------------------------------------ work center
def save_work_center(conn, data, user="", tcode="CR01"):
    arbpl = (data.get("arbpl") or "").strip().upper()
    if not arbpl:
        raise MMError("Enter a work center", "CR", "001")
    werks = data.get("werks") or "1000"
    kostl = (data.get("kostl") or "").upper()
    lstar = (data.get("lstar") or "").upper()
    steus = (data.get("steus") or "PP01").upper()
    if steus not in CONTROL_KEYS:
        raise MMError("Control key %s does not exist" % steus, "CR", "010")
    kapaz = parse_qty(data.get("kapaz") or "8")
    ngrad = int(data.get("ngrad") or 85)
    shifts = int(data.get("shifts") or 1)
    if not (0 < ngrad <= 100) or not (1 <= shifts <= 3) or not (0 < kapaz <= 24000):
        raise MMError("Capacity: hours per shift 0-24, shifts 1-3, utilization 1-100 %",
                      "CR", "011")
    with transaction(conn):
        if tcode == "CR01" and conn.execute("SELECT 1 FROM work_center WHERE arbpl=?",
                                            (arbpl,)).fetchone():
            raise MMError("Work center %s already exists in plant %s" % (arbpl, werks),
                          "CR", "002")
        if not conn.execute("SELECT 1 FROM cost_center WHERE kostl=?", (kostl,)).fetchone():
            raise MMError("Cost center %s does not exist (costing view)" % kostl, "KI", "248")
        if not conn.execute("SELECT 1 FROM activity_type WHERE lstar=?", (lstar,)).fetchone():
            raise MMError("Activity type %s does not exist (KL01)" % lstar, "KL", "001")
        old = conn.execute("SELECT * FROM work_center WHERE arbpl=?", (arbpl,)).fetchone()
        conn.execute("INSERT OR REPLACE INTO work_center (arbpl,werks,ktext,kostl,lstar,kapaz,"
                     "ngrad,shifts,verwe,steus,veran) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                     (arbpl, werks, data.get("ktext") or arbpl, kostl, lstar, kapaz, ngrad,
                      shifts, data.get("verwe") or "0001", steus, data.get("veran") or ""))
        if old:
            items = [("CRHD", arbpl, f, old[f], n) for f, n in
                     (("kostl", kostl), ("lstar", lstar), ("kapaz", kapaz), ("ngrad", ngrad),
                      ("shifts", shifts)) if str(old[f]) != str(n)]
            _log(conn, "WORKCENTER", arbpl, tcode, user, items)
        else:
            _log(conn, "WORKCENTER", arbpl, tcode, user,
                 [("CRHD", arbpl, "arbpl", "", arbpl)], "I")


def work_centers(conn):
    out = rows(conn.execute("SELECT w.*, c.name AS cc_name, a.ktext AS atext FROM work_center w "
                            "LEFT JOIN cost_center c ON c.kostl=w.kostl LEFT JOIN activity_type a "
                            "ON a.lstar=w.lstar ORDER BY arbpl"))
    for w in out:
        w["avail_day"] = (w["kapaz"] or 0) * (w["shifts"] or 1) * (w["ngrad"] or 100) // 100
    return out


# ------------------------------------------------------------------ routing
def save_routing(conn, matnr, werks, basis, ops, user="", tcode="CA01"):
    """ops: [{vornr, arbpl, steus, ltxa1, vgw (per base qty), vgw_setup, lifnr,
    preis, plifz, ekgrp}]"""
    matnr = (matnr or "").upper()
    b = parse_qty(basis)
    if not ops:
        raise MMError("Enter at least one operation", "CP", "001")
    with transaction(conn):
        if not conn.execute("SELECT 1 FROM material_plant WHERE matnr=? AND werks=?",
                            (matnr, werks)).fetchone():
            raise MMError("Material %s is not maintained in plant %s" % (matnr, werks),
                          "CP", "002")
        conn.execute("DELETE FROM routing WHERE matnr=? AND werks=?", (matnr, werks))
        seen = set()
        last = len(ops) - 1
        for i, o in enumerate(ops):
            vornr = str(o.get("vornr") or "%04d" % ((i + 1) * 10)).zfill(4)
            if vornr in seen:
                raise MMError("Operation %s exists twice" % vornr, "CP", "003")
            seen.add(vornr)
            steus = (o.get("steus") or "PP01").upper()
            ck = CONTROL_KEYS.get(steus)
            if not ck:
                raise MMError("Operation %s: control key %s does not exist" % (vornr, steus),
                              "CP", "004")
            arbpl = (o.get("arbpl") or "").upper()
            if not ck["external"] and not conn.execute("SELECT 1 FROM work_center WHERE arbpl=?",
                                                       (arbpl,)).fetchone():
                raise MMError("Operation %s: work center %s does not exist" % (vornr, arbpl),
                              "CR", "001")
            if ck["auto_gr"] and i != last:
                raise MMError("Operation %s: control key PP03 (automatic goods receipt) is only "
                              "allowed for the last operation" % vornr, "CP", "005")
            lifnr = (o.get("lifnr") or "").upper() or None
            preis = parse_amount(o.get("preis") or "0", allow_zero=True)
            if ck["external"]:
                v = conn.execute("SELECT sperm FROM vendor WHERE lifnr=?", (lifnr,)).fetchone()
                if not v:
                    raise MMError("Operation %s: external processing needs a vendor" % vornr,
                                  "CP", "006")
                if not preis:
                    raise MMError("Operation %s: enter the price for external processing"
                                  % vornr, "CP", "007")
            vgw = parse_qty(o.get("vgw") or "0", allow_zero=True)
            if not ck["external"] and vgw <= 0:
                raise MMError("Operation %s: enter a standard value (hours)" % vornr, "CP", "008")
            conn.execute("INSERT INTO routing (matnr,werks,vornr,arbpl,ltxa1,vgw,basis,steus,"
                         "vgw_setup,lifnr,preis,plifz,ekgrp) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                         (matnr, werks, vornr, arbpl or None, o.get("ltxa1") or "", vgw, b, steus,
                          parse_qty(o.get("vgw_setup") or "0", allow_zero=True), lifnr, preis,
                          int(o.get("plifz") or 0), o.get("ekgrp") or "003"))
        _log(conn, "ROUTING", matnr, tcode, user,
             [("PLPO", "%s/%s" % (matnr, v), "vornr", "", v) for v in sorted(seen)],
             "I" if tcode == "CA01" else "U")


def routing(conn, matnr, werks):
    return rows(conn.execute(
        "SELECT r.*, w.ktext AS wtext, w.kostl, w.lstar, v.name AS vname FROM routing r "
        "LEFT JOIN work_center w ON w.arbpl=r.arbpl LEFT JOIN vendor v ON v.lifnr=r.lifnr "
        "WHERE r.matnr=? AND r.werks=? ORDER BY vornr", (matnr.upper(), werks)))


# ------------------------------------------------------------------ C223
def save_version(conn, matnr, werks, verid, text, adatu, bdatu, bstmi="0", bstma="0",
                 lock=False, user=""):
    matnr = matnr.upper()
    with transaction(conn):
        issues = check_version(conn, matnr, werks)
        if issues:
            raise MMError("Production version %s inconsistent: %s" % (verid, "; ".join(issues)),
                          "C2", "001")
        a, b = parse_date(adatu), parse_date(bdatu)
        if b < a:
            raise MMError("Valid-to date is before valid-from date", "C2", "002")
        mi, ma = parse_qty(bstmi or "0", allow_zero=True), parse_qty(bstma or "0", allow_zero=True)
        if ma and mi > ma:
            raise MMError("Minimum lot size is greater than maximum lot size", "C2", "003")
        conn.execute("INSERT OR REPLACE INTO pp_prodver VALUES (?,?,?,?,?,?,?,?,?,?)",
                     (matnr, werks, verid, text, a, b, mi, ma, "01", 1 if lock else 0))
        _log(conn, "PRODVER", matnr, "C223", user, [("MKAL", "%s/%s" % (matnr, verid), "verid",
                                                     "", verid)], "I")


def check_version(conn, matnr, werks):
    issues = []
    mp = conn.execute("SELECT sobsl FROM material_plant WHERE matnr=? AND werks=?",
                      (matnr, werks)).fetchone()
    if not conn.execute("SELECT 1 FROM bom WHERE matnr=? AND werks=?", (matnr, werks)).fetchone():
        issues.append("no BOM")
    if not conn.execute("SELECT 1 FROM routing WHERE matnr=? AND werks=?",
                        (matnr, werks)).fetchone() and not (mp and mp["sobsl"] == "30"):
        issues.append("no routing")
    return issues


def select_version(conn, matnr, werks, qty, day):
    """Version valid on the date and for the lot size (MRP / CO01)."""
    for v in conn.execute("SELECT * FROM pp_prodver WHERE matnr=? AND werks=? AND lock=0 "
                          "AND adatu<=? AND bdatu>=? ORDER BY verid", (matnr, werks, day, day)):
        if (not v["bstmi"] or qty >= v["bstmi"]) and (not v["bstma"] or qty <= v["bstma"]):
            return v["verid"]
    return None


# ------------------------------------------------------------------ CM01
def capacity(conn, d1, d2, arbpl=None):
    """Capacity load per work center and week: requirement of open operations
    (remaining standard hours spread over their scheduled dates) vs available."""
    wcs = {w["arbpl"]: w for w in work_centers(conn)}
    out = {}
    start = datetime.date.fromisoformat(d1)
    end = datetime.date.fromisoformat(d2)
    d = start
    while d <= end:
        wk = (d - datetime.timedelta(days=d.weekday())).isoformat()
        for k, w in wcs.items():
            if arbpl and k != arbpl:
                continue
            r = out.setdefault((k, wk), dict(arbpl=k, week=wk, ktext=w["ktext"], avail=0, req=0))
            if is_workday(d):
                r["avail"] += w["avail_day"]
        d += datetime.timedelta(days=1)
    for o in conn.execute("SELECT p.*, o.stat FROM pp_oper p JOIN orders o ON o.aufnr=p.aufnr "
                          "WHERE o.stat IN ('CRTD','REL') AND p.status NOT IN ('CNF') AND "
                          "p.steus<>'PP02'"):
        if arbpl and o["arbpl"] != arbpl or o["arbpl"] not in wcs:
            continue
        rem = max(o["vgw"] + (o["vgw_setup"] if not o["ism"] else 0) - o["ism"], 0)
        days = [x for x in _days(o["ssavd"], o["ssedd"]) if d1 <= x <= d2]
        if not days or not rem:
            continue
        share = rem // len(days)
        for x in days:
            dd = datetime.date.fromisoformat(x)
            wk = (dd - datetime.timedelta(days=dd.weekday())).isoformat()
            if (o["arbpl"], wk) in out:
                out[(o["arbpl"], wk)]["req"] += share
    res = sorted(out.values(), key=lambda r: (r["arbpl"], r["week"]))
    for r in res:
        r["load"] = round(100.0 * r["req"] / r["avail"], 1) if r["avail"] else 0.0
    return res


def _days(a, b):
    if not a or not b:
        return []
    x, y = datetime.date.fromisoformat(a), datetime.date.fromisoformat(b)
    out = []
    while x <= y:
        if is_workday(x):
            out.append(x.isoformat())
        x += datetime.timedelta(days=1)
    return out or [a]


def op_duration_days(conn, arbpl, hours_milli):
    w = conn.execute("SELECT * FROM work_center WHERE arbpl=?", (arbpl,)).fetchone()
    per_day = (w["kapaz"] or 8000) * (w["shifts"] or 1) * (w["ngrad"] or 100) // 100 if w else 8000
    return max(1, math.ceil(hours_milli / per_day)) if hours_milli else 1


def now():
    return now_ts()
