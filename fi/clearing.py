"""Manual clearing of open items and down payments.

F-44 / F-32 / F-03  clear selected open items of a vendor, customer or an
                    open-item G/L account; a small difference (tolerance) goes
                    to "payment differences", a larger one only as residual item.
F-47 / F-37         down-payment request (statistical, no balance).
F-48 / F-29         down payment through the bank, special G/L indicator A on the
                    alternative reconciliation account (164000 / 170000).
F-54 / F-39         clear the down payment against the final invoice.
"""
from mm.db import atomic, rows, transaction
from mm.util import MMError, now_ts, parse_amount, parse_date

from .document import clear, signed, write

TOLERANCE = 500                      # 5.00 EGP written off to payment differences
DIFF_ACCOUNT = "288000"
DP_ACCOUNT = {"K": "164000", "D": "170000"}
DP_SCHEMA = """
CREATE TABLE IF NOT EXISTS dp_request (     -- F-47 / F-37 noted items
    id INTEGER PRIMARY KEY AUTOINCREMENT, koart TEXT, partner TEXT, amount INTEGER,
    due TEXT, ebeln TEXT DEFAULT '', text TEXT DEFAULT '', status TEXT DEFAULT 'O',
    belnr TEXT, gjahr INTEGER, usnam TEXT, created TEXT);
"""
TCODE = {"K": "F-44", "D": "F-32", "S": "F-03"}


def _items(conn, keys):
    out = []
    for k in keys:
        r = conn.execute("SELECT i.*, h.waers FROM acc_doc_item i JOIN acc_doc h ON h.belnr=i.belnr AND "
                         "h.gjahr=i.gjahr WHERE i.belnr=? AND i.gjahr=? AND i.buzei=?",
                         (str(k[0]), int(k[1]), int(k[2]))).fetchone()
        if not r or r["augbl"]:
            raise MMError("Item %s/%s/%s is not open" % tuple(k), "F5", "263")
        out.append(r)
    return out


def clear_open_items(conn, koart, partner, items, budat, user, residual=False):
    """Clear items [(belnr, gjahr, buzei)] of one vendor (K), customer (D) or
    open-item G/L account (S, partner = account). Returns the clearing document."""
    koart = (koart or "").upper()
    if koart not in TCODE:
        raise MMError("Account type must be K, D or S", "F5", "100")
    partner = (partner or "").upper()
    budat = parse_date(budat)
    with transaction(conn):
        rs = _items(conn, items or [])
        if len(rs) < 2 and not residual:
            raise MMError("Select at least two items that clear each other", "F5", "260")
        for r in rs:
            own = r["hkont"] if koart == "S" else (r["lifnr"] if koart == "K" else r["kunnr"])
            if (koart != "S" and r["koart"] != koart) or own != partner:
                raise MMError("Item %s does not belong to %s" % (r["belnr"], partner), "F5", "264")
            if r["zlspr"]:
                raise MMError("Item %s is blocked for payment - release it first (MRBR)" % r["belnr"],
                              "F5", "267")
        if koart == "S":
            acc = conn.execute("SELECT oi FROM gl_account WHERE hkont=?", (partner,)).fetchone()
            if not acc or not acc["oi"]:
                raise MMError("Account %s is not managed on an open item basis" % partner, "F5", "268")
        if len({r["waers"] or "EGP" for r in rs}) > 1:
            raise MMError("Items in different currencies cannot be cleared together", "F5", "265")
        total = sum(signed(r) for r in rs)            # what remains when they are cleared
        pkey = {"K": "lifnr", "D": "kunnr", "S": "hkont"}[koart]
        base = {"koart": koart, pkey: partner}
        if koart == "S":
            base = {"hkont": partner}
        debit = sum(signed(r) for r in rs if signed(r) > 0)
        credit = sum(signed(r) for r in rs if signed(r) < 0)
        lines = [dict(base, amount=-debit, zfbdt=budat, sgtxt="Clearing (debit items)"),
                 dict(base, amount=-credit, zfbdt=budat, sgtxt="Clearing (credit items)")]
        lines = [l for l in lines if l["amount"]]
        rest = None
        if total:
            if residual:
                rest = dict(base, amount=total, zfbdt=budat, rebzg=rs[0]["belnr"],
                            sgtxt="Residual item after clearing")
                lines.append(rest)
            elif abs(total) <= TOLERANCE:
                lines.append(dict(hkont=DIFF_ACCOUNT, amount=total, sgtxt="Payment difference (tolerance)"))
            else:
                raise MMError("Difference %.2f is larger than the tolerance %.2f - choose 'residual item'"
                              % (total / 100.0, TOLERANCE / 100.0), "F5", "263")
        if not lines:
            raise MMError("Nothing to clear", "F5", "260")
        for l in lines:
            l["wrbtr"] = l["amount"]
        belnr = write(conn, "AB", budat, user, TCODE[koart], "Clearing %s" % partner, lines,
                      tcode=TCODE[koart])
        gj = int(budat[:4])
        n_clearing = len(lines) - (1 if rest else 0) - (1 if total and not residual else 0)
        clear(conn, [(r["belnr"], r["gjahr"], r["buzei"]) for r in rs] +
              [(belnr, gj, i) for i in range(1, n_clearing + 1)], belnr, budat)
    return {"belnr": belnr, "gjahr": gj, "difference": total / 100.0, "residual": bool(rest),
            "message": "Clearing document %s posted" % belnr}


