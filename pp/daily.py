"""Daily meeting boards of the factory (TV screens next to ZPP_BOARD, same dark style).

ZPP_DM_INHOUSE  in-house production per line: plan of the day, yield today / D-1 / month,
                scrap, achievement; share of in-house vs subcontracted output.
ZPP_DM_PENDING  production orders not yet delivered: late, due today, next days, components short.
ZPP_DM_OQC      outgoing quality: finished goods waiting in quality inspection / lots from
                production orders, decisions of the day.
ZPP_DM_PDEFECT  production defects: scrap per line (today, D-1, week, month), defect %,
                scrap reasons (Pareto), internal non-conformances, rework orders.
ZPP_DM_MDEFECT  material defects: incoming lots rejected per vendor, defect codes, vendor
                complaints, returns to vendors.
ZPP_DM_MLOSS    material loss: component consumption above the standard per order, physical
                inventory differences and scrapping in the month (value).
ZPP_DM_SCRAP    pending scrap: blocked (defective) stock waiting for disposal, value and age.
Quantities in milli, values in cents.
"""
import datetime

from mm import util as clock
from mm.board import _price
from mm.util import parse_date, rdiv, value_of

from .config import SCRAP_REASONS


def _days(datum):
    day = datetime.date.fromisoformat(parse_date(datum) if datum else clock.today().isoformat())
    return day, day.isoformat(), (day - datetime.timedelta(days=1)).isoformat(), \
        (day - datetime.timedelta(days=day.weekday())).isoformat(), day.replace(day=1).isoformat()


def _pct(a, b):
    return round(100.0 * a / b, 1) if b else None


def _line_of_order(conn, aufnr):
    r = conn.execute("SELECT arbpl FROM pp_oper WHERE aufnr=? ORDER BY vornr DESC", (aufnr,)).fetchone()
    return r["arbpl"] if r else ""


def last_day(conn, datum):
    r = conn.execute("SELECT MAX(budat) FROM confirmation WHERE stokz=0 AND budat<=?", (datum,)).fetchone()
    return r[0] if r else None


# ------------------------------------------------------------------ in-house production
def inhouse(conn, datum=None):
    day, d0, d1, wk, mon = _days(datum)

    def conf(arbpl, a, b):
        r = conn.execute("SELECT COALESCE(SUM(lmnga),0) y, COALESCE(SUM(xmnga),0) s FROM confirmation WHERE stokz=0 "
                         "AND aueru=1 AND arbpl=? AND budat BETWEEN ? AND ?", (arbpl, a, b)).fetchone()
        return r["y"], r["s"]
    groups = {}
    for wc in conn.execute("SELECT * FROM work_center ORDER BY area, arbpl").fetchall():
        plan = conn.execute("SELECT COALESCE(SUM(plan),0) FROM pp_lineplan WHERE datum=? AND arbpl=?",
                            (d0, wc["arbpl"])).fetchone()[0]
        today, ts = conf(wc["arbpl"], d0, d0)
        y1, _ = conf(wc["arbpl"], d1, d1)
        ym, sm = conf(wc["arbpl"], mon, d0)
        orders = conn.execute("SELECT COUNT(DISTINCT o.aufnr) FROM orders o JOIN pp_oper p ON p.aufnr=o.aufnr WHERE "
                              "p.arbpl=? AND o.stat IN ('REL','DLV') AND o.wemng<o.gamng", (wc["arbpl"],)).fetchone()[0]
        g = groups.setdefault(wc["area"] or "PRODUCTION", [])
        g.append(dict(arbpl=wc["arbpl"], ktext=wc["ktext"], plan=plan, today=today, diff=today - plan if plan else 0,
                      ach=_pct(today, plan), d1=y1, month=ym, scrap=sm, defect=_pct(sm, ym + sm) or 0.0,
                      orders=orders, status="ahead" if plan and today >= plan else "behind" if plan else "none"))
    out = []
    for area, lines in groups.items():
        t = {k: sum(x[k] for x in lines) for k in ("plan", "today", "d1", "month", "scrap", "orders")}
        t.update(diff=t["today"] - t["plan"] if t["plan"] else 0, ach=_pct(t["today"], t["plan"]),
                 defect=_pct(t["scrap"], t["month"] + t["scrap"]) or 0.0, lines=len(lines),
                 running=sum(1 for x in lines if x["today"]))
        out.append(dict(area=area, lines=lines, total=t))
    inh = sum(x["total"]["month"] for x in out)
    sub = conn.execute("SELECT COALESCE(SUM(i.menge),0) FROM mat_doc_item i JOIN mat_doc h ON h.mblnr=i.mblnr AND "
                       "h.mjahr=i.mjahr JOIN po_item p ON p.ebeln=i.ebeln AND p.ebelp=i.ebelp WHERE p.pstyp='L' AND "
                       "i.bwart='101' AND i.canceled=0 AND h.budat BETWEEN ? AND ?", (mon, d0)).fetchone()[0]
    sub_open = conn.execute("SELECT COALESCE(SUM(menge-wemng),0), COUNT(*) FROM po_item WHERE pstyp='L' AND "
                            "COALESCE(loekz,0)=0 AND COALESCE(elikz,0)=0 AND menge>wemng").fetchone()
    return dict(datum=d0, groups=out, inhouse=inh, subcon=sub, inhouse_share=_pct(inh, inh + sub),
                subcon_open=sub_open[0], subcon_items=sub_open[1], last_day=last_day(conn, d0))


