"""MM posting periods (MMPV / MMRV) and stock on a posting date (MB5B).

Without an entry in mm_period every date may be posted (as before). MMPV opens
the next period: goods movements are then allowed in the current period and,
while "previous period open" is set, in the previous one (message M7 053).
Closing a period writes valuation_hist (MBEWH) with the stock and value at the
period end, so past stock is known even after later price changes.
"""
import calendar
import datetime

from mm.db import atomic, rows
from mm.util import MMError, now_ts, parse_date

MMPER_SCHEMA = """
CREATE TABLE IF NOT EXISTS mm_period (      -- MARV
    id INTEGER PRIMARY KEY, gjahr INTEGER, perio INTEGER, prev_open INTEGER DEFAULT 1,
    changed TEXT, changed_by TEXT);
CREATE TABLE IF NOT EXISTS valuation_hist ( -- MBEWH
    matnr TEXT, bwkey TEXT, gjahr INTEGER, perio INTEGER, lbkum INTEGER, salk3 INTEGER,
    verpr INTEGER, stprs INTEGER, vprsv TEXT, PRIMARY KEY (matnr, bwkey, gjahr, perio));
"""


def _prev(y, p):
    return (y - 1, 12) if p == 1 else (y, p - 1)


def _next(y, p):
    return (y + 1, 1) if p == 12 else (y, p + 1)


def current(conn):
    r = conn.execute("SELECT * FROM mm_period WHERE id=1").fetchone()
    return dict(r) if r else None


def check(conn, budat):
    """Called by every goods movement."""
    r = conn.execute("SELECT * FROM mm_period WHERE id=1").fetchone()
    if not r:
        return
    y, m = int(budat[:4]), int(budat[5:7])
    ok = [(r["gjahr"], r["perio"])] + ([_prev(r["gjahr"], r["perio"])] if r["prev_open"] else [])
    if (y, m) not in ok:
        raise MMError("Posting only possible in periods %s in company code 1000 (MMPV)"
                      % " and ".join("%02d %d" % (p, yy) for yy, p in ok), "M7", "053")


def _period_end(y, p):
    return datetime.date(y, p, calendar.monthrange(y, p)[1]).isoformat()


def stock_at(conn, werks, key_date, matnr=None):
    """MB5B: quantity from the material documents and value from the stock
    accounts (BSX lines carry the material) up to the key date."""
    key_date = parse_date(key_date)
    sql = ("SELECT m.matnr, m.maktx, m.meins, "
           "(SELECT COALESCE(SUM(CASE WHEN i.shkzg='S' THEN i.menge ELSE -i.menge END),0) FROM mat_doc_item i "
           " JOIN mat_doc d ON d.mblnr=i.mblnr AND d.mjahr=i.mjahr WHERE i.matnr=m.matnr AND i.werks=? "
           " AND d.budat<=?) AS qty, "
           "(SELECT COALESCE(SUM(CASE WHEN a.shkzg='S' THEN a.dmbtr ELSE -a.dmbtr END),0) FROM acc_doc_item a "
           " JOIN acc_doc h ON h.belnr=a.belnr AND h.gjahr=a.gjahr WHERE a.ktosl='BSX' AND a.matnr=m.matnr "
           " AND a.werks=? AND h.budat<=?) AS value "
           "FROM material m WHERE EXISTS (SELECT 1 FROM valuation v WHERE v.matnr=m.matnr AND v.bwkey=?)")
    a = [werks, key_date, werks, key_date, werks]
    if matnr:
        sql += " AND m.matnr=?"
        a.append(matnr.upper())
    return [r for r in rows(conn.execute(sql + " ORDER BY m.matnr", a)) if r["qty"] or r["value"]]


@atomic
def open_next(conn, gjahr, perio, user="", prev_open=True):
    """MMPV: make (gjahr, perio) the current MM period. The period before the
    previous one is closed and its stock is kept in valuation_hist."""
    gjahr, perio = int(gjahr), int(perio)
    if not 1 <= perio <= 12:
        raise MMError("Period must be 1 - 12", "M7", "054")
    cur = current(conn)
    if cur and (gjahr, perio) != _next(cur["gjahr"], cur["perio"]):
        ny, np_ = _next(cur["gjahr"], cur["perio"])
        raise MMError("Only the next period %02d %d can be opened (current %02d %d)"
                      % (np_, ny, cur["perio"], cur["gjahr"]), "M7", "055")
    closed = _prev(gjahr, perio) if cur else None
    conn.execute("INSERT OR REPLACE INTO mm_period VALUES (1,?,?,?,?,?)",
                 (gjahr, perio, 1 if prev_open else 0, now_ts(), user))
    if closed:
        snapshot(conn, *closed)
    return {"message": "MM period %02d %d is open%s" % (perio, gjahr,
            " (previous period %02d %d stays open)" % _prev(gjahr, perio)[::-1] if prev_open else "")}


@atomic
def close_previous(conn, user=""):
    """MMRV: close the previous period (only the current one stays open)."""
    cur = current(conn)
    if not cur:
        raise MMError("MM periods are not active yet - open one with MMPV", "M7", "056")
    conn.execute("UPDATE mm_period SET prev_open=0, changed=?, changed_by=? WHERE id=1", (now_ts(), user))
    snapshot(conn, *_prev(cur["gjahr"], cur["perio"]))


def snapshot(conn, y, p):
    end = _period_end(y, p)
    for w in conn.execute("SELECT DISTINCT bwkey FROM valuation").fetchall():
        for r in stock_at(conn, w[0], end):
            v = conn.execute("SELECT * FROM valuation WHERE matnr=? AND bwkey=?", (r["matnr"], w[0])).fetchone()
            conn.execute("INSERT OR REPLACE INTO valuation_hist VALUES (?,?,?,?,?,?,?,?,?)",
                         (r["matnr"], w[0], y, p, r["qty"], r["value"], v["verpr"], v["stprs"], v["vprsv"]))


def history(conn, matnr=None):
    sql, a = "SELECT * FROM valuation_hist WHERE 1=1", []
    if matnr:
        sql += " AND matnr=?"
        a.append(matnr.upper())
    return rows(conn.execute(sql + " ORDER BY gjahr DESC, perio DESC, matnr", a))
