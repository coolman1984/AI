"""JSON API of the external audit area (ZAUD_*)."""
import base64

from extaudit import analytics as A, engagement as E, pack
from extaudit.standards import EAS, ESA, STATUS
from mm.util import MMError, require

from .server import db, route


def _y(q):
    from mm import util as clock
    return q.get("gjahr") or clock.today().year


def _auditor(req):
    """the audit firm (AUDITOR role) accepts / returns PBC items and closes queries"""
    on = getattr(req, "_auth_on", None)
    if not (on and on()):
        return True
    c = db()
    roles = {r[0] for r in c.execute("SELECT role FROM usr_role WHERE bname=?", (req.user,))}
    return bool(roles & {"AUDITOR", "ADMIN"})


@route("GET", "/api/audit/cockpit")
def aud_cockpit(req, q):
    return E.cockpit(db(), _y(q))


@route("GET", "/api/audit/eng")
def aud_eng(req, q):
    return dict(E.engagement(db(), _y(q)), bases=E.BASES, auditor=_auditor(req))


@route("POST", "/api/audit/eng")
def aud_eng_save(req, q):
    return E.save_engagement(db(), req.body, req.user)


@route("GET", "/api/audit/pbc")
def aud_pbc(req, q):
    return {"rows": E.pbc(db(), _y(q)), "status": STATUS, "auditor": _auditor(req)}


@route("POST", "/api/audit/pbc")
def aud_pbc_save(req, q):
    require(req.body, "code")
    return E.update_pbc(db(), _y(req.body), req.body["code"], req.body, req.user, _auditor(req))


@route("GET", "/api/audit/queries")
def aud_queries(req, q):
    return {"rows": E.queries(db(), _y(q)), "auditor": _auditor(req)}


@route("POST", "/api/audit/(?P<act>query|answer)")
def aud_query_act(req, q, act):
    if act == "query":
        return E.ask(db(), _y(req.body), req.body, req.user)
    require(req.body, "id")
    return E.answer(db(), req.body["id"], req.body, req.user, _auditor(req))


@route("GET", "/api/audit/aje")
def aud_aje(req, q):
    return E.adjustments(db(), _y(q))


@route("POST", "/api/audit/aje")
def aud_aje_propose(req, q):
    return E.propose(db(), _y(req.body), req.body, req.user)


@route("POST", "/api/audit/aje/(?P<act>post|reject)")
def aud_aje_act(req, q, act):
    require(req.body, "id")
    if act == "post":
        return E.post(db(), req.body["id"], req.body, req.user)
    return E.decide(db(), req.body["id"], req.body, req.user)


KINDS = {"jet": lambda c, y, e: A.jet(c, y, int(e["performance"] * 100) or None), "ar": lambda c, y, e: A.partners(c, y, "D"),
         "ap": lambda c, y, e: A.partners(c, y, "K"), "ecl": lambda c, y, e: A.ecl(c, y), "bank": lambda c, y, e: A.bank(c, y),
         "unrec": lambda c, y, e: A.unrecorded(c, y), "inv": lambda c, y, e: A.inventory(c, y),
         "fa": lambda c, y, e: A.fixed_assets(c, y), "cutoff": lambda c, y, e: A.cutoff(c, y),
         "payroll": lambda c, y, e: A.payroll(c, y), "subsequent": lambda c, y, e: A.subsequent(c, y, int(e["performance"] * 100) or 1),
         "lead": lambda c, y, e: {"rows": A.lead_schedules(c, y), "statements": A.statements(c, y)}}


@route("GET", "/api/audit/test/(?P<kind>jet|ar|ap|ecl|bank|unrec|inv|fa|cutoff|payroll|subsequent|lead)")
def aud_test(req, q, kind):
    c = db()
    e = E.engagement(c, _y(q))
    return KINDS[kind](c, e["gjahr"], e)


@route("GET", "/api/audit/pack")
def aud_pack(req, q):
    c = db()
    y = E.engagement(c, _y(q))["gjahr"]
    return {"name": "NERP_Audit_Pack_%d.xlsx" % y, "xlsx": base64.b64encode(pack.build(c, y)).decode("ascii")}


@route("GET", "/api/audit/standards")
def aud_standards(req, q):
    return {"eas": [dict(no=k, title=v[0], title_ar=v[1], verified=v[2]) for k, v in EAS.items()],
            "esa": [dict(no=k, title=v) for k, v in ESA.items()]}


@route("POST", "/api/audit/access")
def aud_access(req, q):
    if not req.body.get("valid_to"):
        raise MMError("Enter until when the audit firm may log on", "AU", "923")
    return E.grant_access(db(), req.body, req.user)
