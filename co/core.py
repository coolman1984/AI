"""CO document posting (COBK/COEP) and small shared helpers.

Objects (OBJNR):  KS<cost center>   cost center
                  OR<order>         internal / production order
Values are integer cents, debit positive. wkf = fixed portion of the value.
"""
import datetime

from mm.db import atomic, next_number
from mm.util import MMError, now_ts, rdiv


def ks(kostl):
    return "KS" + kostl


def orn(aufnr):
    return "OR" + aufnr


def obj_text(objnr):
    if objnr.startswith("KS"):
        return "Cost center " + objnr[2:]
    if objnr.startswith("OR"):
        return "Order " + objnr[2:]
    return objnr


def closing_date(gjahr, perio):
    """Posting date for period-end documents: the last day of the period, but
    never after today (closing the current month early posts on today)."""
    import calendar
    from mm import util
    last = datetime.date(int(gjahr), int(perio), calendar.monthrange(int(gjahr), int(perio))[1])
    t = util.today()
    if last > t and (t.year, t.month) == (last.year, last.month):
        last = t
    return last.isoformat()


def period_of(budat):
    d = datetime.date.fromisoformat(budat)
    return d.year, d.month


def first_day(gjahr, perio):
    return "%04d-%02d-01" % (gjahr, perio)


def last_day(gjahr, perio):
    if perio == 12:
        return "%04d-12-31" % gjahr
    return (datetime.date(gjahr, perio + 1, 1) - datetime.timedelta(days=1)).isoformat()


def is_co_active(conn):
    return conn.execute("SELECT 1 FROM cost_element LIMIT 1").fetchone() is not None


def cost_element(conn, kstar):
    return conn.execute("SELECT * FROM cost_element WHERE kstar=?", (kstar,)).fetchone()


def split(total, weights):
    """Split an integer amount by weights; the rounding rest goes to the
    largest receiver so the parts always add up exactly to the total."""
    tw = sum(weights)
    if tw == 0:
        return [0] * len(weights)
    parts = [rdiv(total * w, tw) for w in weights]
    rest = total - sum(parts)
    if rest:
        i = max(range(len(weights)), key=lambda j: abs(weights[j]))
        parts[i] += rest
    return parts


@atomic
def post_co_doc(conn, vrgng, wrttp, gjahr, perio, items, text="", user="",
                budat=None, refbn=None, run_id=None, balanced=True):
    """items: dict(objnr, kstar, wtg, wkf=0, qty=0, meinh, lstar, parob,
    matnr, sgtxt). Returns the CO document number."""
    items = [i for i in items if i.get("wtg") or i.get("qty")]
    if not items:
        return None
    if balanced and sum(i["wtg"] for i in items) != 0:
        raise MMError("CO document is not balanced (internal error)", "KI", "999")
    budat = budat or first_day(gjahr, perio)
    belnr = str(next_number(conn, "CODOC"))
    conn.execute("INSERT INTO co_doc (belnr,gjahr,perio,budat,vrgng,wrttp,bltxt,"
                 "usnam,cpudt,refbn,run_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                 (belnr, gjahr, perio, budat, vrgng, wrttp, text[:50], user,
                  now_ts(), refbn, run_id))
    for n, i in enumerate(items, start=1):
        conn.execute(
            "INSERT INTO co_item (belnr,buzei,gjahr,perio,wrttp,objnr,kstar,wtg,"
            "wkf,qty,meinh,lstar,parob,vrgng,matnr,budat,sgtxt) VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (belnr, n, gjahr, perio, wrttp, i["objnr"], i["kstar"], i["wtg"],
             i.get("wkf", 0), i.get("qty", 0), i.get("meinh"), i.get("lstar"),
             i.get("parob"), vrgng, i.get("matnr"), budat, i.get("sgtxt")))
    return belnr


@atomic
def reverse_co_doc(conn, belnr, user="", text=""):
    """Post the exact opposite of a CO document (like KB24N / KB14N)."""
    h = conn.execute("SELECT * FROM co_doc WHERE belnr=?", (belnr,)).fetchone()
    if not h:
        raise MMError("CO document %s does not exist" % belnr, "KI", "060")
    if h["stflg"]:
        raise MMError("CO document %s is already reversed" % belnr, "KI", "061")
    items = [dict(objnr=r["objnr"], kstar=r["kstar"], wtg=-r["wtg"], wkf=-r["wkf"],
                  qty=-r["qty"], meinh=r["meinh"], lstar=r["lstar"],
                  parob=r["parob"], matnr=r["matnr"], sgtxt=r["sgtxt"])
             for r in conn.execute("SELECT * FROM co_item WHERE belnr=? ORDER BY "
                                   "buzei", (belnr,))]
    new = post_co_doc(conn, h["vrgng"], h["wrttp"], h["gjahr"], h["perio"], items,
                      text or "Reversal of %s" % belnr, user, h["budat"], belnr,
                      h["run_id"], balanced=False)
    conn.execute("UPDATE co_doc SET stflg=1, stokz=? WHERE belnr=?", (new, belnr))
    conn.execute("UPDATE co_doc SET stflg=1, stokz=? WHERE belnr=?", (belnr, new))
    return new


def object_balance(conn, objnr, gjahr, perio, wrttp="04"):
    return conn.execute("SELECT COALESCE(SUM(wtg),0) FROM co_item WHERE objnr=? AND "
                        "gjahr=? AND perio=? AND wrttp=?",
                        (objnr, gjahr, perio, wrttp)).fetchone()[0]
