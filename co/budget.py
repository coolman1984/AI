"""Budget and availability control (2-x), like SAP budgeting of orders / FM budget control.

Every cost center (KS...) or internal order (OR...) can get an overall budget per fiscal
year: original budget (2-3 ZBUD01) + supplements - returns (2-6 ZBUD02). Only the
released part can be spent (2-6 ZBUD_REL). The availability control (2-1 / 2-4 ZBUD_PROF)
checks
  - every actual cost posting from FI / MM (goods issue, invoice, FB50 ...): actual costs
    of the year + the new posting must not exceed err_pct % of the released budget;
  - every purchase order with account assignment (if check_po): actual + open commitments
    + the new order must not exceed it either.
Above warn_pct % the posting is allowed but a warning is written to the budget log.
Objects without a budget are not checked.
"""
from mm.db import transaction
from mm.util import MMError, now_ts, parse_amount, parse_int

TYPES = {"ORIG": "Original budget", "SUPP": "Supplement", "RET": "Return", "REL": "Release",
         "WARN": "Availability control: warning", "ERR": "Availability control: refused"}


def _obj(conn, objnr):
    objnr = (objnr or "").strip().upper()
    if objnr.startswith("KS"):
        if conn.execute("SELECT 1 FROM cost_center WHERE kostl=?", (objnr[2:],)).fetchone():
            return objnr, "Cost center %s" % objnr[2:]
        raise MMError("Cost center %s does not exist" % objnr[2:], "BP", "601")
    if objnr.startswith("OR"):
        if conn.execute("SELECT 1 FROM orders WHERE aufnr=?", (objnr[2:],)).fetchone():
            return objnr, "Order %s" % objnr[2:]
        raise MMError("Order %s does not exist" % objnr[2:], "BP", "601")
    if objnr.isdigit() and conn.execute("SELECT 1 FROM cost_center WHERE kostl=?", (objnr,)).fetchone():
        return "KS" + objnr, "Cost center %s" % objnr
    raise MMError("Enter a cost center (e.g. 4200) or an order (OR + number)", "BP", "600")


def profile(conn):
    r = conn.execute("SELECT * FROM co_budget_prof WHERE prof='0001'").fetchone()
    return dict(r) if r else dict(prof="0001", warn_pct=90, err_pct=100, check_po=1, usnam="", ts="")


def set_profile(conn, warn_pct, err_pct, check_po=True, user=""):
    """2-1 ZBUD_PROF: tolerance limits of the availability control"""
    w = parse_int(warn_pct, "warning limit %", 1, 200)
    e = parse_int(err_pct, "error limit %", 1, 200)
    if w > e:
        raise MMError("The warning limit must not be above the error limit", "BP", "602")
    with transaction(conn):
        conn.execute("INSERT OR REPLACE INTO co_budget_prof VALUES ('0001',?,?,?,?,?)",
                     (w, e, 1 if check_po in (True, 1, "1", "X", "true") else 0, user, now_ts()))
    return {"message": "Availability control: warning from %d %%, refused from %d %% of the released budget" % (w, e)}


def _row(conn, objnr, gjahr):
    return conn.execute("SELECT * FROM co_budget WHERE objnr=? AND gjahr=?", (objnr, gjahr)).fetchone()


def _log(conn, objnr, gjahr, typ, amount, text, user):
    conn.execute("INSERT INTO co_budget_log (objnr,gjahr,typ,amount,text,usnam,ts) VALUES (?,?,?,?,?,?,?)",
                 (objnr, gjahr, typ, amount, (text or "")[:80], user, now_ts()))


def consumption(conn, objnr, gjahr, exclude_ref=None):
    """actual primary costs of the year and open commitments (PO / PR) of the object"""
    actual = conn.execute("SELECT COALESCE(SUM(i.wtg),0) FROM co_item i JOIN cost_element e USING (kstar) "
                          "WHERE i.objnr=? AND i.gjahr=? AND i.wrttp='04' AND e.katyp=1",
                          (objnr, int(gjahr))).fetchone()[0]
    from .reports import commitments
    commit = sum(c["amount"] for c in commitments(conn, objnr, int(gjahr)) if c["refbn"] != exclude_ref)
    return {"actual": actual, "commitment": commit}


