"""BI dashboards: charts (bars + % line on a second axis) with a key-figure table
below, computed from the info providers. Variables: year, period, display
currency (EGP / USD / EUR at the rate of the period end) and amount scaling."""
import calendar
import datetime

from mm.util import MMError
from mm import util as mmclock

from . import engine, providers as P

SCALES = {"1": "1", "1000": "1,000", "1000000": "1,000,000"}
DASHBOARDS = {"PL_STATUS": "PL Status", "SALES_STATUS": "Sales Status", "INV_STATUS": "Inventory Status",
              "COST_STATUS": "Cost Center Status (primary costs)"}


class _Ctx:
    def __init__(self, conn, q):
        t = mmclock.today()
        self.conn = conn
        self.y = int(q.get("year") or t.year)
        self.p = int(q.get("period") or t.month)
        if not 1 <= self.p <= 12:
            raise MMError("Period must be 1 - 12", "BI", "002")
        self.cur = (q.get("currency") or "EGP").upper()
        self.scale = str(q.get("scale") or "1")
        if self.scale not in SCALES:
            raise MMError("Amount scaling must be 1, 1000 or 1000000", "BI", "012")
        end = datetime.date(self.y, self.p, calendar.monthrange(self.y, self.p)[1])
        self.end = min(end, t).isoformat() if end > t else end.isoformat()
        from fi.document import RATE_SCALE, rate
        self.kurs = rate(conn, self.cur, self.end) if self.cur != "EGP" else RATE_SCALE
        self.RS = RATE_SCALE

    def amt(self, v):
        """engine values are EGP units (already /100) -> currency and scaling."""
        if v is None:
            return None
        return round(v * self.RS / self.kurs / int(self.scale), 2)

    def info(self):
        return {"year": self.y, "period": self.p, "currency": self.cur, "scale": self.scale,
                "note": "Currency: %s, Amount scaling: %s%s" % (self.cur, SCALES[self.scale],
                                                                "" if self.cur == "EGP" else
                                                                " (rate %.4f on %s)" % (self.kurs / self.RS, self.end))}


def _pct(a, b):
    return round(a * 100.0 / b, 1) if a is not None and b else None


def _pl(ctx, columns, year=None):
    res = engine.run(ctx.conn, dict(provider="COPA", structure="PL", year=year or ctx.y, period=ctx.p, columns=columns))
    return {r["node"]: r["values"] for r in res["rows"]}


def _combo(title, cats, bar_name, bars, line_name, line, unit="%"):
    return dict(type="combo", title=title, categories=cats, bars=[dict(name=bar_name, values=bars)],
                line=dict(name=line_name, values=line, unit=unit))


def pl_status(ctx):
    y, p = ctx.y, ctx.p
    cols = [dict(version="PLAN", time="P"), dict(version="ACT", time="P"),
            dict(version="PLAN", time="YTD"), dict(version="ACT", time="YTD"),
            dict(version="PLAN", time="PY"), dict(version="ACT", time="PY")]
    v = _pl(ctx, cols)
    m = "%04d.%02d" % (y, p)
    acc = "%04d.01~%04d.%02d" % (y, y, p)
    py = "%04d.%02d" % (y - 1, p)
    groups = [(m, 0, 1), (acc, 2, 3), (py, 4, 5)]
    rows = []
    for label, node, kind in (("Net Sales", "NS", "amt"), ("Gross Margin", "GM", "amt"), ("Gross Margin(%)", "GM", "pct"),
                              ("Operating Profit", "OP", "amt"), ("Operating Profit(%)", "OP", "pct"),
                              ("Net Profit", "NI", "amt"), ("Net Profit(%)", "NI", "pct")):
        vals = []
        for _, ip, ia in groups:
            if kind == "pct":
                a, b = _pct(v[node][ip], v["NS"][ip]), _pct(v[node][ia], v["NS"][ia])
                vals += [a, b, _pct(b, a) if a and b is not None else None]
            else:
                vals += [ctx.amt(v[node][ip]), ctx.amt(v[node][ia]), _pct(v[node][ia], v[node][ip])]
        rows.append(dict(label=label, values=vals, bold=kind == "amt", kind=kind))
    columns = []
    for g, _, _ in groups:
        columns += [dict(label="%s Plan" % g, group=g, type="amt"), dict(label="%s Actual" % g, group=g, type="amt"),
                    dict(label="%s Ach(%%)" % g, group=g, type="pct")]
    # charts: Pre.Actual / Plan / Actual for the month and accumulated; 3 years actual
    np = lambda a, b: _pct(a, b)  # noqa: E731
    month = _combo("P/L (Current Month)", ["Pre.Actual", "Plan", "Actual"], "Net Sales",
                   [ctx.amt(v["NS"][5]), ctx.amt(v["NS"][0]), ctx.amt(v["NS"][1])], "Net Profit(%)",
                   [np(v["NI"][5], v["NS"][5]), np(v["NI"][0], v["NS"][0]), np(v["NI"][1], v["NS"][1])])
    pyt = _pl(ctx, [dict(version="ACT", time="PYTD")])
    accum = _combo("P/L (Accum. Month)", ["Pre.Actual", "Plan", "Actual"], "Net Sales",
                   [ctx.amt(pyt["NS"][0]), ctx.amt(v["NS"][2]), ctx.amt(v["NS"][3])], "Net Profit(%)",
                   [np(pyt["NI"][0], pyt["NS"][0]), np(v["NI"][2], v["NS"][2]), np(v["NI"][3], v["NS"][3])])
    yrs = [y - 2, y - 1, y]
    yv = []
    for yy in yrs:
        res = engine.run(ctx.conn, dict(provider="COPA", structure="PL", year=yy, period=12 if yy < y else p,
                                        columns=[dict(version="ACT", time="YTD")]))
        yv.append({r["node"]: r["values"] for r in res["rows"]})
    three = _combo("P/L (3 Year)", [str(yy) for yy in yrs], "Net Sales", [ctx.amt(x["NS"][0]) for x in yv],
                   "Net Profit(%)", [np(x["NI"][0], x["NS"][0]) for x in yv])
    return dict(widgets=[month, accum, three], table=dict(title="P/L status", columns=columns, rows=rows),
                drill="CO_PL_DETAIL")