# ------------------------------------------------------------------ production pending
def pending(conn, datum=None):
    day, d0, *_ = _days(datum)
    rows = []
    for o in conn.execute("SELECT o.*, m.maktx FROM orders o LEFT JOIN material m ON m.matnr=o.matnr WHERE "
                          "o.stat IN ('CRTD','REL','DLV') AND o.gamng>o.wemng AND o.auart NOT IN ('ZINT') "
                          "ORDER BY o.gltrp, o.aufnr").fetchall():
        due = o["gltrp"] or o["gstrp"] or d0
        late = (day - datetime.date.fromisoformat(due)).days
        short = conn.execute("SELECT COUNT(*) FROM pp_resb r WHERE r.aufnr=? AND COALESCE(r.xloek,0)=0 AND "
                             "COALESCE(r.kzear,0)=0 AND r.bdmng>r.enmng AND (SELECT COALESCE(SUM(qty),0) FROM quant q "
                             "WHERE q.matnr=r.matnr AND q.werks=r.werks AND q.insmk='U') < r.bdmng-r.enmng",
                             (o["aufnr"],)).fetchone()[0]
        rows.append(dict(aufnr=o["aufnr"], auart=o["auart"], matnr=o["matnr"], maktx=o["maktx"] or o["ktext"],
                         line=_line_of_order(conn, o["aufnr"]), stat=o["stat"], start=o["gstrp"], due=due,
                         planned=o["gamng"], done=o["wemng"], pending=o["gamng"] - o["wemng"],
                         progress=_pct(o["wemng"], o["gamng"]) or 0.0, late=max(late, 0), short=short,
                         bucket="late" if late > 0 else "today" if late == 0 else "next"))
    b = {k: [r for r in rows if r["bucket"] == k] for k in ("late", "today", "next")}
    return dict(datum=d0, rows=rows, late=len(b["late"]), today=len(b["today"]), next=len(b["next"]),
                pending_qty=sum(r["pending"] for r in rows), short_orders=sum(1 for r in rows if r["short"]),
                not_released=sum(1 for r in rows if r["stat"] == "CRTD"), last_day=last_day(conn, d0))


