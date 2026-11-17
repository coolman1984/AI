"""Read-only tools of the assistant. Every tool reads the books through the existing engines
(the same figures as the screens), returns a small JSON-able dict in EGP / units and names the
screen (T-code) where the user sees the details. Each tool belongs to an authorization area:
the assistant only reads what the user may display.

Nothing here writes to the database.
"""
import datetime

from mm import util as clock
from mm.util import parse_date, parse_int


def _egp(c):
    return round((c or 0) / 100.0, 2)


def _u(m):
    return round((m or 0) / 1000.0, 3)


def _period(args, default_days=None):
    t = clock.today()
    d2 = parse_date(args.get("date_to")) if args.get("date_to") else t.isoformat()
    if args.get("date_from"):
        d1 = parse_date(args["date_from"])
    elif default_days:
        d1 = (datetime.date.fromisoformat(d2) - datetime.timedelta(days=default_days)).isoformat()
    else:
        d1 = d2[:8] + "01"
    return d1, d2


PERIOD = {"date_from": {"type": "string", "description": "First day, YYYY-MM-DD. Default: first day of the current month."},
          "date_to": {"type": "string", "description": "Last day, YYYY-MM-DD. Default: today."}}


def sales_overview(conn, args):
    from sd.reports import cockpit
    d1, d2 = _period(args)
    c = cockpit(conn, d1, d2)
    k = c["kpi"]
    top = lambda rows: [dict(key=r["key"], name=r.get("name"), net_egp=_egp(r["net"]), qty=_u(r["qty"]),   # noqa: E731
                             margin_pct=r.get("margin_pct"), invoices=r.get("invoices")) for r in rows[:5]]
    return {"period": [d1, d2], "screen": "ZSD_COCKPIT",
            "revenue_egp": _egp(k["revenue"]), "incoming_orders_egp": _egp(k["incoming"]), "orders": k["orders"],
            "backlog_egp": _egp(k["backlog"]), "margin_egp": _egp(k["margin"]), "margin_pct": k["margin_pct"],
            "discount_pct": k["discount_pct"], "on_time_in_full_pct": k["otif"], "returns_pct": k["returns_pct"],
            "dso_days": k["dso"], "credit_blocked_orders": k["credit_blocked_n"],
            "top_customers": top(c["top_customers"]), "top_products": top(c["top_materials"])}


def receivables(conn, args):
    from fi.reports import aging
    day = parse_date(args.get("key_date")) if args.get("key_date") else clock.today().isoformat()
    a = aging(conn, "D", day)
    rows = sorted(a["rows"], key=lambda r: -(r["total"] - r["not_due"]))
    tot = {k: round(sum(r[k] for r in a["rows"]), 2) for k, _ in a["buckets"]}
    return {"key_date": day, "screen": "S_ALR_87012168", "currency": "EGP", "buckets": dict(a["buckets"]),
            "totals": tot, "overdue_total": round(sum(v for k, v in tot.items() if k != "not_due"), 2),
            "customers": [dict(r, overdue=round(r["total"] - r["not_due"], 2)) for r in rows[:10]]}


def finance_overview(conn, args):
    from fi.reports import cockpit
    t = clock.today()
    y = parse_int(args.get("year") or t.year, "year", 2000, 2100)
    p = parse_int(args.get("period") or t.month, "period", 1, 12)
    k = cockpit(conn, y, p)["kpi"]
    keep = ("cash", "ar", "overdue", "ap", "inventory", "dso", "dpo", "working_capital", "current_ratio", "result",
            "revenue", "ytd_result", "ytd_revenue", "equity_ratio", "balanced", "ebitda")
    return dict({k2: k[k2] for k2 in keep if k2 in k}, year=y, period=p, currency="EGP", screen="ZFI_COCKPIT",
                note="result / revenue = the month; ytd = year to date; ar / ap = receivables / payables")


def purchasing_overview(conn, args):
    from pur.analytics import cockpit
    d1, d2 = _period(args)
    c = cockpit(conn, d1, d2)
    return {"period": [d1, d2], "screen": "ZPUR_COCKPIT", "currency": "EGP", "kpi": c["kpi"],
            "overdue_po_items": c["overdue"][:10]}


def production_overview(conn, args):
    from pp.reports import cockpit
    d1, d2 = _period(args)
    k = cockpit(conn, d1, d2)["kpi"]
    from pp.daily import pending
    p = pending(conn)
    return {"period": [d1, d2], "screen": "ZPP_COCKPIT", "orders": k["orders"], "open_orders": k["open_orders"],
            "late_orders": k["late"], "on_time_pct": k["on_time"], "yield_units": _u(k["yield_qty"]),
            "scrap_units": _u(k["scrap_qty"]), "scrap_pct": k["scrap_pct"], "wip_egp": _egp(k["wip"]),
            "variance_egp": _egp(k["variance"]), "orders_missing_components": k["missing"],
            "pending_orders": [dict(order=r["aufnr"], material=r["matnr"], text=r["maktx"], line=r["line"], due=r["due"],
                                    pending_units=_u(r["pending"]), late_days=r["late"], short_components=r["short"])
                               for r in p["rows"][:15]]}


