"""Egyptian payroll (PC00_M99_CALC), posting to accounting (PC00_M99_CIPE), bank
transfer (PC00_M99_DTA), remuneration statement (PC00_M99_CEDT), payroll journal.

Per employee and month (all amounts in cents):
  earnings  = (basic + allowances) x paid days / 30 + overtime - unpaid absence
  insurable = contractual wage limited to min / max insurable wage
  SI        = 11 % employee / 18.75 % employer of the insurable wage
  income tax= annual brackets on ((gross - employee SI) x 12 - exemption) / 12
  martyrs   = 0.05 % of gross
  net       = gross - employee SI - tax - martyrs - other deductions
Posting: Dr wages (workers) / salaries (staff) and employer SI per cost center (CO actual
costs), Cr payroll payable (net), social insurance, tax and martyrs' fund payable.
"""
import calendar
import datetime

from mm.db import atomic, rows, transaction
from mm.util import MMError, now_ts, rdiv
from mm import util as mmclock

from .config import ABSENCE_TYPES, ACCOUNTS
from .engine import _workdays, cfg, cfg_int


def _period(y, p):
    y, p = int(y), int(p)
    if not 1 <= p <= 12:
        raise MMError("Period must be 1 - 12", "PY", "001")
    first = datetime.date(y, p, 1)
    last = datetime.date(y, p, calendar.monthrange(y, p)[1])
    return y, p, first.isoformat(), last.isoformat()


def annual_tax(conn, taxable_year):
    """Bracket tax on an annual taxable amount (cents)."""
    tax, low = 0, 0
    for part in cfg(conn, "tax_brackets").split(","):
        upper, rate = (int(x) for x in part.split(":"))
        if taxable_year <= low:
            break
        tax += rdiv((min(taxable_year, upper) - low) * rate, 10000)
        low = upper
    return tax


def calc(conn, e, y, p, first, last):
    """Pay currency USD: the contract amounts are converted to EGP at the month-end rate
    (OB08); insurance, tax and posting are in EGP, the net pay is paid in USD."""
    from fi.config import LOCAL_CURRENCY
    from fi.document import rate
    waers = (e["waers"] if "waers" in e.keys() and e["waers"] else LOCAL_CURRENCY)
    kurs = rate(conn, waers, last)
    if waers != LOCAL_CURRENCY:
        e = dict(e)
        for f in ("basic", "allow_transport", "allow_housing", "allow_other", "ins_wage"):
            e[f] = rdiv((e[f] or 0) * kurs, 100000)
    days_m = cfg_int(conn, "days_per_month")
    start = max(first, e["hire_date"])
    end = min(last, e["leave_date"]) if e["leave_date"] else last
    if start > end:
        return None
    full = start == first and end == last
    paid_days = days_m if full else min(days_m, (datetime.date.fromisoformat(end) -
                                                 datetime.date.fromisoformat(start)).days + 1)
    contract = e["basic"] + e["allow_transport"] + e["allow_housing"] + e["allow_other"]
    basic = rdiv(e["basic"] * paid_days, days_m)
    allow = rdiv((contract - e["basic"]) * paid_days, days_m)
    # unpaid absences (working days inside the month)
    unpaid_days = 0
    for a in conn.execute("SELECT * FROM hr_absence WHERE pernr=? AND status='A' AND begda<=? AND endda>=?",
                          (e["pernr"], last, first)):
        if not ABSENCE_TYPES.get(a["awart"], {}).get("paid", True):
            unpaid_days += _workdays(max(a["begda"], first), min(a["endda"], last))
    unpaid = rdiv(contract * unpaid_days, days_m)
    # overtime on the hourly rate of the basic salary
    hourly_div = days_m * cfg_int(conn, "hours_per_day")
    pct = {"D": cfg_int(conn, "ot_day_pct"), "N": cfg_int(conn, "ot_night_pct"), "R": cfg_int(conn, "ot_rest_pct")}
    ot = 0
    for o in conn.execute("SELECT ottype, SUM(hours) h FROM hr_overtime WHERE pernr=? AND datum BETWEEN ? AND ? "
                          "GROUP BY ottype", (e["pernr"], first, last)):
        ot += rdiv(e["basic"] * o["h"] * pct.get(o["ottype"], 10000), hourly_div * 1000 * 10000)
    gross = max(basic + allow + ot - unpaid, 0)
    ins = e["ins_wage"] or contract
    ins = min(max(ins, cfg_int(conn, "si_min")), cfg_int(conn, "si_max"))
    ins = rdiv(ins * paid_days, days_m)
    si_ee = rdiv(ins * cfg_int(conn, "si_ee_pct"), 10000)
    si_er = rdiv(ins * cfg_int(conn, "si_er_pct"), 10000)
    taxable = max(gross - si_ee, 0)
    year_base = max(taxable * 12 - cfg_int(conn, "tax_exemption"), 0)
    tax = rdiv(annual_tax(conn, year_base), 12)
    martyrs = rdiv(gross * cfg_int(conn, "martyrs_pct"), 10000)
    net = gross - si_ee - tax - martyrs
    return dict(gjahr=y, perio=p, pernr=e["pernr"], kostl=e["kostl"], persk=e["persk"], days=days_m,
                paid_days=paid_days - unpaid_days, basic=basic, allowances=allow, overtime=ot, unpaid=unpaid,
                gross=gross, ins_wage=ins, si_ee=si_ee, si_er=si_er, taxable=taxable, tax=tax, martyrs=martyrs,
                other=0, net=net, waers=waers, kurs=kurs,
                gross_fc=gross if waers == LOCAL_CURRENCY else rdiv(gross * 100000, kurs),
                net_fc=net if waers == LOCAL_CURRENCY else rdiv(net * 100000, kurs))


