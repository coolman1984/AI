"""JSON API of the daily briefing and alerts: my messages and subscriptions (ZNOTIF) and the
administration (ZNOTIF_CONF: channels, all subscriptions, run now, log)."""
from mm.util import require
from notify import channels, engine

from .server import db, route


def _meta():
    return {"cats": {k: v[0] for k, v in engine.CATS.items()}, "channels": channels.CHANNELS}


@route("GET", "/api/notif/my")
def notif_my(req, q):
    c = db()
    return dict(engine.inbox(c, req.user), subs=engine.subs(c, req.user), **_meta())


@route("POST", "/api/notif/(?P<act>seen|sub|delete|test)")
def notif_my_act(req, q, act):
    c, b = db(), req.body
    if act == "seen":
        return engine.mark_seen(c, req.user)
    if act == "sub":
        return engine.save_sub(c, b, req.user)
    require(b, "id")
    if act == "delete":
        return engine.delete_sub(c, b["id"], req.user)
    return engine.test_message(c, b["id"], req.user)


@route("GET", "/api/notif/admin")
def notif_admin(req, q):
    c = db()
    return dict(settings=engine.public_settings(c), subs=engine.subs(c), log=engine.log(c, 60),
                state={k: v for k, v in engine.STATE.items() if k != "last_alerts"},
                alerts=engine.alerts(c, req.user), **_meta())


@route("POST", "/api/notif/admin/(?P<act>settings|sub|delete|test|daily|alerts|chats)")
def notif_admin_act(req, q, act):
    c, b = db(), req.body
    if act == "settings":
        return engine.save_settings(c, b, req.user)
    if act == "sub":
        return engine.save_sub(c, b, req.user, admin=True)
    if act == "delete":
        require(b, "id")
        return engine.delete_sub(c, b["id"], req.user, admin=True)
    if act == "test":
        require(b, "id")
        return engine.test_message(c, b["id"], req.user, admin=True)
    if act == "daily":
        n = engine.run_daily(c, force_sub=int(b["id"])) if b.get("id") else engine.run_daily(c)
        return {"message": "%d daily briefing(s) sent" % n}
    if act == "alerts":
        return {"message": "%d alert message(s) sent" % engine.run_alerts(c)}
    try:
        return {"rows": channels.telegram_chats(engine.settings(c))}
    except channels.NotifyError as e:
        from mm.util import MMError
        raise MMError(str(e), "NT", "908")
