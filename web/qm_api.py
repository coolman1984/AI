"""JSON API of quality management (QA*/QM*) and plant maintenance (IE*/IP*/IW*)."""
import datetime

from mm import util as clock
from mm.util import require
from qm import maintenance as pm, quality as qm

from .server import db, route


def _range(q, days=None):
    t = clock.today()
    d1 = (t - datetime.timedelta(days=days)) if days else t.replace(day=1)
    return q.get("d1") or d1.isoformat(), q.get("d2") or t.isoformat()


# ------------------------------------------------------------------ quality
@route("GET", "/api/qm/cockpit")
def qm_cockpit(req, q):
    return qm.cockpit(db(), *_range(q, 30))


@route("GET", "/api/qm/plan")
def qm_plan(req, q):
    c, matnr = db(), (q.get("matnr") or "").upper()
    return {"matnr": matnr, "chars": qm.plan(c, matnr, q.get("werks") or "1000"),
            "active": qm.qm_active(c, matnr, q.get("werks") or "1000") if matnr else False,
            "materials": [dict(r) for r in c.execute(
                "SELECT p.matnr, m.maktx, p.insmk, (SELECT COUNT(*) FROM qm_char c WHERE c.matnr=p.matnr AND "
                "c.werks=p.werks) chars FROM material_plant p JOIN material m ON m.matnr=p.matnr WHERE p.werks='1000' "
                "AND (p.insmk=1 OR EXISTS (SELECT 1 FROM qm_char c WHERE c.matnr=p.matnr)) ORDER BY p.matnr")]}


@route("POST", "/api/qm/plan")
def qm_plan_save(req, q):
    b = req.body
    require(b, "matnr")
    c = db()
    res = qm.save_plan(c, b["matnr"], b.get("werks") or "1000", b.get("chars") or [], req.user)
    if "active" in b:
        qm.set_active(c, b["matnr"], b.get("werks") or "1000", bool(b["active"]), req.user)
    return res


@route("GET", "/api/qm/lots")
def qm_lots(req, q):
    return {"rows": qm.lots(db(), q.get("status") or None, q.get("matnr") or None, q.get("lifnr") or None),
            "origins": qm.ORIGINS}


@route("GET", "/api/qm/lot")
def qm_lot(req, q):
    require(q, "prueflos")
    return dict(qm.lot(db(), q["prueflos"]), defect_codes=qm.DEFECTS)


@route("POST", "/api/qm/(?P<act>lot|record|ud)")
def qm_act(req, q, act):
    b, c = req.body, db()
    if act == "lot":
        return qm.create_lot(c, b, req.user)
    require(b, "prueflos")
    if act == "record":
        return qm.record(c, b["prueflos"], b.get("values") or {}, req.user)
    return qm.usage_decision(c, b["prueflos"], b, req.user)


@route("GET", "/api/qm/notif")
def qm_notifs(req, q):
    return {"rows": qm.notifications(db(), q.get("status") or None), "types": qm.NOTIF_TYPES, "defects": qm.DEFECTS}


@route("POST", "/api/qm/notif")
def qm_notif_save(req, q):
    b = req.body
    if b.get("qmnum"):
        return qm.update_notification(db(), b["qmnum"], b, req.user)
    return qm.create_notification(db(), b, req.user)


@route("GET", "/api/qm/vendors")
def qm_vendors(req, q):
    return {"rows": qm.vendor_quality(db(), *_range(q))}


# ------------------------------------------------------------------ maintenance
@route("GET", "/api/pm/cockpit")
def pm_cockpit(req, q):
    return pm.cockpit(db(), *_range(q, 90))


@route("GET", "/api/pm/equi")
def pm_equi(req, q):
    c = db()
    return {"rows": pm.equipment(c), "crit": pm.CRIT,
            "lines": [dict(r) for r in c.execute("SELECT arbpl, ktext, kostl FROM work_center ORDER BY arbpl")]}


@route("POST", "/api/pm/equi")
def pm_equi_save(req, q):
    return pm.save_equipment(db(), req.body, req.user)


@route("GET", "/api/pm/plans")
def pm_plans(req, q):
    return {"rows": pm.plans(db())}


@route("POST", "/api/pm/(?P<act>plan|schedule)")
def pm_plan_act(req, q, act):
    if act == "plan":
        return pm.save_plan(db(), req.body, req.user)
    return pm.schedule(db(), req.user, req.body.get("horizon") or 0)


@route("GET", "/api/pm/orders")
def pm_orders(req, q):
    c = db()
    return {"rows": pm.orders(c, q.get("status") or None), "notifs": pm.notifications(c), "types": pm.ORDER_TYPES,
            "ntypes": pm.NOTIF_TYPES}


@route("POST", "/api/pm/(?P<act>notif|order|parts|confirm|complete)")
def pm_act(req, q, act):
    b, c = req.body, db()
    if act == "notif":
        return pm.create_notification(c, b, req.user)
    if act == "order":
        return pm.create_order(c, b, req.user)
    require(b, "aufnr")
    if act == "parts":
        return pm.issue_parts(c, b["aufnr"], b.get("items") or [], req.user, b.get("budat"))
    if act == "confirm":
        return pm.confirm(c, b["aufnr"], b, req.user)
    return pm.complete(c, b["aufnr"], b, req.user)


@route("GET", "/api/pm/reliability")
def pm_rel(req, q):
    return {"rows": pm.reliability(db(), *_range(q, 90))}
