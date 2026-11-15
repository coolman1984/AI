"""ZSD_BOARD sales status board (TV screen for the sales department).

Per product, grouped by material group, for the month of the selected day:
  PLAN     sales plan of the month (CO-PA plan, KE11)
  TARGET   the part of the plan that should be reached by the selected day
           (plan x elapsed share of the month)
  ACTUAL   sales of the month up to the day (CO-PA actual, from the billing documents)
  DIFF     ACTUAL - TARGET;  ACH % = ACTUAL / TARGET
  TODAY    sales of the selected day
  BACKLOG  open sales orders not yet delivered (value)
Top customers of the month with their open orders and overdue receivables, then the panels:
orders, deliveries, credit, receivables aging, returns & complaints and e-invoices.
All values in EGP cents.
"""
import calendar
import datetime

from mm import util as clock
from mm.util import parse_date, rdiv


def _month(day):
    first = day.replace(day=1)
    last = day.replace(day=calendar.monthrange(day.year, day.month)[1])
    return first, last


def _backlog(conn):
    """open (not delivered) value per sales order item of standard orders"""
    out = {}
    for r in conn.execute("SELECT p.vbeln, p.posnr, p.matnr, p.kwmeng, p.netwr, k.kunnr FROM sd_vbap p JOIN sd_vbak k "
                          "ON k.vbeln=p.vbeln WHERE k.vbtyp='C' AND k.gbstk<>'C' AND COALESCE(p.abgru,'')='' "
                          "AND p.kwmeng>0"):
        done = conn.execute("SELECT COALESCE(SUM(i.lfimg),0) FROM sd_lips i JOIN sd_likp h ON h.vbeln=i.vbeln "
                            "WHERE i.vgbel=? AND i.vgpos=? AND h.wbstk='C'", (r["vbeln"], r["posnr"])).fetchone()[0]
        open_q = max(0, r["kwmeng"] - done)
        if open_q:
            out[(r["vbeln"], r["posnr"])] = dict(matnr=r["matnr"], kunnr=r["kunnr"], qty=open_q,
                                                 value=rdiv(r["netwr"] * open_q, r["kwmeng"]))
    return out


