"""Parked documents (2-2 FV50 / FBV0 / FBV3): a clerk enters (parks) a G/L document, it is
checked completely but not posted; a second person checks it and posts it (four-eyes
principle) or deletes it. Parked documents wait in the approval inbox (ZINBOX)."""
import json

from mm.db import transaction
from mm.util import MMError, now_ts, parse_amount, parse_date


class _Rollback(Exception):
    pass


def _simulate(conn, header, lines, user):
    """runs the real posting with every check and rolls it back"""
    from fi import gl
    try:
        with transaction(conn):
            gl.general_posting(conn, header, lines, user)
            raise _Rollback()
    except _Rollback:
        pass


def park(conn, doc, user):
    lines = doc.get("lines") or []
    header = {"budat": parse_date(doc.get("budat")), "bktxt": doc.get("bktxt") or "", "xblnr": doc.get("xblnr") or ""}
    if not header["bktxt"].strip():
        raise MMError("Enter a header text (what the document is about)", "FPK", "830")
    _simulate(conn, header, lines, user)                     # same checks as the posting itself
    amount = sum(parse_amount(l.get("amount")) for l in lines if str(l.get("bschl")) in ("40", "01", "21", "25", "70"))
    with transaction(conn):
        cur = conn.execute("INSERT INTO fi_parked (budat,bktxt,xblnr,lines,amount,parked_by,parked_ts) VALUES "
                           "(?,?,?,?,?,?,?)", (header["budat"], header["bktxt"], header["xblnr"], json.dumps(lines),
                                               amount, user, now_ts()))
    return cur.lastrowid


def _get(conn, pid):
    r = conn.execute("SELECT * FROM fi_parked WHERE id=?", (int(pid),)).fetchone()
    if not r:
        raise MMError("Parked document %s does not exist" % pid, "FPK", "831")
    if r["status"] != "P":
        raise MMError("Parked document %s is already %s" % (pid, "posted" if r["status"] == "S" else "deleted"),
                      "FPK", "833")
    return r


def post(conn, pid, user):
    """FBV0: post a parked document - not by the person who parked it"""
    from fi import gl
    with transaction(conn):
        r = _get(conn, pid)
        if (r["parked_by"] or "").upper() == (user or "").upper():
            raise MMError("You parked document %s yourself - a second person must post it (four eyes)" % pid,
                          "FPK", "832")
        belnr = gl.general_posting(conn, {"budat": r["budat"], "bktxt": r["bktxt"], "xblnr": r["xblnr"]},
                                   json.loads(r["lines"]), user)
        conn.execute("UPDATE fi_parked SET status='S', posted_by=?, posted_ts=?, belnr=?, gjahr=? WHERE id=?",
                     (user, now_ts(), belnr, int(r["budat"][:4]), r["id"]))
    return {"belnr": belnr, "message": "Parked document %s posted as %s" % (pid, belnr)}


def delete(conn, pid, user):
    with transaction(conn):
        r = _get(conn, pid)
        conn.execute("UPDATE fi_parked SET status='D', posted_by=?, posted_ts=? WHERE id=?", (user, now_ts(), r["id"]))
    return {"message": "Parked document %s deleted" % pid}


def listing(conn, status=None):
    sql, a = "SELECT * FROM fi_parked", []
    if status:
        sql += " WHERE status=?"
        a.append(status)
    out = []
    for r in conn.execute(sql + " ORDER BY id DESC", a):
        d = dict(r)
        d["lines"] = json.loads(r["lines"])
        d["status_text"] = {"P": "Parked - waiting", "S": "Posted", "D": "Deleted"}[r["status"]]
        out.append(d)
    return out