# ------------------------------------------------------------------ outgoing quality (OQC)
def oqc(conn, datum=None):
    day, d0, d1, wk, mon = _days(datum)
    cache = {}
    stock = []
    for q in conn.execute("SELECT q.matnr, m.maktx, m.mtart, q.werks, q.lgort, q.insmk, SUM(q.qty) qty, MIN(q.wdatu) "
                          "since FROM quant q JOIN material m ON m.matnr=q.matnr WHERE q.insmk='Q' AND q.qty>0 AND "
                          "m.mtart IN ('FERT','HALB') GROUP BY q.matnr, q.werks, q.lgort", ()):
        p, pe = _price(conn, q["matnr"], q["werks"], cache)
        lot = conn.execute("SELECT MIN(created) FROM qm_lot WHERE matnr=? AND werks=? AND lgort=? AND status IN "
                           "('OPEN','RESULTS')", (q["matnr"], q["werks"], q["lgort"])).fetchone()[0]
        since = lot or q["since"]                   # waiting since the inspection lot, else since the receipt
        stock.append(dict(matnr=q["matnr"], maktx=q["maktx"], lgort=q["lgort"], qty=q["qty"],
                          value=value_of(q["qty"], p, pe), since=since,
                          age=max(0, (day - datetime.date.fromisoformat(since)).days)))
    lots = [dict(r, age=max(0, (day - datetime.date.fromisoformat(r["created"])).days)) for r in conn.execute(
        "SELECT l.prueflos, l.matnr, m.maktx, l.qty, l.aufnr, l.created, l.status FROM qm_lot l LEFT JOIN material m ON "
        "m.matnr=l.matnr WHERE l.status IN ('OPEN','RESULTS') AND (l.origin='04' OR m.mtart IN ('FERT','HALB')) "
        "ORDER BY l.created")]
    dec = conn.execute("SELECT COUNT(*) n, SUM(ud_code='A') a, COALESCE(SUM(qty_ok),0) ok, COALESCE(SUM(qty_rej),0) rej "
                       "FROM qm_lot WHERE status='UD' AND ud_date=? AND origin='04'", (d0,)).fetchone()
    mdec = conn.execute("SELECT COUNT(*) n, COALESCE(SUM(qty),0) q, COALESCE(SUM(qty_rej),0) rej FROM qm_lot WHERE "
                        "status='UD' AND origin='04' AND ud_date BETWEEN ? AND ?", (mon, d0)).fetchone()
    blocked_fg = sum(value_of(q["qty"], *_price(conn, q["matnr"], q["werks"], cache)) for q in conn.execute(
        "SELECT q.matnr, q.werks, SUM(q.qty) qty FROM quant q JOIN material m ON m.matnr=q.matnr WHERE q.insmk='B' AND "
        "q.qty>0 AND m.mtart IN ('FERT','HALB') GROUP BY q.matnr, q.werks"))
    return dict(datum=d0, stock=stock, stock_qty=sum(s["qty"] for s in stock), stock_value=sum(s["value"] for s in stock),
                lots=lots, today=dict(lots=dec["n"] or 0, ok=dec["ok"], rej=dec["rej"]),
                month=dict(lots=mdec["n"] or 0, ppm=round(mdec["rej"] * 1000000 / mdec["q"]) if mdec["q"] else 0),
                blocked_fg=blocked_fg, last_day=last_day(conn, d0))


# ------------------------------------------------------------------ production defects
def pdefect(conn, datum=None):
    day, d0, d1, wk, mon = _days(datum)

    def s(arbpl, a, b):
        r = conn.execute("SELECT COALESCE(SUM(xmnga),0) s, COALESCE(SUM(lmnga),0) y FROM confirmation WHERE stokz=0 "
                         "AND arbpl=? AND budat BETWEEN ? AND ?", (arbpl, a, b)).fetchone()
        return r["s"], r["y"]
    lines = []
    for wc in conn.execute("SELECT * FROM work_center ORDER BY area, arbpl"):
        t, ty = s(wc["arbpl"], d0, d0)
        y1, _ = s(wc["arbpl"], d1, d1)
        w, _ = s(wc["arbpl"], wk, d0)
        m, my = s(wc["arbpl"], mon, d0)
        lines.append(dict(arbpl=wc["arbpl"], ktext=wc["ktext"], area=wc["area"] or "", today=t, today_pct=_pct(t, t + ty),
                          d1=y1, week=w, month=m, month_pct=_pct(m, m + my), good=my))
    pareto = [dict(grund=r["grund"] or "--", text=SCRAP_REASONS.get(r["grund"], "No reason given"), qty=r["q"],
                   count=r["n"]) for r in conn.execute(
        "SELECT grund, SUM(xmnga) q, COUNT(*) n FROM confirmation WHERE stokz=0 AND xmnga>0 AND budat BETWEEN ? AND ? "
        "GROUP BY grund ORDER BY q DESC", (mon, d0))]
    ncr = [dict(r) for r in conn.execute("SELECT qmnum, matnr, text, defect, created, status FROM qm_notif WHERE "
                                         "qmart='Q3' AND status<>'CLOSED' ORDER BY created DESC")]
    rework = conn.execute("SELECT COUNT(*) FROM orders WHERE auart IN ('ZREF','ZP03') AND stat IN ('CRTD','REL','DLV') "
                          "AND wemng<gamng").fetchone()[0]
    tm = sum(x["month"] for x in lines)
    return dict(datum=d0, lines=lines, pareto=pareto, ncr=ncr, rework=rework, month=tm,
                month_pct=_pct(tm, tm + sum(x["good"] for x in lines)), today=sum(x["today"] for x in lines),
                last_day=last_day(conn, d0))


