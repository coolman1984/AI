"""FI reports.

FS10N / FAGLB03   G/L account balance per period
FBL3N / FBL1N / FBL5N  G/L, vendor, customer line items (open / cleared / all)
S_ALR_87012277    G/L account balances (trial balance)
F.01 / S_ALR_87012284  balance sheet and P&L (financial statement version FSEG)
FK10N / FD10N     vendor / customer balances
S_ALR_87012078 / S_ALR_87012168  vendor / customer due date analysis (aging)
FF7A / FF7B       cash position and liquidity forecast
AR01              asset balances
ZFI_COCKPIT       finance KPIs for management
"""
import calendar
import datetime

from mm.db import rows
from mm.util import amt_out

from .ap import discount_date, open_items
from .config import (ASSET_CLASSES, CHART, FSV_NODES, LOCAL_CURRENCY, PAYMENT_TERMS,
                     TAX_CODES)
from .document import signed, signed_fc
from mm import util as mmclock  # noqa: E402


def _a(c):
    return amt_out(c or 0)


def eop(gjahr, perio):
    return "%04d-%02d-%02d" % (gjahr, perio, calendar.monthrange(gjahr, perio)[1])


def gl_balance(conn, hkont, upto):
    return conn.execute("SELECT COALESCE(SUM(CASE WHEN i.shkzg='S' THEN i.dmbtr ELSE "
                        "-i.dmbtr END),0) FROM acc_doc_item i JOIN acc_doc h ON h.belnr="
                        "i.belnr AND h.gjahr=i.gjahr WHERE i.hkont=? AND h.budat<=?",
                        (hkont, upto)).fetchone()[0]


def _accounts(conn):
    return {r["hkont"]: dict(r) for r in conn.execute("SELECT * FROM gl_account")}


def _sums(conn, d1, d2, by="hkont"):
    out = {}
    for r in conn.execute(
            "SELECT i.%s AS k, SUM(CASE WHEN i.shkzg='S' THEN i.dmbtr ELSE 0 END) AS d, "
            "SUM(CASE WHEN i.shkzg='H' THEN i.dmbtr ELSE 0 END) AS c FROM acc_doc_item i "
            "JOIN acc_doc h ON h.belnr=i.belnr AND h.gjahr=i.gjahr WHERE h.budat BETWEEN ? "
            "AND ? GROUP BY i.%s" % (by, by), (d1, d2)):
        out[r["k"]] = (r["d"] or 0, r["c"] or 0)
    return out


# ---------------------------------------------------------------- FS10N
def account_balance(conn, hkont, gjahr):
    acc = _accounts(conn).get(hkont)
    if not acc:
        from mm.util import MMError
        raise MMError("G/L account %s does not exist" % hkont, "FH", "010")
    carry = gl_balance(conn, hkont, "%04d-12-31" % (gjahr - 1)) if acc["typ"] == "BS" \
        else 0
    out, cum = [dict(perio="Bal.c/f", debit=0, credit=0, balance=_a(carry),
                     cumulative=_a(carry))], carry
    for p in range(1, 13):
        s = _sums(conn, "%04d-%02d-01" % (gjahr, p), eop(gjahr, p)).get(hkont, (0, 0))
        cum += s[0] - s[1]
        out.append(dict(perio=p, debit=_a(s[0]), credit=_a(s[1]), balance=_a(s[0] - s[1]),
                        cumulative=_a(cum)))
    return {"hkont": hkont, "txt": acc["txt"], "typ": acc["typ"], "recon": acc["recon"],
            "oi": acc["oi"], "rows": out, "total": _a(cum)}


