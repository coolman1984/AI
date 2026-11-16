"""HR in depth:

ZHR_LOAN     employee loan / salary advance: paid out from the bank (Dr 117000 / Cr 113100);
             the payroll deducts the monthly installment until it is repaid (Cr 117000)
ZHR_ADDPAY   one-time payments and deductions of a month: bonus, incentive (taxable earnings),
             penalty in days of pay (to the workers' penalties fund 177500), other deductions
ZHR_EVENTS   follow-up: probation ending, fixed-term contracts ending, retirement age,
             service anniversaries
ZHR_LEAVEBAL leave balances of all employees (entitlement, taken, requested, remaining)
ZHR_COST     payroll cost per cost center and month (gross + employer social insurance)
ZHR_CLOSE    HR / payroll month-end: the open work in order with its status
"""
import calendar
import datetime

from mm import util as clock
from mm.db import transaction
from mm.util import MMError, now_ts, parse_amount, parse_date, parse_int, rdiv

from .config import ACCOUNTS, ADDPAY_TYPES, LOAN_TYPES, PROBATION_DAYS, RETIREMENT_AGE


def _emp(conn, pernr):
    e = conn.execute("SELECT * FROM hr_employee WHERE pernr=?", ((pernr or "").strip(),)).fetchone()
    if not e:
        raise MMError("Employee %s does not exist" % pernr, "HR", "981")
    if e["status"] != "A":
        raise MMError("Employee %s has left the company" % pernr, "HR", "982")
    return e


