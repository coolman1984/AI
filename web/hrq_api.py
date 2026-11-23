"""JSON API of the skills matrix and certifications (ZHR_SKILLS)."""
from hr import skills
from mm.util import require

from .server import db, route


@route("GET", "/api/hr/skills")
def hr_skills(req, q):
    return dict(skills.matrix(db(), q.get("day") or None), levels=skills.LEVELS)


@route("POST", "/api/hr/qualify")
def hr_qualify(req, q):
    b = req.body
    require(b, "pernr", "skill")
    return skills.qualify(db(), b["pernr"], b["skill"], b.get("level") or 1, b.get("valid_from") or None, req.user,
                          trainer=b.get("trainer") or "", note=b.get("note") or "", valid_to=b.get("valid_to") or None)
