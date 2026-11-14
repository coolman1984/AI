"""Cheques (3-4 / 4-4 / 5-3): post-dated cheques as they are used in Egypt.

Received from a customer (ZCHQ_IN):  Dr 115000 notes receivable / Cr customer
    (clears the selected invoices, or on account)
  collected at the due date (ZCHQ):   Dr 113100 bank / Cr 115000
  bounced (returned unpaid):          Dr customer (open again) / Cr 115000
Issued to a vendor (ZCHQ_OUT):        Dr vendor / Cr 165000 notes payable
  cashed by the vendor (ZCHQ):        Dr 165000 / Cr 113100 bank
The register (ZCHQ) lists every cheque with its due date and status.
"""


from mm.db import transaction
from mm.util import MMError, now_ts, parse_date

NOTES_REC, NOTES_PAY, BANK = "115000", "165000", "113100"
STATUS = {"REC": "Received (in portfolio)", "ISS": "Issued (not cashed)", "COL": "Collected / cashed",
          "BNC": "Bounced (returned)"}


def _base(conn, data, direction):
    chqno = (data.get("chqno") or "").strip()
    bank = (data.get("bank") or "").strip().upper()
    if not chqno or not bank:
        raise MMError("Enter the cheque number and the bank of the cheque", "FCH", "801")
    if conn.execute("SELECT 1 FROM fi_cheque WHERE dir=? AND bank=? AND chqno=?", (direction, bank, chqno)).fetchone():
        raise MMError("Cheque %s of bank %s is already registered" % (chqno, bank), "FCH", "802")
    return chqno, bank, parse_date(data.get("due")), parse_date(data.get("budat"))


def _items(data):
    return [tuple(x) for x in (data.get("items") or []) if x]


def _note_amount(conn, belnr, gjahr, hkont):
    r = conn.execute("SELECT COALESCE(SUM(dmbtr),0) FROM acc_doc_item WHERE belnr=? AND gjahr=? AND hkont=?",
                     (belnr, gjahr, hkont)).fetchone()
    return r[0]


def _save(conn, direction, koart, partner, chqno, bank, amount, due, budat, belnr, gjahr, text, user):
    cur = conn.execute("INSERT INTO fi_cheque (dir,chqno,bank,koart,partner,amount,due,budat,status,belnr,gjahr,text,"
                       "usnam,ts) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                       (direction, chqno, bank, koart, partner, amount, due, budat, "REC" if direction == "IN" else "ISS",
                        belnr, gjahr, text, user, now_ts()))
    return cur.lastrowid


def receive(conn, data, user):
    """ZCHQ_IN: a cheque from a customer - clears the selected invoices (or on account)"""
    from fi import ap, gl
    kunnr = (data.get("kunnr") or "").strip().upper()
    if not conn.execute("SELECT 1 FROM customer WHERE kunnr=?", (kunnr,)).fetchone():
        raise MMError("Customer %s does not exist" % kunnr, "FCH", "803")
    with transaction(conn):
        chqno, bank, due, budat = _base(conn, data, "IN")
        text = "Cheque %s %s due %s" % (chqno, bank, due)
        items = _items(data)
        if items:
            r = ap.pay(conn, "D", kunnr, budat, items, user, bank=NOTES_REC, take_discount=False, blart="DZ",
                       bktxt=text[:25], tcode="ZCHQ_IN")
            belnr, gjahr = r["belnr"], r["gjahr"]
        else:
            amt = data.get("amount")
            if not amt:
                raise MMError("Select the invoices or enter the amount (on account)", "FCH", "804")
            belnr = gl.general_posting(conn, {"budat": budat, "blart": "DZ", "bktxt": text[:25]}, [
                {"bschl": "40", "account": NOTES_REC, "amount": amt, "sgtxt": text},
                {"bschl": "15", "account": kunnr, "amount": amt, "sgtxt": text}], user)
            gjahr = int(budat[:4])
        amount = _note_amount(conn, belnr, gjahr, NOTES_REC)
        cid = _save(conn, "IN", "D", kunnr, chqno, bank, amount, due, budat, belnr, gjahr, data.get("text") or "", user)
    return {"id": cid, "belnr": belnr, "amount": amount,
            "message": "Cheque %s received: %.2f in notes receivable (document %s)" % (chqno, amount / 100.0, belnr)}


def issue(conn, data, user):
    """ZCHQ_OUT: a cheque to a vendor - pays the selected invoices (or on account)"""
    from fi import ap, gl
    lifnr = (data.get("lifnr") or "").strip().upper()
    if not conn.execute("SELECT 1 FROM vendor WHERE lifnr=?", (lifnr,)).fetchone():
        raise MMError("Vendor %s does not exist" % lifnr, "FCH", "803")
    with transaction(conn):
        chqno, bank, due, budat = _base(conn, data, "OUT")
        text = "Cheque %s %s due %s" % (chqno, bank, due)
        items = _items(data)
        if items:
            r = ap.pay(conn, "K", lifnr, budat, items, user, bank=NOTES_PAY, take_discount=False, blart="KZ",
                       bktxt=text[:25], tcode="ZCHQ_OUT")
            belnr, gjahr = r["belnr"], r["gjahr"]
        else:
            amt = data.get("amount")
            if not amt:
                raise MMError("Select the invoices or enter the amount (on account)", "FCH", "804")
            belnr = gl.general_posting(conn, {"budat": budat, "blart": "KZ", "bktxt": text[:25]}, [
                {"bschl": "25", "account": lifnr, "amount": amt, "sgtxt": text},
                {"bschl": "50", "account": NOTES_PAY, "amount": amt, "sgtxt": text}], user)
            gjahr = int(budat[:4])
        amount = _note_amount(conn, belnr, gjahr, NOTES_PAY)
        cid = _save(conn, "OUT", "K", lifnr, chqno, bank, amount, due, budat, belnr, gjahr, data.get("text") or "", user)
    return {"id": cid, "belnr": belnr, "amount": amount,
            "message": "Cheque %s issued: %.2f in notes payable (document %s)" % (chqno, amount / 100.0, belnr)}


