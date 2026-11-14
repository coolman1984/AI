"""E-1 ZCO_SIM - profit simulation ("what if"): the P&L of a year / period range (actual or
plan CO-PA) recalculated with changed drivers, without posting anything.

  price %      sales prices         -> gross sales and sales deductions
  volume %     sold quantity        -> sales, deductions and the variable costs
  material %   material prices      -> direct material costs (and material overhead)
  labor %      wages / salaries     -> labor costs
  overhead %   fixed overheads      -> production overhead, sales and administration costs
Fixed costs do not move with the volume. Values in currency units.
"""
from mm.util import MMError, parse_int, parse_pct

LINES = [
    ("GS", "Gross sales", "s"), ("SD", "Sales deductions", "s"), ("NS", "Net sales", "t"),
    ("MAT", "Material costs", "c"), ("LAB", "Labor costs", "c"), ("MAC", "Machine costs", "c"),
    ("MOH", "Production overhead", "c"), ("COGS", "Cost of goods sold", "t"), ("GM", "Gross margin", "t"),
    ("VAR", "Production variances / absorption", "c"), ("SEX", "Sales & marketing costs", "c"),
    ("AEX", "Administration costs", "c"), ("OP", "Operating profit", "t"),
]


def _f(q, key):
    v = q.get(key)
    if v in (None, ""):
        return 1.0
    return 1 + parse_pct(v) / 10000.0


def run(conn, q):
    gjahr = parse_int(q.get("gjahr"), "fiscal year", 2000, 2100)
    pfrom = parse_int(q.get("pfrom") or 1, "period from", 1, 12)
    pto = parse_int(q.get("pto") or 12, "period to", 1, 12)
    if pto < pfrom:
        raise MMError("Period to is before period from", "KE", "301")
    plikz = 1 if str(q.get("version") or "ACT").upper() == "PLAN" else 0
    r = conn.execute("SELECT " + ",".join("COALESCE(SUM(vv%s),0)" % k for k in (
        "010", "020", "030", "040", "050", "051", "060", "061", "070", "080", "090", "100", "110")) +
        " FROM copa_item WHERE plikz=? AND gjahr=? AND perio BETWEEN ? AND ?", (plikz, gjahr, pfrom, pto)).fetchone()
    v = dict(zip(("010", "020", "030", "040", "050", "051", "060", "061", "070", "080", "090", "100", "110"),
                 [x / 100.0 for x in r]))
    p, vol, m, lab, oh = (_f(q, k) for k in ("price", "volume", "material", "labor", "overhead"))

    def calc(p, vol, m, lab, oh):
        x = {"GS": v["010"] * p * vol, "SD": v["020"] * p * vol,
             "MAT": (v["030"] + v["040"]) * vol * m, "LAB": v["050"] * vol * lab + v["051"] * lab,
             "MAC": v["060"] * vol + v["061"], "MOH": v["070"] * oh, "VAR": v["080"] + v["090"],
             "SEX": v["100"] * oh, "AEX": v["110"] * oh}
        x["NS"] = x["GS"] - x["SD"]
        x["COGS"] = x["MAT"] + x["LAB"] + x["MAC"] + x["MOH"]
        x["GM"] = x["NS"] - x["COGS"]
        x["OP"] = x["GM"] - x["VAR"] - x["SEX"] - x["AEX"]
        return x
    base, sim = calc(1, 1, 1, 1, 1), calc(p, vol, m, lab, oh)
    rows = []
    for node, text, kind in LINES:
        b, s = round(base[node], 2), round(sim[node], 2)
        rows.append(dict(node=node, text=text, kind=kind, base=b, sim=s, diff=round(s - b, 2),
                         pct=round((s - b) * 100.0 / abs(b), 1) if b else None))
    margin = lambda x: round(x["OP"] * 100.0 / x["NS"], 1) if x["NS"] else None        # noqa: E731
    # volume at which the simulated operating profit is zero (contribution margin view)
    variable = (v["030"] + v["040"]) * m + v["050"] * lab + v["060"]
    contrib = (v["010"] - v["020"]) * p - variable
    fixed = contrib * vol - sim["OP"]                    # OP = contribution x volume - fixed costs
    breakeven = round(fixed * 100.0 / contrib, 2) if contrib > 0 else None
    return {"gjahr": gjahr, "pfrom": pfrom, "pto": pto, "version": "PLAN" if plikz else "ACT", "rows": rows,
            "drivers": {k: q.get(k) or "0" for k in ("price", "volume", "material", "labor", "overhead")},
            "margin_base": margin(base), "margin_sim": margin(sim),
            "breakeven_volume_pct": breakeven,
            "message": "Operating profit %s -> %s (%s)" % (
                "{:,.2f}".format(base["OP"]), "{:,.2f}".format(sim["OP"]),
                ("%+.1f %%" % ((sim["OP"] - base["OP"]) * 100.0 / abs(base["OP"]))) if base["OP"] else "-")}
