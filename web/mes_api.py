"""JSON API of GMES (ZMES_*): stations, serial numbers, bookings, genealogy, andon, SPC and the reports."""
from hr import skills
from mes import reports as R, track as T
from mm.util import require

from .server import db, route


@route("GET", "/api/mes/cockpit")
def mes_cockpit(req, q):
    return R.cockpit(db(), q.get("day") or None)


@route("GET", "/api/mes/master")
def mes_master(req, q):
    c = db()
    return {"stations": T.stations(c), "kinds": T.KINDS, "defects": T.DEFECTS, "andon": T.ANDON, "results": T.RESULTS,
            "skills": skills.skills(c), "chars": [dict(r) for r in c.execute("SELECT * FROM mes_char ORDER BY code")],
            "lines": [dict(r) for r in c.execute("SELECT arbpl, ktext FROM work_center ORDER BY arbpl")],
            "orders": [dict(r) for r in c.execute("SELECT o.aufnr, o.matnr, o.gamng, o.stat, (SELECT COUNT(*) FROM mes_unit u "
                                                  "WHERE u.aufnr=o.aufnr) units FROM orders o WHERE o.stat='REL' AND o.auart='PP01' "
                                                  "ORDER BY o.aufnr")]}


@route("POST", "/api/mes/(?P<obj>station|char|skill)")
def mes_master_save(req, q, obj):
    c, b = db(), req.body
    if obj == "station":
        return T.save_station(c, b)
    if obj == "char":
        return T.save_char(c, b)
    require(b, "code")
    return skills.save_skill(c, b["code"], b.get("text"), b.get("valid_months") or 24, b.get("kind") or "SKILL")


@route("GET", "/api/mes/units")
def mes_units(req, q):
    return {"rows": T.units(db(), q.get("aufnr") or None, q.get("status") or None)}


@route("GET", "/api/mes/unit")
def mes_unit(req, q):
    return T.unit(db(), q.get("serial"))


@route("POST", "/api/mes/(?P<act>release|book|confirm|ship)")
def mes_act(req, q, act):
    c, b = db(), req.body
    if act == "release":
        return T.release_units(c, b.get("aufnr"), b.get("count"), req.user)
    if act == "book":
        return T.book(c, b.get("serial"), b.get("station"), b.get("result"), b.get("operator"), req.user, defect=b.get("defect"),
                      cycle_sec=b.get("cycle_sec"), components=b.get("components") if isinstance(b.get("components"), list) else None,
                      note=b.get("note") or "")
    if act == "confirm":
        return T.confirm_to_order(c, b.get("aufnr"), req.user)
    return T.ship(c, b.get("serials") or "", b.get("vbeln"), req.user)


@route("GET", "/api/mes/trace")
def mes_trace(req, q):
    return T.trace(db(), q.get("key"))


@route("GET", "/api/mes/andon")
def mes_andon(req, q):
    return T.andon_board(db(), q.get("from") or None, q.get("to") or None)


@route("POST", "/api/mes/andon/(?P<act>open|ack|close)")
def mes_andon_act(req, q, act):
    c, b = db(), req.body
    if act == "open":
        return T.andon_open(c, b.get("arbpl"), b.get("kind"), b.get("text"), req.user, b.get("station"))
    return T.andon_step(c, b.get("id"), act, req.user, b.get("resolution") or "")


@route("GET", "/api/mes/spc")
def mes_spc(req, q):
    return T.spc(db(), q.get("code"), q.get("last") or 25)


@route("POST", "/api/mes/measure")
def mes_measure(req, q):
    b = req.body
    return T.measure(db(), b.get("code"), b.get("value"), req.user, b.get("serial"), b.get("station"), b.get("operator"))


@route("GET", "/api/mes/report/(?P<kind>hourly|quality|wip|cycle|operators)")
def mes_report(req, q, kind):
    c = db()
    if kind == "hourly":
        return R.hourly(c, q.get("day") or None, q.get("arbpl") or None)
    if kind == "wip":
        return R.wip(c)
    fn = {"quality": R.quality, "cycle": R.cycle, "operators": R.operators}[kind]
    return fn(c, q.get("from") or None, q.get("to") or None) if kind != "quality" else R.quality(c, q.get("from") or None,
                                                                                                  q.get("to") or None, q.get("arbpl") or None)