# ------------------------------------------------------------------ material defects (incoming)
def mdefect(conn, datum=None):
    day, d0, d1, wk, mon = _days(datum)
    vendors = []
    for r in conn.execute("SELECT l.lifnr, v.name, COUNT(*) lots, SUM(l.qty_rej>0) bad, SUM(l.qty) q, SUM(l.qty_rej) rej "
                          "FROM qm_lot l LEFT JOIN vendor v ON v.lifnr=l.lifnr WHERE l.status='UD' AND l.origin='01' AND "
                          "l.ud_date BETWEEN ? AND ? GROUP BY l.lifnr ORDER BY rej DESC", (mon, d0)):
        vendors.append(dict(lifnr=r["lifnr"], name=r["name"], lots=r["lots"], bad=r["bad"], qty=r["q"], rej=r["rej"],
                            ppm=round(r["rej"] * 1000000 / r["q"]) if r["q"] else 0))
    codes = [dict(code=r["code"], qty=r["q"], count=r["n"]) for r in conn.execute(
        "SELECT d.code, SUM(d.qty) q, COUNT(*) n FROM qm_defect d JOIN qm_lot l ON l.prueflos=d.prueflos WHERE "
        "l.origin='01' AND l.ud_date BETWEEN ? AND ? GROUP BY d.code ORDER BY q DESC", (mon, d0))]
    from qm.quality import DEFECTS
    for c in codes:
        c["text"] = DEFECTS.get(c["code"], c["code"])
    complaints = [dict(r) for r in conn.execute(
        "SELECT n.qmnum, n.lifnr, v.name, n.matnr, n.qty, n.text, n.due, n.status FROM qm_notif n LEFT JOIN vendor v ON "
        "v.lifnr=n.lifnr WHERE n.qmart='Q2' AND n.status<>'CLOSED' ORDER BY n.due")]
    ret = conn.execute("SELECT COUNT(*), COALESCE(SUM(i.dmbtr),0) FROM mat_doc_item i JOIN mat_doc h ON h.mblnr=i.mblnr "
                       "AND h.mjahr=i.mjahr WHERE i.bwart='122' AND i.canceled=0 AND h.budat BETWEEN ? AND ?",
                       (mon, d0)).fetchone()
    cache = {}
    blocked = sum(value_of(q["qty"], *_price(conn, q["matnr"], q["werks"], cache)) for q in conn.execute(
        "SELECT q.matnr, q.werks, SUM(q.qty) qty FROM quant q JOIN material m ON m.matnr=q.matnr WHERE q.insmk='B' AND "
        "q.qty>0 AND m.mtart NOT IN ('FERT','HALB') GROUP BY q.matnr, q.werks"))
    t_q, t_r = sum(v["qty"] for v in vendors), sum(v["rej"] for v in vendors)
    return dict(datum=d0, vendors=vendors, codes=codes, complaints=complaints, returns=ret[0], returns_value=ret[1],
                blocked_value=blocked, ppm=round(t_r * 1000000 / t_q) if t_q else 0,
                open_lots=conn.execute("SELECT COUNT(*) FROM qm_lot WHERE origin='01' AND status IN ('OPEN','RESULTS')").fetchone()[0],
                last_day=last_day(conn, d0))