def sales_status(ctx):
    y, p = ctx.y, ctx.p
    facts = [f for f in P.sales(ctx.conn) if f["month"] and f["month"][:4] == str(y) and int(f["month"][5:]) <= p]
    months = ["%04d-%02d" % (y, m) for m in range(max(1, p - 5), p + 1)]
    by_m = {m: [f for f in facts if f["month"] == m] for m in months}
    trend = _combo("Net sales by month", months, "Net Sales", [ctx.amt(sum(f["net"] for f in by_m[m]) / 100.0) for m in months],
                   "Margin(%)", [_pct(sum(f["margin"] for f in by_m[m]), sum(f["net"] for f in by_m[m])) for m in months])

    def by(char, top=None):
        g = {}
        for f in facts:
            k = f.get(char) or "#"
            a = g.setdefault(k, [0, 0])
            a[0] += f["net"]
            a[1] += f["margin"]
        items = sorted(g.items(), key=lambda x: -x[1][0])
        return items[:top] if top else items
    ch = by("vtweg")
    chan = _combo("Net sales by channel (YTD)", [k for k, _ in ch], "Net Sales", [ctx.amt(a[0] / 100.0) for _, a in ch],
                  "Margin(%)", [_pct(a[1], a[0]) for _, a in ch])
    tc = by("customer", 5)
    cust = _combo("Top 5 customers (YTD)", [k for k, _ in tc], "Net Sales", [ctx.amt(a[0] / 100.0) for _, a in tc],
                  "Margin(%)", [_pct(a[1], a[0]) for _, a in tc])
    tot = sum(a[0] for _, a in by("region")) or 0
    rows = [dict(label=k, values=[ctx.amt(a[0] / 100.0), ctx.amt(a[1] / 100.0), _pct(a[1], a[0]), _pct(a[0], tot)], bold=False)
            for k, a in by("region")]
    rows.append(dict(label="Total", values=[ctx.amt(tot / 100.0), ctx.amt(sum(a[1] for _, a in by("region")) / 100.0),
                                            _pct(sum(a[1] for _, a in by("region")), tot), 100.0 if tot else None], bold=True))
    cols = [dict(label="Net sales YTD", type="amt"), dict(label="Gross margin", type="amt"),
            dict(label="Margin(%)", type="pct"), dict(label="Share(%)", type="pct")]
    return dict(widgets=[trend, chan, cust], table=dict(title="Sales by region (year to date)", columns=cols, rows=rows),
                drill="SD_SALES")


