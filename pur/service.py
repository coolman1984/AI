"""Service procurement (6-x): service entry sheets (ML81N).

A service is bought with a PO item with account assignment (cost center K / order F) and a
short text instead of a material - e.g. cleaning, maintenance, security, consulting.
The supplier performs the work, the requester enters what was done (service entry sheet)
and a second person accepts it. Only the acceptance posts: the expense goes to the cost
center (Dr expense / Cr GR/IR), so the vendor invoice (MIRO) can be matched against it.
Rejected sheets post nothing.
"""
from mm.db import next_number, transaction
from mm.util import MMError, now_ts, parse_date, parse_qty, qty_out, value_of

STATUS = {"P": "Waiting for acceptance", "A": "Accepted (posted)", "R": "Rejected"}


def _get(conn, lblni):
    r = conn.execute("SELECT * FROM svc_entry WHERE lblni=?", (str(lblni),)).fetchone()
    if not r:
        raise MMError("Service entry sheet %s does not exist" % lblni, "SE", "921")
    return r


def _open_qty(conn, ebeln, ebelp):
    pending = conn.execute("SELECT COALESCE(SUM(menge),0) FROM svc_entry WHERE ebeln=? AND ebelp=? AND status='P'",
                           (ebeln, ebelp)).fetchone()[0]
    i = conn.execute("SELECT * FROM po_item WHERE ebeln=? AND ebelp=?", (ebeln, ebelp)).fetchone()
    return i, i["menge"] - i["wemng"] - pending if i else 0


def service_items(conn, ebeln=None):
    """PO items that are services (account assigned) with ordered / accepted / open quantity"""
    sql = ("SELECT i.*, h.lifnr, h.bedat, v.name FROM po_item i JOIN po_header h ON h.ebeln=i.ebeln "
           "LEFT JOIN vendor v ON v.lifnr=h.lifnr WHERE i.knttp IN ('K','F') AND COALESCE(i.loekz,0)=0")
    a = []
    if ebeln:
        sql += " AND i.ebeln=?"
        a.append(ebeln)
    out = []
    for r in conn.execute(sql + " ORDER BY i.ebeln DESC, i.ebelp", a):
        d = dict(r)
        _, d["open"] = _open_qty(conn, r["ebeln"], r["ebelp"])
        d["value"] = value_of(r["menge"], r["netpr"], r["peinh"])
        out.append(d)
    return out


def create(conn, data, user):
    ebeln = (data.get("ebeln") or "").strip()
    try:
        ebelp = int(data.get("ebelp") or 0)
    except ValueError:
        ebelp = 0
    menge = parse_qty(data.get("menge"))
    text = (data.get("text") or "").strip()
    if not text:
        raise MMError("Describe the work that was done", "SE", "922")
    with transaction(conn):
        i, open_q = _open_qty(conn, ebeln, ebelp)
        if not i:
            raise MMError("Purchase order item %s/%s does not exist" % (ebeln, ebelp), "SE", "923")
        if i["knttp"] not in ("K", "F"):
            raise MMError("Item %s/%s is not a service (no cost center / order)" % (ebeln, ebelp), "SE", "924")
        if menge > open_q:
            raise MMError("Only %s still open on item %s/%s" % (qty_out(max(open_q, 0)), ebeln, ebelp), "SE", "925")
        lblni = str(next_number(conn, "SES"))
        amount = value_of(menge, i["netpr"], i["peinh"])
        conn.execute("INSERT INTO svc_entry (lblni,ebeln,ebelp,menge,amount,budat,text,status,created_by,ts) "
                     "VALUES (?,?,?,?,?,?,?,?,?,?)", (lblni, ebeln, ebelp, menge, amount,
                                                      parse_date(data.get("budat")), text[:120], "P", user, now_ts()))
    return {"lblni": lblni, "amount": amount,
            "message": "Service entry sheet %s created - waiting for acceptance by a second person" % lblni}


def accept(conn, lblni, user, budat=None):
    from mm.posting import post_goods_movement
    with transaction(conn):
        s = _get(conn, lblni)
        if s["status"] != "P":
            raise MMError("Service entry sheet %s is already %s" % (lblni, STATUS[s["status"]].lower()), "SE", "926")
        if s["created_by"] == user:
            raise MMError("You entered sheet %s yourself - a second person must accept it" % lblni, "SE", "927")
        r = post_goods_movement(conn, {"budat": parse_date(budat) if budat else s["budat"],
                                       "bktxt": ("Service entry %s" % lblni)[:25], "xblnr": lblni},
                                [{"bwart": "101", "ebeln": s["ebeln"], "ebelp": s["ebelp"],
                                  "qty": qty_out(s["menge"]), "sgtxt": s["text"][:50]}], user, tcode="ML81N")
        mblnr, mjahr = r["mblnr"], r["mjahr"]
        conn.execute("UPDATE svc_entry SET status='A', accepted_by=?, mblnr=?, mjahr=? WHERE lblni=?",
                     (user, mblnr, mjahr, s["lblni"]))
    return {"mblnr": mblnr, "message": "Service entry sheet %s accepted - %.2f EGP posted to the cost "
                                       "object (document %s)" % (lblni, s["amount"] / 100.0, mblnr)}


def reject(conn, lblni, user, reason=""):
    with transaction(conn):
        s = _get(conn, lblni)
        if s["status"] != "P":
            raise MMError("Service entry sheet %s is already %s" % (lblni, STATUS[s["status"]].lower()), "SE", "926")
        if not (reason or "").strip():
            raise MMError("Enter the reason for the rejection", "SE", "928")
        conn.execute("UPDATE svc_entry SET status='R', accepted_by=?, reason=? WHERE lblni=?",
                     (user, reason.strip()[:80], s["lblni"]))
    return {"message": "Service entry sheet %s rejected" % lblni}


def sheets(conn, status=None):
    sql, a = ("SELECT s.*, i.txz01, i.kostl, i.aufnr, h.lifnr, v.name FROM svc_entry s JOIN po_item i "
              "ON i.ebeln=s.ebeln AND i.ebelp=s.ebelp JOIN po_header h ON h.ebeln=s.ebeln LEFT JOIN vendor v "
              "ON v.lifnr=h.lifnr", [])
    if status:
        sql += " WHERE s.status=?"
        a.append(status)
    out = []
    for r in conn.execute(sql + " ORDER BY s.lblni DESC", a):
        d = dict(r)
        d["status_text"] = STATUS[r["status"]]
        out.append(d)
    return out
