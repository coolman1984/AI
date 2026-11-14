"""Closing management (1-5): CO period lock (OKP1) and the period-end closing cockpit
(ZCO_CLOSE) - every step of the month-end with its status, in the order it must run:

  accruals -> activity prices -> distribution -> assessment -> overhead -> variances ->
  settlement -> assessment to CO-PA -> reconciliation FI = CO-PA -> period lock
"""
from mm.db import transaction
from mm.util import MMError, now_ts, parse_int


def is_locked(conn, gjahr, perio):
    return conn.execute("SELECT 1 FROM co_period_lock WHERE gjahr=? AND perio=?",
                        (int(gjahr), int(perio))).fetchone() is not None


def check(conn, gjahr, perio):
    """called for every actual CO posting"""
    if is_locked(conn, gjahr, perio):
        raise MMError("Period %02d/%04d is locked in Controlling for actual postings (OKP1) - unlock it or "
                      "post into an open period" % (int(perio), int(gjahr)), "KI", "400")


def lock(conn, gjahr, perio, on, user):
    """OKP1: lock / unlock a period for all actual CO postings."""
    gjahr = parse_int(gjahr, "fiscal year", 2000, 2100)
    perio = parse_int(perio, "period", 1, 12)
    with transaction(conn):
        if on:
            conn.execute("INSERT OR REPLACE INTO co_period_lock VALUES (?,?,?,?)", (gjahr, perio, user, now_ts()))
        else:
            conn.execute("DELETE FROM co_period_lock WHERE gjahr=? AND perio=?", (gjahr, perio))
    return {"message": "Period %02d/%04d %s for actual postings" % (perio, gjahr, "locked" if on else "unlocked")}


def locks(conn, gjahr):
    return [dict(r) for r in conn.execute("SELECT * FROM co_period_lock WHERE gjahr=? ORDER BY perio",
                                          (int(gjahr),))]


def _docs(conn, vrgng, gjahr, perio):
    return conn.execute("SELECT COUNT(*) FROM co_doc WHERE vrgng=? AND wrttp='04' AND gjahr=? AND perio=? "
                        "AND COALESCE(stflg,0)=0", (vrgng, gjahr, perio)).fetchone()[0]


def status(conn, gjahr, perio):
    """ZCO_CLOSE: status of every closing step of the period (done / open / not needed)."""
    gjahr = parse_int(gjahr, "fiscal year", 2000, 2100)
    perio = parse_int(perio, "period", 1, 12)
    steps = []

    def add(step, tcode, done, info, needed=True):
        steps.append(dict(no=len(steps) + 1, step=step, tcode=tcode,
                          status="done" if done else ("open" if needed else "n/a"), info=info))
    rules = conn.execute("SELECT COUNT(*) FROM co_accrual_rule WHERE gjahr=? AND active=1", (gjahr,)).fetchone()[0]
    runs = conn.execute("SELECT COUNT(*) FROM co_accrual_run WHERE gjahr=? AND perio=? AND reversed=0",
                        (gjahr, perio)).fetchone()[0]
    add("Accruals", "ZACR_RUN", runs > 0, "%d rule(s), %d posted" % (rules, runs), rules > 0)
    prices = conn.execute("SELECT COUNT(*) FROM cc_activity WHERE gjahr=? AND perio=? AND (price_fix+price_var)>0",
                          (gjahr, perio)).fetchone()[0]
    planned = conn.execute("SELECT COUNT(*) FROM cc_activity WHERE gjahr=? AND perio=?", (gjahr, perio)).fetchone()[0]
    add("Activity prices", "KSPI", prices > 0, "%d of %d activity types priced" % (prices, planned), planned > 0)
    for step, tcode, vrgng in (("Distribution", "KSV5", "RKIV"), ("Assessment", "KSU5", "RKIU"),
                               ("Overhead on orders", "KGI2", "KZPI")):
        n = _docs(conn, vrgng, gjahr, perio)
        add(step, tcode, n > 0, "%d document(s)" % n)
    var = conn.execute("SELECT COUNT(DISTINCT aufnr) FROM order_variance WHERE gjahr=? AND perio=?", (gjahr, perio)).fetchone()[0]
    add("Variances of production orders", "KKS2", var > 0, "%d order(s)" % var)
    n = _docs(conn, "KOAO", gjahr, perio)
    add("Settlement of orders", "CO88", n > 0, "%d document(s)" % n)
    n = _docs(conn, "KEU5", gjahr, perio)
    add("Assessment to CO-PA", "KEU5", n > 0, "%d document(s)" % n)
    try:
        from .reports import reconcile
        rec = reconcile(conn, gjahr, perio, perio)
        diff = rec.get("difference") or 0
        ok = abs(float(diff)) < 0.005
        info = "FI result = CO-PA operating result" if ok else "difference %s" % diff
    except Exception as e:  # noqa - shown in the cockpit
        ok, info = False, str(e)
    add("Reconciliation FI = CO-PA", "ZCO_RECON", ok, info)
    locked = is_locked(conn, gjahr, perio)
    add("Period lock", "OKP1", locked, "locked" if locked else "open for postings")
    done = sum(1 for s in steps if s["status"] == "done")
    needed = sum(1 for s in steps if s["status"] != "n/a")
    return {"gjahr": gjahr, "perio": perio, "steps": steps, "locked": locked, "done": done, "needed": needed,
            "message": "%d of %d closing steps done for %02d/%04d" % (done, needed, perio, gjahr)}
