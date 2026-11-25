"""Egyptian tax returns and the tax calendar.

ZTAX_VAT   VAT return (form 10) of a month: sales and output tax by rate, purchases and input
           tax, credit carried from the previous month, net payable / credit
ZTAX_41    withholding tax form 41 of a quarter: per vendor with tax registration number
ZTAX_SAL   salary tax return (form 4) of a month from the payroll results
ZTAX_CIT   corporate income tax estimate of a year (accounting profit x rate)
ZTAX_SIMP  simplified regime (Law 6/2025): eligibility and tax on turnover
ZTAX_CAL   tax calendar: every return of the year with due date, amount and filed / paid status
"""
import calendar
import datetime

from mm import util as clock
from mm.db import transaction
from mm.util import MMError, now_ts, parse_amount, parse_date, parse_int, rdiv

from . import rules

TYPES = {"VAT": "VAT return (form 10)", "SAL": "Salary tax (form 4)", "WHT": "Withholding tax (form 41)",
         "CIT": "Corporate income tax return", "SALY": "Annual salary tax settlement"}


def _month(y, m):
    y, m = int(y), int(m)
    return "%04d-%02d-01" % (y, m), "%04d-%02d-%02d" % (y, m, calendar.monthrange(y, m)[1])


def _filing(conn, typ, period):
    r = conn.execute("SELECT * FROM tax_filing WHERE typ=? AND period=?", (typ, period)).fetchone()
    return dict(r) if r else None


# ------------------------------------------------------------------ VAT form 10
def vat_return(conn, y, m):
    from fi.gl import vat_report
    y = parse_int(y, "year", 2000, 2100)
    m = parse_int(m, "month", 1, 12)
    d1, d2 = _month(y, m)
    v = vat_report(conn, d1, d2)
    by = {r["mwskz"]: r for r in v["rows"]}

    def g(code, k):
        return (by.get(code) or {}).get(k, 0)
    py, pm = (y - 1, 12) if m == 1 else (y, m - 1)
    prev = _filing(conn, "VAT", "%04d-%02d" % (py, pm))
    carried = -prev["amount"] if prev and prev["amount"] < 0 else 0
    lines = [
        dict(no="1", text="Local sales taxable at %s %%" % rules.get(conn, "VAT_STD", d2)["value"], base=g("A1", "base"),
             tax=g("A1", "tax")),
        dict(no="2", text="Exports (0 %)", base=g("A0", "base"), tax=0),
        dict(no="3", text="Total output tax", base=g("A1", "base") + g("A0", "base"), tax=v["output"]),
        dict(no="4", text="Local purchases with input tax", base=g("V1", "base"), tax=g("V1", "tax")),
        dict(no="4a", text="Imports - VAT paid at customs", base=g("VI", "base"), tax=g("VI", "tax")),
        dict(no="5", text="Purchases without input tax (0 %)", base=g("V0", "base"), tax=0),
        dict(no="6", text="Total deductible input tax", base=g("V1", "base") + g("V0", "base") + g("VI", "base"),
             tax=v["input"]),
        dict(no="7", text="Credit carried forward from the previous month", base=0, tax=carried),
    ]
    net = v["output"] - v["input"] - carried
    lines.append(dict(no="8", text="Tax payable" if net >= 0 else "Credit to carry forward", base=0, tax=net))
    from .eta import input_vat_at_risk
    risk = input_vat_at_risk(conn, d1, d2)
    return {"period": "%04d-%02d" % (y, m), "d1": d1, "d2": d2, "lines": lines, "payable": net,
            "due": _due(conn, "VAT", y, m), "filing": _filing(conn, "VAT", "%04d-%02d" % (y, m)),
            "input_at_risk": risk["amount"], "input_at_risk_docs": risk["count"]}


# ------------------------------------------------------------------ WHT form 41
def form41(conn, y, q):
    from fi.wht import report
    y = parse_int(y, "year", 2000, 2100)
    q = parse_int(q, "quarter", 1, 4)
    d1 = "%04d-%02d-01" % (y, 3 * q - 2)
    d2 = _month(y, 3 * q)[1]
    rows = report(conn, d1, d2)
    for r in rows:
        v = conn.execute("SELECT stcd1, city FROM vendor WHERE lifnr=?", (r["lifnr"],)).fetchone()
        r["taxid"] = (v["stcd1"] if v and v["stcd1"] else r.get("taxid")) or ""
        r["missing_taxid"] = not r["taxid"]
    period = "%04d-Q%d" % (y, q)
    return {"period": period, "d1": d1, "d2": d2, "rows": rows, "base": sum(r["base"] for r in rows),
            "amount": sum(r["amount"] for r in rows), "missing_taxid": sum(1 for r in rows if r["missing_taxid"]),
            "due": _due(conn, "WHT", y, 3 * q), "filing": _filing(conn, "WHT", period)}


