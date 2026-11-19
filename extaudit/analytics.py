"""Audit analytics for a fiscal year - what the audit firm tests, prepared from the books.
Amounts in EGP (2 decimals) for display and Excel; quantities in units."""
import datetime

from mm.util import parse_int

ROUND = 1000000                       # cents: a multiple of EGP 10,000 is a "round" amount
KEYWORDS = ("adjust", "correct", "error", "reverse", "write off", "تسوية", "تصحيح", "خطأ", "إلغاء", "اعدام", "إعدام")
MANUAL_TCODES = ("FB50", "F-02", "FB01", "FBS1", "FB08", "", None)


def _e(c):
    return round((c or 0) / 100.0, 2)


def _u(m):
    return round((m or 0) / 1000.0, 3)


def dates(y):
    y = parse_int(y, "fiscal year", 2000, 2100)
    return y, "%04d-01-01" % y, "%04d-12-31" % y


# ------------------------------------------------------------------ statements, lead schedules
def statements(conn, y):
    from fi.reports import statements as st
    y, _, _ = dates(y)
    return st(conn, y, 1, 12)


def lead_schedules(conn, y):
    """per financial statement line: accounts, this year, comparison, change"""
    out = []
    for r in statements(conn, y)["rows"]:
        if not r["accounts"]:
            continue
        out.append(dict(node=r["node"], text=r["text"], cur=r["cur"], cmp=r["cmp"], diff=r["diff"], pct=r["pct"],
                        accounts=r["accounts"]))
    return out


def figures(conn, y):
    """bases for materiality (EGP)"""
    s = statements(conn, y)
    rows = {r["node"]: r for r in s["rows"]}
    revenue = abs(sum(r["cur"] for n, r in rows.items() if n == "R10")) if "R10" in rows else 0.0
    return {"profit_before_tax": abs(s.get("result") or 0.0), "result": s.get("result"), "revenue": revenue,
            "total_assets": s.get("assets") or 0.0}


# ------------------------------------------------------------------ journal entry testing (ESA 240)
def jet(conn, y, large=None):
    y, d1, d2 = dates(y)
    docs = {}
    users = {r["usnam"]: r["n"] for r in conn.execute(
        "SELECT usnam, COUNT(*) n FROM acc_doc WHERE budat BETWEEN ? AND ? GROUP BY usnam", (d1, d2))}
    for h in conn.execute("SELECT * FROM acc_doc WHERE budat BETWEEN ? AND ? ORDER BY budat, belnr", (d1, d2)).fetchall():
        items = conn.execute("SELECT * FROM acc_doc_item WHERE belnr=? AND gjahr=?", (h["belnr"], h["gjahr"])).fetchall()
        total = sum(i["dmbtr"] for i in items if i["shkzg"] == "S")
        flags = []
        manual = h["blart"] in ("SA", "AB") and (h["tcode"] in MANUAL_TCODES)
        if manual:
            flags.append("Manual journal")
        day = datetime.date.fromisoformat(h["budat"])
        if manual and day.weekday() in (4, 5):
            flags.append("Posted on Friday / Saturday")
        if manual and any(i["dmbtr"] >= ROUND and i["dmbtr"] % ROUND == 0 for i in items):
            flags.append("Round amount")
        if h["budat"] >= "%04d-12-29" % y or (h["monat"] or 0) > 12:
            flags.append("Year-end / special period")
        txt = " ".join([h["bktxt"] or ""] + [i["sgtxt"] or "" for i in items]).lower()
        if any(k in txt for k in KEYWORDS):
            flags.append("Keyword (adjust / correct / reverse)")
        if manual and any(i["hkont"].startswith("8") and i["shkzg"] == "S" for i in items):
            flags.append("Manual debit to revenue")
        if manual and users.get(h["usnam"], 0) <= 3:
            flags.append("User rarely posts")
        if manual and large and total >= large:
            flags.append("Above performance materiality")
        if flags:
            docs[(h["belnr"], h["gjahr"])] = dict(belnr=h["belnr"], budat=h["budat"], blart=h["blart"], tcode=h["tcode"] or "",
                                                  usnam=h["usnam"], text=h["bktxt"] or "", amount=_e(total), flags=flags,
                                                  score=len(flags))
    rows = sorted(docs.values(), key=lambda r: (-r["score"], -r["amount"]))
    count = conn.execute("SELECT COUNT(*) FROM acc_doc WHERE budat BETWEEN ? AND ?", (d1, d2)).fetchone()[0]
    return {"documents": count, "flagged": len(rows), "rows": rows}