# ---------------------------------------------------------------- FBLxN
def line_items(conn, koart, key="", status="open", key_date=None, d1=None, d2=None):
    key_date = key_date or mmclock.today().isoformat()
    sql = ("SELECT i.*, h.blart, h.budat, h.bldat, h.xblnr, h.waers, h.bktxt, h.tcode, "
           "h.stblg FROM acc_doc_item i JOIN acc_doc h ON h.belnr=i.belnr AND "
           "h.gjahr=i.gjahr WHERE 1=1")
    args = []
    if koart == "S":
        if key:
            sql += " AND i.hkont IN (%s)" % ",".join("?" * len(key.split(",")))
            args += [k.strip() for k in key.split(",")]
    else:
        sql += " AND i.koart=?"
        args.append(koart)
        if key:
            sql += " AND %s=?" % ("i.lifnr" if koart == "K" else "i.kunnr")
            args.append(key)
    if status == "open":
        sql += " AND h.budat<=? AND (i.augbl IS NULL OR i.augdt>?)"
        args += [key_date, key_date]
    elif status == "cleared":
        sql += " AND i.augbl IS NOT NULL AND i.augdt<=?"
        args.append(key_date)
    if d1:
        sql += " AND h.budat>=?"
        args.append(d1)
    if d2:
        sql += " AND h.budat<=?"
        args.append(d2)
    names = {}
    for t, k in (("vendor", "lifnr"), ("customer", "kunnr")):
        for r in conn.execute("SELECT %s AS k, name FROM %s" % (k, t)):
            names[r["k"]] = r["name"]
    kd = datetime.date.fromisoformat(key_date)
    out = []
    for r in conn.execute(sql + " ORDER BY h.budat, i.belnr, i.buzei LIMIT 10000", args):
        d = dict(r)
        d["amount"] = _a(signed(r))
        d["amount_fc"] = _a(signed_fc(r))
        d["partner"] = r["lifnr"] or r["kunnr"] or ""
        d["name"] = names.get(d["partner"], "")
        d["txt"] = CHART.get(r["hkont"], ("",))[0]
        d["open"] = not r["augbl"] or (r["augdt"] or "") > key_date
        d["arrears"] = (kd - datetime.date.fromisoformat(r["netdt"])).days \
            if r["netdt"] and d["open"] else None
        d["disc_date"] = discount_date(r) if r["zbd1p"] else None
        d["status"] = "open" if d["open"] else "cleared"
        out.append(d)
    return out


# ---------------------------------------------------------------- carry-forward
RETAINED_EARNINGS = "081000"


def pl_before(conn, gjahr):
    """Sum (debit +) of all P&L postings before 1 January of gjahr = the result
    of all previous years, carried forward to retained earnings."""
    accs = _accounts(conn)
    pl = [k for k, a in accs.items() if a["typ"] == "PL"]
    if not pl:
        return 0
    return conn.execute("SELECT COALESCE(SUM(CASE WHEN i.shkzg='S' THEN i.dmbtr ELSE -i.dmbtr END),0) "
                        "FROM acc_doc_item i JOIN acc_doc h ON h.belnr=i.belnr AND h.gjahr=i.gjahr "
                        "WHERE h.budat<? AND i.hkont IN (%s)" % ",".join("?" * len(pl)),
                        ["%04d-01-01" % gjahr] + pl).fetchone()[0]


def retained_earnings(conn, gjahr):
    """Balance carry-forward into gjahr. Always computed from the postings (so a late
    posting into a closed year is carried automatically, like SAP); the F.16 table
    only records which years were confirmed. Returns (amount, years_not_confirmed)."""
    amount = pl_before(conn, gjahr)
    first = conn.execute("SELECT MIN(budat) FROM acc_doc").fetchone()[0]
    missing = []
    if first:
        done = {r[0] for r in conn.execute("SELECT gjahr FROM fi_carry_forward")}
        missing = [y for y in range(int(first[:4]), gjahr) if y not in done]
    return amount, missing


# ---------------------------------------------------------------- trial balance
def trial_balance(conn, gjahr, pfrom, pto):
    accs = _accounts(conn)
    d1, d2 = "%04d-%02d-01" % (gjahr, pfrom), eop(gjahr, pto)
    before = "%04d-%02d-01" % (gjahr, pfrom)
    per = _sums(conn, d1, d2)
    carry, _ = retained_earnings(conn, gjahr)
    out = []
    for k in sorted(accs):
        a = accs[k]
        if a["typ"] == "BS":
            ob = conn.execute("SELECT COALESCE(SUM(CASE WHEN i.shkzg='S' THEN i.dmbtr ELSE "
                              "-i.dmbtr END),0) FROM acc_doc_item i JOIN acc_doc h ON "
                              "h.belnr=i.belnr AND h.gjahr=i.gjahr WHERE i.hkont=? AND "
                              "h.budat<?", (k, before)).fetchone()[0]
        else:
            ob = conn.execute("SELECT COALESCE(SUM(CASE WHEN i.shkzg='S' THEN i.dmbtr ELSE "
                              "-i.dmbtr END),0) FROM acc_doc_item i JOIN acc_doc h ON "
                              "h.belnr=i.belnr AND h.gjahr=i.gjahr WHERE i.hkont=? AND "
                              "h.budat>=? AND h.budat<?", (k, "%04d-01-01" % gjahr,
                                                            before)).fetchone()[0]
        if k == RETAINED_EARNINGS:
            ob += carry                     # balance carry-forward of previous years
        dr, cr = per.get(k, (0, 0))
        if not (ob or dr or cr):
            continue
        out.append(dict(hkont=k, txt=a["txt"], typ=a["typ"], fsv=a["fsv"],
                        opening=_a(ob), debit=_a(dr), credit=_a(cr),
                        period=_a(dr - cr), closing=_a(ob + dr - cr)))
    return out


