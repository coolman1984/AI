"""Cost center planning (version 0).

KP06  primary cost planning (fixed / variable, activity-dependent or not)
KP26  activity type planning: quantity, capacity, manual price
KP46  statistical key figure planning
KP06 (layout 1-102) activity input planning: receiver needs sender activity
KSPI  plan price calculation (iterative), then plan activity credits

Plan price of an activity type (like SAP, price indicator 1):
    fixed price    = planned fixed costs    / planned activity quantity
    variable price = planned variable costs / planned activity quantity
Activity-dependent costs (planned with the activity type) go to that
activity; activity-independent costs are split equally over the activity
types of the cost center (equivalence number 1).
"""
from mm.db import transaction
from mm.util import MMError, parse_amount, parse_qty, rdiv

from .core import ks, post_co_doc, split


def _periods(pfrom, pto):
    pfrom, pto = int(pfrom), int(pto)
    if not (1 <= pfrom <= pto <= 12):
        raise MMError("Periods must be between 1 and 12 (from <= to)", "KP", "001")
    return list(range(pfrom, pto + 1))


def _cleanup_docs(conn):
    conn.execute("DELETE FROM co_doc WHERE wrttp='01' AND belnr NOT IN "
                 "(SELECT DISTINCT belnr FROM co_item WHERE wrttp='01')")


def plan_costs(conn, gjahr, pfrom, pto, kostl, kstar, fix, var, lstar="",
               distribute=True, user=""):
    """KP06. fix/var = totals for the range (distribute=True, key 2 'equal')
    or values per period (distribute=False)."""
    gjahr = int(gjahr)
    pers = _periods(pfrom, pto)
    fix_c = parse_amount(fix or "0", allow_zero=True)
    var_c = parse_amount(var or "0", allow_zero=True)
    lstar = (lstar or "").upper()
    with transaction(conn):
        if not conn.execute("SELECT 1 FROM cost_center WHERE kostl=?", (kostl,)).fetchone():
            raise MMError("Cost center %s does not exist" % kostl, "KI", "248")
        ce = conn.execute("SELECT katyp FROM cost_element WHERE kstar=?",
                          (kstar,)).fetchone()
        if not ce or ce["katyp"] != 1:
            raise MMError("Cost element %s is not a primary cost element" % kstar,
                          "KP", "002")
        if lstar and not conn.execute("SELECT 1 FROM cc_activity WHERE kostl=? AND "
                                      "lstar=? AND gjahr=?", (kostl, lstar, gjahr)).fetchone():
            raise MMError("Activity type %s is not planned for cost center %s - plan "
                          "it first (KP26)" % (lstar, kostl), "KP", "003")
        if lstar == "" and var_c:
            raise MMError("Variable costs can only be planned activity-dependent "
                          "(enter an activity type)", "KP", "004")
        fparts = split(fix_c, [1] * len(pers)) if distribute else [fix_c] * len(pers)
        vparts = split(var_c, [1] * len(pers)) if distribute else [var_c] * len(pers)
        for p, f, v in zip(pers, fparts, vparts):
            conn.execute("DELETE FROM co_item WHERE wrttp='01' AND vrgng='RKP1' AND "
                         "gjahr=? AND perio=? AND objnr=? AND kstar=? AND "
                         "COALESCE(lstar,'')=?", (gjahr, p, ks(kostl), kstar, lstar))
            post_co_doc(conn, "RKP1", "01", gjahr, p,
                        [dict(objnr=ks(kostl), kstar=kstar, wtg=f + v, wkf=f,
                              lstar=lstar or None)], "Primary cost planning", user,
                        balanced=False)
        _cleanup_docs(conn)