# ------------------------------------------------------------------ receivables / payables (ESA 505, 530)
def partners(conn, y, koart, coverage=0.7):
    """aging at year end and a confirmation sample: the largest balances up to the coverage,
    then every 3rd of the rest (systematic)"""
    from fi.reports import aging
    y, _, d2 = dates(y)
    a = aging(conn, koart, d2)
    rows = [dict(r, abs_total=abs(r["total"])) for r in a["rows"]]
    total = sum(r["abs_total"] for r in rows)
    acc, sample = 0.0, []
    for i, r in enumerate(sorted(rows, key=lambda r: -r["abs_total"])):
        if acc < coverage * total:
            r["sample"], r["why"] = True, "key item (top balances)"
            acc += r["abs_total"]
        elif i % 3 == 0:
            r["sample"], r["why"] = True, "systematic sample"
        else:
            r["sample"], r["why"] = False, ""
        sample.append(r)
    return {"key_date": d2, "buckets": a["buckets"], "rows": sample, "total": round(total, 2),
            "sampled": sum(1 for r in sample if r["sample"]),
            "coverage_pct": round(100.0 * sum(r["abs_total"] for r in sample if r["sample"]) / total, 1) if total else 0}


def ecl(conn, y, rates=(0.5, 2, 5, 15, 50)):
    """simplified expected credit loss matrix on the receivables aging (EAS 47) - rates in % per bucket,
    to be calibrated on the company's loss history"""
    p = partners(conn, y, "D")
    keys = [b for b, _ in p["buckets"]]
    tot = {k: round(sum(max(r[k], 0) for r in p["rows"]), 2) for k in keys}
    lines = [dict(bucket=t, balance=tot[k], rate=rates[i], allowance=round(tot[k] * rates[i] / 100.0, 2))
             for i, (k, t) in enumerate(p["buckets"])]
    return {"lines": lines, "allowance": round(sum(x["allowance"] for x in lines), 2)}


def bank(conn, y):
    from fi.config import HOUSE_BANKS
    from fi.reports import gl_balance
    y, _, d2 = dates(y)
    out = []
    for hb, acct, text, gl, cur in HOUSE_BANKS:
        out.append(dict(bank=hb, account=acct, text=text, gl=gl, currency=cur, balance=_e(gl_balance(conn, gl, d2))))
    seen = {b["gl"] for b in out}
    for r in conn.execute("SELECT hkont, txt FROM gl_account WHERE fsv='A50' ORDER BY hkont"):
        if r["hkont"] not in seen:
            bal = gl_balance(conn, r["hkont"], d2)
            if bal:
                out.append(dict(bank="", account="", text=r["txt"], gl=r["hkont"], currency="EGP", balance=_e(bal)))
    return {"key_date": d2, "rows": out}


def unrecorded(conn, y, days=60):
    """payments to vendors in the first days of the next year (may belong to this year) and the GR/IR balance"""
    from mm.config import gl_for
    from fi.reports import gl_balance
    y, _, d2 = dates(y)
    end = (datetime.date.fromisoformat(d2) + datetime.timedelta(days=days)).isoformat()
    rows = [dict(belnr=r["belnr"], budat=r["budat"], vendor=r["name"] or r["lifnr"], amount=_e(r["a"]), text=r["bktxt"] or "")
            for r in conn.execute("SELECT h.belnr, h.budat, h.bktxt, i.lifnr, v.name, SUM(i.dmbtr) a FROM acc_doc h JOIN acc_doc_item i "
                                  "ON i.belnr=h.belnr AND i.gjahr=h.gjahr AND i.koart='K' AND i.shkzg='S' LEFT JOIN vendor v ON "
                                  "v.lifnr=i.lifnr WHERE h.blart IN ('KZ','ZP') AND h.budat>? AND h.budat<=? GROUP BY h.belnr, "
                                  "h.gjahr ORDER BY a DESC", (d2, end))]
    return {"from": d2, "to": end, "payments": rows, "grir_balance": _e(gl_balance(conn, gl_for("WRX", "*"), d2)),
            "note": "GR/IR credit balance = goods received, vendor invoice not yet posted (accrue at year end)"}