def board(conn, datum=None, now=None):
    now = now or clock.now()
    if isinstance(now, str):
        now = datetime.datetime.fromisoformat(now)
    datum = parse_date(datum) if datum else now.date().isoformat()
    day = datetime.date.fromisoformat(datum)
    first, last = _month(day)
    share = day.day / float(last.day)                         # elapsed share of the month (end of the day)
    y, m = day.year, day.month
    a, d = first.isoformat(), datum
    backlog = _backlog(conn)
    # ---------------------------------------------------------------- products
    prods = {}

    def row(matnr):
        if matnr not in prods:
            mt = conn.execute("SELECT maktx, matkl FROM material WHERE matnr=?", (matnr,)).fetchone()
            prods[matnr] = dict(matnr=matnr, maktx=mt["maktx"] if mt else "", matkl=(mt["matkl"] if mt else "") or "-",
                                plan=0, plan_qty=0, actual=0, qty=0, today=0, backlog=0)
        return prods[matnr]
    for r in conn.execute("SELECT matnr, SUM(vv010) v, SUM(qty) q FROM copa_item WHERE plikz=1 AND gjahr=? AND perio=? "
                          "AND matnr IS NOT NULL GROUP BY matnr", (y, m)):
        x = row(r["matnr"])
        x["plan"], x["plan_qty"] = r["v"], r["q"]
    for r in conn.execute("SELECT matnr, SUM(vv010) v, SUM(qty) q, SUM(CASE WHEN budat=? THEN vv010 ELSE 0 END) t "
                          "FROM copa_item WHERE plikz=0 AND budat BETWEEN ? AND ? AND matnr IS NOT NULL "
                          "GROUP BY matnr", (d, a, d)):
        if r["v"] or r["t"]:
            x = row(r["matnr"])
            x["actual"], x["qty"], x["today"] = r["v"], r["q"], r["t"]
    for b in backlog.values():
        if b["matnr"]:
            row(b["matnr"])["backlog"] += b["value"]
    groups = {}
    for x in prods.values():
        x["target"] = int(round(x["plan"] * share))
        x["diff"] = x["actual"] - x["target"]
        x["ach"] = round(x["actual"] * 100.0 / x["target"], 1) if x["target"] else None
        x["status"] = "none" if not x["plan"] else "ahead" if x["actual"] >= x["target"] else "behind"
        if x["plan"] or x["actual"] or x["today"] or x["backlog"]:
            groups.setdefault(x["matkl"], []).append(x)

    def total(rows):
        t = {k: sum(r[k] for r in rows) for k in ("plan", "target", "actual", "today", "backlog")}
        t["diff"] = t["actual"] - t["target"]
        t["ach"] = round(t["actual"] * 100.0 / t["target"], 1) if t["target"] else None
        t["lines"], t["ahead"] = len(rows), sum(1 for r in rows if r["status"] == "ahead")
        return t
    out_groups = [dict(area=g, lines=sorted(rows, key=lambda r: -r["plan"] - r["actual"]), total=total(rows))
                  for g, rows in sorted(groups.items(), key=lambda kv: -sum(r["plan"] + r["actual"] for r in kv[1]))]
    allrows = [r for g in out_groups for r in g["lines"]]
    # ---------------------------------------------------------------- customers
    from fi.reports import aging
    ag = {r["partner"]: r for r in aging(conn, "D", datum)["rows"]}
    cust = {}
    for r in conn.execute("SELECT kunnr, SUM(vv010) v FROM copa_item WHERE plikz=0 AND budat BETWEEN ? AND ? "
                          "AND kunnr IS NOT NULL GROUP BY kunnr", (a, d)):
        cust[r["kunnr"]] = dict(kunnr=r["kunnr"], sales=r["v"], backlog=0)
    for b in backlog.values():
        cust.setdefault(b["kunnr"], dict(kunnr=b["kunnr"], sales=0, backlog=0))["backlog"] += b["value"]
    customers = []
    for c in cust.values():
        n = conn.execute("SELECT name FROM customer WHERE kunnr=?", (c["kunnr"],)).fetchone()
        g = ag.get(c["kunnr"], {})
        c["name"] = n["name"] if n else ""
        c["receivable"] = int(round((g.get("total") or 0) * 100))
        c["overdue"] = int(round(sum(g.get(k) or 0 for k in ("d30", "d60", "d90", "d90p")) * 100))
        c["blocked"] = conn.execute("SELECT COUNT(*) FROM sd_vbak WHERE kunnr=? AND cmgst='B'", (c["kunnr"],)).fetchone()[0]
        customers.append(c)
    customers.sort(key=lambda c: -(c["sales"] + c["backlog"]))
    # ---------------------------------------------------------------- panels
    w1 = (day - datetime.timedelta(days=day.weekday())).isoformat()
    one = lambda sql, *p: conn.execute(sql, p).fetchone()                     # noqa: E731
    orders = dict(
        today=dict(zip(("count", "value"), one("SELECT COUNT(*), COALESCE(SUM(netwr),0) FROM sd_vbak WHERE vbtyp='C' "
                                               "AND audat=?", d))),
        week=dict(zip(("count", "value"), one("SELECT COUNT(*), COALESCE(SUM(netwr),0) FROM sd_vbak WHERE vbtyp='C' "
                                              "AND audat BETWEEN ? AND ?", w1, d))),
        month=dict(zip(("count", "value"), one("SELECT COUNT(*), COALESCE(SUM(netwr),0) FROM sd_vbak WHERE vbtyp='C' "
                                               "AND audat BETWEEN ? AND ?", a, d))),
        quotations=dict(zip(("count", "value"), one("SELECT COUNT(*), COALESCE(SUM(netwr),0) FROM sd_vbak WHERE "
                                                    "vbtyp='B' AND gbstk<>'C'"))),
        backlog=sum(b["value"] for b in backlog.values()))
    deliveries = dict(
        due=one("SELECT COUNT(*) FROM sd_likp WHERE wbstk<>'C' AND wadat=?", d)[0],
        late=one("SELECT COUNT(*) FROM sd_likp WHERE wbstk<>'C' AND wadat<?", d)[0],
        shipped=one("SELECT COUNT(*) FROM sd_likp WHERE wbstk='C' AND COALESCE(wadat_ist,wadat)=?", d)[0],
        to_bill=one("SELECT COUNT(*) FROM sd_likp WHERE wbstk='C' AND fkstk<>'C'")[0])
    credit = dict(zip(("count", "value"), one("SELECT COUNT(*), COALESCE(SUM(netwr),0) FROM sd_vbak WHERE cmgst='B'")))
    buckets = {k: 0 for k in ("not_due", "d30", "d60", "d90", "d90p")}
    for g in ag.values():
        for k in buckets:
            buckets[k] += int(round((g.get(k) or 0) * 100))
    returns = dict(
        month=dict(zip(("count", "value"), one("SELECT COUNT(*), COALESCE(SUM(netwr),0) FROM sd_vbak WHERE vbtyp='H' "
                                               "AND audat BETWEEN ? AND ?", a, d))),
        complaints=one("SELECT COUNT(*) FROM sd_qmel WHERE status<>'NOCO'")[0],
        credit_memos=dict(zip(("count", "value"), one(
            "SELECT COUNT(*), COALESCE(-SUM(netwr),0) FROM billing WHERE cancelled=0 AND netwr<0 AND fkdat "
            "BETWEEN ? AND ?", a, d))))
    einv = [dict(status=r[0] or "Not generated", count=r[1]) for r in conn.execute(
        "SELECT e.status, COUNT(*) FROM billing b LEFT JOIN sd_einv e ON e.vbeln=b.vbeln WHERE b.cancelled=0 AND "
        "b.fkdat BETWEEN ? AND ? GROUP BY e.status ORDER BY 2 DESC", (a, d))]
    lastd = one("SELECT MAX(fkdat) FROM billing WHERE fkdat<=? AND cancelled=0", now.date().isoformat())[0]
    return {"datum": datum, "now": now.isoformat(timespec="seconds"), "month": first.strftime("%m/%Y"),
            "share": round(share * 100, 1), "groups": out_groups, "total": total(allrows) if allrows else None,
            "customers": customers[:10], "orders": orders, "deliveries": deliveries, "credit": credit,
            "aging": buckets, "returns": returns, "einvoice": einv, "last_day": lastd}