# ---------------------------------------------------------------- F.01
def _bs_values(conn, upto, gjahr):
    accs = _accounts(conn)
    vals = {}
    for r in conn.execute("SELECT i.hkont, SUM(CASE WHEN i.shkzg='S' THEN i.dmbtr ELSE "
                          "-i.dmbtr END) AS b FROM acc_doc_item i JOIN acc_doc h ON "
                          "h.belnr=i.belnr AND h.gjahr=i.gjahr WHERE h.budat<=? GROUP BY "
                          "i.hkont", (upto,)):
        vals[r["hkont"]] = r["b"] or 0
    bs = {k: v for k, v in vals.items() if accs.get(k, {}).get("typ") == "BS"}
    # result of the year of the key date only; earlier years are in retained earnings
    y = int(upto[:4])
    carry = pl_before(conn, y)
    if carry:
        bs[RETAINED_EARNINGS] = bs.get(RETAINED_EARNINGS, 0) + carry
    result = -(sum(v for k, v in vals.items() if accs.get(k, {}).get("typ") == "PL") - carry)
    return bs, result


def _pl_values(conn, d1, d2):
    accs = _accounts(conn)
    return {k: dc[0] - dc[1] for k, dc in _sums(conn, d1, d2).items()
            if accs.get(k, {}).get("typ") == "PL"}


def statements(conn, gjahr, pfrom, pto):
    """Balance sheet at the end of pto, P&L pfrom..pto, with comparison to the
    previous period of the same length."""
    accs = _accounts(conn)
    length = pto - pfrom + 1
    c_to_y, c_to_p = (gjahr, pfrom - 1) if pfrom > 1 else (gjahr - 1, 12)
    cy, cp = c_to_y, c_to_p - length + 1
    while cp < 1:
        cy, cp = cy - 1, cp + 12
    d_end, c_end = eop(gjahr, pto), eop(c_to_y, c_to_p)
    bs, res = _bs_values(conn, d_end, gjahr)
    bs_c, res_c = _bs_values(conn, c_end, c_to_y)
    pl = _pl_values(conn, "%04d-%02d-01" % (gjahr, pfrom), d_end)
    pl_c = _pl_values(conn, "%04d-%02d-01" % (cy, cp), c_end)
    nodes = {n: dict(node=n, text=t, parent=par, side=s, cur=0, cmp=0, accounts=[])
             for n, t, par, s in FSV_NODES}
    for k, a in sorted(accs.items()):
        n = a["fsv"]
        if n not in nodes:
            continue
        side = nodes[n]["side"]
        sgn = 1 if side == "A" else -1           # liabilities / revenue as positive
        cur = (bs.get(k, 0) if a["typ"] == "BS" else pl.get(k, 0)) * sgn
        cmpv = (bs_c.get(k, 0) if a["typ"] == "BS" else pl_c.get(k, 0)) * sgn
        if cur or cmpv:
            nodes[n]["accounts"].append(dict(hkont=k, txt=a["txt"], cur=_a(cur),
                                             cmp=_a(cmpv)))
            nodes[n]["cur"] += cur
            nodes[n]["cmp"] += cmpv
    nodes["P15"]["cur"], nodes["P15"]["cmp"] = res, res_c
    order = [n for n, *_ in FSV_NODES]
    for n in reversed(order):                  # roll up
        par = nodes[n]["parent"]
        if par:
            nodes[par]["cur"] += nodes[n]["cur"]
            nodes[par]["cmp"] += nodes[n]["cmp"]
    out = []

    def depth(n):
        d = 0
        while nodes[n]["parent"]:
            n = nodes[n]["parent"]
            d += 1
        return d
    for n in order:
        x = nodes[n]
        out.append(dict(node=n, text=x["text"], level=depth(n), cur=_a(x["cur"]),
                        cmp=_a(x["cmp"]), diff=_a(x["cur"] - x["cmp"]),
                        pct=round((x["cur"] - x["cmp"]) / abs(x["cmp"]) * 100, 1)
                        if x["cmp"] else None, accounts=x["accounts"]))
    pnl = nodes["PNL"]
    op = sum(nodes[n]["cur"] for n in ("R10", "R20", "R30", "R40", "R50", "R60", "R70",
                                       "R80", "R85"))
    return {"rows": out, "period": "%02d-%02d/%s" % (pfrom, pto, gjahr),
            "cmp_period": "%02d-%02d/%s" % (cp, c_to_p, cy),
            "assets": _a(nodes["ASSETS"]["cur"]), "liabilities": _a(nodes["LIAB"]["cur"]),
            "balanced": nodes["ASSETS"]["cur"] == nodes["LIAB"]["cur"],
            "result": _a(pnl["cur"]), "operating": _a(op),
            "financial": _a(nodes["R90"]["cur"]), "period_result": _a(pnl["cur"])}