# ------------------------------------------------------------------ inventory (EAS 2, ESA 501)
def inventory(conn, y, slow_days=180):
    from mm.periods import stock_at
    y, d1, d2 = dates(y)
    kd = datetime.date.fromisoformat(d2)
    out = []
    for p in conn.execute("SELECT werks FROM plant ORDER BY werks").fetchall():
        for r in stock_at(conn, p["werks"], d2):
            last = conn.execute("SELECT MAX(h.budat) FROM mat_doc_item i JOIN mat_doc h ON h.mblnr=i.mblnr AND h.mjahr=i.mjahr "
                                "WHERE i.matnr=? AND i.werks=? AND h.budat<=?", (r["matnr"], p["werks"], d2)).fetchone()[0]
            sp = conn.execute("SELECT i.net, i.fkimg FROM billing_item i JOIN billing b ON b.vbeln=i.vbeln WHERE i.matnr=? AND "
                              "b.cancelled=0 AND b.fkdat<=? AND i.fkimg>0 ORDER BY b.fkdat DESC LIMIT 1", (r["matnr"], d2)).fetchone()
            unit = r["value"] / (r["qty"] / 1000.0) if r["qty"] else 0
            price = sp["net"] / (sp["fkimg"] / 1000.0) if sp else None
            idle = (kd - datetime.date.fromisoformat(last)).days if last else None
            flags = []
            if price is not None and price < unit:
                flags.append("NRV below cost")
            if idle is not None and idle > slow_days:
                flags.append("Slow moving (> %d days)" % slow_days)
            if r["qty"] < 0 or r["value"] < 0:
                flags.append("Negative stock / value")
            out.append(dict(werks=p["werks"], matnr=r["matnr"], text=r["maktx"], unit=r["meins"], qty=_u(r["qty"]),
                            value=_e(r["value"]), unit_cost=_e(unit), last_price=_e(price) if price is not None else None,
                            nrv_writedown=_e(max(0, (unit - price) * r["qty"] / 1000.0)) if price is not None and price < unit else 0.0,
                            last_move=last or "", idle_days=idle, flags=flags))
    diffs = [dict(r) for r in conn.execute(
        "SELECT i.bwart, COUNT(*) n, SUM(i.dmbtr) v FROM mat_doc_item i JOIN mat_doc h ON h.mblnr=i.mblnr AND h.mjahr=i.mjahr "
        "WHERE i.bwart IN ('701','702') AND i.canceled=0 AND h.budat BETWEEN ? AND ? GROUP BY i.bwart", (d1, d2))]
    return {"key_date": d2, "rows": out, "total": round(sum(r["value"] for r in out), 2),
            "nrv_writedown": round(sum(r["nrv_writedown"] for r in out), 2),
            "slow_value": round(sum(r["value"] for r in out if any(f.startswith("Slow") for f in r["flags"])), 2),
            "count_differences": [dict(movement=d["bwart"], documents=d["n"], value=_e(d["v"])) for d in diffs]}


# ------------------------------------------------------------------ fixed assets (EAS 10)
def fixed_assets(conn, y):
    from fi.aa import values
    y, d1, d2 = dates(y)
    prev = "%04d-12-31" % (y - 1)
    out = []
    for a in conn.execute("SELECT * FROM asset ORDER BY anln1").fetchall():
        c0, dep0, _ = values(conn, a["anln1"], prev)
        c1, dep1, nbv = values(conn, a["anln1"], d2)
        out.append(dict(anln1=a["anln1"], text=a["txt"] or a["anln1"], cls=a["anlkl"],
                        cost_open=_e(c0), additions=_e(max(c1 - c0, 0)), disposals=_e(min(c1 - c0, 0)), cost_close=_e(c1),
                        dep_open=_e(dep0), dep_charge=_e(dep1 - dep0), dep_close=_e(dep1), nbv=_e(nbv)))
    keys = ("cost_open", "additions", "disposals", "cost_close", "dep_open", "dep_charge", "dep_close", "nbv")
    return {"rows": out, "total": {k: round(sum(r[k] for r in out), 2) for k in keys}}


