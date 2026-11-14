"""Petty cash journal (5-2 FBCJ): cash in from the bank, cash out to the bank, expenses
paid in cash (to a cost center) and cash receipts. Account 100000 petty cash; the cash
can never go below zero. The book shows opening balance, every entry with the running
balance and the closing balance (to compare with the cash count)."""
from mm.db import transaction
from mm.util import MMError, parse_amount, parse_date

CASH, BANK = "100000", "113100"
TYPES = {"BANK_IN": "Cash from the bank", "BANK_OUT": "Cash to the bank", "EXPENSE": "Expense paid in cash",
         "RECEIPT": "Cash receipt"}


def balance(conn, upto="9999-12-31"):
    from fi.reports import gl_balance
    return gl_balance(conn, CASH, upto)


def post(conn, data, user):
    from fi import gl
    typ = (data.get("typ") or "").upper()
    if typ not in TYPES:
        raise MMError("Choose the kind of entry: cash from / to the bank, expense or receipt", "FCJ", "810")
    budat = parse_date(data.get("budat"))
    amt = parse_amount(data.get("amount"))
    text = (data.get("text") or "").strip()
    if not text:
        raise MMError("Enter the text of the entry (what was paid / received)", "FCJ", "812")
    money = "%.2f" % (amt / 100.0)
    hkont = (data.get("hkont") or "").strip()
    kostl = (data.get("kostl") or "").strip().upper() or None
    if typ in ("EXPENSE", "RECEIPT"):
        a = conn.execute("SELECT typ FROM gl_account WHERE hkont=?", (hkont,)).fetchone()
        if not a or (typ == "EXPENSE" and a["typ"] != "PL") or hkont in (CASH, BANK):
            raise MMError("Account %s cannot be used for a cash %s - choose an expense / income account" % (
                hkont, "expense" if typ == "EXPENSE" else "receipt"), "FCJ", "813")
    with transaction(conn):
        if typ in ("BANK_OUT", "EXPENSE") and balance(conn) - amt < 0:
            raise MMError("Not enough cash: the cash box has %.2f" % (balance(conn) / 100.0), "FCJ", "811")
        dr, cr = {"BANK_IN": ((CASH, None), (BANK, None)), "BANK_OUT": ((BANK, None), (CASH, None)),
                  "EXPENSE": ((hkont, kostl), (CASH, None)), "RECEIPT": ((CASH, None), (hkont, kostl))}[typ]
        belnr = gl.general_posting(conn, {"budat": budat, "bktxt": ("Cash: " + text)[:25]}, [
            {"bschl": "40", "account": dr[0], "amount": money, "kostl": dr[1], "sgtxt": text},
            {"bschl": "50", "account": cr[0], "amount": money, "kostl": cr[1], "sgtxt": text}], user)
    return {"belnr": belnr, "balance": balance(conn),
            "message": "%s %.2f posted (document %s) - cash now %.2f" % (TYPES[typ], amt / 100.0, belnr,
                                                                       balance(conn) / 100.0)}


def book(conn, d1, d2):
    d1, d2 = parse_date(d1), parse_date(d2)
    import datetime
    before = (datetime.date.fromisoformat(d1) - datetime.timedelta(days=1)).isoformat()
    opening = balance(conn, before)
    run = opening
    lines = []
    for r in conn.execute("SELECT h.budat, i.belnr, i.gjahr, h.bktxt, i.sgtxt, i.shkzg, i.dmbtr, h.usnam FROM "
                          "acc_doc_item i JOIN acc_doc h ON h.belnr=i.belnr AND h.gjahr=i.gjahr WHERE i.hkont=? AND "
                          "h.budat BETWEEN ? AND ? ORDER BY h.budat, i.belnr", (CASH, d1, d2)):
        rec = r["dmbtr"] if r["shkzg"] == "S" else 0
        pay = r["dmbtr"] if r["shkzg"] == "H" else 0
        run += rec - pay
        lines.append(dict(budat=r["budat"], belnr=r["belnr"], text=r["sgtxt"] or r["bktxt"], receipt=rec,
                          payment=pay, balance=run, usnam=r["usnam"]))
    return {"d1": d1, "d2": d2, "opening": opening, "closing": run, "lines": lines,
            "receipts": sum(x["receipt"] for x in lines), "payments": sum(x["payment"] for x in lines)}
