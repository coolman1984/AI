"""Recurring entries (2-3 FBD1 / FBD3 / F.14): rent, leasing, subscriptions, service
contracts - a G/L document that is posted every month between the first and the last
date. The run F.14 posts every due document once per period (on the first day of the
period, or on the first date in the start month)."""
import calendar
import json

from mm.db import transaction
from mm.util import MMError, now_ts, parse_amount, parse_date, parse_int


def _check_lines(conn, lines):
    from fi.config import POSTING_KEYS
    from mm.config import GL_ACCOUNTS
    if len(lines) < 2:
        raise MMError("Enter at least two lines", "FRE", "820")
    total = 0
    out = []
    for n, l in enumerate(lines, start=1):
        k = str(l.get("bschl") or "").strip()
        pk = POSTING_KEYS.get(k)
        if not pk or pk[1] not in "SKD":
            raise MMError("Line %d: posting key %s is not allowed here (40/50 G/L, 01/15 customer, 31/25 vendor)"
                          % (n, k), "FRE", "823")
        a = str(l.get("account") or "").strip().upper()
        if pk[1] == "S" and a not in GL_ACCOUNTS:
            raise MMError("Line %d: G/L account %s does not exist" % (n, a), "FRE", "824")
        if pk[1] in "KD" and not conn.execute("SELECT 1 FROM %s WHERE %s=?" % (
                ("vendor", "lifnr") if pk[1] == "K" else ("customer", "kunnr")), (a,)).fetchone():
            raise MMError("Line %d: %s %s does not exist" % (n, "vendor" if pk[1] == "K" else "customer", a),
                          "FRE", "824")
        amt = parse_amount(l.get("amount"))
        total += amt if pk[2] == "S" else -amt
        out.append({"bschl": k, "account": a, "amount": "%.2f" % (amt / 100.0),
                    "kostl": (l.get("kostl") or "").strip().upper() or None, "sgtxt": l.get("sgtxt") or ""})
    if total:
        raise MMError("Debit and credit differ by %.2f" % (total / 100.0), "FRE", "821")
    return out


def save(conn, data, user):
    text = (data.get("text") or "").strip()
    if not text:
        raise MMError("Enter a description (e.g. warehouse rent)", "FRE", "825")
    first = parse_date(data.get("first"))
    last = parse_date(data.get("last")) if data.get("last") else ""
    if last and last < first:
        raise MMError("The last date is before the first date", "FRE", "826")
    lines = _check_lines(conn, data.get("lines") or [])
    with transaction(conn):
        cur = conn.execute("INSERT INTO fi_recurring (text,first,last,lines,usnam,ts) VALUES (?,?,?,?,?,?)",
                           (text, first, last, json.dumps(lines), user, now_ts()))
    return cur.lastrowid


def documents(conn):
    out = []
    for r in conn.execute("SELECT * FROM fi_recurring ORDER BY id"):
        d = dict(r)
        d["lines"] = json.loads(r["lines"])
        d["amount"] = sum(parse_amount(x["amount"]) for x in d["lines"] if x["bschl"] in ("40", "01", "21", "25"))
        d["runs"] = conn.execute("SELECT COUNT(*) FROM fi_recurring_run WHERE rec_id=?", (r["id"],)).fetchone()[0]
        out.append(d)
    return out


def run(conn, gjahr, perio, user, test=False):
    """F.14: post the due recurring documents of the period"""
    from fi import gl
    gjahr = parse_int(gjahr, "fiscal year", 2000, 2100)
    perio = parse_int(perio, "period", 1, 12)
    p1 = "%04d-%02d-01" % (gjahr, perio)
    p2 = "%04d-%02d-%02d" % (gjahr, perio, calendar.monthrange(gjahr, perio)[1])
    due = conn.execute("SELECT * FROM fi_recurring WHERE active=1 AND first<=? AND (last='' OR last IS NULL OR "
                       "last>=?) ORDER BY id", (p2, p1)).fetchall()
    todo = [r for r in due if not conn.execute("SELECT 1 FROM fi_recurring_run WHERE rec_id=? AND gjahr=? AND "
                                               "perio=?", (r["id"], gjahr, perio)).fetchone()]
    if due and not todo:
        raise MMError("The recurring documents of %02d/%04d are already posted" % (perio, gjahr), "FRE", "822")
    docs = []
    with transaction(conn):
        for r in todo:
            budat = max(p1, r["first"])
            d = dict(id=r["id"], text=r["text"], budat=budat, belnr="")
            if not test:
                belnr = gl.general_posting(conn, {"budat": budat, "bktxt": ("Recurring: " + r["text"])[:25]},
                                           json.loads(r["lines"]), user)
                conn.execute("INSERT INTO fi_recurring_run (rec_id,gjahr,perio,belnr,fi_gjahr,usnam,ts) VALUES "
                             "(?,?,?,?,?,?,?)", (r["id"], gjahr, perio, belnr, int(budat[:4]), user, now_ts()))
                d["belnr"] = belnr
            docs.append(d)
    return {"posted": 0 if test else len(docs), "docs": docs, "test": test,
            "message": "%s %d recurring document(s) for %02d/%04d" % ("Test run:" if test else "Posted", len(docs),
                                                                       perio, gjahr)}


def runs(conn, gjahr=None):
    sql, a = ("SELECT r.*, d.text FROM fi_recurring_run r JOIN fi_recurring d ON d.id=r.rec_id", [])
    if gjahr:
        sql += " WHERE r.gjahr=?"
        a.append(int(gjahr))
    return [dict(x) for x in conn.execute(sql + " ORDER BY r.gjahr DESC, r.perio DESC, r.id", a)]