def plan_activity(conn, gjahr, pfrom, pto, kostl, lstar, qty, capacity=None,
                  price_fix=None, price_var=None):
    """KP26: planned activity per period (quantity is per period)."""
    gjahr = int(gjahr)
    q = parse_qty(qty)
    cap = parse_qty(capacity, allow_zero=True) if capacity not in (None, "") else q
    manual = price_fix not in (None, "") or price_var not in (None, "")
    pf = parse_amount(price_fix or "0", allow_zero=True)
    pv = parse_amount(price_var or "0", allow_zero=True)
    with transaction(conn):
        if not conn.execute("SELECT 1 FROM activity_type WHERE lstar=?", (lstar,)).fetchone():
            raise MMError("Activity type %s does not exist" % lstar, "KL", "002")
        if not conn.execute("SELECT 1 FROM cost_center WHERE kostl=?", (kostl,)).fetchone():
            raise MMError("Cost center %s does not exist" % kostl, "KI", "248")
        for p in _periods(pfrom, pto):
            conn.execute("INSERT INTO cc_activity (gjahr,perio,kostl,lstar,plan_qty,"
                         "capacity,price_fix,price_var,price_ind) VALUES "
                         "(?,?,?,?,?,?,?,?,?) ON CONFLICT(gjahr,perio,kostl,lstar) DO "
                         "UPDATE SET plan_qty=excluded.plan_qty, capacity=excluded."
                         "capacity, price_fix=CASE WHEN excluded.price_ind='3' THEN "
                         "excluded.price_fix ELSE price_fix END, price_var=CASE WHEN "
                         "excluded.price_ind='3' THEN excluded.price_var ELSE price_var "
                         "END, price_ind=excluded.price_ind",
                         (gjahr, p, kostl, lstar, q, cap, pf, pv,
                          "3" if manual else "1"))


def plan_skf(conn, gjahr, pfrom, pto, kostl, stagr, value, wrttp="01"):
    """KP46 (plan) / KB31N (actual, wrttp 04): value per period."""
    v = parse_qty(value, allow_zero=True)
    with transaction(conn):
        if not conn.execute("SELECT 1 FROM stat_kf WHERE stagr=?", (stagr,)).fetchone():
            raise MMError("Statistical key figure %s does not exist" % stagr, "KK", "001")
        if not conn.execute("SELECT 1 FROM cost_center WHERE kostl=?", (kostl,)).fetchone():
            raise MMError("Cost center %s does not exist" % kostl, "KI", "248")
        for p in _periods(pfrom, pto):
            conn.execute("INSERT OR REPLACE INTO skf_value VALUES (?,?,?,?,?,?)",
                         (wrttp, int(gjahr), p, kostl, stagr, v))


def plan_activity_input(conn, gjahr, pfrom, pto, kostl, skostl, lstar, qty):
    q = parse_qty(qty, allow_zero=True)
    with transaction(conn):
        if not conn.execute("SELECT 1 FROM cc_activity WHERE kostl=? AND lstar=? AND "
                            "gjahr=?", (skostl, lstar, int(gjahr))).fetchone():
            raise MMError("Sender %s/%s has no activity plan" % (skostl, lstar),
                          "KP", "005")
        for p in _periods(pfrom, pto):
            conn.execute("INSERT OR REPLACE INTO plan_act_input VALUES (?,?,?,?,?,?)",
                         (int(gjahr), p, kostl, skostl, lstar, q))


def price(conn, gjahr, perio, kostl, lstar):
    r = conn.execute("SELECT * FROM cc_activity WHERE gjahr=? AND perio=? AND "
                     "kostl=? AND lstar=?", (gjahr, perio, kostl, lstar)).fetchone()
    if not r:
        raise MMError("No plan price for activity %s on cost center %s in period "
                      "%s/%s (KP26 + KSPI)" % (lstar, kostl, perio, gjahr), "KP", "010")
    if r["price_fix"] + r["price_var"] == 0:
        raise MMError("Plan price of %s/%s is zero - run the plan price "
                      "calculation (KSPI)" % (kostl, lstar), "KP", "011")
    return r


def act_value(qty_m, pf, pv):
    """Value (total, fixed) of an activity quantity at fixed/variable prices."""
    fixed = rdiv(qty_m * pf, 1000)
    return fixed + rdiv(qty_m * pv, 1000), fixed