# ---------------------------------------------------------------- FK10N / FD10N
def partner_balances(conn, koart, gjahr):
    tab, key = ("vendor", "lifnr") if koart == "K" else ("customer", "kunnr")
    out = []
    for p in conn.execute("SELECT * FROM %s ORDER BY %s" % (tab, key)).fetchall():
        r = conn.execute(
            "SELECT SUM(CASE WHEN i.shkzg='S' AND h.gjahr=? THEN i.dmbtr ELSE 0 END) AS d, "
            "SUM(CASE WHEN i.shkzg='H' AND h.gjahr=? THEN i.dmbtr ELSE 0 END) AS c, "
            "SUM(CASE WHEN i.shkzg='S' THEN i.dmbtr ELSE -i.dmbtr END) AS b, "
            "SUM(CASE WHEN i.augbl IS NULL THEN (CASE WHEN i.shkzg='S' THEN i.dmbtr ELSE "
            "-i.dmbtr END) ELSE 0 END) AS o FROM acc_doc_item i JOIN acc_doc h ON "
            "h.belnr=i.belnr AND h.gjahr=i.gjahr WHERE i.%s=? AND i.koart=?" % key,
            (gjahr, gjahr, p[key], koart)).fetchone()
        out.append(dict(partner=p[key], name=p["name"], city=p["city"],
                        akont=p["akont"], zterm=p["zterm"],
                        waers=(p["waers"] if koart == "K" else LOCAL_CURRENCY) or "EGP",
                        debit=_a(r["d"]), credit=_a(r["c"]), balance=_a(r["b"]),
                        open=_a(r["o"]),
                        klimk=_a(p["klimk"]) if koart == "D" else None))
    return out


# ---------------------------------------------------------------- aging
BUCKETS = [("not_due", "Not due"), ("d30", "1-30"), ("d60", "31-60"), ("d90", "61-90"),
           ("d90p", "> 90")]


def aging(conn, koart, key_date):
    kd = datetime.date.fromisoformat(key_date)
    tab, key = ("vendor", "lifnr") if koart == "K" else ("customer", "kunnr")
    names = {r[key]: r["name"] for r in conn.execute("SELECT %s, name FROM %s" % (key, tab))}
    out = {}
    for r in open_items(conn, koart, key_date=key_date):
        p = r[key]
        o = out.setdefault(p, dict(partner=p, name=names.get(p, ""), total=0,
                                   **{b: 0 for b, _ in BUCKETS}))
        v = signed(r) * (-1 if koart == "K" else 1)
        days = (kd - datetime.date.fromisoformat(r["netdt"])).days
        b = "not_due" if days <= 0 else "d30" if days <= 30 else "d60" if days <= 60 \
            else "d90" if days <= 90 else "d90p"
        o[b] += v
        o["total"] += v
    res = []
    for o in out.values():
        if o["total"]:
            res.append({k: (_a(v) if isinstance(v, int) else v) for k, v in o.items()})
    return {"rows": sorted(res, key=lambda x: -x["total"]), "buckets": BUCKETS}


# ---------------------------------------------------------------- FF7A / FF7B
def cash_position(conn, key_date, weeks=8):
    kd = datetime.date.fromisoformat(key_date)
    bank = sum(gl_balance(conn, k, key_date) for k in ("113100", "100000"))
    cols = []
    for w in range(weeks):
        cols.append(dict(week=w + 1, start=(kd + datetime.timedelta(days=7 * w)).isoformat(),
                         end=(kd + datetime.timedelta(days=7 * w + 6)).isoformat(),
                         inflow=0, outflow=0))
    overdue_in = overdue_out = 0
    for koart in ("D", "K"):
        for r in open_items(conn, koart, key_date=key_date):
            dd = discount_date(r) if koart == "K" and r["zbd1p"] else None
            due = dd if dd and dd >= key_date else r["netdt"]
            v = signed(r)
            if due < key_date:
                if koart == "D":
                    overdue_in += v
                else:
                    overdue_out += v
                continue
            for c in cols:
                if c["start"] <= due <= c["end"]:
                    if koart == "D":
                        c["inflow"] += v
                    else:
                        c["outflow"] += v
    bal = bank
    for c in cols:
        bal += c["inflow"] + c["outflow"]
        c["balance"] = _a(bal)
        c["inflow"], c["outflow"] = _a(c["inflow"]), _a(c["outflow"])
    return {"key_date": key_date, "bank": _a(bank), "overdue_in": _a(overdue_in),
            "overdue_out": _a(overdue_out), "weeks": cols}


