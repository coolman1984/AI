"""ERP dashboard (separate "MM Core Dashboard" window): one call returns every card -
finance, profitability, manufacturing, quality, warehouse, procurement, sales,
controlling, analytics and the open work items - from the live data."""
import datetime

from mm import util as mmclock

from . import engine, providers as P


def _a(c):
    """cents -> currency units (2 decimals)."""
    return round((c or 0) / 100.0, 2)


def _pct(a, b):
    return round(a * 100.0 / b, 1) if b else None


def _months(today, n=12):
    out, y, m = [], today.year, today.month
    for _ in range(n):
        out.append("%04d-%02d" % (y, m))
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    return out[::-1]


def overview(conn, user="", everything=True):
    t = mmclock.today()
    y, p = t.year, t.month
    months = _months(t, 12)

    # ---------------------------------------------------------------- P&L (CO-PA)
    pl = engine.run(conn, dict(provider="COPA", structure="PL", year=y, period=p,
                               columns=[dict(version="ACT", time="YTD"), dict(version="PLAN", time="YTD"),
                                        dict(version="ACT", time="P"), dict(version="ACT", time="PY")]))
    v = {r["node"]: r["values"] for r in pl["rows"]}
    trend = engine.run(conn, dict(provider="COPA", structure="PL", columns=[dict(version="ACT")], colchar="month"))
    tm = trend["months"]
    tv = {r["node"]: r["values"] for r in trend["rows"]}
    ns_by_m = {m: tv["NS"][i] for i, m in enumerate(tm)}
    op_by_m = {m: tv["OP"][i] for i, m in enumerate(tm)}
    show = [m for m in months if m <= t.strftime("%Y-%m")][-8:]
    income = [ns_by_m.get(m, 0) or 0 for m in show]
    expenses = (v["COGS"][0] or 0) + (v["OPEX"][0] or 0) + (v["VAR"][0] or 0)

    # ---------------------------------------------------------------- bank, receivables, payables
    from fi.reports import gl_balance
    bank = sum(gl_balance(conn, h, t.isoformat()) for h in ("113100", "113101", "113109"))
    oi = P.open_items(conn)
    ar = sum(f["amount"] for f in oi if f["koart"] == "Customers")
    ap = sum(f["amount"] for f in oi if f["koart"] == "Vendors")
    ar_over = sum(f["overdue"] for f in oi if f["koart"] == "Customers")
    invoices = [dict(no=r["vbeln"], customer=r["name"] or r["kunnr"], date=r["fkdat"], amount=_a(r["netwr"]),
                     status="Cancelled" if r["cancelled"] else ("Credit memo" if (r["fkart"] or "") in ("G2", "RE") else "Posted"))
                for r in conn.execute("SELECT b.vbeln, b.fkdat, b.kunnr, b.netwr, b.cancelled, b.fkart, c.name FROM billing b "
                                      "LEFT JOIN customer c USING (kunnr) ORDER BY b.fkdat DESC, b.vbeln DESC LIMIT 5")]

    # ---------------------------------------------------------------- manufacturing
    today = t.isoformat()
    done = run_ = late = crtd = 0
    for o in conn.execute("SELECT stat, gltrp FROM orders WHERE matnr IS NOT NULL AND matnr<>''"):
        s = (o["stat"] or "CRTD").split()[0]
        if s in ("DLV", "TECO", "CLSD", "CNF"):
            done += 1
        elif s == "CRTD":
            crtd += 1
        elif o["gltrp"] and o["gltrp"] < today:
            late += 1
        else:
            run_ += 1
    n_ord = done + run_ + late + crtd
    prod = dict(total=n_ord, done=done, running=run_, late=late, created=crtd,
                on_track=_pct(done + run_, n_ord) or 0)

    # ---------------------------------------------------------------- quality
    q = conn.execute("SELECT COALESCE(SUM(lmnga),0), COALESCE(SUM(xmnga),0), COUNT(*) FROM confirmation "
                     "WHERE COALESCE(stokz,0) IN (0,'0','')").fetchone()
    inv = P.inventory(conn)
    q_stock = sum(f["value"] for f in inv if f["stock_type"] == "Quality inspection")
    b_stock = sum(f["value"] for f in inv if f["stock_type"] == "Blocked")
    q_lots = len({f["matnr"] for f in inv if f["stock_type"] == "Quality inspection"})
    activity = [dict(text="%s %s" % (r["tcode"] or "", r["bktxt"] or "Material document"), doc=r["mblnr"],
                     date=r["budat"], user=r["usnam"])
                for r in conn.execute("SELECT mblnr, budat, usnam, bktxt, tcode FROM mat_doc ORDER BY cpudt DESC, mblnr DESC "
                                      "LIMIT 4")] if _has_col(conn, "mat_doc", "cpudt") else []
    quality = dict(yield_pct=_pct(q[0], q[0] + q[1]) or 100.0, scrap=q[1] / 1000.0, confirmations=q[2],
                   q_stock=_a(q_stock), blocked=_a(b_stock), q_materials=q_lots, activity=activity)

    # ---------------------------------------------------------------- warehouse
    by_grp = {}
    for f in inv:
        by_grp[f["matkl"] or "#"] = by_grp.get(f["matkl"] or "#", 0) + f["value"]
    grp = sorted(by_grp.items(), key=lambda x: -x[1])[:10]
    low = conn.execute("SELECT COUNT(*) FROM material_plant mp WHERE mp.minbe>0 AND (SELECT COALESCE(SUM(qty),0) FROM quant q "
                       "WHERE q.matnr=mp.matnr AND q.werks=mp.werks AND q.insmk='U') < mp.minbe").fetchone()[0]
    old = sum(f["value"] for f in inv if f["aging"] in ("181-365", ">365"))
    open_cnt = conn.execute("SELECT COUNT(*) FROM inv_doc WHERE status IN ('CRTD','CNTD')").fetchone()[0]
    warehouse = dict(value=_a(sum(f["value"] for f in inv)), groups=[dict(name=k, value=_a(x)) for k, x in grp],
                     materials=len({f["matnr"] for f in inv}), bins=len({(f["werks"], f["lgort"], f["lgpla"]) for f in inv if f["lgpla"] != "#"}),
                     below_reorder=low, old_stock=_a(old), q_blocked=_a(q_stock + b_stock), counts_open=open_cnt)

    # ---------------------------------------------------------------- procurement
    pur = P.purchasing(conn)
    ytd = [f for f in pur if f["month"][:4] == str(y)]
    sp = {}
    for f in ytd:
        sp[f["matkl"]] = sp.get(f["matkl"], 0) + f["ordered"]
    spend = sorted(sp.items(), key=lambda x: -x[1])
    top = spend[:5] + ([("Other", sum(x for _, x in spend[5:]))] if len(spend) > 5 else [])
    this_m = sum(f["ordered"] for f in pur if f["month"] == t.strftime("%Y-%m"))
    prev_key = (t.replace(day=1) - datetime.timedelta(days=1)).strftime("%Y-%m")
    prev_m = sum(f["ordered"] for f in pur if f["month"] == prev_key)
    procurement = dict(spend_ytd=_a(sum(f["ordered"] for f in ytd)), groups=[dict(name=k, value=_a(x)) for k, x in top],
                       open_value=_a(sum(f["open_value"] for f in pur)), open_items=sum(1 for f in pur if f["open_value"] > 0),
                       waiting_release=len({f["vendor"] for f in pur if f["release"] == "Waiting for release"}),
                       change=_pct(this_m - prev_m, prev_m), vendors=len({f["vendor"] for f in ytd}))

    # ---------------------------------------------------------------- sales & CRM
    orders = P.orders(conn)
    sales = P.sales(conn)
    s_by_m = {}
    for f in sales:
        s_by_m[f["month"]] = s_by_m.get(f["month"], 0) + f["net"]
    sales_card = dict(month=_a(s_by_m.get(t.strftime("%Y-%m"), 0)), trend=[_a(s_by_m.get(m, 0)) for m in show],
                      backlog=_a(sum(f["backlog"] for f in orders)), open_orders=len({(f["customer"], f["month"], f["auart"])
                                                                                      for f in orders if f["open_qty"] > 0}),
                      blocked=sum(1 for f in orders if f["credit"] == "Blocked"),
                      customers=len({f["customer"] for f in sales if f["month"][:4] == str(y)}),
                      margin_pct=_pct(sum(f["margin"] for f in sales if f["month"][:4] == str(y)),
                                      sum(f["net"] for f in sales if f["month"][:4] == str(y))))

    # ---------------------------------------------------------------- controlling (cost centers)
    ovh = engine.run(conn, dict(provider="OVH", rows=["cost_center"], year=y, period=p, filters={"category": ["Primary"]},
                                columns=[dict(kf="amount", version="PLAN", time="YTD"), dict(kf="amount", version="ACT", time="YTD")]))
    tot = [r for r in ovh["rows"] if r.get("total")][0]["values"]
    cc = sorted([r for r in ovh["rows"] if not r.get("total")], key=lambda r: -(r["values"][1] or 0))[:4]
    controlling = dict(plan=tot[0], actual=tot[1], ach=_pct(tot[1] or 0, tot[0]),
                       centers=[dict(name=r["labels"][0], plan=r["values"][0], actual=r["values"][1],
                                     ach=_pct(r["values"][1] or 0, r["values"][0])) for r in cc])

    # ---------------------------------------------------------------- tasks
    from sec import inbox
    tasks = [dict(typ=r["typ"], text=r["text"], date=r["date"], tcode=r["tcode"], key=r["key"])
             for r in inbox.inbox(conn, user, everything=everything)][:8]

    return dict(
        date=today, period="%04d/%02d" % (y, p), months=show,
        finance=dict(income_ytd=v["NS"][0], income_plan=v["NS"][1], income_ach=_pct(v["NS"][0] or 0, v["NS"][1]),
                     income_trend=income, bank=_a(bank), receivables=_a(ar), payables=_a(ap), overdue=_a(ar_over)),
        profit=dict(income=v["NS"][0], expenses=round(expenses, 2), profit=v["OP"][0], net=v["NI"][0],
                    margin_pct=_pct(v["OP"][0] or 0, v["NS"][0]), invoices=invoices),
        production=prod, quality=quality, warehouse=warehouse, procurement=procurement, sales=sales_card,
        controlling=controlling,
        analytics=dict(op_ytd=v["OP"][0], gm_pct=_pct(v["GM"][0] or 0, v["NS"][0]), month_sales=v["NS"][2],
                       prev_year=v["NS"][3], op_trend=[op_by_m.get(m, 0) or 0 for m in show]),
        tasks=tasks)


def _has_col(conn, table, col):
    return any(r[1] == col for r in conn.execute("PRAGMA table_info(%s)" % table))