# ------------------------------------------------------------------ down payments
@atomic
def request(conn, koart, partner, amount, due, user, ebeln="", text=""):
    """F-47 (vendor) / F-37 (customer): noted item, no balance."""
    koart = (koart or "").upper()
    partner = (partner or "").upper()
    tab, key = ("vendor", "lifnr") if koart == "K" else ("customer", "kunnr")
    if koart not in ("K", "D") or not conn.execute("SELECT 1 FROM %s WHERE %s=?" % (tab, key),
                                                   (partner,)).fetchone():
        raise MMError("Partner %s does not exist" % partner, "F2", "103")
    cur = conn.execute("INSERT INTO dp_request (koart,partner,amount,due,ebeln,text,usnam,created) "
                       "VALUES (?,?,?,?,?,?,?,?)", (koart, partner, parse_amount(amount), parse_date(due),
                                                    (ebeln or "")[:10], (text or "")[:50], user, now_ts()))
    return cur.lastrowid


def requests(conn, koart=None, status="O"):
    sql, a = "SELECT * FROM dp_request WHERE 1=1", []
    if koart:
        sql += " AND koart=?"
        a.append(koart)
    if status:
        sql += " AND status=?"
        a.append(status)
    return rows(conn.execute(sql + " ORDER BY id", a))


def down_payment(conn, koart, partner, amount, budat, user, bank="113100", request_id=None, text=""):
    """F-48 (vendor: paid to the vendor) / F-29 (customer: received)."""
    koart = (koart or "").upper()
    partner = (partner or "").upper()
    budat = parse_date(budat)
    with transaction(conn):
        if request_id:
            r = conn.execute("SELECT * FROM dp_request WHERE id=?", (int(request_id),)).fetchone()
            if not r or r["status"] != "O" or r["koart"] != koart or r["partner"] != partner:
                raise MMError("Down-payment request %s is not open for %s" % (request_id, partner), "F5", "270")
            amt = r["amount"] if amount in (None, "") else parse_amount(amount)
        else:
            amt = parse_amount(amount)
        if koart not in DP_ACCOUNT:
            raise MMError("Account type must be K or D", "F5", "100")
        pkey = "lifnr" if koart == "K" else "kunnr"
        sign = 1 if koart == "K" else -1              # vendor DP is an asset (debit)
        lines = [dict(koart=koart, **{pkey: partner}, hkont=DP_ACCOUNT[koart], umskz="A",
                      amount=sign * amt, wrbtr=sign * amt, zfbdt=budat, zterm="0001",
                      sgtxt=(text or "Down payment")[:50]),
                 dict(hkont=bank, amount=-sign * amt, wrbtr=-sign * amt, sgtxt="Down payment %s" % partner)]
        tc = "F-48" if koart == "K" else "F-29"
        belnr = write(conn, "KZ" if koart == "K" else "DZ", budat, user, tc, "Down payment", lines, tcode=tc)
        if request_id:
            conn.execute("UPDATE dp_request SET status='P', belnr=?, gjahr=? WHERE id=?",
                         (belnr, int(budat[:4]), int(request_id)))
    return {"belnr": belnr, "message": "Down payment %s posted (special G/L A)" % belnr}


def clear_down_payment(conn, koart, partner, dp_item, invoice_item, budat, user):
    """F-54 / F-39: transfer the down payment to the normal account and clear the
    invoice with it (the rest of the invoice stays open)."""
    koart = (koart or "").upper()
    partner = (partner or "").upper()
    budat = parse_date(budat)
    with transaction(conn):
        dp, inv = _items(conn, [dp_item, invoice_item])
        pkey = "lifnr" if koart == "K" else "kunnr"
        if dp["umskz"] != "A" or dp[pkey] != partner:
            raise MMError("Item %s is not a down payment of %s" % (dp["belnr"], partner), "F5", "271")
        if inv["umskz"] or inv[pkey] != partner or inv["koart"] != koart:
            raise MMError("Item %s is not an invoice of %s" % (inv["belnr"], partner), "F5", "272")
        d, i = signed(dp), signed(inv)
        if (d > 0) == (i > 0):
            raise MMError("Down payment and invoice must have opposite signs", "F5", "273")
        use = min(abs(d), abs(i))
        sgn = 1 if d > 0 else -1
        lines = [dict(koart=koart, **{pkey: partner}, hkont=DP_ACCOUNT[koart], umskz="A",
                      amount=-sgn * abs(d), zfbdt=budat, zterm="0001", sgtxt="Clear down payment %s" % dp["belnr"]),
                 dict(koart=koart, **{pkey: partner}, amount=sgn * use, zfbdt=budat, zterm="0001",
                      rebzg=inv["belnr"], sgtxt="Down payment against invoice %s" % inv["belnr"])]
        if abs(d) > use:      # down payment larger than the invoice: the rest stays a down payment
            lines.append(dict(koart=koart, **{pkey: partner}, hkont=DP_ACCOUNT[koart], umskz="A",
                              amount=sgn * (abs(d) - use), zfbdt=budat, zterm="0001",
                              sgtxt="Remaining down payment"))
        for l in lines:
            l["wrbtr"] = l["amount"]
        tc = "F-54" if koart == "K" else "F-39"
        belnr = write(conn, "AB", budat, user, tc, "Down-payment clearing", lines, tcode=tc)
        gj = int(budat[:4])
        clear(conn, [(dp["belnr"], dp["gjahr"], dp["buzei"]), (belnr, gj, 1)], belnr, budat)
        if use == abs(i):
            clear(conn, [(inv["belnr"], inv["gjahr"], inv["buzei"]), (belnr, gj, 2)], belnr, budat)
    return {"belnr": belnr, "message": "Down payment cleared with document %s%s" % (
        belnr, "" if use == abs(i) else " - rest of the invoice remains open")}