def status(conn, y, p):
    r = conn.execute("SELECT * FROM hr_payroll_run WHERE gjahr=? AND perio=?", (int(y), int(p))).fetchone()
    return dict(r) if r else None


@atomic
def run(conn, y, p, user, simulate=False):
    """Payroll run for a month. simulate=True: results are shown, nothing is kept."""
    y, p, first, last = _period(y, p)
    st = status(conn, y, p)
    if st and st["status"] in ("POST", "PAID"):
        raise MMError("Payroll %04d/%02d is posted - reverse the posting first" % (y, p), "PY", "002")
    if (y, p) > (mmclock.today().year, mmclock.today().month):
        raise MMError("Payroll for a future month is not possible", "PY", "003")
    res = []
    for e in conn.execute("SELECT * FROM hr_employee WHERE hire_date<=? AND (leave_date='' OR leave_date IS NULL OR "
                          "leave_date>=?) ORDER BY pernr", (last, first)):
        r = calc(conn, e, y, p, first, last)
        if r:
            res.append(r)
    if not res:
        raise MMError("No employee is active in %04d/%02d" % (y, p), "PY", "004")
    if simulate:
        return dict(status="SIM", results=res, totals=_totals(res))
    conn.execute("DELETE FROM hr_payroll WHERE gjahr=? AND perio=?", (y, p))
    for r in res:
        conn.execute("INSERT INTO hr_payroll (%s) VALUES (%s)" % (",".join(r), ",".join("?" * len(r))), list(r.values()))
    conn.execute("INSERT OR REPLACE INTO hr_payroll_run (gjahr,perio,status,run_ts,usnam,employees) VALUES "
                 "(?,?,?,?,?,?)", (y, p, "REL", now_ts(), user, len(res)))
    return dict(status="REL", results=res, totals=_totals(res))


def _totals(res):
    keys = ("basic", "allowances", "overtime", "unpaid", "gross", "si_ee", "si_er", "tax", "martyrs", "other", "net")
    return {k: sum(r[k] for r in res) for k in keys}


def results(conn, y, p, pernr=None):
    sql = ("SELECT r.*, e.name, e.name_ar, e.national_id, e.iban, e.job, o.text AS org_text FROM hr_payroll r "
           "JOIN hr_employee e USING (pernr) LEFT JOIN hr_orgunit o ON o.orgeh=e.orgeh WHERE r.gjahr=? AND r.perio=?")
    a = [int(y), int(p)]
    if pernr:
        sql += " AND r.pernr=?"
        a.append(str(pernr))
    return rows(conn.execute(sql + " ORDER BY r.pernr", a))


def _posting_date(last):
    t = mmclock.today().isoformat()
    return min(last, t)