# ------------------------------------------------------------------ loans
def create_loan(conn, data, user):
    from fi import gl
    typ = (data.get("typ") or "LOAN").upper()
    if typ not in LOAN_TYPES:
        raise MMError("Loan type %s does not exist" % typ, "HR", "983")
    amount = parse_amount(data.get("amount"))
    inst = parse_amount(data.get("installment")) if data.get("installment") not in (None, "") else amount
    if inst > amount:
        raise MMError("The installment is higher than the loan", "HR", "984")
    y = parse_int(data.get("gjahr"), "first year", 2000, 2100)
    p = parse_int(data.get("perio"), "first month", 1, 12)
    budat = parse_date(data.get("budat"))
    with transaction(conn):
        e = _emp(conn, data.get("pernr"))
        net = conn.execute("SELECT net FROM hr_payroll WHERE pernr=? ORDER BY gjahr DESC, perio DESC LIMIT 1",
                           (e["pernr"],)).fetchone()
        if net and inst > net["net"]:
            raise MMError("The installment %.2f is higher than the last net pay %.2f" % (inst / 100.0, net["net"] / 100.0),
                          "HR", "985")
        txt = ("%s %s %s" % (LOAN_TYPES[typ], e["pernr"], e["name"]))[:50]
        m = "%.2f" % (amount / 100.0)
        belnr = gl.general_posting(conn, {"budat": budat, "bktxt": txt[:25]}, [
            {"bschl": "40", "account": ACCOUNTS["loans"], "amount": m, "sgtxt": txt},
            {"bschl": "50", "account": ACCOUNTS["bank"], "amount": m, "sgtxt": txt}], user)
        lid = conn.execute("INSERT INTO hr_loan (pernr,typ,amount,installment,start_gjahr,start_perio,belnr,text,usnam,ts)"
                           " VALUES (?,?,?,?,?,?,?,?,?,?)", (e["pernr"], typ, amount, inst, y, p, belnr,
                                                             (data.get("text") or "")[:60], user, now_ts())).lastrowid
    months = -(-amount // inst)
    return {"id": lid, "belnr": belnr, "months": months,
            "message": "%s %s paid out (document %s) - %d installment(s) from %02d/%d" % (
                LOAN_TYPES[typ], lid, belnr, months, p, y)}


def _repaid(conn, lid, exclude=None):
    sql, a = "SELECT COALESCE(SUM(amount),0) FROM hr_loan_rep WHERE loan_id=?", [lid]
    if exclude:
        sql += " AND NOT (gjahr=? AND perio=?)"
        a += list(exclude)
    return conn.execute(sql, a).fetchone()[0]


def loans(conn, pernr=None, status=None):
    sql, a = "SELECT l.*, e.name FROM hr_loan l JOIN hr_employee e ON e.pernr=l.pernr WHERE 1=1", []
    if pernr:
        sql += " AND l.pernr=?"
        a.append(pernr)
    if status:
        sql += " AND l.status=?"
        a.append(status)
    out = []
    for r in conn.execute(sql + " ORDER BY l.id DESC", a):
        d = dict(r)
        d["repaid"] = _repaid(conn, r["id"])
        d["balance"] = r["amount"] - d["repaid"]
        d["typ_text"] = LOAN_TYPES.get(r["typ"], r["typ"])
        d["start"] = "%02d/%d" % (r["start_perio"], r["start_gjahr"])
        out.append(d)
    return out


# ------------------------------------------------------------------ one-time payments
def add_payment(conn, data, user):
    wt = (data.get("wtype") or "").upper()
    if wt not in ADDPAY_TYPES:
        raise MMError("Wage type %s does not exist" % wt, "HR", "986")
    y = parse_int(data.get("gjahr"), "year", 2000, 2100)
    p = parse_int(data.get("perio"), "month", 1, 12)
    days = amount = 0
    if ADDPAY_TYPES[wt].get("days"):
        from mm.util import parse_num
        d = parse_num(data.get("days"), "days")
        if not 0 < d <= 10:
            raise MMError("A penalty is between 0.25 and 10 days of pay", "HR", "987")
        days = int(round(d * 100))
    else:
        amount = parse_amount(data.get("amount"))
    with transaction(conn):
        e = _emp(conn, data.get("pernr"))
        st = conn.execute("SELECT status FROM hr_payroll_run WHERE gjahr=? AND perio=?", (y, p)).fetchone()
        if st and st["status"] in ("POST", "PAID"):
            raise MMError("Payroll %02d/%d is already posted" % (p, y), "HR", "988")
        aid = conn.execute("INSERT INTO hr_addpay (pernr,gjahr,perio,wtype,amount,days,text,usnam,ts) VALUES "
                           "(?,?,?,?,?,?,?,?,?)", (e["pernr"], y, p, wt, amount, days, (data.get("text") or "")[:60],
                                                   user, now_ts())).lastrowid
    return {"id": aid, "message": "%s for %s %s entered for payroll %02d/%d" % (
        ADDPAY_TYPES[wt]["text"].split(" - ")[0], e["pernr"], e["name"], p, y)}


def delete_payment(conn, aid, user):
    with transaction(conn):
        r = conn.execute("SELECT * FROM hr_addpay WHERE id=?", (int(aid),)).fetchone()
        if not r:
            raise MMError("Entry %s does not exist" % aid, "HR", "989")
        st = conn.execute("SELECT status FROM hr_payroll_run WHERE gjahr=? AND perio=?", (r["gjahr"], r["perio"])).fetchone()
        if st and st["status"] in ("POST", "PAID"):
            raise MMError("Payroll %02d/%d is already posted" % (r["perio"], r["gjahr"]), "HR", "988")
        conn.execute("DELETE FROM hr_addpay WHERE id=?", (r["id"],))
    return {"message": "Entry %s deleted" % aid}


def payments(conn, y, p):
    out = []
    for r in conn.execute("SELECT a.*, e.name FROM hr_addpay a JOIN hr_employee e ON e.pernr=a.pernr WHERE a.gjahr=? "
                          "AND a.perio=? ORDER BY a.pernr, a.id", (int(y), int(p))):
        d = dict(r)
        d["text_wt"] = ADDPAY_TYPES[r["wtype"]]["text"]
        d["kind"] = ADDPAY_TYPES[r["wtype"]]["kind"]
        out.append(d)
    return out


# ------------------------------------------------------------------ payroll hook
def period_items(conn, e, y, p, contract, days_m):
    """additions (taxable), penalties and other deductions and loan installments of a month"""
    add = pen = ded = 0
    for r in conn.execute("SELECT * FROM hr_addpay WHERE pernr=? AND gjahr=? AND perio=?", (e["pernr"], y, p)):
        t = ADDPAY_TYPES[r["wtype"]]
        if t["kind"] == "+":
            add += r["amount"]
        elif t.get("days"):
            pen += rdiv(contract * r["days"], days_m * 100)
        else:
            ded += r["amount"]
    inst = []
    for l in conn.execute("SELECT * FROM hr_loan WHERE pernr=? AND status='A' AND (start_gjahr<? OR (start_gjahr=? AND "
                          "start_perio<=?)) ORDER BY id", (e["pernr"], y, y, p)):
        left = l["amount"] - _repaid(conn, l["id"], exclude=(y, p))
        if left > 0:
            inst.append((l["id"], min(l["installment"], left)))
    return add, pen, ded, inst


def store_installments(conn, y, p, results):
    """called by the payroll run: keep the installments deducted in the month; close repaid loans"""
    conn.execute("DELETE FROM hr_loan_rep WHERE gjahr=? AND perio=?", (y, p))
    for r in results:
        for lid, amt in r.get("_loans") or []:
            if amt:
                conn.execute("INSERT INTO hr_loan_rep (loan_id,gjahr,perio,amount) VALUES (?,?,?,?)", (lid, y, p, amt))
    for l in conn.execute("SELECT id, amount, status FROM hr_loan").fetchall():
        done = _repaid(conn, l["id"]) >= l["amount"]
        new = "C" if done else "A"
        if new != l["status"]:
            conn.execute("UPDATE hr_loan SET status=? WHERE id=?", (new, l["id"]))


# ------------------------------------------------------------------ follow-up
def _add_years(d, n):
    try:
        return d.replace(year=d.year + n)
    except ValueError:
        return d.replace(year=d.year + n, day=28)


def events(conn, key_date=None, days=60):
    kd = datetime.date.fromisoformat(parse_date(key_date) if key_date else clock.today().isoformat())
    horizon = kd + datetime.timedelta(days=parse_int(days, "days", 1, 400))
    out = []
    for e in conn.execute("SELECT e.*, o.text org FROM hr_employee e LEFT JOIN hr_orgunit o ON o.orgeh=e.orgeh WHERE "
                          "e.status='A' ORDER BY e.pernr"):
        hire = datetime.date.fromisoformat(e["hire_date"])

        def add(typ, day, text, urgent):
            out.append(dict(pernr=e["pernr"], name=e["name"], org=e["org"] or "", typ=typ, date=day.isoformat(),
                            days=(day - kd).days, text=text, urgent=urgent))
        prob = hire + datetime.timedelta(days=PROBATION_DAYS)
        if kd <= prob <= horizon:
            add("Probation ends", prob, "Decide: confirm the employment or end it before this date", (prob - kd).days <= 14)
        ce = e["contract_end"] if "contract_end" in e.keys() else ""
        if ce:
            d = datetime.date.fromisoformat(ce)
            if d <= horizon:
                add("Contract ends", d, "Fixed-term contract: renew it or prepare the leaving (PA40)" if d >= kd
                    else "Contract already ended - renew or terminate (PA40)", (d - kd).days <= 30)
        if e["birth_date"]:
            ret = _add_years(datetime.date.fromisoformat(e["birth_date"]), RETIREMENT_AGE)
            if ret <= kd + datetime.timedelta(days=365):
                add("Retirement age", ret, "Reaches %d - plan the successor and the leaving" % RETIREMENT_AGE,
                    ret <= horizon)
        for n in (5, 10, 15, 20, 25, 30):
            a = _add_years(hire, n)
            if kd <= a <= horizon:
                add("%d years of service" % n, a, "Service anniversary - recognition", False)
    out.sort(key=lambda r: (r["date"], r["pernr"]))
    return {"key_date": kd.isoformat(), "horizon": horizon.isoformat(), "rows": out,
            "urgent": sum(1 for r in out if r["urgent"])}


def leave_balances(conn, year=None):
    from .engine import quota
    y = int(year or clock.today().year)
    out = []
    for e in conn.execute("SELECT e.pernr, e.name, o.text org FROM hr_employee e LEFT JOIN hr_orgunit o ON "
                          "o.orgeh=e.orgeh WHERE e.status='A' ORDER BY e.pernr"):
        q = quota(conn, e["pernr"], y)
        q.update(pernr=e["pernr"], name=e["name"], org=e["org"] or "",
                 used_pct=round(q["taken"] * 100.0 / q["entitlement"], 1) if q["entitlement"] else 0)
        out.append(q)
    return {"year": y, "rows": out, "remaining": sum(r["remaining"] for r in out),
            "taken": sum(r["taken"] for r in out), "entitlement": sum(r["entitlement"] for r in out)}


def cost(conn, year=None):
    y = int(year or clock.today().year)
    rows = {}
    for r in conn.execute("SELECT p.kostl, c.name AS ktext, p.perio, SUM(p.gross) g, SUM(p.si_er) s, COUNT(*) n FROM "
                          "hr_payroll p LEFT JOIN cost_center c ON c.kostl=p.kostl WHERE p.gjahr=? GROUP BY p.kostl, "
                          "p.perio", (y,)):
        x = rows.setdefault(r["kostl"], dict(kostl=r["kostl"], ktext=r["ktext"] or "", total=0, heads=0,
                                             **{"m%02d" % m: 0 for m in range(1, 13)}))
        x["m%02d" % r["perio"]] += r["g"] + r["s"]
        x["total"] += r["g"] + r["s"]
        x["heads"] = max(x["heads"], r["n"])
    res = sorted(rows.values(), key=lambda r: -r["total"])
    months = [m for m in range(1, 13) if any(r["m%02d" % m] for r in res)]
    return {"year": y, "rows": res, "months": months, "total": sum(r["total"] for r in res)}


def status(conn, gjahr, perio):
    from .payroll import status as prun
    gjahr = parse_int(gjahr, "year", 2000, 2100)
    perio = parse_int(perio, "period", 1, 12)
    first = "%04d-%02d-01" % (gjahr, perio)
    last = "%04d-%02d-%02d" % (gjahr, perio, calendar.monthrange(gjahr, perio)[1])
    one = lambda sql, *a: conn.execute(sql, a).fetchone()[0]          # noqa: E731
    run = prun(conn, gjahr, perio) or {}
    st = run.get("status") or ""
    steps = []

    def add(step, tcode, ok, info, needed=True):
        steps.append(dict(no=len(steps) + 1, step=step, tcode=tcode, info=info,
                          status="done" if ok else ("open" if needed else "n/a")))
    n = one("SELECT COUNT(*) FROM hr_absence WHERE status='R' AND begda<=?", last)
    add("Leave requests to decide", "ZLEAVE", n == 0, "%d request(s) waiting" % n)
    n = one("SELECT COUNT(*) FROM hr_employee WHERE status='A' AND contract_end<>'' AND contract_end<=?", last)
    add("Ended contracts to renew or terminate", "PA40", n == 0, "%d contract(s)" % n)
    n = one("SELECT COUNT(*) FROM hr_overtime WHERE datum BETWEEN ? AND ?", first, last)
    add("Overtime of the month entered", "PA61", True, "%d entry(ies)" % n)
    n = one("SELECT COUNT(*) FROM hr_addpay WHERE gjahr=? AND perio=?", gjahr, perio)
    add("Bonuses, incentives, penalties entered", "ZHR_ADDPAY", True, "%d entry(ies)" % n)
    n = one("SELECT COUNT(*) FROM hr_loan WHERE status='A'")
    add("Loan installments (deducted by the payroll)", "ZHR_LOAN", True, "%d active loan(s)" % n)
    add("Payroll run", "PC00_M99_CALC", st in ("REL", "POST", "PAID"), st and "status %s" % st or "not run")
    add("Payroll posted to accounting", "PC00_M99_CIPE", st in ("POST", "PAID"), run.get("belnr") or "not posted")
    add("Net pay transferred to the bank", "PC00_M99_DTA", st == "PAID", run.get("pay_belnr") or "not paid")
    done = sum(1 for s in steps if s["status"] == "done")
    return {"gjahr": gjahr, "perio": perio, "steps": steps, "done": done,
            "needed": sum(1 for s in steps if s["status"] != "n/a")}
