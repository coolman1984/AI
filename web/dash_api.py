"""API of the separate ERP dashboard window (web/static/dashboard.html)."""
from bi import overview

from web.server import db, route


@route("GET", "/api/dash/overview")
def dash_overview(req, q):
    auth_on = getattr(getattr(req, "server", None), "auth", False)
    out = overview.overview(db(), req.user, everything=not auth_on)
    out["user"] = req.user
    out["auth"] = auth_on
    return out
