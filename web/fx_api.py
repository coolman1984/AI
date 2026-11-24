"""JSON API of the exchange rates of all currencies (ZFX)."""
from fi import currency as fx

from .server import db, route


@route("GET", "/api/fi/fx")
def fx_overview(req, q):
    return fx.overview(db(), everything=q.get("all") == "1", day=q.get("day") or None)


@route("GET", "/api/fi/fx/history")
def fx_history(req, q):
    return fx.history(db(), q.get("waers"))


@route("GET", "/api/fi/fx/convert")
def fx_convert(req, q):
    return fx.convert(db(), q.get("amount") or "1", q.get("from"), q.get("to"), q.get("day") or None)


@route("POST", "/api/fi/fx/(?P<act>rate|rates|active)")
def fx_act(req, q, act):
    c, b = db(), req.body
    if act == "rate":
        fx.set_rate(c, b.get("waers"), b.get("gdatu"), b.get("rate"))
        return {"message": "Rate %s saved" % (b.get("waers") or "").upper()}
    if act == "rates":
        return fx.save_rates(c, b.get("text"), b.get("gdatu"), req.user)
    return fx.set_active(c, b.get("waers"), bool(b.get("active")))