def inventory_status(ctx):
    inv = P.inventory(ctx.conn)
    mon = P.inventory_monthly(ctx.conn)
    months = sorted({f["month"] for f in mon})
    total = {m: sum(f["value"] for f in mon if f["month"] == m) for m in months}
    cur_total = sum(f["value"] for f in inv) or 0
    old_now = sum(f["value"] for f in inv if f["aging"] in ("181-365", ">365"))
    trend = _combo("Stock value at month end", months, "Stock value", [ctx.amt(total[m] / 100.0) for m in months],
                   "Change(%)", [None] + [_pct(total[months[i]] - total[months[i - 1]], total[months[i - 1]])
                                          for i in range(1, len(months))])
    buckets = ["0-30", "31-60", "61-90", "91-180", "181-365", ">365"]
    bv = [sum(f["value"] for f in inv if f["aging"] == b) for b in buckets]
    aging = _combo("Stock aging (days since receipt)", buckets, "Stock value", [ctx.amt(x / 100.0) for x in bv],
                   "Share(%)", [_pct(x, cur_total) for x in bv])
    grp = {}
    for f in inv:
        a = grp.setdefault(f["matkl"] or "#", [0, 0])
        a[0] += f["value"]
        a[1] += f["value"] if f["aging"] in ("181-365", ">365") else 0
    gi = sorted(grp.items(), key=lambda x: -x[1][0])[:8]
    group = _combo("Stock by material group", [k for k, _ in gi], "Stock value", [ctx.amt(a[0] / 100.0) for _, a in gi],
                   "Older than 180 days(%)", [_pct(a[1], a[0]) for _, a in gi])
    plants = {}
    for f in inv:
        a = plants.setdefault("%s / %s" % (f["werks"], f["lgort"]), [0, 0, 0])
        a[0] += f["value"]
        a[1] += f["value"] if f["aging"] in ("181-365", ">365") else 0
        a[2] += f["value"] if f["stock_type"] != "Unrestricted" else 0
    rows = [dict(label=k, values=[ctx.amt(a[0] / 100.0), ctx.amt(a[1] / 100.0), _pct(a[1], a[0]), ctx.amt(a[2] / 100.0),
                                  _pct(a[0], cur_total)]) for k, a in sorted(plants.items())]
    rows.append(dict(label="Total", bold=True, values=[ctx.amt(cur_total / 100.0), ctx.amt(old_now / 100.0),
                                                       _pct(old_now, cur_total), ctx.amt(sum(a[2] for a in plants.values()) / 100.0),
                                                       100.0 if cur_total else None]))
    cols = [dict(label="Stock value", type="amt"), dict(label="Older than 180 days", type="amt"),
            dict(label="Old(%)", type="pct"), dict(label="Quality / blocked", type="amt"), dict(label="Share(%)", type="pct")]
    return dict(widgets=[trend, aging, group], table=dict(title="Stock by plant / storage location", columns=cols, rows=rows),
                drill="LO_AGING")


def cost_status(ctx):
    prim = {"category": ["Primary"]}          # primary costs (allocations would net to zero)
    res = engine.run(ctx.conn, dict(provider="OVH", rows=["cost_center"], year=ctx.y, period=ctx.p, filters=prim,
                                    columns=[dict(kf="amount", version="PLAN", time="P"), dict(kf="amount", version="ACT", time="P"),
                                             dict(kf="amount", version="PLAN", time="YTD"), dict(kf="amount", version="ACT", time="YTD")]))
    body = [r for r in res["rows"] if not r.get("total")]
    tot = [r for r in res["rows"] if r.get("total")][0]["values"]
    cc = [r["labels"][0] for r in body]
    w1 = _combo("Cost centers - current month", cc, "Actual", [ctx.amt(r["values"][1]) for r in body], "Ach(%)",
                [_pct(r["values"][1], r["values"][0]) for r in body])
    w2 = _combo("Cost centers - accumulated", cc, "Actual", [ctx.amt(r["values"][3]) for r in body], "Ach(%)",
                [_pct(r["values"][3], r["values"][2]) for r in body])
    tr = engine.run(ctx.conn, dict(provider="OVH", rows=["category"], filters=prim, columns=[dict(kf="amount", version="ACT"),
                                                                             dict(kf="amount", version="PLAN")], colchar="month"))
    months = tr["months"]
    n = len(months)
    tt = [r for r in tr["rows"] if r.get("total")][0]["values"]
    w3 = _combo("Overhead by month (actual vs plan)", months, "Actual", [ctx.amt(x) for x in tt[:n]], "Ach(%)",
                [_pct(tt[i], tt[n + 1 + i]) if len(tt) > n + 1 + i else None for i in range(n)])
    rows = [dict(label=r["labels"][0], values=[ctx.amt(r["values"][0]), ctx.amt(r["values"][1]), _pct(r["values"][1], r["values"][0]),
                                               ctx.amt(r["values"][2]), ctx.amt(r["values"][3]), _pct(r["values"][3], r["values"][2])])
            for r in body]
    rows.append(dict(label="Total", bold=True, values=[ctx.amt(tot[0]), ctx.amt(tot[1]), _pct(tot[1], tot[0]),
                                                       ctx.amt(tot[2]), ctx.amt(tot[3]), _pct(tot[3], tot[2])]))
    g1, g2 = "%04d.%02d" % (ctx.y, ctx.p), "%04d.01~%04d.%02d" % (ctx.y, ctx.y, ctx.p)
    cols = [dict(label="%s Plan" % g1, group=g1, type="amt"), dict(label="%s Actual" % g1, group=g1, type="amt"),
            dict(label="%s Ach(%%)" % g1, group=g1, type="pct"), dict(label="%s Plan" % g2, group=g2, type="amt"),
            dict(label="%s Actual" % g2, group=g2, type="amt"), dict(label="%s Ach(%%)" % g2, group=g2, type="pct")]
    return dict(widgets=[w1, w2, w3], table=dict(title="Cost centers plan / actual", columns=cols, rows=rows), drill="CO_OVH")


_FN = {"PL_STATUS": pl_status, "SALES_STATUS": sales_status, "INV_STATUS": inventory_status, "COST_STATUS": cost_status}


def run(conn, did, q):
    fn = _FN.get((did or "").upper())
    if not fn:
        raise MMError("Dashboard %s does not exist" % did, "BI", "008")
    ctx = _Ctx(conn, q)
    out = fn(ctx)
    out.update(ctx.info(), id=did.upper(), title=DASHBOARDS[did.upper()])
    return out