def _get(conn, cid):
    r = conn.execute("SELECT * FROM fi_cheque WHERE id=?", (int(cid),)).fetchone()
    if not r:
        raise MMError("Cheque %s does not exist" % cid, "FCH", "807")
    return r


def collect(conn, cid, budat, user):
    """the bank collected the customer cheque / the vendor cashed our cheque"""
    from fi import gl
    budat = parse_date(budat)
    with transaction(conn):
        c = _get(conn, cid)
        if c["status"] not in ("REC", "ISS"):
            raise MMError("Cheque %s is already %s" % (c["chqno"], STATUS[c["status"]].lower()), "FCH", "805")
        money = "%.2f" % (c["amount"] / 100.0)
        text = "Cheque %s %s collected" % (c["chqno"], c["bank"])
        if c["dir"] == "IN":
            lines = [{"bschl": "40", "account": BANK, "amount": money, "sgtxt": text},
                     {"bschl": "50", "account": NOTES_REC, "amount": money, "sgtxt": text}]
        else:
            lines = [{"bschl": "40", "account": NOTES_PAY, "amount": money, "sgtxt": text},
                     {"bschl": "50", "account": BANK, "amount": money, "sgtxt": text}]
        belnr = gl.general_posting(conn, {"budat": budat, "bktxt": text[:25]}, lines, user)
        conn.execute("UPDATE fi_cheque SET status='COL', col_belnr=? WHERE id=?", (belnr, c["id"]))
    return {"belnr": belnr, "message": "%s - document %s" % (text, belnr)}


def bounce(conn, cid, budat, user, reason=""):
    """a customer cheque came back unpaid: the customer owes the amount again"""
    from fi import gl
    budat = parse_date(budat)
    with transaction(conn):
        c = _get(conn, cid)
        if c["dir"] != "IN":
            raise MMError("Only received cheques can bounce", "FCH", "806")
        if c["status"] != "REC":
            raise MMError("Cheque %s is already %s" % (c["chqno"], STATUS[c["status"]].lower()), "FCH", "805")
        money = "%.2f" % (c["amount"] / 100.0)
        text = ("Bounced cheque %s %s" % (c["chqno"], reason or ""))[:50]
        belnr = gl.general_posting(conn, {"budat": budat, "blart": "DR", "bktxt": text[:25]}, [
            {"bschl": "01", "account": c["partner"], "amount": money, "sgtxt": text},
            {"bschl": "50", "account": NOTES_REC, "amount": money, "sgtxt": text}], user)
        conn.execute("UPDATE fi_cheque SET status='BNC', bnc_belnr=?, text=? WHERE id=?",
                     (belnr, ((c["text"] or "") + " " + (reason or "")).strip()[:80], c["id"]))
    return {"belnr": belnr, "message": "Cheque %s bounced - the customer owes %.2f again (document %s)" % (
        c["chqno"], c["amount"] / 100.0, belnr)}


def register(conn, direction=None, status=None, key_date=None):
    """ZCHQ: all cheques; days = days until due (negative = overdue)"""
    import datetime
    from mm import util as mmclock
    kd = datetime.date.fromisoformat(key_date) if key_date else mmclock.today()
    sql, a = "SELECT * FROM fi_cheque WHERE 1=1", []
    if direction:
        sql += " AND dir=?"
        a.append(direction)
    if status:
        sql += " AND status=?"
        a.append(status)
    out = []
    for r in conn.execute(sql + " ORDER BY due, id", a):
        d = dict(r)
        tab = "customer" if r["koart"] == "D" else "vendor"
        key = "kunnr" if r["koart"] == "D" else "lifnr"
        n = conn.execute("SELECT name FROM %s WHERE %s=?" % (tab, key), (r["partner"],)).fetchone()
        d["name"] = n["name"] if n else ""
        d["days"] = (datetime.date.fromisoformat(r["due"]) - kd).days
        d["overdue"] = d["days"] < 0 and r["status"] in ("REC", "ISS")
        d["status_text"] = STATUS.get(r["status"], r["status"])
        out.append(d)
    return out


def summary(conn):
    out = {}
    for d, s in (("IN", "REC"), ("OUT", "ISS")):
        r = conn.execute("SELECT COUNT(*), COALESCE(SUM(amount),0) FROM fi_cheque WHERE dir=? AND status=?",
                         (d, s)).fetchone()
        out[d] = {"count": r[0], "amount": r[1]}
    return out