# ------------------------------------------------------------------ revenue cut-off (EAS 48)
def cutoff(conn, y, days=7):
    y, _, d2 = dates(y)
    ye = datetime.date.fromisoformat(d2)
    a, b = (ye - datetime.timedelta(days=days)).isoformat(), (ye + datetime.timedelta(days=days)).isoformat()
    out = []
    for r in conn.execute("SELECT b.vbeln, b.fkdat, b.kunnr, c.name, b.netwr, b.mblnr, b.mjahr, (SELECT budat FROM mat_doc "
                          "WHERE mblnr=b.mblnr AND mjahr=b.mjahr) gi FROM billing b LEFT JOIN customer c ON c.kunnr=b.kunnr "
                          "WHERE b.cancelled=0 AND b.fkdat BETWEEN ? AND ? ORDER BY b.fkdat", (a, b)):
        gi = r["gi"] or ""
        issue = bool(gi) and ((r["fkdat"] <= d2) != (gi <= d2))
        out.append(dict(vbeln=r["vbeln"], invoice_date=r["fkdat"], goods_issue=gi, customer=r["name"] or r["kunnr"],
                        net=_e(r["netwr"]), year_of_invoice=r["fkdat"][:4], issue=issue))
    return {"window": [a, b], "rows": out, "issues": sum(1 for r in out if r["issue"])}


# ------------------------------------------------------------------ payroll (EAS 38)
def payroll(conn, y):
    from hr.config import ACCOUNTS
    y, _, _ = dates(y)
    accts = (ACCOUNTS["wages"], ACCOUNTS["salaries"], ACCOUNTS["employer_si"])
    out = []
    for m in range(1, 13):
        p = conn.execute("SELECT COUNT(*) n, COALESCE(SUM(gross),0) g, COALESCE(SUM(si_er),0) s, COALESCE(SUM(net),0) net "
                         "FROM hr_payroll WHERE gjahr=? AND perio=?", (y, m)).fetchone()
        run = conn.execute("SELECT belnr FROM hr_payroll_run WHERE gjahr=? AND perio=?", (y, m)).fetchone()
        gl = conn.execute("SELECT COALESCE(SUM(CASE WHEN i.shkzg='S' THEN i.dmbtr ELSE -i.dmbtr END),0) FROM acc_doc_item i "
                          "WHERE i.hkont IN (?,?,?) AND i.belnr=?", accts + ((run["belnr"] if run else "") or "-",)).fetchone()[0]
        if p["n"] or gl:
            pay = p["g"] + p["s"]
            out.append(dict(month="%04d-%02d" % (y, m), employees=p["n"], gross=_e(p["g"]), employer_si=_e(p["s"]),
                            payroll_cost=_e(pay), ledger=_e(gl), difference=_e(pay - gl), net=_e(p["net"]),
                            note="" if abs(pay - gl) < 100 else ("payroll run not posted to the ledger yet" if not (run and run["belnr"]) else "check")))
    return {"rows": out, "difference": round(sum(r["difference"] for r in out), 2)}


# ------------------------------------------------------------------ subsequent events (EAS 7, ESA 560)
def subsequent(conn, y, threshold, days=90):
    y, _, d2 = dates(y)
    end = (datetime.date.fromisoformat(d2) + datetime.timedelta(days=days)).isoformat()
    rows = []
    for h in conn.execute("SELECT h.*, (SELECT SUM(dmbtr) FROM acc_doc_item i WHERE i.belnr=h.belnr AND i.gjahr=h.gjahr AND "
                          "i.shkzg='S') a FROM acc_doc h WHERE h.budat>? AND h.budat<=? ORDER BY a DESC", (d2, end)):
        if (h["a"] or 0) >= threshold or h["stblg"]:
            rows.append(dict(belnr=h["belnr"], budat=h["budat"], blart=h["blart"], text=h["bktxt"] or "", amount=_e(h["a"]),
                             why="reversal" if h["stblg"] else "large"))
    return {"from": d2, "to": end, "rows": rows}