def kspi(conn, gjahr, perio, user=""):
    """Iterative plan price calculation for one period. Returns the prices."""
    gjahr, perio = int(gjahr), int(perio)
    acts = {r["lstar"]: r for r in conn.execute("SELECT * FROM activity_type")}
    with transaction(conn):
        for _ in range(20):
            conn.execute("DELETE FROM co_item WHERE wrttp='01' AND vrgng IN ('RKP2',"
                         "'RKPL') AND gjahr=? AND perio=?", (gjahr, perio))
            # activity input of receivers, valued at the current sender prices
            for i in conn.execute("SELECT * FROM plan_act_input WHERE gjahr=? AND "
                                  "perio=?", (gjahr, perio)).fetchall():
                r = conn.execute("SELECT * FROM cc_activity WHERE gjahr=? AND perio=? "
                                 "AND kostl=? AND lstar=?", (gjahr, perio, i["skostl"],
                                                             i["lstar"])).fetchone()
                if not r:
                    continue
                v, f = act_value(i["qty"], r["price_fix"], r["price_var"])
                post_co_doc(conn, "RKP2", "01", gjahr, perio, [dict(
                    objnr=ks(i["kostl"]), kstar=acts[i["lstar"]]["kstar"], wtg=v, wkf=f,
                    qty=i["qty"], meinh=acts[i["lstar"]]["meinh"], lstar=i["lstar"],
                    parob=ks(i["skostl"]))], "Plan activity input", user,
                    balanced=False)
            changed = False
            ccs = {}
            for r in conn.execute("SELECT * FROM cc_activity WHERE gjahr=? AND perio=?",
                                  (gjahr, perio)).fetchall():
                ccs.setdefault(r["kostl"], []).append(r)
            for kostl, alist in ccs.items():
                costs = conn.execute(
                    "SELECT lstar, vrgng, SUM(wtg) AS w, SUM(wkf) AS f FROM co_item WHERE "
                    "wrttp='01' AND gjahr=? AND perio=? AND objnr=? AND vrgng<>'RKPL' "
                    "GROUP BY lstar, vrgng", (gjahr, perio, ks(kostl))).fetchall()
                n = len(alist)
                for a in alist:
                    if a["price_ind"] != "1" or a["plan_qty"] == 0:
                        continue
                    fix = var = 0
                    for c in costs:
                        dep = c["vrgng"] == "RKP1" and c["lstar"]
                        if dep and c["lstar"] != a["lstar"]:
                            continue
                        share = 1 if dep else n
                        fix += rdiv(c["f"], share)
                        var += rdiv(c["w"] - c["f"], share)
                    pf = rdiv(fix * 1000, a["plan_qty"])
                    pv = rdiv(var * 1000, a["plan_qty"])
                    if (pf, pv) != (a["price_fix"], a["price_var"]):
                        changed = True
                        conn.execute("UPDATE cc_activity SET price_fix=?, price_var=? "
                                     "WHERE gjahr=? AND perio=? AND kostl=? AND lstar=?",
                                     (pf, pv, gjahr, perio, kostl, a["lstar"]))
            if not changed:
                break
        # plan credit of the planned activity output (sender side)
        for a in conn.execute("SELECT * FROM cc_activity WHERE gjahr=? AND perio=?",
                              (gjahr, perio)).fetchall():
            v, f = act_value(a["plan_qty"], a["price_fix"], a["price_var"])
            post_co_doc(conn, "RKPL", "01", gjahr, perio, [dict(
                objnr=ks(a["kostl"]), kstar=acts[a["lstar"]]["kstar"], wtg=-v, wkf=-f,
                qty=-a["plan_qty"], meinh=acts[a["lstar"]]["meinh"],
                lstar=a["lstar"])], "Plan activity output", user, balanced=False)
        _cleanup_docs(conn)
    return [dict(r) for r in conn.execute(
        "SELECT * FROM cc_activity WHERE gjahr=? AND perio=? ORDER BY kostl, lstar",
        (gjahr, perio))]