def post(conn, objnr, gjahr, typ, amount, user, text=""):
    """budget document: ORIG / SUPP / RET / REL (amount in currency units, positive)"""
    objnr, otext = _obj(conn, objnr)
    gjahr = parse_int(gjahr, "fiscal year", 2000, 2100)
    typ = (typ or "").upper()
    if typ not in ("ORIG", "SUPP", "RET", "REL"):
        raise MMError("Budget transaction %s does not exist (ORIG, SUPP, RET, REL)" % typ, "BP", "604")
    amt = parse_amount(amount)
    with transaction(conn):
        r = _row(conn, objnr, gjahr)
        if not r:
            if typ != "ORIG":
                raise MMError("%s has no budget for %d - enter the original budget first (ZBUD01)" % (otext, gjahr),
                              "BP", "605")
            conn.execute("INSERT INTO co_budget (objnr,gjahr) VALUES (?,?)", (objnr, gjahr))
            r = _row(conn, objnr, gjahr)
        budget = r["orig"] + r["supp"] - r["ret"]
        if typ == "ORIG":
            conn.execute("UPDATE co_budget SET orig=orig+? WHERE objnr=? AND gjahr=?", (amt, objnr, gjahr))
        elif typ == "SUPP":
            conn.execute("UPDATE co_budget SET supp=supp+? WHERE objnr=? AND gjahr=?", (amt, objnr, gjahr))
        elif typ == "RET":
            used = consumption(conn, objnr, gjahr)
            free = budget - max(used["actual"] + used["commitment"], 0)
            if amt > free:
                raise MMError("Only %.2f of the budget is not used yet - a return of %.2f is not possible" % (
                    free / 100.0, amt / 100.0), "BP", "612")
            conn.execute("UPDATE co_budget SET ret=ret+?, released=MIN(released, ?) WHERE objnr=? AND gjahr=?",
                         (amt, budget - amt, objnr, gjahr))
        else:
            if r["released"] + amt > budget:
                raise MMError("Release %.2f exceeds the budget: budget %.2f, already released %.2f" % (
                    amt / 100.0, budget / 100.0, r["released"] / 100.0), "BP", "611")
            conn.execute("UPDATE co_budget SET released=released+? WHERE objnr=? AND gjahr=?", (amt, objnr, gjahr))
        _log(conn, objnr, gjahr, typ, amt, text, user)
    return {"message": "%s %d: %s %.2f posted" % (otext, gjahr, TYPES[typ], amt / 100.0)}


def check(conn, objnr, gjahr, add, with_commitments=False, what="posting", user="", exclude_ref=None):
    """availability control; add = new costs (cents). Objects without budget are not checked."""
    if add <= 0:
        return None
    r = _row(conn, objnr, int(gjahr))
    if not r:
        return None
    prof = profile(conn)
    used = consumption(conn, objnr, gjahr, exclude_ref)
    total = used["actual"] + (used["commitment"] if with_commitments else 0) + add
    limit = r["released"] * prof["err_pct"] // 100
    otext = ("Cost center %s" if objnr.startswith("KS") else "Order %s") % objnr[2:]
    if total > limit:
        raise MMError("Budget exceeded: %s %d - released budget %.2f, already used %.2f, this %s %.2f "
                      "(ZBUD_RPT)" % (otext, int(gjahr), r["released"] / 100.0, (total - add) / 100.0, what,
                                      add / 100.0), "BP", "603")
    if total > r["released"] * prof["warn_pct"] // 100:
        _log(conn, objnr, int(gjahr), "WARN", add, "%s: %.0f %% of the released budget used" % (
            what, total * 100.0 / max(r["released"], 1)), user)
    return True


def check_items(conn, items, gjahr, with_commitments=False, what="posting", user="", exclude_ref=None):
    """items: [{objnr, wtg}] - sum per object and check each"""
    per = {}
    for i in items:
        if i.get("objnr") and (i.get("wtg") or 0) > 0:
            per[i["objnr"]] = per.get(i["objnr"], 0) + i["wtg"]
    for objnr, add in per.items():
        check(conn, objnr, gjahr, add, with_commitments, what, user, exclude_ref)


def report(conn, gjahr):
    """2-6 ZBUD_RPT: budget / released / actual / commitment / available per object"""
    out = []
    for r in conn.execute("SELECT * FROM co_budget WHERE gjahr=? ORDER BY objnr", (int(gjahr),)):
        used = consumption(conn, r["objnr"], r["gjahr"])
        budget = r["orig"] + r["supp"] - r["ret"]
        name = ""
        if r["objnr"].startswith("KS"):
            c = conn.execute("SELECT name FROM cost_center WHERE kostl=?", (r["objnr"][2:],)).fetchone()
            name = c["name"] if c else ""
        else:
            o = conn.execute("SELECT ktext FROM orders WHERE aufnr=?", (r["objnr"][2:],)).fetchone()
            name = o["ktext"] if o and "ktext" in o.keys() else ""
        avail = r["released"] - used["actual"] - used["commitment"]
        out.append(dict(objnr=r["objnr"], obj=r["objnr"][2:], typ="Cost center" if r["objnr"].startswith("KS")
                        else "Order", name=name, orig=r["orig"], supp=r["supp"], ret=r["ret"], budget=budget,
                        released=r["released"], actual=used["actual"], commitment=used["commitment"],
                        available=avail, used_pct=round((used["actual"] + used["commitment"]) * 100.0 /
                                                        r["released"], 1) if r["released"] else None))
    return out


def log(conn, objnr=None, gjahr=None):
    sql, a = "SELECT * FROM co_budget_log WHERE 1=1", []
    if objnr:
        sql += " AND objnr=?"
        a.append(_obj(conn, objnr)[0])
    if gjahr:
        sql += " AND gjahr=?"
        a.append(int(gjahr))
    out = [dict(r) for r in conn.execute(sql + " ORDER BY id DESC LIMIT 500", a)]
    for r in out:
        r["typ_text"] = TYPES.get(r["typ"], r["typ"])
    return out