def production_today(conn, args):
    from pp.board import board
    from pp.daily import last_day
    day = parse_date(args.get("date")) if args.get("date") else clock.today().isoformat()
    b = board(conn, day)
    used = day
    if not b["groups"] and args.get("date") is None:
        ld = last_day(conn, day)
        if ld:
            b, used = board(conn, ld), ld
    lines = []
    for g in b["groups"]:
        for r in g["lines"]:
            lines.append(dict(area=g["area"], line=r["arbpl"], model=r.get("model"), plan=_u(r["plan"]),
                              produced=_u(r["prod"]), target_now=_u(r["target"]), achievement_pct=r["ach"],
                              defect_pct=r["defect"], downtime_min=r["loss_min"]))
    t = b["total"] or {}
    return {"date": used, "screen": "ZPP_BOARD", "lines": lines,
            "total": {"plan": _u(t.get("plan")), "produced": _u(t.get("prod")), "achievement_pct": t.get("ach"),
                      "downtime_min": t.get("loss_min"), "lines_running": t.get("running"), "lines": t.get("lines")},
            "note": "" if used == day else "No production on %s - showing the last production day" % day}


def stock_lookup(conn, args):
    from mm.board import _price
    from mm.util import value_of
    q = (args.get("query") or "").strip()
    cache, out = {}, []
    like = "%" + q.upper() + "%"
    mats = conn.execute("SELECT matnr, maktx, meins, mtart FROM material WHERE UPPER(matnr) LIKE ? OR UPPER(maktx) LIKE ? "
                        "ORDER BY matnr LIMIT 15", (like, like)).fetchall() if q else []
    for m in mats:
        rows = conn.execute("SELECT werks, lgort, insmk, SUM(qty) q FROM quant WHERE matnr=? AND qty<>0 "
                            "GROUP BY werks, lgort, insmk", (m["matnr"],)).fetchall()
        by = {"U": 0, "Q": 0, "B": 0}
        val = 0
        for r in rows:
            by[r["insmk"]] = by.get(r["insmk"], 0) + r["q"]
            p, pe = _price(conn, m["matnr"], r["werks"], cache)
            val += value_of(r["q"], p, pe)
        out.append(dict(material=m["matnr"], text=m["maktx"], unit=m["meins"], type=m["mtart"],
                        unrestricted=_u(by["U"]), quality_inspection=_u(by["Q"]), blocked=_u(by["B"]),
                        value_egp=_egp(val), by_location=[dict(plant=r["werks"], sloc=r["lgort"], stock_type=r["insmk"],
                                                               qty=_u(r["q"])) for r in rows]))
    return {"query": q, "screen": "MMBE", "materials": out,
            "note": "" if out else "No material matches '%s' - try part of the number or the description" % q}


def quality_overview(conn, args):
    from qm.quality import cockpit
    d1, d2 = _period(args, 30)
    c = cockpit(conn, d1, d2)
    return {"period": [d1, d2], "screen": "ZQM_COCKPIT", "lots_in_inspection": c["open_lots"],
            "lots_waiting_over_3_days": c["overdue_lots"], "accepted_lots_pct": c["accept_pct"],
            "rejected_ppm": c["ppm"], "open_complaints": c["open_notifs"], "defects": c["pareto"][:8],
            "vendors": c["vendors"][:10],
            "open_lots": [dict(lot=x["prueflos"], material=x["matnr"], qty=x["qty"], vendor=x["vendor"], days=x["age"])
                          for x in c["lots"][:10]]}


def maintenance_overview(conn, args):
    from qm.maintenance import cockpit
    d1, d2 = _period(args, 90)
    c = cockpit(conn, d1, d2)
    return {"period": [d1, d2], "screen": "ZPM_COCKPIT", "currency": "EGP",
            "open_orders": c["open_orders"], "overdue_orders": c["overdue_orders"], "overdue_preventive_plans": c["overdue_plans"],
            "breakdowns": c["breakdowns"], "downtime_min": c["downtime"], "mttr_min": c["mttr"],
            "availability_pct": c["availability"], "preventive_share_pct": c["planned_share"], "cost_egp": c["cost"],
            "machines": c["machines"],
            "open_order_list": [dict(order=o["aufnr"], type=o["type_text"], machine=o["eqktx"], work=o["text"], due=o["due"])
                                for o in c["orders"][:10]]}


def tax_calendar(conn, args):
    from tax.returns import calendar_year
    t = clock.today()
    y = parse_int(args.get("year") or t.year, "year", 2000, 2100)
    c = calendar_year(conn, y)
    rows = [dict(r, amount=_egp(r["amount"])) for r in c["rows"]]
    return {"year": y, "screen": "ZTAX_CAL", "currency": "EGP",
            "overdue": [r for r in rows if r["status"] == "overdue"][:12],
            "due_next_30_days": [r for r in rows if r["status"] not in ("paid", "overdue") and 0 <= r["days"] <= 30],
            "counts": {s: sum(1 for r in rows if r["status"] == s) for s in sorted(set(r["status"] for r in rows))}}