# ------------------------------------------------------------------ salary tax
def salary_return(conn, y, m):
    y = parse_int(y, "year", 2000, 2100)
    m = parse_int(m, "month", 1, 12)
    r = conn.execute("SELECT COUNT(*) n, COALESCE(SUM(gross),0) gross, COALESCE(SUM(si_ee),0) si_ee, "
                     "COALESCE(SUM(si_er),0) si_er, COALESCE(SUM(taxable),0) taxable, COALESCE(SUM(tax),0) tax, "
                     "COALESCE(SUM(martyrs),0) martyrs FROM hr_payroll WHERE gjahr=? AND perio=?", (y, m)).fetchone()
    run = conn.execute("SELECT status FROM hr_payroll_run WHERE gjahr=? AND perio=?", (y, m)).fetchone()
    period = "%04d-%02d" % (y, m)
    return dict(period=period, employees=r["n"], gross=r["gross"], si_ee=r["si_ee"], si_er=r["si_er"],
                taxable=r["taxable"], tax=r["tax"], martyrs=r["martyrs"], payroll=run["status"] if run else "",
                due=_due(conn, "SAL", y, m), filing=_filing(conn, "SAL", period))


# ------------------------------------------------------------------ corporate income tax
def cit_estimate(conn, y):
    from fi.reports import _accounts
    y = parse_int(y, "year", 2000, 2100)
    pl = [k for k, a in _accounts(conn).items() if a["typ"] == "PL"]
    s = conn.execute("SELECT COALESCE(SUM(CASE WHEN i.shkzg='S' THEN i.dmbtr ELSE -i.dmbtr END),0) FROM acc_doc_item i "
                     "JOIN acc_doc h ON h.belnr=i.belnr AND h.gjahr=i.gjahr WHERE h.budat BETWEEN ? AND ? AND "
                     "i.hkont IN (%s)" % ",".join("?" * len(pl)), ["%04d-01-01" % y, "%04d-12-31" % y] + pl).fetchone()[0]
    profit = -s
    rate = rules.num(conn, "CIT_RATE", "%04d-12-31" % y)
    tax = rdiv(max(profit, 0) * int(round(rate * 100)), 10000)
    return dict(year=y, profit=profit, rate=rate, tax=tax, due=_due(conn, "CIT", y, 12),
                filing=_filing(conn, "CIT", str(y)),
                note="Estimate on the accounting profit - the return adds non-deductible costs and deducts exempt "
                     "income; ask the tax adviser")


# ------------------------------------------------------------------ simplified regime (Law 6/2025)
def simplified(conn, turnover, day=None):
    t = parse_amount(turnover)
    day = parse_date(day) if day else clock.today().isoformat()
    limit = int(rules.num(conn, "SIMP_LIMIT", day) * 100)
    bands = []
    for part in rules.get(conn, "SIMP_BANDS", day)["value"].split(","):
        up, rate = part.split(":")
        bands.append((int(float(up) * 100), float(rate)))
    tolerance = rdiv(limit * 120, 100)
    ok = t <= limit
    rate = next((r for up, r in bands if t <= up), bands[-1][1])
    return dict(turnover=t, limit=limit, eligible=ok, within_tolerance=not ok and t <= tolerance, rate=rate,
                tax=rdiv(t * int(round(rate * 100)), 10000), bands=[dict(upto=u, rate=r) for u, r in bands],
                note="Tax on turnover instead of profit; no withholding / advance payments; e-invoice and e-receipt "
                     "required. Bands to be confirmed (rule SIMP_BANDS).")


# ------------------------------------------------------------------ calendar
def _end_of(y, m):
    return _month(y, m)[1]


def _due(conn, typ, y, m):
    nm_y, nm = (y + 1, 1) if m == 12 else (y, m + 1)
    if typ == "VAT":
        return _end_of(nm_y, nm)
    if typ == "SAL":
        day = int(rules.num(conn, "SAL_DUE", _end_of(y, m)))
        return "%04d-%02d-%02d" % (nm_y, nm, day)
    if typ == "WHT":
        return _end_of(nm_y, nm)
    if typ == "CIT":
        months = int(rules.num(conn, "CIT_DUE", _end_of(y, 12)))
        return _end_of(y + 1, months)
    if typ == "SALY":
        return _end_of(y + 1, 1)
    raise MMError("Unknown return type %s" % typ, "TX", "910")