# ---------------------------------------------------------------- AR01
def asset_list(conn, upto=None):
    from .aa import values
    out = []
    for a in conn.execute("SELECT a.*, c.name AS ccname FROM asset a LEFT JOIN "
                          "cost_center c ON c.kostl=a.kostl ORDER BY anln1").fetchall():
        apc, dep, nbv = values(conn, a["anln1"], upto)
        out.append(dict(a, cls=ASSET_CLASSES[a["anlkl"]][0], apc=_a(apc), accdep=_a(dep),
                        nbv=_a(nbv), monthly=_a(apc // (a["ndjar"] * 12)) if apc else 0))
    return out


# ---------------------------------------------------------------- cockpit
def cockpit(conn, gjahr, perio):
    end = eop(gjahr, perio)
    st = statements(conn, gjahr, perio, perio)
    ytd = statements(conn, gjahr, 1, perio)
    node = {r["node"]: r for r in st["rows"]}
    ar_open = sum(signed(r) for r in open_items(conn, "D", key_date=end))
    ap_open = -sum(signed(r) for r in open_items(conn, "K", key_date=end))
    overdue = sum(signed(r) for r in open_items(conn, "D", key_date=end)
                  if r["netdt"] < end)
    cash = sum(gl_balance(conn, k, end) for k in ("113100", "100000"))
    inv = sum(gl_balance(conn, k, end) for k in ("300000", "303000", "305000", "790000",
                                                  "792000"))
    rev = node["R10"]["cur"] * 100
    days = calendar.monthrange(gjahr, perio)[1]
    cogs = (node["R30"]["cur"] + node["R40"]["cur"]) * -100
    vat = -sum(gl_balance(conn, k, end) for k in ("154000", "175000", "179000"))
    cur_liab = ap_open + vat - sum(gl_balance(conn, k, end) for k in ("176000", "190000",
                                                                      "191100"))
    ebitda = (st["operating"] - node["R70"]["cur"]) * 100
    aged = aging(conn, "D", end)
    return {
        "gjahr": gjahr, "perio": perio, "currency": LOCAL_CURRENCY,
        "kpi": {"cash": _a(cash), "ar": _a(ar_open), "overdue": _a(overdue),
                "ap": _a(ap_open), "inventory": _a(inv),
                "dso": round(ar_open / rev * days, 1) if rev else None,
                "dpo": round(ap_open / cogs * days, 1) if cogs else None,
                "working_capital": _a(cash + ar_open + inv - cur_liab),
                "current_ratio": round((cash + ar_open + inv) / cur_liab, 2) if cur_liab else None,
                "result": st["result"], "operating": st["operating"],
                "ebitda": _a(ebitda), "revenue": node["R10"]["cur"],
                "ytd_result": ytd["result"], "ytd_revenue": {r["node"]: r for r in
                                                             ytd["rows"]}["R10"]["cur"],
                "equity_ratio": round(({r["node"]: r for r in st["rows"]}["P10"]["cur"] +
                                       st["result"] * 0 + {r["node"]: r for r in
                                                           st["rows"]}["P15"]["cur"])
                                      / st["assets"] * 100, 1) if st["assets"] else None,
                "balanced": st["balanced"], "assets_total": st["assets"]},
        "statements": st, "aging": aged,
        "cash": cash_position(conn, end, 8),
        "vat": {k: _a(v) if isinstance(v, int) else v for k, v in
                __import__("fi.gl", fromlist=["vat_report"]).vat_report(
                    conn, "%04d-%02d-01" % (gjahr, perio), end).items() if k != "rows"},
    }


def master_lists(conn):
    return {
        "terms": [dict(zterm=k, text=v[0], disc_days=v[1], disc_pct=v[2] / 100.0,
                       net_days=v[3]) for k, v in PAYMENT_TERMS.items()],
        "tax": [dict(mwskz=k, text=v[0], pct=v[1] / 100.0, typ=v[2], hkont=v[3])
                for k, v in TAX_CODES.items()],
        "rates": rows(conn.execute("SELECT * FROM exch_rate ORDER BY waers, gdatu DESC")),
        "period": dict(conn.execute("SELECT * FROM posting_period WHERE id=1").fetchone()
                       or {}),
    }
