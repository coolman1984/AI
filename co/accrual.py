"""Accruals (5-x): costs that are paid once a year (13th salary, annual bonus, insurance,
maintenance contracts ...) are charged to the cost centers month by month, so that every
month carries its fair share (like SAP KSA3 / FI recurring accruals).

  5-2 ZACR_DEF   rules: cost center, expense account (primary cost element), annual amount
  5-3 ZACR_RUN   monthly run: FI document  Dr expense (cost center)  /  Cr 190000 accrued
                 expenses; one twelfth per month, the last month takes the rounding rest;
                 reversal of a run
  5-4 ZACR_RPT   accrued so far against the annual amount; when the real payment is made
                 it is posted against 190000 (no second expense)
"""
from mm.db import transaction
from mm.util import MMError, now_ts, parse_amount, parse_int, rdiv

LIABILITY = "190000"


def monthly_amounts(annual):
    """12 parts of an annual amount (cents) that add up exactly: rest in December"""
    part = rdiv(annual, 12)
    return [part] * 11 + [annual - 11 * part]


def save_rule(conn, data, user):
    """ZACR_DEF: data text, kostl, hkont, annual, gjahr (, liab, active, id to change)"""
    text = (data.get("text") or "").strip()
    if not text:
        raise MMError("Enter a description of the accrual (e.g. annual bonus)", "CO", "701")
    kostl = (data.get("kostl") or "").strip().upper()
    if not conn.execute("SELECT 1 FROM cost_center WHERE kostl=?", (kostl,)).fetchone():
        raise MMError("Cost center %s does not exist" % kostl, "CO", "704")
    hkont = (data.get("hkont") or "").strip()
    ce = conn.execute("SELECT katyp FROM cost_element WHERE kstar=?", (hkont,)).fetchone()
    if not ce or ce["katyp"] != 1:
        raise MMError("Account %s is not a primary cost element (expense account)" % hkont, "CO", "705")
    liab = (data.get("liab") or LIABILITY).strip()
    from mm.config import GL_ACCOUNTS
    if liab not in GL_ACCOUNTS:
        raise MMError("Accrual account %s does not exist" % liab, "CO", "706")
    annual = parse_amount(data.get("annual"))
    gjahr = parse_int(data.get("gjahr"), "fiscal year", 2000, 2100)
    active = 0 if str(data.get("active", "1")) in ("0", "false", "False", "") else 1
    with transaction(conn):
        if data.get("id"):
            rid = parse_int(data["id"], "rule")
            if not conn.execute("SELECT 1 FROM co_accrual_rule WHERE id=?", (rid,)).fetchone():
                raise MMError("Accrual rule %s does not exist" % rid, "CO", "707")
            conn.execute("UPDATE co_accrual_rule SET text=?, kostl=?, hkont=?, liab=?, annual=?, gjahr=?, active=?, "
                         "usnam=?, ts=? WHERE id=?", (text, kostl, hkont, liab, annual, gjahr, active, user, now_ts(),
                                                      rid))
            return rid
        cur = conn.execute("INSERT INTO co_accrual_rule (text,kostl,hkont,liab,annual,gjahr,active,usnam,ts) VALUES "
                           "(?,?,?,?,?,?,?,?,?)", (text, kostl, hkont, liab, annual, gjahr, active, user, now_ts()))
        return cur.lastrowid


def rules(conn, gjahr=None):
    sql, a = "SELECT r.*, c.name AS kostl_name FROM co_accrual_rule r LEFT JOIN cost_center c USING (kostl)", []
    if gjahr:
        sql += " WHERE r.gjahr=?"
        a.append(int(gjahr))
    return [dict(r) for r in conn.execute(sql + " ORDER BY r.id", a)]


