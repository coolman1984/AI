"""Shop-floor execution: stations, serial numbers, bookings with route enforcement and operator
certification, the repair loop, genealogy, shipping link, andon calls, SPC measurements and the
hand-over of finished units to the production order confirmation (CO11N)."""
import datetime

from mm import util as clock
from mm.db import transaction
from mm.util import MMError, parse_int

KINDS = {"OP": "Operation", "TEST": "Test / inspection", "REPAIR": "Repair"}
RESULTS = {"OK": "Passed", "NG": "Failed (defect)", "REPAIRED": "Repaired", "SCRAP": "Scrapped"}
DEFECTS = {"ASSY": "Assembly error / missing part", "DIM": "Dimension out of tolerance", "SURF": "Surface / scratches",
           "PAINT": "Paint / coating defect", "WELD": "Welding / joining defect", "FUNC": "Function test failed",
           "ELEC": "Electrical fault", "LABEL": "Label / marking wrong", "PACK": "Packaging damaged", "MAT": "Material defect"}
ANDON = {"MAT": "Material missing", "QUAL": "Quality problem", "MAINT": "Machine / maintenance", "HELP": "Help / supervisor",
         "SAFE": "Safety"}
MAX_REPAIRS = 3


def _ts(t=None):
    return (t or clock.now()).replace(microsecond=0).isoformat(sep=" ")


# ------------------------------------------------------------------ master data
def save_station(conn, data):
    st = (data.get("station") or "").strip().upper()
    if not st:
        raise MMError("Enter the station code", "SF", "901")
    wc = conn.execute("SELECT arbpl FROM work_center WHERE arbpl=?", ((data.get("arbpl") or "").upper(),)).fetchone()
    if not wc:
        raise MMError("Work center (line) %s does not exist" % data.get("arbpl"), "SF", "902")
    kind = (data.get("kind") or "OP").upper()
    if kind not in KINDS:
        raise MMError("Station kind must be OP, TEST or REPAIR", "SF", "903")
    vornr = str(data.get("vornr") or "").strip()
    if kind != "REPAIR" and not vornr:
        raise MMError("Enter the operation (e.g. 0010) the station performs", "SF", "904")
    skill = (data.get("skill") or "").strip().upper()
    if skill and not conn.execute("SELECT 1 FROM hr_skill WHERE code=?", (skill,)).fetchone():
        raise MMError("Skill %s does not exist (HR skills catalog)" % skill, "SF", "905")
    with transaction(conn):
        conn.execute("INSERT OR REPLACE INTO mes_station (station, arbpl, vornr, kind, text, skill, ct_std, opps, active) "
                     "VALUES (?,?,?,?,?,?,?,?,?)",
                     (st[:12], wc["arbpl"], vornr.zfill(4) if vornr else None, kind, (data.get("text") or "")[:60], skill or None,
                      parse_int(data.get("ct_std") or 0, "standard cycle time", 0, 86400),
                      parse_int(data.get("opps") or 1, "defect opportunities", 1, 1000), 0 if data.get("active") is False else 1))
    return {"message": "Station %s saved" % st}


def stations(conn):
    return [dict(r) for r in conn.execute("SELECT s.*, w.ktext line_text FROM mes_station s LEFT JOIN work_center w "
                                          "ON w.arbpl=s.arbpl ORDER BY s.arbpl, s.vornr, s.station")]


def _station(conn, st):
    s = conn.execute("SELECT * FROM mes_station WHERE station=? AND active=1", ((st or "").upper(),)).fetchone()
    if not s:
        raise MMError("Station %s does not exist or is inactive" % st, "SF", "906")
    return s


def route(conn, matnr, werks):
    """operation sequence of the material (routing), external operations excluded"""
    return [dict(r) for r in conn.execute(
        "SELECT vornr, arbpl, ltxa1, vgw, basis FROM routing WHERE matnr=? AND werks=? AND arbpl IS NOT NULL ORDER BY vornr",
        (matnr, werks))]