# ------------------------------------------------------------------ material loss
def mloss(conn, datum=None):
    day, d0, d1, wk, mon = _days(datum)
    cache = {}
    rows = []
    for o in conn.execute("SELECT DISTINCT o.* FROM orders o JOIN confirmation c ON c.aufnr=o.aufnr WHERE c.stokz=0 AND "
                          "c.budat BETWEEN ? AND ? AND o.gamng>0", (mon, d0)).fetchall():
        made = conn.execute("SELECT COALESCE(SUM(lmnga+xmnga),0) FROM confirmation WHERE aufnr=? AND stokz=0 AND aueru=1",
                            (o["aufnr"],)).fetchone()[0] or o["wemng"]
        for r in conn.execute("SELECT matnr, werks, SUM(bdmng) bd, SUM(enmng) en FROM pp_resb WHERE aufnr=? AND "
                              "COALESCE(xloek,0)=0 GROUP BY matnr, werks", (o["aufnr"],)):
            std = rdiv(r["bd"] * min(made, o["gamng"]), o["gamng"]) if made else 0
            over = r["en"] - std
            if std <= 0 or over <= 0:
                continue
            p, pe = _price(conn, r["matnr"], r["werks"], cache)
            rows.append(dict(aufnr=o["aufnr"], line=_line_of_order(conn, o["aufnr"]), matnr=r["matnr"], std=std,
                             actual=r["en"], over=over, pct=_pct(over, std), value=value_of(over, p, pe)))
    rows.sort(key=lambda r: -r["value"])

    def mv(bwarts):
        r = conn.execute("SELECT COUNT(*), COALESCE(SUM(CASE WHEN i.shkzg='H' THEN i.dmbtr ELSE -i.dmbtr END),0) FROM "
                         "mat_doc_item i JOIN mat_doc h ON h.mblnr=i.mblnr AND h.mjahr=i.mjahr WHERE i.bwart IN (%s) AND "
                         "i.canceled=0 AND h.budat BETWEEN ? AND ?" % ",".join("'%s'" % b for b in bwarts),
                         (mon, d0)).fetchone()
        return r[0], r[1]
    inv_n, inv_v = mv(("701", "702"))
    scr_n, scr_v = mv(("551", "552"))
    usage = sum(r["value"] for r in rows)
    return dict(datum=d0, rows=rows[:30], usage_value=usage, inv_docs=inv_n, inv_value=inv_v, scrap_docs=scr_n,
                scrap_value=scr_v, total=usage + max(inv_v, 0) + scr_v, last_day=last_day(conn, d0))


# ------------------------------------------------------------------ pending scrap
def pending_scrap(conn, datum=None):
    day, d0, d1, wk, mon = _days(datum)
    cache = {}
    rows = []
    for q in conn.execute("SELECT q.matnr, m.maktx, m.mtart, q.werks, q.lgort, SUM(q.qty) qty, MIN(q.wdatu) since FROM quant "
                          "q JOIN material m ON m.matnr=q.matnr WHERE q.insmk='B' AND q.qty>0 GROUP BY q.matnr, q.werks, "
                          "q.lgort ORDER BY since"):
        p, pe = _price(conn, q["matnr"], q["werks"], cache)
        age = max(0, (day - datetime.date.fromisoformat(q["since"])).days)
        rows.append(dict(matnr=q["matnr"], maktx=q["maktx"], mtart=q["mtart"], werks=q["werks"], lgort=q["lgort"],
                         qty=q["qty"], value=value_of(q["qty"], p, pe), since=q["since"], age=age,
                         bucket="> 90 days" if age > 90 else "31-90 days" if age > 30 else "0-30 days"))
    aging = {k: sum(r["value"] for r in rows if r["bucket"] == k) for k in ("0-30 days", "31-90 days", "> 90 days")}
    done = conn.execute("SELECT COUNT(*), COALESCE(SUM(i.dmbtr),0) FROM mat_doc_item i JOIN mat_doc h ON h.mblnr=i.mblnr "
                        "AND h.mjahr=i.mjahr WHERE i.bwart='551' AND i.canceled=0 AND h.budat BETWEEN ? AND ?",
                        (mon, d0)).fetchone()
    return dict(datum=d0, rows=rows, qty=sum(r["qty"] for r in rows), value=sum(r["value"] for r in rows), aging=aging,
                scrapped_docs=done[0], scrapped_value=done[1], last_day=last_day(conn, d0))
