"""JSON API of the assistant "Ask NERP" (ZAI) and its settings (ZAI_CONF)."""
from ai import agent

from .server import db, route


@route("POST", "/api/ai/ask")
def ai_ask(req, q):
    b = req.body
    hist = b.get("history") if isinstance(b.get("history"), list) else []
    auth_on = getattr(req, "_auth_on", None)            # off in developer mode and in tools
    return agent.ask(db(), b.get("question"), req.user, hist, check_auth=bool(auth_on and auth_on()))


@route("GET", "/api/ai/settings")
def ai_settings(req, q):
    c = db()
    return dict(agent.public_settings(c), log=agent.log(c, 30), tools=[
        dict(name=n, area=t[1], description=t[2]) for n, t in agent.T.TOOLS.items()])


@route("POST", "/api/ai/settings")
def ai_settings_save(req, q):
    return agent.save_settings(db(), req.body, req.user)


@route("GET", "/api/ai/status")
def ai_status(req, q):
    s = agent.public_settings(db())
    return {"mode": s["mode"], "model": s["model"] if s["mode"] == "ai" else ""}


@route("GET", "/api/ai/day")
def ai_day(req, q):
    """daily review (ZDAY): only the modules the user may display"""
    from ai import review
    from notify.engine import _allowed
    c = db()
    auth_on = getattr(req, "_auth_on", None)
    allowed = _allowed(c, req.user) if (auth_on and auth_on()) else None
    return review.day_review(c, q.get("date") or None, req.user, allowed)
