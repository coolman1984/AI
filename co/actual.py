"""Actual postings in CO.

KB11N  manual reposting of primary costs (keeps the cost element)
KB21N  direct activity allocation: sender cost center / activity type ->
       receiver cost center or order, valued at the plan price (fix + var)
CO11N  production order confirmation (activity from the work center's cost
       center to the order) - same posting logic as KB21N
KB31N  actual statistical key figures
"""
from mm.db import transaction
from mm.util import MMError, parse_amount, parse_date, parse_qty

from .core import ks, orn, period_of, post_co_doc
from .planning import act_value, plan_skf, price


def _receiver(conn, kostl=None, aufnr=None):
    if aufnr:
        o = conn.execute("SELECT stat FROM orders WHERE aufnr=?", (aufnr,)).fetchone()
        if not o:
            raise MMError("Order %s does not exist" % aufnr, "KO", "001")
        if o["stat"] in ("CRTD", "CLSD"):
            raise MMError("Order %s does not allow postings (status %s)"
                          % (aufnr, o["stat"]), "KO", "011")
        return orn(aufnr)
    if kostl:
        if not conn.execute("SELECT 1 FROM cost_center WHERE kostl=?", (kostl,)).fetchone():
            raise MMError("Cost center %s does not exist" % kostl, "KI", "248")
        return ks(kostl)
    raise MMError("Enter a receiver (cost center or order)", "KI", "235")


def repost(conn, budat, sender, receiver, kstar, amount, text="", user=""):
    """KB11N. sender / receiver: dict(kostl=..) or dict(aufnr=..)"""
    budat = parse_date(budat)
    gjahr, perio = period_of(budat)
    value = parse_amount(amount)
    with transaction(conn):
        ce = conn.execute("SELECT katyp FROM cost_element WHERE kstar=?",
                          (kstar,)).fetchone()
        if not ce or ce["katyp"] != 1:
            raise MMError("Only primary cost elements can be reposted", "KI", "180")
        s = _receiver(conn, **sender)
        r = _receiver(conn, **receiver)
        if s == r:
            raise MMError("Sender and receiver are identical", "KI", "181")
        return post_co_doc(conn, "KAMV", "04", gjahr, perio, [
            dict(objnr=s, kstar=kstar, wtg=-value, parob=r, sgtxt=text),
            dict(objnr=r, kstar=kstar, wtg=value, parob=s, sgtxt=text)],
            text or "Manual repost", user, budat)


def allocate_activity(conn, budat, skostl, lstar, qty, receiver, text="", user="",
                      vrgng="RKL"):
    """KB21N / CO11N. Returns the CO document number."""
    budat = parse_date(budat)
    gjahr, perio = period_of(budat)
    q = parse_qty(qty)
    with transaction(conn):
        a = conn.execute("SELECT * FROM activity_type WHERE lstar=?", (lstar,)).fetchone()
        if not a:
            raise MMError("Activity type %s does not exist" % lstar, "KL", "002")
        p = price(conn, gjahr, perio, skostl, lstar)
        r = _receiver(conn, **receiver)
        if r == ks(skostl):
            raise MMError("Sender and receiver are identical", "KI", "181")
        v, f = act_value(q, p["price_fix"], p["price_var"])
        return post_co_doc(conn, vrgng, "04", gjahr, perio, [
            dict(objnr=ks(skostl), kstar=a["kstar"], wtg=-v, wkf=-f, qty=-q,
                 meinh=a["meinh"], lstar=lstar, parob=r, sgtxt=text),
            dict(objnr=r, kstar=a["kstar"], wtg=v, wkf=f, qty=q, meinh=a["meinh"],
                 lstar=lstar, parob=ks(skostl), sgtxt=text)],
            text or "Activity allocation", user, budat)


def confirm(conn, aufnr, vornr, yield_qty, act_qty, budat, user=""):
    """CO11N: time ticket for one operation of a production order."""
    budat = parse_date(budat)
    with transaction(conn):
        o = conn.execute("SELECT * FROM orders WHERE aufnr=?", (aufnr,)).fetchone()
        if not o or o["auart"] != "PP01":
            raise MMError("Production order %s does not exist" % aufnr, "CO", "001")
        op = conn.execute("SELECT r.*, w.kostl, w.lstar FROM routing r JOIN work_center "
                          "w ON w.arbpl=r.arbpl WHERE r.matnr=? AND r.werks=? AND "
                          "r.vornr=?", (o["matnr"], o["werks"], vornr)).fetchone()
        if not op:
            raise MMError("Operation %s does not exist in order %s" % (vornr, aufnr),
                          "RU", "001")
        doc = allocate_activity(conn, budat, op["kostl"], op["lstar"], act_qty,
                                {"aufnr": aufnr}, "Confirmation %s/%s" % (aufnr, vornr),
                                user)
        conn.execute("INSERT INTO confirmation (aufnr,vornr,arbpl,lmnga,ism,budat,"
                     "codoc,usnam) VALUES (?,?,?,?,?,?,?,?)",
                     (aufnr, vornr, op["arbpl"], parse_qty(yield_qty, allow_zero=True),
                      parse_qty(act_qty), budat, doc, user))
    return doc


def post_skf(conn, budat, kostl, stagr, value):
    """KB31N (actual statistical key figure for the posting period)."""
    gjahr, perio = period_of(parse_date(budat))
    plan_skf(conn, gjahr, perio, perio, kostl, stagr, value, wrttp="04")
    return gjahr, perio