def run(conn, gjahr, perio, user, test=False):
    """ZACR_RUN: one FI document per active rule of the year; test=True shows the amounts only"""
    from co.core import closing_date
    from co.fi import post_gl_document
    gjahr = parse_int(gjahr, "fiscal year", 2000, 2100)
    perio = parse_int(perio, "period", 1, 12)
    if conn.execute("SELECT 1 FROM co_accrual_run WHERE gjahr=? AND perio=? AND reversed=0",
                    (gjahr, perio)).fetchone():
        raise MMError("The accruals of %02d/%04d are already posted - reverse the run first" % (perio, gjahr),
                      "CO", "702")
    budat = closing_date(gjahr, perio)
    docs = []
    with transaction(conn):
        for r in conn.execute("SELECT * FROM co_accrual_rule WHERE gjahr=? AND active=1 ORDER BY id",
                              (gjahr,)).fetchall():
            amt = monthly_amounts(r["annual"])[perio - 1]
            if not amt:
                continue
            d = dict(rule=r["id"], text=r["text"], kostl=r["kostl"], hkont=r["hkont"], amount=amt, belnr="")
            if not test:
                money = "%.2f" % (amt / 100.0)
                res = post_gl_document(conn, {"budat": budat, "bktxt": "Accrual %02d/%04d" % (perio, gjahr)}, [
                    {"hkont": r["hkont"], "debit": money, "kostl": r["kostl"], "sgtxt": "ACR%d %s" % (r["id"], r["text"])},
                    {"hkont": r["liab"] or LIABILITY, "credit": money, "sgtxt": "ACR%d %s" % (r["id"], r["text"])}],
                    user)
                d["belnr"] = res["belnr"]
                conn.execute("INSERT INTO co_accrual_run (gjahr,perio,rule_id,belnr,fi_gjahr,amount,usnam,ts) "
                             "VALUES (?,?,?,?,?,?,?,?)", (gjahr, perio, r["id"], res["belnr"], res["gjahr"], amt,
                                                          user, now_ts()))
            docs.append(d)
    total = sum(d["amount"] for d in docs)
    return {"posted": 0 if test else len(docs), "docs": docs, "total": total, "test": test,
            "message": "%s %d accrual(s) for %02d/%04d, total %.2f%s" % (
                "Test run:" if test else "Posted", len(docs), perio, gjahr, total / 100.0,
                "" if docs else " - no active rule for this year (ZACR_DEF)")}


def reverse(conn, gjahr, perio, user):
    from fi import gl
    gjahr = parse_int(gjahr, "fiscal year", 2000, 2100)
    perio = parse_int(perio, "period", 1, 12)
    with transaction(conn):
        rows = conn.execute("SELECT * FROM co_accrual_run WHERE gjahr=? AND perio=? AND reversed=0",
                            (gjahr, perio)).fetchall()
        if not rows:
            raise MMError("No accrual run to reverse in %02d/%04d" % (perio, gjahr), "CO", "703")
        for r in rows:
            gl.reverse(conn, r["belnr"], r["fi_gjahr"], None, "01", user)
            conn.execute("UPDATE co_accrual_run SET reversed=1 WHERE id=?", (r["id"],))
    return {"message": "%d accrual document(s) of %02d/%04d reversed" % (len(rows), perio, gjahr)}


def report(conn, gjahr):
    """ZACR_RPT: per rule the annual amount, accrued so far, open rest, months posted"""
    out = []
    for r in rules(conn, gjahr):
        runs = conn.execute("SELECT perio, amount FROM co_accrual_run WHERE rule_id=? AND reversed=0 ORDER BY perio",
                            (r["id"],)).fetchall()
        accrued = sum(x["amount"] for x in runs)
        out.append(dict(r, accrued=accrued, rest=r["annual"] - accrued, months=len(runs),
                        periods=",".join(str(x["perio"]) for x in runs),
                        pct=round(accrued * 100.0 / r["annual"], 1) if r["annual"] else None))
    return out


def runs(conn, gjahr):
    return [dict(r) for r in conn.execute(
        "SELECT a.*, r.text, r.kostl FROM co_accrual_run a JOIN co_accrual_rule r ON r.id=a.rule_id WHERE a.gjahr=? "
        "ORDER BY a.perio DESC, a.id", (int(gjahr),))]