def post(conn, y, p, user):
    """PC00_M99_CIPE: one FI document; expenses per cost center go to CO as actual costs."""
    from fi.document import write
    y, p, first, last = _period(y, p)
    with transaction(conn):
        st = status(conn, y, p)
        if not st or st["status"] != "REL":
            raise MMError("Run the payroll for %04d/%02d first (status must be 'released')" % (y, p), "PY", "005")
        res = results(conn, y, p)
        lines = []
        exp = {}
        for r in res:
            acc = ACCOUNTS["wages"] if r["persk"] == "W" else ACCOUNTS["salaries"]
            exp[(acc, r["kostl"])] = exp.get((acc, r["kostl"]), 0) + r["gross"]
            exp[(ACCOUNTS["employer_si"], r["kostl"])] = exp.get((ACCOUNTS["employer_si"], r["kostl"]), 0) + r["si_er"]
        for (acc, k), amt in sorted(exp.items()):
            if amt:
                lines.append(dict(hkont=acc, amount=amt, kostl=k, sgtxt="Payroll %04d/%02d" % (y, p)))
        tot = _totals(res)
        for acc, amt, txt in ((ACCOUNTS["payable"], tot["net"], "Net pay"),
                              (ACCOUNTS["si_payable"], tot["si_ee"] + tot["si_er"], "Social insurance"),
                              (ACCOUNTS["tax_payable"], tot["tax"], "Salary income tax"),
                              (ACCOUNTS["martyrs_payable"], tot["martyrs"], "Martyrs' fund")):
            if amt:
                lines.append(dict(hkont=acc, amount=-amt, sgtxt="%s %04d/%02d" % (txt, y, p)))
        belnr = write(conn, "SA", _posting_date(last), user, "PY%04d%02d" % (y, p), "Payroll %04d/%02d" % (y, p),
                      lines, tcode="PC00_M99_CIPE")
        conn.execute("UPDATE hr_payroll_run SET status='POST', belnr=? WHERE gjahr=? AND perio=?", (belnr, y, p))
    return dict(belnr=belnr, message="Payroll %04d/%02d posted - accounting document %s" % (y, p, belnr))


def reverse_posting(conn, y, p, user):
    from fi import gl
    y, p, first, last = _period(y, p)
    with transaction(conn):
        st = status(conn, y, p)
        if not st or st["status"] != "POST":
            raise MMError("Payroll %04d/%02d is not posted (or already paid)" % (y, p), "PY", "006")
        gl.reverse(conn, st["belnr"], int(_posting_date(last)[:4]), _posting_date(last), "01", user)
        conn.execute("UPDATE hr_payroll_run SET status='REL', belnr='' WHERE gjahr=? AND perio=?", (y, p))
    return dict(message="Posting of payroll %04d/%02d reversed - correct and post again" % (y, p))


def pay(conn, y, p, user, budat=None):
    """PC00_M99_DTA: bank transfer of the net pay (payroll payable to bank)."""
    from fi.document import write
    from mm.util import parse_date
    y, p, first, last = _period(y, p)
    with transaction(conn):
        st = status(conn, y, p)
        if not st or st["status"] != "POST":
            raise MMError("Post payroll %04d/%02d before paying it" % (y, p), "PY", "007")
        net = sum(r["net"] for r in results(conn, y, p))
        d = parse_date(budat) if budat else _posting_date(last)
        belnr = write(conn, "SA", d, user, "PYPAY%04d%02d" % (y, p), "Salary transfer %04d/%02d" % (y, p),
                      [dict(hkont=ACCOUNTS["payable"], amount=net, sgtxt="Net pay %04d/%02d" % (y, p)),
                       dict(hkont=ACCOUNTS["bank"], amount=-net, sgtxt="Salary transfer %04d/%02d" % (y, p))],
                      tcode="PC00_M99_DTA")
        conn.execute("UPDATE hr_payroll_run SET status='PAID', pay_belnr=? WHERE gjahr=? AND perio=?", (belnr, y, p))
        transfers = [dict(pernr=r["pernr"], name=r["name"], iban=r["iban"], local=r["net"],
                          waers=r["waers"] or "EGP", amount=r["net_fc"] if r["net_fc"] is not None else r["net"])
                     for r in results(conn, y, p)]
    return dict(belnr=belnr, transfers=transfers,
                message="Net pay %04d/%02d transferred - accounting document %s" % (y, p, belnr))


def runs(conn):
    return rows(conn.execute("SELECT * FROM hr_payroll_run ORDER BY gjahr DESC, perio DESC"))