def hr_overview(conn, args):
    from hr.reports import cockpit
    c = cockpit(conn)
    h = c["headcount"]
    return {"screen": "ZHR_COCKPIT", "headcount": h["total"], "by_department": h["by_org"], "female": h["female"],
            "male": h["male"], "average_age": h["avg_age"], "average_service_years": h["avg_service"],
            "monthly_personnel_cost_egp": _egp(h["monthly_cost"]), "on_leave_today": c["on_leave"],
            "open_leave_requests": c["open_requests"], "turnover_pct": c["turnover_pct"]}


def daily_meeting(conn, args):
    from pp import daily
    day = parse_date(args.get("date")) if args.get("date") else clock.today().isoformat()
    d, m, s = daily.pdefect(conn, day), daily.mloss(conn, day), daily.pending_scrap(conn, day)
    p = daily.pending(conn, day)
    return {"date": day, "screens": ["ZPP_DM_PENDING", "ZPP_DM_PDEFECT", "ZPP_DM_MLOSS", "ZPP_DM_SCRAP"],
            "orders_late": p["late"], "orders_due_today": p["today"], "orders_missing_components": p["short_orders"],
            "scrap_today_units": _u(d["today"]), "scrap_month_units": _u(d["month"]), "defect_month_pct": d["month_pct"],
            "scrap_reasons": [dict(reason=x["text"], units=_u(x["qty"])) for x in d["pareto"][:5]],
            "material_loss_month_egp": _egp(m["total"]), "pending_scrap_egp": _egp(s["value"]),
            "pending_scrap_over_90_days_egp": _egp(s["aging"]["> 90 days"])}


# name -> (function, authorization area, description, extra properties)
TOOLS = {
    "sales_overview": (sales_overview, "SD", "Sales of a period: revenue, incoming orders, backlog, margin, on-time delivery, "
                       "DSO, top customers and top products.", PERIOD),
    "receivables": (receivables, "FI", "Customer receivables by age (not due, 1-30, 31-60, 61-90, >90 days late) and the "
                    "customers with the highest overdue amounts.",
                    {"key_date": {"type": "string", "description": "Key date YYYY-MM-DD, default today."}}),
    "finance_overview": (finance_overview, "FI", "Finance cockpit of a month: cash, receivables, payables, inventory, "
                         "working capital, result and revenue of the month and year to date, DSO / DPO.",
                         {"year": {"type": "integer"}, "period": {"type": "integer", "description": "Month 1-12"}}),
    "purchasing_overview": (purchasing_overview, "PUR", "Purchasing of a period: spend, open commitments, overdue purchase "
                            "order items, requisitions waiting, savings, vendor on-time rate.", PERIOD),
    "production_overview": (production_overview, "PP", "Production of a period: orders, late orders, yield, scrap, work in "
                            "process, variances and the open production orders with missing components.", PERIOD),
    "production_today": (production_today, "PP", "Shop-floor status of a day per line: plan, produced, achievement, "
                         "defects, downtime (production board).",
                         {"date": {"type": "string", "description": "YYYY-MM-DD, default today (or the last production day)"}}),
    "stock_lookup": (stock_lookup, "MM", "Stock of materials found by number or description: unrestricted, in quality "
                     "inspection, blocked, value and storage locations.",
                     {"query": {"type": "string", "description": "Part of the material number or description, e.g. 'glass' or 'FG-3001'"}}),
    "quality_overview": (quality_overview, "MM", "Quality: lots in inspection, accepted lots %, rejected ppm, defect "
                         "Pareto, vendor quality rating, open complaints.", PERIOD),
    "maintenance_overview": (maintenance_overview, "PP", "Maintenance: open and overdue orders, breakdowns, downtime, MTTR, "
                             "availability and cost per machine.", PERIOD),
    "tax_calendar": (tax_calendar, "FI", "Egyptian tax calendar: returns and payments overdue or due in the next 30 days "
                     "(VAT, withholding form 41, salary tax, corporate tax).", {"year": {"type": "integer"}}),
    "hr_overview": (hr_overview, "HR", "Personnel: headcount by department, monthly personnel cost, leave, turnover.", {}),
    "daily_meeting": (daily_meeting, "PP", "Daily production meeting summary: late orders, scrap, defect rate, material "
                      "loss and pending scrap.", {"date": {"type": "string", "description": "YYYY-MM-DD, default today"}}),
}


def definitions():
    """tool definitions for the Messages API (stable order - keeps the prompt prefix cacheable)"""
    return [{"name": n, "description": d, "input_schema": {"type": "object", "properties": props}}
            for n, (_, _, d, props) in TOOLS.items()]


def run(conn, name, args, allowed=None):
    """execute one tool; allowed(area) -> bool decides the authorization"""
    if name not in TOOLS:
        raise KeyError("Unknown tool %s" % name)
    fn, area, _, _ = TOOLS[name]
    if allowed is not None and not allowed(area):
        raise PermissionError("No authorization to display area %s" % area)
    return fn(conn, args if isinstance(args, dict) else {})
