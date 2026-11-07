"""Minimal FI: G/L account document entry (FB50) and the FI P&L used to
reconcile CO-PA. Expenses on cost elements flow to CO automatically."""
from mm.config import GL_ACCOUNTS, PNL_ACCOUNTS
from mm.db import transaction
from mm.posting import _write_acc_doc
from mm.util import MMError, parse_amount, parse_date


def post_gl_document(conn, header, lines, user):
    """header: budat, bktxt, xblnr.  lines: [{hkont, debit|credit, kostl,
    aufnr, sgtxt}]  -> accounting document number"""
    budat = parse_date(header.get("budat"))
    if len(lines) < 2:
        raise MMError("Enter at least two line items", "F5", "001")
    acc = []
    for n, l in enumerate(lines, start=1):
        hkont = str(l.get("hkont") or "").strip()
        if hkont not in GL_ACCOUNTS:
            raise MMError("Line %d: G/L account %s does not exist" % (n, hkont),
                          "FH", "010")
        d, c = str(l.get("debit") or "").strip(), str(l.get("credit") or "").strip()
        if bool(d) == bool(c):
            raise MMError("Line %d: enter either a debit or a credit amount" % n,
                          "F5", "002")
        amount = parse_amount(d) if d else -parse_amount(c)
        acc.append(dict(ktosl="", hkont=hkont, amount=amount, matnr=None,
                        werks=None, menge=None, zeile=n,
                        kostl=(l.get("kostl") or "").strip().upper() or None,
                        aufnr=(l.get("aufnr") or "").strip() or None,
                        sgtxt=l.get("sgtxt") or ""))
    bal = sum(a["amount"] for a in acc)
    if bal:
        raise MMError("Balance in transaction currency %.2f - debit must equal "
                      "credit" % (bal / 100.0), "F5", "702")
    with transaction(conn):
        belnr = _write_acc_doc(conn, "SA", budat, user, "FB50",
                               (header.get("bktxt") or "")[:25], acc)
    return {"belnr": belnr, "gjahr": int(budat[:4]),
            "message": "Document %s was posted in company code 1000" % belnr}


def fi_pnl(conn, gjahr, perio_from, perio_to):
    """Balances of P&L accounts (4xxxxx-8xxxxx) for the period range."""
    d1 = "%04d-%02d-01" % (gjahr, perio_from)
    d2 = "%04d-%02d-31" % (gjahr, perio_to)
    out = []
    for r in conn.execute(
            "SELECT i.hkont, SUM(CASE WHEN i.shkzg='S' THEN i.dmbtr ELSE -i.dmbtr "
            "END) AS bal FROM acc_doc_item i JOIN acc_doc h ON h.belnr=i.belnr AND "
            "h.gjahr=i.gjahr WHERE h.budat BETWEEN ? AND ? GROUP BY i.hkont "
            "ORDER BY i.hkont", (d1, d2)):
        if r["bal"] and r["hkont"] in PNL_ACCOUNTS:
            out.append({"hkont": r["hkont"], "txt": GL_ACCOUNTS.get(r["hkont"], ""),
                        "balance": r["bal"]})
    return out