# ------------------------------------------------------------------ serial numbers
def release_units(conn, aufnr, count, user, prefix=None):
    o = conn.execute("SELECT * FROM orders WHERE aufnr=?", (str(aufnr),)).fetchone()
    if not o:
        raise MMError("Order %s does not exist" % aufnr, "SF", "907")
    if o["stat"] != "REL":
        raise MMError("Order %s is not released (status %s)" % (aufnr, o["stat"]), "SF", "908")
    r = route(conn, o["matnr"], o["werks"])
    if not r:
        raise MMError("Material %s has no routing - units cannot be tracked" % o["matnr"], "SF", "909")
    n = parse_int(count, "number of units", 1, 100000)
    have = conn.execute("SELECT COUNT(*) FROM mes_unit WHERE aufnr=?", (o["aufnr"],)).fetchone()[0]
    if have + n > o["gamng"] // 1000:
        raise MMError("Order %s is for %d units - %d serial numbers exist already" % (o["aufnr"], o["gamng"] // 1000, have),
                      "SF", "910")
    pre = (prefix or "%s-" % o["aufnr"]).strip()
    made = []
    with transaction(conn):
        for i in range(have + 1, have + n + 1):
            sn = "%s%04d" % (pre, i)
            conn.execute("INSERT INTO mes_unit (serial, aufnr, matnr, werks, status, next_vornr, created) VALUES (?,?,?,?,?,?,?)",
                         (sn, o["aufnr"], o["matnr"], o["werks"], "WIP", r[0]["vornr"], _ts()))
            made.append(sn)
    return {"serials": made, "message": "%d serial numbers released for order %s (%s ... %s)" % (n, o["aufnr"], made[0], made[-1])}


def unit(conn, serial):
    u = conn.execute("SELECT * FROM mes_unit WHERE serial=?", ((serial or "").strip().upper(),)).fetchone()
    if not u:
        raise MMError("Serial number %s does not exist" % serial, "SF", "911")
    d = dict(u)
    d["route"] = route(conn, u["matnr"], u["werks"])
    d["events"] = [dict(e) for e in conn.execute("SELECT * FROM mes_event WHERE serial=? ORDER BY id", (u["serial"],))]
    d["components"] = [dict(g) for g in conn.execute("SELECT * FROM mes_genealogy WHERE serial=? ORDER BY id", (u["serial"],))]
    return d


def units(conn, aufnr=None, status=None):
    q, a = "SELECT * FROM mes_unit WHERE 1=1", []
    if aufnr:
        q += " AND aufnr=?"
        a.append(str(aufnr))
    if status:
        q += " AND status=?"
        a.append(status)
    return [dict(r) for r in conn.execute(q + " ORDER BY serial", a)]


# ------------------------------------------------------------------ booking at a station
def book(conn, serial, station, result, operator, user, defect=None, cycle_sec=None, components=None, note="", at=None):
    """one booking with the shop-floor rules:
    - the unit must be in WIP at its next operation (no skipping, no double booking) or in REPAIR at a repair station
    - the operator must be an active employee certified for the station's skill
    - NG needs a defect code and sends the unit to repair; REPAIRED sends it back to the failed operation
    - after MAX_REPAIRS repairs the unit must be scrapped; OK at the last operation finishes the unit"""
    from hr.skills import certified
    s = _station(conn, station)
    u = conn.execute("SELECT * FROM mes_unit WHERE serial=?", ((serial or "").strip().upper(),)).fetchone()
    if not u:
        raise MMError("Serial number %s does not exist" % serial, "SF", "911")
    result = (result or "").upper()
    if result not in RESULTS:
        raise MMError("Result must be OK, NG, REPAIRED or SCRAP", "SF", "912")
    t = at or clock.now()
    day = t.date().isoformat()
    why = certified(conn, operator, s["skill"], day)
    if why:
        raise MMError("%s - booking refused" % why, "SF", "913")
    if u["status"] in ("DONE", "SCRAP"):
        raise MMError("Unit %s is already %s" % (u["serial"], "finished" if u["status"] == "DONE" else "scrapped"), "SF", "914")
    r = route(conn, u["matnr"], u["werks"])
    ops = [x["vornr"] for x in r]
    if s["kind"] == "REPAIR":
        if u["status"] != "REPAIR":
            raise MMError("Unit %s is not waiting for repair" % u["serial"], "SF", "915")
        if result not in ("REPAIRED", "SCRAP"):
            raise MMError("At a repair station the result is REPAIRED or SCRAP", "SF", "916")
        if result == "REPAIRED" and u["repairs"] + 1 > MAX_REPAIRS:
            raise MMError("Unit %s was repaired %d times - scrap it" % (u["serial"], u["repairs"]), "SF", "917")
        vornr = u["next_vornr"]
    else:
        if u["status"] == "REPAIR":
            raise MMError("Unit %s failed and must go to repair first" % u["serial"], "SF", "918")
        if s["vornr"] != u["next_vornr"]:
            exp = next((x for x in r if x["vornr"] == u["next_vornr"]), {})
            raise MMError("Wrong station: unit %s needs operation %s (%s) next, this station does %s" % (
                u["serial"], u["next_vornr"], exp.get("ltxa1", ""), s["vornr"]), "SF", "919")
        if s["arbpl"] != next((x["arbpl"] for x in r if x["vornr"] == s["vornr"]), s["arbpl"]):
            raise MMError("Station %s is not on the line of operation %s" % (s["station"], s["vornr"]), "SF", "920")
        if result == "REPAIRED":
            raise MMError("REPAIRED is booked at a repair station", "SF", "916")
        vornr = s["vornr"]
    defect = (defect or "").upper() or None
    if result == "NG" and defect not in DEFECTS:
        raise MMError("Choose the defect code: %s" % ", ".join(DEFECTS), "SF", "921")
    if result == "SCRAP" and not defect:
        defect = "MAT"
    attempt = conn.execute("SELECT COUNT(*) FROM mes_event WHERE serial=? AND vornr=? AND result IN ('OK','NG')",
                           (u["serial"], vornr)).fetchone()[0] + 1
    comps = []
    for c in components or []:
        if not (c.get("matnr") and c.get("lot")):
            continue
        if not conn.execute("SELECT 1 FROM material WHERE matnr=?", (c["matnr"].upper(),)).fetchone():
            raise MMError("Component %s does not exist" % c["matnr"], "SF", "922")
        comps.append((c["matnr"].upper(), str(c["lot"]).strip().upper()[:30], int(round(float(c.get("qty") or 1) * 1000))))
    status, nxt, fin, rep = u["status"], u["next_vornr"], None, u["repairs"]
    if result == "OK":
        i = ops.index(vornr)
        if i + 1 < len(ops):
            nxt = ops[i + 1]
        else:
            status, nxt, fin = "DONE", None, _ts(t)
    elif result == "NG":
        status = "REPAIR"
    elif result == "REPAIRED":
        status, rep = "WIP", rep + 1
    else:
        status, fin = "SCRAP", _ts(t)
    with transaction(conn):
        conn.execute("INSERT INTO mes_event (serial, aufnr, matnr, arbpl, vornr, station, operator, ts, day, result, attempt, "
                     "defect, cycle_sec, note, usnam) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (u["serial"], u["aufnr"], u["matnr"], s["arbpl"], vornr, s["station"], str(operator), _ts(t), day, result,
                      attempt if result in ("OK", "NG") else 0, defect,
                      parse_int(cycle_sec, "cycle time", 0, 86400) if cycle_sec not in (None, "") else None, (note or "")[:200], user))
        for m, lot, q in comps:
            conn.execute("INSERT INTO mes_genealogy (serial, matnr, lot, qty, vornr, station, ts, usnam) VALUES (?,?,?,?,?,?,?,?)",
                         (u["serial"], m, lot, q, vornr, s["station"], _ts(t), user))
        conn.execute("UPDATE mes_unit SET status=?, next_vornr=?, repairs=?, finished=? WHERE serial=?",
                     (status, nxt, rep, fin, u["serial"]))
    txt = {"DONE": "finished ✓", "REPAIR": "to repair", "SCRAP": "scrapped"}.get(status, "next operation %s" % nxt)
    return {"serial": u["serial"], "status": status, "next_vornr": nxt,
            "message": "%s %s at %s - %s" % (u["serial"], RESULTS[result].lower(), s["station"], txt)}


