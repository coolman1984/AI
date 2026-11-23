"""JSON API of the What-If simulator (ZWHATIF - "ماذا لو")."""
import json

from ai import whatif as W
from mm.util import MMError

from .server import db, route


def _p(q):
    try:
        return json.loads(q.get("p") or "{}")
    except ValueError:
        raise MMError("Invalid scenario parameters", "WI", "901")


@route("GET", "/api/whatif/sim")
def whatif_sim(req, q):
    """simulate the year with the levers in p (JSON); lang ar|en"""
    return W.simulate(db(), _p(q), q.get("lang") or "ar")


@route("GET", "/api/whatif/goal")
def whatif_goal(req, q):
    """the value of one lever that gives the target profit"""
    return W.goal_seek(db(), q.get("target"), q.get("lever") or "price", _p(q), q.get("lang") or "ar")


@route("GET", "/api/whatif/scenarios")
def whatif_scenarios(req, q):
    lang = q.get("lang") or "ar"
    ids = [int(x) for x in (q.get("ids") or "").split(",") if x.strip().isdigit()]
    return {"rows": W.scenarios(db()), "presets": W.presets(lang), "compare": W.compare(db(), ids, lang) if ids else None}


@route("POST", "/api/whatif/(?P<act>save|delete)")
def whatif_act(req, q, act):
    if act == "save":
        return W.save(db(), req.body, req.user)
    return W.delete(db(), req.body.get("id"), req.user)