def calendar_year(conn, y, key_date=None):
    from fi.gl import vat_report
    y = parse_int(y, "year", 2000, 2100)
    kd = parse_date(key_date) if key_date else clock.today().isoformat()
    out = []

    def add(typ, period, label, due, amount):
        f = _filing(conn, typ, period)
        days = (datetime.date.fromisoformat(due) - datetime.date.fromisoformat(kd)).days
        st = "paid" if f and f.get("paid_on") else "filed" if f and f.get("filed_on") else \
            "overdue" if days < 0 else "due soon" if days <= 10 else "open"
        out.append(dict(typ=typ, typ_text=TYPES[typ], period=period, label=label, due=due, days=days, amount=amount,
                        status=st, ref_no=(f or {}).get("ref_no") or "", filed_on=(f or {}).get("filed_on") or "",
                        paid_on=(f or {}).get("paid_on") or ""))
    for m in range(1, 13):
        d1, d2 = _month(y, m)
        if d1 > kd:
            break
        add("VAT", "%04d-%02d" % (y, m), "VAT %02d/%d" % (m, y), _due(conn, "VAT", y, m),
            vat_report(conn, d1, d2)["payable"])
        tax = conn.execute("SELECT COALESCE(SUM(tax),0) FROM hr_payroll WHERE gjahr=? AND perio=?", (y, m)).fetchone()[0]
        add("SAL", "%04d-%02d" % (y, m), "Salary tax %02d/%d" % (m, y), _due(conn, "SAL", y, m), tax)
        if m % 3 == 0:
            add("WHT", "%04d-Q%d" % (y, m // 3), "WHT form 41 Q%d/%d" % (m // 3, y), _due(conn, "WHT", y, m),
                form41(conn, y, m // 3)["amount"])
    add("SALY", str(y), "Annual salary settlement %d" % y, _due(conn, "SALY", y, 12), 0)
    add("CIT", str(y), "Corporate tax return %d" % y, _due(conn, "CIT", y, 12), cit_estimate(conn, y)["tax"])
    out.sort(key=lambda r: r["due"])
    return {"year": y, "key_date": kd, "rows": out, "overdue": sum(1 for r in out if r["status"] == "overdue"),
            "due_soon": sum(1 for r in out if r["status"] == "due soon")}


def mark(conn, data, user):
    """record that a return was filed (with the ETA reference) and / or paid"""
    typ = (data.get("typ") or "").upper()
    if typ not in TYPES:
        raise MMError("Return type %s does not exist" % typ, "TX", "911")
    period = (data.get("period") or "").strip()
    if not period:
        raise MMError("Enter the period", "TX", "912")
    filed_on = parse_date(data["filed_on"]) if data.get("filed_on") else None
    paid_on = parse_date(data["paid_on"]) if data.get("paid_on") else None
    if not filed_on and not paid_on:
        raise MMError("Enter the filing date and / or the payment date", "TX", "913")
    if filed_on and not (data.get("ref_no") or "").strip():
        raise MMError("Enter the reference number of the return (ETA portal)", "TX", "914")
    amount = data.get("amount")
    with transaction(conn):
        cur = _filing(conn, typ, period)
        if paid_on and not (filed_on or (cur and cur["filed_on"])):
            raise MMError("Record the filing of the return before its payment", "TX", "915")
        conn.execute("INSERT INTO tax_filing (typ,period,filed_on,ref_no,amount,paid_on,pay_ref,usnam,ts) VALUES "
                     "(?,?,?,?,?,?,?,?,?) ON CONFLICT(typ,period) DO UPDATE SET filed_on=COALESCE(excluded.filed_on,"
                     "filed_on), ref_no=COALESCE(excluded.ref_no,ref_no), amount=COALESCE(excluded.amount,amount), "
                     "paid_on=COALESCE(excluded.paid_on,paid_on), pay_ref=COALESCE(excluded.pay_ref,pay_ref), "
                     "usnam=excluded.usnam, ts=excluded.ts",
                     (typ, period, filed_on, (data.get("ref_no") or "").strip() or None,
                      _signed(amount) if amount not in (None, "") else None, paid_on,
                      (data.get("pay_ref") or "").strip() or None, user, now_ts()))
    return {"message": "%s %s: %s" % (TYPES[typ], period, "paid" if paid_on else "filed")}


def _signed(v):
    t = str(v).replace(",", "").strip()
    return -parse_amount(t[1:], allow_zero=True) if t.startswith("-") else parse_amount(t, allow_zero=True)
