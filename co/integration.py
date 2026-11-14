"""FI/MM -> CO integration.

Every accounting line on a primary cost element must carry a CO object
(cost center, order, or profitability segment for revenues). If the posting
has none, the default account assignment (OKB9) is used; if there is no
default either, the posting is rejected - message KI 235, like SAP.
"""
from mm.util import MMError

from .core import is_co_active, ks, orn, period_of, post_co_doc


def check_order(conn, aufnr, for_gr=False):
    o = conn.execute("SELECT * FROM orders WHERE aufnr=?", (aufnr,)).fetchone()
    if not o:
        raise MMError("Order %s does not exist" % aufnr, "KO", "001")
    if o["stat"] == "CRTD":
        raise MMError("Order %s is not released (status CRTD)" % aufnr, "KO", "011")
    if o["stat"] == "CLSD":
        raise MMError("Order %s is closed - no postings allowed" % aufnr, "KO", "012")
    from pp.config import GR_ORDER_TYPES
    if for_gr and o["auart"] not in GR_ORDER_TYPES:
        raise MMError("Order %s is not a production order" % aufnr, "KO", "013")
    return o


def derive_assignments(conn, lines):
    if not is_co_active(conn):
        return
    ces = {r["kstar"]: r["katyp"] for r in conn.execute("SELECT kstar, katyp FROM "
                                                         "cost_element")}
    for l in lines:
        katyp = ces.get(l["hkont"])
        if katyp is None:
            l["kostl"] = l["aufnr"] = None      # not CO-relevant
            continue
        if katyp in (11, 12):
            if not l.get("paobj"):
                raise MMError("Revenue account %s requires a profitability "
                              "segment (post via billing)" % l["hkont"], "KI", "236")
            continue
        if l.get("aufnr"):
            o = conn.execute("SELECT stat FROM orders WHERE aufnr=?",
                             (l["aufnr"],)).fetchone()
            if not o:
                raise MMError("Order %s does not exist" % l["aufnr"], "KO", "001")
            if o["stat"] == "CLSD":
                raise MMError("Order %s is closed" % l["aufnr"], "KO", "012")
            l["kostl"] = None                   # order is the real object
            continue
        if not l.get("kostl"):
            d = conn.execute("SELECT kostl FROM default_aa WHERE kstar=?",
                             (l["hkont"],)).fetchone()
            if d and d["kostl"]:
                l["kostl"] = d["kostl"]
            else:
                raise MMError("Account %s requires an assignment to a CO object"
                              % l["hkont"], "KI", "235")
        if not conn.execute("SELECT 1 FROM cost_center WHERE kostl=?",
                            (l["kostl"],)).fetchone():
            raise MMError("Cost center %s does not exist" % l["kostl"], "KI", "248")


def post_from_fi(conn, belnr, gjahr, budat, user, awkey, bktxt, lines):
    """Create the CO document (business transaction COIN) for all lines on
    primary cost elements with a cost center or order."""
    if not is_co_active(conn):
        return None
    year, perio = period_of(budat)
    items = []
    for l in lines:
        obj = orn(l["aufnr"]) if l.get("aufnr") else ks(l["kostl"]) if l.get("kostl") \
            else None
        if not obj:
            continue
        ce = conn.execute("SELECT katyp FROM cost_element WHERE kstar=?",
                          (l["hkont"],)).fetchone()
        if not ce or ce["katyp"] != 1:
            continue
        meinh = None
        if l.get("matnr"):
            m = conn.execute("SELECT meins FROM material WHERE matnr=?",
                             (l["matnr"],)).fetchone()
            meinh = m["meins"] if m else None
        sign = 1 if l["amount"] > 0 else -1
        items.append(dict(objnr=obj, kstar=l["hkont"], wtg=l["amount"],
                          qty=sign * (l.get("menge") or 0) if l.get("matnr") else 0,
                          meinh=meinh, matnr=l.get("matnr"),
                          sgtxt=l.get("sgtxt") or bktxt))
    if not items:
        return None
    from .budget import check_items                      # availability control (budgets)
    check_items(conn, items, year, what="posting %s" % (bktxt or belnr), user=user)
    return post_co_doc(conn, "COIN", "04", year, perio, items,
                       bktxt or "FI document %s" % belnr, user, budat,
                       refbn="%s/%s" % (belnr, awkey), balanced=False)