def confirm_to_order(conn, aufnr, user):
    """hand finished / scrapped units over to the production order: final confirmation quantity (CO11N)"""
    from pp import order as ppo
    o = conn.execute("SELECT * FROM orders WHERE aufnr=?", (str(aufnr),)).fetchone()
    if not o:
        raise MMError("Order %s does not exist" % aufnr, "SF", "907")
    done = [r["serial"] for r in conn.execute("SELECT serial FROM mes_unit WHERE aufnr=? AND status='DONE' AND confirmed=0", (o["aufnr"],))]
    scrap = [r["serial"] for r in conn.execute("SELECT serial FROM mes_unit WHERE aufnr=? AND status='SCRAP' AND confirmed=0",
                                               (o["aufnr"],))]
    if not done and not scrap:
        raise MMError("No finished or scrapped units of order %s to confirm" % o["aufnr"], "SF", "923")
    sns = done + scrap
    ops = [r["vornr"] for r in conn.execute("SELECT vornr, steus FROM pp_oper WHERE aufnr=? AND status<>'CNF' ORDER BY vornr",
                                             (o["aufnr"],)) if not ppo.CONTROL_KEYS.get(r["steus"], {}).get("external")]
    if not ops:
        raise MMError("Order %s has no open operation to confirm" % o["aufnr"], "SF", "924")
    mark = ",".join("?" * len(sns))
    confs = []
    for v in ops:     # per operation: units passed / scrapped there, minus what is already confirmed (also by hand in CO11N)
        q = ("SELECT COUNT(DISTINCT e.serial) FROM mes_event e JOIN mes_unit u ON u.serial=e.serial WHERE e.vornr=? AND e.result=? "
             "AND u.aufnr=? AND (u.confirmed=1 OR u.serial IN (%s))" % mark)
        op = conn.execute("SELECT lmnga, xmnga FROM pp_oper WHERE aufnr=? AND vornr=?", (o["aufnr"], v)).fetchone()
        y = max(0, conn.execute(q, [v, "OK", o["aufnr"]] + sns).fetchone()[0] - (op["lmnga"] or 0) // 1000)
        x = max(0, conn.execute(q, [v, "SCRAP", o["aufnr"]] + sns).fetchone()[0] - (op["xmnga"] or 0) // 1000)
        if y or x:
            confs.append(ppo.confirm(conn, o["aufnr"], v, str(y), str(x), user=user, final=False, grund="01" if x else None))
    with transaction(conn):
        for sn in sns:
            conn.execute("UPDATE mes_unit SET confirmed=1 WHERE serial=?", (sn,))
    return {"yield": len(done), "scrap": len(scrap), "confirmations": confs,
            "message": "Order %s: %d good and %d scrapped units confirmed (%s)" % (o["aufnr"], len(done), len(scrap), ", ".join(ops))}


def ship(conn, serials, vbeln, user):
    """link finished units to the outbound delivery (forward traceability up to the customer)"""
    d = conn.execute("SELECT vbeln, kunnr FROM sd_likp WHERE vbeln=?", (str(vbeln),)).fetchone()
    if not d:
        raise MMError("Delivery %s does not exist" % vbeln, "SF", "925")
    sns = [s.strip().upper() for s in (serials if isinstance(serials, list) else str(serials).split(",")) if s.strip()]
    with transaction(conn):
        for sn in sns:
            u = conn.execute("SELECT status FROM mes_unit WHERE serial=?", (sn,)).fetchone()
            if not u or u["status"] != "DONE":
                raise MMError("Unit %s is not finished - it cannot be shipped" % sn, "SF", "926")
            conn.execute("UPDATE mes_unit SET vbeln=?, kunnr=?, shipped=? WHERE serial=?", (d["vbeln"], d["kunnr"], _ts(), sn))
    return {"message": "%d units linked to delivery %s" % (len(sns), d["vbeln"])}


# ------------------------------------------------------------------ genealogy
def trace(conn, key):
    """backward from a serial (route history + components) or forward from a component lot (units, orders, customers)"""
    key = (key or "").strip().upper()
    if not key:
        raise MMError("Enter a serial number or a component lot", "SF", "927")
    if conn.execute("SELECT 1 FROM mes_unit WHERE serial=?", (key,)).fetchone():
        u = unit(conn, key)
        cust = conn.execute("SELECT name FROM customer WHERE kunnr=?", (u["kunnr"],)).fetchone() if u["kunnr"] else None
        return {"direction": "backward", "serial": key, "unit": u, "customer": cust["name"] if cust else None}
    used = [dict(r) for r in conn.execute(
        "SELECT g.serial, g.matnr comp, g.qty, g.ts, u.aufnr, u.matnr, u.status, u.vbeln, u.kunnr, c.name customer "
        "FROM mes_genealogy g JOIN mes_unit u ON u.serial=g.serial LEFT JOIN customer c ON c.kunnr=u.kunnr WHERE g.lot=? "
        "ORDER BY g.serial", (key,))]
    if not used:
        raise MMError("%s is neither a serial number nor a component lot used in production" % key, "SF", "928")
    return {"direction": "forward", "lot": key, "units": used, "orders": sorted({x["aufnr"] for x in used}),
            "customers": sorted({x["customer"] for x in used if x["customer"]}),
            "shipped": sum(1 for x in used if x["vbeln"]), "in_house": sum(1 for x in used if not x["vbeln"])}


# ------------------------------------------------------------------ andon
def andon_open(conn, arbpl, kind, text, user, station=None, at=None):
    kind = (kind or "").upper()
    if kind not in ANDON:
        raise MMError("Andon type must be one of %s" % ", ".join(ANDON), "SF", "929")
    if not conn.execute("SELECT 1 FROM work_center WHERE arbpl=?", ((arbpl or "").upper(),)).fetchone():
        raise MMError("Line %s does not exist" % arbpl, "SF", "902")
    with transaction(conn):
        aid = conn.execute("INSERT INTO mes_andon (arbpl, station, kind, text, opened, opened_by) VALUES (?,?,?,?,?,?)",
                           (arbpl.upper(), (station or "").upper() or None, kind, (text or ANDON[kind])[:200], _ts(at), user)).lastrowid
    return {"id": aid, "message": "Andon %d: %s on %s" % (aid, ANDON[kind], arbpl.upper())}


def andon_step(conn, aid, step, user, resolution="", at=None):
    a = conn.execute("SELECT * FROM mes_andon WHERE id=?", (parse_int(aid, "andon call"),)).fetchone()
    if not a:
        raise MMError("Andon call %s does not exist" % aid, "SF", "930")
    with transaction(conn):
        if step == "ack":
            if a["status"] != "OPEN":
                raise MMError("Andon call %s is already %s" % (a["id"], a["status"].lower()), "SF", "931")
            conn.execute("UPDATE mes_andon SET ack=?, ack_by=?, status='ACK' WHERE id=?", (_ts(at), user, a["id"]))
        else:
            if a["status"] == "CLOSED":
                raise MMError("Andon call %s is already closed" % a["id"], "SF", "931")
            if not (resolution or "").strip():
                raise MMError("Write what was done to solve the problem", "SF", "932")
            conn.execute("UPDATE mes_andon SET ack=COALESCE(ack, ?), ack_by=COALESCE(ack_by, ?), closed=?, closed_by=?, "
                         "resolution=?, status='CLOSED' WHERE id=?", (_ts(at), user, _ts(at), user, resolution.strip()[:300], a["id"]))
    return {"message": "Andon call %d %s" % (a["id"], "acknowledged" if step == "ack" else "closed")}


def _mins(a, b):
    if not (a and b):
        return None
    return round((datetime.datetime.fromisoformat(b) - datetime.datetime.fromisoformat(a)).total_seconds() / 60.0, 1)


def andon_board(conn, d1=None, d2=None):
    d2 = d2 or clock.today().isoformat()
    d1 = d1 or (datetime.date.fromisoformat(d2) - datetime.timedelta(days=30)).isoformat()
    now = _ts()
    rows = []
    for a in conn.execute("SELECT * FROM mes_andon WHERE status<>'CLOSED' OR substr(opened,1,10) BETWEEN ? AND ? "
                          "ORDER BY status='CLOSED', opened DESC", (d1, d2)):
        rows.append(dict(a, kind_text=ANDON.get(a["kind"], a["kind"]), respond_min=_mins(a["opened"], a["ack"]),
                         resolve_min=_mins(a["opened"], a["closed"]), open_min=_mins(a["opened"], now) if a["status"] != "CLOSED" else None))
    closed = [r for r in rows if r["status"] == "CLOSED" and d1 <= r["opened"][:10] <= d2]
    by = {}
    for r in closed:
        b = by.setdefault(r["kind"], dict(kind=r["kind"], text=r["kind_text"], calls=0, respond=[], resolve=[]))
        b["calls"] += 1
        b["respond"].append(r["respond_min"] or 0)
        b["resolve"].append(r["resolve_min"] or 0)
    kinds = [dict(kind=b["kind"], text=b["text"], calls=b["calls"], avg_respond_min=round(sum(b["respond"]) / b["calls"], 1),
                  avg_resolve_min=round(sum(b["resolve"]) / b["calls"], 1)) for b in by.values()]
    return {"open": [r for r in rows if r["status"] != "CLOSED"], "closed": closed, "by_kind": sorted(kinds, key=lambda x: -x["calls"]),
            "kinds": ANDON, "period": [d1, d2]}


# ------------------------------------------------------------------ SPC
A2 = {2: 1.880, 3: 1.023, 4: 0.729, 5: 0.577, 6: 0.483, 7: 0.419, 8: 0.373, 9: 0.337, 10: 0.308}
D3 = {2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0.076, 8: 0.136, 9: 0.184, 10: 0.223}
D4 = {2: 3.267, 3: 2.574, 4: 2.282, 5: 2.114, 6: 2.004, 7: 1.924, 8: 1.864, 9: 1.816, 10: 1.777}
D2 = {2: 1.128, 3: 1.693, 4: 2.059, 5: 2.326, 6: 2.534, 7: 2.704, 8: 2.847, 9: 2.970, 10: 3.078}


def save_char(conn, data):
    code = (data.get("code") or "").strip().upper()
    if not code or not (data.get("text") or "").strip():
        raise MMError("Enter code and text of the characteristic", "SF", "933")
    try:
        lsl, usl = float(data["lsl"]), float(data["usl"])
        target = float(data.get("target") or (lsl + usl) / 2)
    except (KeyError, TypeError, ValueError):
        raise MMError("Enter lower and upper specification limits as numbers", "SF", "934")
    if lsl >= usl:
        raise MMError("The lower limit must be below the upper limit", "SF", "935")
    n = parse_int(data.get("n") or 5, "subgroup size", 2, 10)
    with transaction(conn):
        conn.execute("INSERT OR REPLACE INTO mes_char (code, text, station, unit, lsl, usl, target, n) VALUES (?,?,?,?,?,?,?,?)",
                     (code[:12], data["text"].strip()[:60], (data.get("station") or "").upper() or None, (data.get("unit") or "")[:10],
                      lsl, usl, target, n))
    return {"message": "Characteristic %s saved" % code}


def measure(conn, code, value, user, serial=None, station=None, operator=None, at=None):
    c = conn.execute("SELECT * FROM mes_char WHERE code=?", ((code or "").upper(),)).fetchone()
    if not c:
        raise MMError("Characteristic %s does not exist" % code, "SF", "936")
    try:
        v = float(str(value).replace(",", "."))
    except ValueError:
        raise MMError("Enter the measured value as a number", "SF", "937")
    t = at or clock.now()
    with transaction(conn):
        conn.execute("INSERT INTO mes_measure (code, value, serial, station, operator, ts, day) VALUES (?,?,?,?,?,?,?)",
                     (c["code"], v, (serial or "").upper() or None, station or c["station"], operator or user, _ts(t), t.date().isoformat()))
    out = not (c["lsl"] <= v <= c["usl"])
    msg = ("⚠️ %s = %s is OUT of specification (%s .. %s)" % (c["code"], v, c["lsl"], c["usl"]) if out
           else "%s = %s recorded" % (c["code"], v))
    return {"out_of_spec": out, "message": msg}


def spc(conn, code, last=25):
    """X-bar / R chart of the last `last` subgroups, process capability and the run rules"""
    c = conn.execute("SELECT * FROM mes_char WHERE code=?", ((code or "").upper(),)).fetchone()
    if not c:
        raise MMError("Characteristic %s does not exist" % code, "SF", "936")
    n = c["n"]
    vals = [dict(r) for r in conn.execute("SELECT value, ts FROM mes_measure WHERE code=? ORDER BY ts, id", (c["code"],))]
    groups = [vals[i:i + n] for i in range(0, len(vals) - len(vals) % n, n)][-parse_int(last, "subgroups", 2, 500):]
    if len(groups) < 2:
        return {"char": dict(c), "groups": [], "enough": False, "measurements": len(vals),
                "note": "At least 2 complete subgroups of %d measurements are needed" % n}
    pts = [dict(ts=g[-1]["ts"], xbar=sum(x["value"] for x in g) / n, r=max(x["value"] for x in g) - min(x["value"] for x in g))
           for g in groups]
    xbb = sum(p["xbar"] for p in pts) / len(pts)
    rb = sum(p["r"] for p in pts) / len(pts)
    ucl, lcl = xbb + A2[n] * rb, xbb - A2[n] * rb
    sigma = rb / D2[n] if rb else 0.0
    cp = (c["usl"] - c["lsl"]) / (6 * sigma) if sigma else None
    cpk = min(c["usl"] - xbb, xbb - c["lsl"]) / (3 * sigma) if sigma else None
    rules = []
    for i, p in enumerate(pts):
        if p["xbar"] > ucl or p["xbar"] < lcl:
            rules.append(dict(i=i, rule=1, text="Point outside the control limits"))
        if i >= 7 and (all(q["xbar"] > xbb for q in pts[i - 7:i + 1]) or all(q["xbar"] < xbb for q in pts[i - 7:i + 1])):
            rules.append(dict(i=i, rule=2, text="8 points in a row on one side of the center line (shift)"))
        if i >= 5:
            w = [q["xbar"] for q in pts[i - 5:i + 1]]
            if all(a < b for a, b in zip(w, w[1:])) or all(a > b for a, b in zip(w, w[1:])):
                rules.append(dict(i=i, rule=3, text="6 points rising or falling (trend)"))
        if p["r"] > D4[n] * rb:
            rules.append(dict(i=i, rule=4, text="Range above its control limit (spread)"))
    r3 = lambda x: None if x is None else round(x, 4)  # noqa: E731
    verdict = ("capable" if cpk and cpk >= 1.33 else "marginal" if cpk and cpk >= 1.0 else "not capable") if cpk else "no spread"
    out_spec = sum(1 for v in vals if not c["lsl"] <= v["value"] <= c["usl"])
    return {"char": dict(c), "enough": True, "n": n, "groups": [dict(p, xbar=r3(p["xbar"]), r=r3(p["r"])) for p in pts],
            "xbarbar": r3(xbb), "rbar": r3(rb), "ucl": r3(ucl), "lcl": r3(lcl), "r_ucl": r3(D4[n] * rb), "r_lcl": r3(D3[n] * rb),
            "sigma": r3(sigma), "cp": r3(cp), "cpk": r3(cpk), "verdict": verdict, "rules": rules, "in_control": not rules,
            "measurements": len(vals), "out_of_spec": out_spec}
