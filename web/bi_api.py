"""API of the BI portal (ZBI): catalog, query, characteristic values, saved views,
executive KPI cockpit."""
import json

from bi import catalog, engine
from bi.providers import PROVIDERS
from mm.util import MMError, amt_out, parse_int
from mm import util as mmclock

from web.server import db, route


@route("GET", "/api/bi/catalog")
def bi_catalog(req, q):
    return {"tree": catalog.tree(), "views": catalog.views(db(), req.user),
            "providers": {k: v[0] for k, v in PROVIDERS.items()}}


@route("GET", "/api/bi/report/(?P<rid>[A-Z0-9_]+)")
def bi_report(req, q, rid):
    r = catalog.flat().get(rid)
    if not r:
        raise MMError("Report %s does not exist" % rid, "BI", "006")
    return r


@route("GET", "/api/bi/query")
def bi_query(req, q):
    try:
        query = json.loads(q.get("q") or "{}")
    except ValueError:
        raise MMError("The query is not valid", "BI", "007")
    if not isinstance(query, dict):
        raise MMError("The query is not valid", "BI", "007")
    _hr_guard(req, query.get("provider"))
    return engine.run(db(), query)


def _hr_guard(req, provider):
    """Personnel cost is confidential: only users with the HR area (when the logon is on)."""
    if provider != "HR" or not getattr(getattr(req, "server", None), "auth", False):
        return
    from sec import auth
    if not auth.area_allowed(auth.profile(db(), req.user), "HR", "03"):
        raise auth.refuse(db(), req.user, "S_AREA", "HR", "Human resources - Display")


@route("GET", "/api/bi/values")
def bi_values(req, q):
    _hr_guard(req, q.get("provider"))
    return engine.values(db(), q.get("provider"), q.get("char"))


@route("POST", "/api/bi/view")
def bi_view_save(req, q):
    b = req.body
    if b.get("delete"):
        catalog.delete_view(db(), req.user, parse_int(b.get("id"), "view"))
        return {"message": "View deleted"}
    if not isinstance(b.get("query"), dict):
        raise MMError("Nothing to save", "BI", "011")
    n = catalog.save_view(db(), req.user, b.get("report") or "", b.get("title"), b["query"])
    return {"id": n, "message": "View '%s' saved under 'My views'" % (b.get("title") or "").strip()}


@route("GET", "/api/bi/dashboard/(?P<did>[A-Z_]+)")
def bi_dashboard(req, q, did):
    if did != "EXEC":
        from bi import dashboards
        return dashboards.run(db(), did, q)
    c = db()
    t = mmclock.today()
    y, p = t.year, t.month
    pl = engine.run(c, dict(provider="COPA", structure="PL", year=y, period=p, columns=[
        dict(version="ACT", time="P"), dict(version="PLAN", time="P"), dict(version="ACT", time="YTD"),
        dict(version="PLAN", time="YTD")]))
    row = {r["node"]: r["values"] for r in pl["rows"]}
    from bi import providers as P
    inv = P.inventory(c)
    oi = P.open_items(c)
    orders = P.orders(c)
    pur = P.purchasing(c)
    prod = P.production(c)
    trend = engine.run(c, dict(provider="COPA", structure="PL", columns=[dict(version="ACT"), dict(version="PLAN")],
                               colchar="month"))
    months = trend["months"]
    tr = {r["node"]: r["values"] for r in trend["rows"]}
    n = len(months)

    def pct(a, b):
        return round(a * 100.0 / b, 1) if b else None
    ns_a, ns_p = row["NS"][0] or 0, row["NS"][1] or 0
    kpi = [
        dict(k="Net sales (month)", v=ns_a, plan=ns_p, ach=pct(ns_a, ns_p), unit="EGP", go="CO_PL_DETAIL"),
        dict(k="Net sales (year to date)", v=row["NS"][2], plan=row["NS"][3], ach=pct(row["NS"][2] or 0, row["NS"][3]),
             unit="EGP", go="CO_SALES_PROFIT"),
        dict(k="Gross margin % (YTD)", v=pct(row["GM"][2] or 0, row["NS"][2]), plan=pct(row["GM"][3] or 0, row["NS"][3]),
             unit="%", go="CO_PL_DETAIL"),
        dict(k="Operating profit (YTD)", v=row["OP"][2], plan=row["OP"][3], ach=pct(row["OP"][2] or 0, row["OP"][3]),
             unit="EGP", go="CO_PL_FORECAST"),
        dict(k="Inventory value", v=amt_out(sum(f["value"] for f in inv)), unit="EGP", go="LO_INV_PLANT"),
        dict(k="Stock older than 180 days", v=amt_out(sum(f["value"] for f in inv if f["aging"] in ("181-365", ">365"))),
             unit="EGP", go="RSK_OLD_STOCK", bad=True),
        dict(k="Receivables overdue", v=amt_out(sum(f["overdue"] for f in oi if f["koart"] == "Customers")),
             unit="EGP", go="RSK_AR_OVERDUE", bad=True),
        dict(k="Order backlog", v=amt_out(sum(f["backlog"] for f in orders)), unit="EGP", go="SD_BACKLOG"),
        dict(k="Open purchase orders", v=amt_out(sum(f["open_value"] for f in pur)), unit="EGP", go="PU_OPEN"),
        dict(k="Scrap quantity", v=sum(f["scrap"] for f in prod) / 1000.0, unit="pcs", go="PP_SCRAP", bad=True),
    ]
    return {"year": y, "period": p, "kpis": kpi, "months": months,
            "trend": {"net_actual": tr["NS"][:n], "net_plan": tr["NS"][n + 1:2 * n + 1] if len(tr["NS"]) > n + 1 else [],
                      "op_actual": tr["OP"][:n]}}
