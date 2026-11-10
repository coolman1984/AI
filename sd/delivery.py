"""Shipping.

VL10A   delivery due list: confirmed schedule lines due until a date, no blocks
VL01N   create outbound delivery (LF) / returns delivery (LR) from the order;
        checks: credit status, delivery block, incompletion, stock
VL02N   picking (quantity + bin, FIFO proposal) and post goods issue:
        LF -> 601 (COGS), free items too; LR -> 651 returns into BLOCKED stock
        (reverses COGS); serial-number materials create equipment (IE01) with
        the warranty start = goods issue date
VL09    reverse goods issue
VL06O   delivery monitor
"""
import datetime

from mm.db import next_number, rows, transaction
from mm.util import MMError, now_ts, parse_date, parse_qty

from .config import DOC_TYPES, ITEM_CATS, SERIALIZED, WARRANTY_MONTHS
from .order import delivered_qty, flow, incompletion, _status


def due_list(conn, until):
    out = []
    for p in conn.execute("SELECT p.*, k.auart, k.kunnr, k.kunwe, k.cmgst, k.lifsk, c.name FROM sd_vbap p "
                          "JOIN sd_vbak k USING (vbeln) JOIN customer c ON c.kunnr=k.kunnr WHERE "
                          "k.vbtyp IN ('C','H') AND COALESCE(p.abgru,'')='' ORDER BY p.vbeln, p.posnr"):
        if not ITEM_CATS[p["pstyv"]]["delivery"]:
            continue
        due = conn.execute("SELECT COALESCE(SUM(bmeng),0) FROM sd_vbep WHERE vbeln=? AND posnr=? AND "
                           "mbdat<=?", (p["vbeln"], p["posnr"], until)).fetchone()[0]
        open_ = conn.execute("SELECT COALESCE(SUM(lfimg),0) FROM sd_lips WHERE vgbel=? AND vgpos=?",
                             (p["vbeln"], p["posnr"])).fetchone()[0]
        q = due - open_
        if q > 0:
            d = dict(p)
            d.update(due=q, blocked="credit" if p["cmgst"] == "B" else ("delivery block " + p["lifsk"])
                     if p["lifsk"] else "")
            out.append(d)
    return out


def create(conn, vbeln, user, lfdat=None, items=None):
    """VL01N for all due items of one order (or given {posnr: qty})."""
    lfdat = parse_date(lfdat)
    if items is not None:
        if not isinstance(items, dict):
            raise MMError("Delivery quantities must be given per item", "VL", "468")
        items = {str(k): v for k, v in items.items()}
    with transaction(conn):
        k = conn.execute("SELECT * FROM sd_vbak WHERE vbeln=?", (vbeln,)).fetchone()
        if not k:
            raise MMError("Order %s does not exist" % vbeln, "VL", "001")
        t = DOC_TYPES[k["auart"]]
        if not t["lfart"]:
            raise MMError("%s %s is not relevant for delivery" % (t["text"], vbeln), "VL", "002")
        if k["cmgst"] == "B":
            raise MMError("Order %s is blocked for credit - release with VKM1" % vbeln, "VL", "460")
        if k["lifsk"]:
            raise MMError("Order %s has delivery block %s" % (vbeln, k["lifsk"]), "VL", "461")
        inc = incompletion(conn, vbeln)
        if inc:
            raise MMError("Order %s is incomplete (V.02): %s" % (vbeln, ", ".join(inc)), "VL", "462")
        c = conn.execute("SELECT * FROM customer WHERE kunnr=?", (k["kunwe"],)).fetchone()
        if c["lifsd"]:
            raise MMError("Ship-to %s has a delivery block" % k["kunwe"], "VL", "463")
        lines = []
        for p in conn.execute("SELECT * FROM sd_vbap WHERE vbeln=? AND COALESCE(abgru,'')='' ORDER BY posnr",
                              (vbeln,)).fetchall():
            if not ITEM_CATS[p["pstyv"]]["delivery"]:
                continue
            done = conn.execute("SELECT COALESCE(SUM(lfimg),0) FROM sd_lips WHERE vgbel=? AND vgpos=?",
                                (vbeln, p["posnr"])).fetchone()[0]
            if t["vbtyp"] == "H":
                avail = p["kwmeng"] - done
            else:
                avail = conn.execute("SELECT COALESCE(SUM(bmeng),0) FROM sd_vbep WHERE vbeln=? AND posnr=? "
                                     "AND mbdat<=?", (vbeln, p["posnr"], lfdat)).fetchone()[0] - done
            if items is not None:
                if str(p["posnr"]) not in items:
                    continue
                q = parse_qty(items[str(p["posnr"])])
                if q > p["kwmeng"] - done:
                    raise MMError("Item %d: delivery quantity exceeds open quantity" % p["posnr"],
                                  "VL", "464")
            else:
                q = avail
            if q > 0:
                lines.append((p, q))
        if not lines:
            raise MMError("No schedule lines due for delivery up to %s (VL10A)" % lfdat, "VL", "465")
        dl = str(next_number(conn, "DLV"))
        from pp.master import add_workdays
        conn.execute("INSERT INTO sd_likp (vbeln,lfart,vstel,kunnr,kunag,lfdat,wadat,ernam,erdat,vgbel) "
                     "VALUES (?,?,?,?,?,?,?,?,?,?)",
                     (dl, t["lfart"], "1000", k["kunwe"], k["kunnr"], k["vdatu"] if k["vdatu"] > lfdat
                      else lfdat, add_workdays(lfdat, 0), user, lfdat, vbeln))
        for n, (p, q) in enumerate(lines, start=1):
            conn.execute("INSERT INTO sd_lips (vbeln,posnr,matnr,arktx,lfimg,werks,lgort,vgbel,vgpos,pstyv) "
                         "VALUES (?,?,?,?,?,?,?,?,?,?)",
                         (dl, n * 10, p["matnr"], p["arktx"], q, p["werks"], p["lgort"], vbeln, p["posnr"],
                          p["pstyv"]))
            flow(conn, vbeln, p["posnr"], dl, n * 10, k["vbtyp"], "T" if t["vbtyp"] == "H" else "J", q, 0)
    return {"vbeln": dl, "items": len(lines)}


def pick(conn, vbeln, items=None):
    """VL02N picking: quantity (default = delivery qty) and storage bin (FIFO)."""
    with transaction(conn):
        h = _head(conn, vbeln)
        for l in conn.execute("SELECT * FROM sd_lips WHERE vbeln=?", (vbeln,)).fetchall():
            q = parse_qty(items[str(l["posnr"])]["qty"]) if items and str(l["posnr"]) in items else l["lfimg"]
            if q > l["lfimg"]:
                raise MMError("Picked quantity exceeds the delivery quantity", "VL", "470")
            b = (items or {}).get(str(l["posnr"]), {}).get("lgpla") if items else None
            if not b and h["lfart"] == "LF":
                r = conn.execute("SELECT lgpla FROM quant WHERE matnr=? AND werks=? AND lgort=? AND insmk='U' "
                                 "AND qty>=? ORDER BY wdatu, lgpla LIMIT 1",
                                 (l["matnr"], l["werks"], l["lgort"], q)).fetchone()
                b = r["lgpla"] if r else ""
            conn.execute("UPDATE sd_lips SET pikmg=?, lgpla=? WHERE vbeln=? AND posnr=?",
                         (q, b or "", vbeln, l["posnr"]))
        conn.execute("UPDATE sd_likp SET kostk='C' WHERE vbeln=?", (vbeln,))


def _head(conn, vbeln):
    h = conn.execute("SELECT * FROM sd_likp WHERE vbeln=?", (vbeln,)).fetchone()
    if not h:
        raise MMError("Delivery %s does not exist" % vbeln, "VL", "001")
    return h


def post_gi(conn, vbeln, user, budat=None):
    """Post goods issue (LF: 601) / goods receipt for returns (LR: 651 to blocked stock)."""
    budat = parse_date(budat)
    from mm.posting import post_goods_movement, propose_bin
    with transaction(conn):
        h = _head(conn, vbeln)
        if h["wbstk"] == "C":
            raise MMError("Goods movement for delivery %s is already posted" % vbeln, "VL", "602")
        if h["kostk"] != "C":
            pick(conn, vbeln)
        lips = conn.execute("SELECT * FROM sd_lips WHERE vbeln=? ORDER BY posnr", (vbeln,)).fetchall()
        k = conn.execute("SELECT * FROM sd_vbak WHERE vbeln=?", (h["vgbel"],)).fetchone()
        if h["lfart"] != "LR":
            _check_before_goods_issue(conn, k, lips, budat)
        lines = []
        for l in lips:
            q = l["pikmg"] or l["lfimg"]
            if q != l["lfimg"]:
                conn.execute("UPDATE sd_lips SET lfimg=? WHERE vbeln=? AND posnr=?", (q, vbeln, l["posnr"]))
            if h["lfart"] == "LR":
                pb = propose_bin(conn, l["matnr"], l["werks"], l["lgort"], "B")
                lines.append({"bwart": "651", "matnr": l["matnr"], "werks": l["werks"], "lgort": l["lgort"],
                              "lgpla": pb["lgpla"] if pb else "", "qty": "%.3f" % (q / 1000.0),
                              "insmk": "B", "sgtxt": "Returns %s" % h["vgbel"]})
            else:
                lines.append({"bwart": "601", "matnr": l["matnr"], "werks": l["werks"], "lgort": l["lgort"],
                              "lgpla": l["lgpla"], "qty": "%.3f" % (q / 1000.0),
                              "sgtxt": "Delivery %s" % vbeln})
        r = post_goods_movement(conn, {"budat": budat, "xblnr": vbeln, "bktxt": "Delivery %s" % vbeln},
                                lines, user, tcode="VL02N")
        for l, m in zip(lips, conn.execute("SELECT * FROM mat_doc_item WHERE mblnr=? AND mjahr=? ORDER BY "
                                           "zeile", (r["mblnr"], r["mjahr"])).fetchall()):
            conn.execute("UPDATE sd_lips SET cogs=? WHERE vbeln=? AND posnr=?", (m["salk"], vbeln, l["posnr"]))
        conn.execute("UPDATE sd_likp SET wbstk='C', wadat_ist=?, mblnr=?, mjahr=? WHERE vbeln=?",
                     (budat, r["mblnr"], r["mjahr"], vbeln))
        # free-of-charge items (samples, warranty): cost of sales to CO-PA at goods issue
        free = [(l, m) for l, m in zip(lips, conn.execute(
            "SELECT * FROM mat_doc_item WHERE mblnr=? AND mjahr=? ORDER BY zeile",
            (r["mblnr"], r["mjahr"])).fetchall()) if l["pstyv"] == "TANN"]
        if free:
            _copa_free(conn, k, free, budat, vbeln, user)
        if h["lfart"] == "LF":
            _equipment(conn, k, vbeln, lips, budat)
        _status(conn, h["vgbel"])
    return {"vbeln": vbeln, "mblnr": r["mblnr"], "belnr": r.get("belnr")}


def _copa_free(conn, k, free, budat, vbeln, user):
    from co.copa import _cost_values
    from co.core import period_of
    from co.period_end import _copa_post
    c = conn.execute("SELECT * FROM customer WHERE kunnr=?", (k["kunnr"],)).fetchone()
    gjahr, perio = period_of(budat)
    for l, m in free:
        mat = conn.execute("SELECT matkl FROM material WHERE matnr=?", (l["matnr"],)).fetchone()
        vals = _cost_values(conn, l["matnr"], l["werks"], m["menge"], m["salk"])
        _copa_post(conn, "F", 0, gjahr, perio, dict(kunnr=c["kunnr"], matnr=l["matnr"], matkl=mat["matkl"],
                                                   region=c["region"], kdgrp=c["kdgrp"], vtweg=k["vtweg"],
                                                   werks=l["werks"]), vals, refdoc=vbeln, user=user,
                   qty=m["menge"], budat=budat)


def _equipment(conn, k, vbeln, lips, budat):
    d = datetime.date.fromisoformat(budat)
    y, m = d.year + (d.month - 1 + WARRANTY_MONTHS) // 12, (d.month - 1 + WARRANTY_MONTHS) % 12 + 1
    end = datetime.date(y, m, min(d.day, 28)).isoformat()
    for l in lips:
        if l["matnr"] not in SERIALIZED or l["pstyv"] != "TAN":
            continue
        for _ in range((l["pikmg"] or l["lfimg"]) // 1000):
            eq = str(next_number(conn, "EQUI"))
            conn.execute("INSERT INTO sd_equi (equnr,matnr,sernr,kunnr,inbdt,gwlen,vbeln,lieferung,eqktx) VALUES "
                         "(?,?,?,?,?,?,?,?,?)", (eq, l["matnr"], "SN%s" % eq[-6:], k["kunwe"], budat, end,
                                                 k["vbeln"], vbeln, l["arktx"]))


def _check_before_goods_issue(conn, k, lips, budat):
    """Goods issue re-checks the order: no rejected items, no delivery block, credit."""
    if k["lifsk"]:
        raise MMError("Order %s has delivery block %s" % (k["vbeln"], k["lifsk"]), "VL", "461")
    for l in lips:
        p = conn.execute("SELECT abgru FROM sd_vbap WHERE vbeln=? AND posnr=?", (l["vgbel"], l["vgpos"])
                         ).fetchone()
        if p and p["abgru"]:
            raise MMError("Order item %s/%s is rejected - delete it from the delivery"
                          % (l["vgbel"], l["vgpos"]), "VL", "467")
    from .credit import check_step
    check_step(conn, k, "goods_issue", budat)


def delete(conn, vbeln, user):
    """VL02N delete: only while the goods issue is not posted."""
    with transaction(conn):
        h = _head(conn, vbeln)
        if h["wbstk"] == "C":
            raise MMError("Goods issue of delivery %s is posted - reverse it first (VL09)" % vbeln,
                          "VL", "605")
        conn.execute("DELETE FROM sd_lips WHERE vbeln=?", (vbeln,))
        conn.execute("DELETE FROM sd_vbfa WHERE vbeln=? OR vbelv=?", (vbeln, vbeln))
        conn.execute("DELETE FROM sd_likp WHERE vbeln=?", (vbeln,))
        from md.changes import log
        log(conn, "LIEFERUNG", vbeln, "VL02N", user, [("LIKP", vbeln, "deleted", "", "X")], ind="D")
        _status(conn, h["vgbel"])
    return {"message": "Delivery %s deleted" % vbeln}


def change(conn, vbeln, items, user):
    """VL02N: reduce delivery quantities before goods issue ({posnr: qty}, 0 = delete line)."""
    with transaction(conn):
        h = _head(conn, vbeln)
        if h["wbstk"] == "C":
            raise MMError("Goods issue of delivery %s is posted - no changes" % vbeln, "VL", "606")
        log = []
        for posnr, q in {str(k): v for k, v in (items or {}).items()}.items():
            l = conn.execute("SELECT * FROM sd_lips WHERE vbeln=? AND posnr=?", (vbeln, int(posnr))).fetchone()
            if not l:
                raise MMError("Delivery item %s does not exist" % posnr, "VL", "607")
            qty = parse_qty(q, allow_zero=True)
            if qty > l["lfimg"]:
                raise MMError("Item %s: a delivery quantity can only be reduced here" % posnr, "VL", "608")
            if qty == 0:
                conn.execute("DELETE FROM sd_lips WHERE vbeln=? AND posnr=?", (vbeln, int(posnr)))
                conn.execute("DELETE FROM sd_vbfa WHERE vbeln=? AND posnn=?", (vbeln, int(posnr)))
            else:
                conn.execute("UPDATE sd_lips SET lfimg=?, pikmg=MIN(COALESCE(pikmg,0),?) WHERE vbeln=? "
                             "AND posnr=?", (qty, qty, vbeln, int(posnr)))
            log.append(("LIPS", "%s/%s" % (vbeln, posnr), "lfimg", l["lfimg"], qty))
        if not conn.execute("SELECT 1 FROM sd_lips WHERE vbeln=?", (vbeln,)).fetchone():
            conn.execute("DELETE FROM sd_likp WHERE vbeln=?", (vbeln,))
        from md.changes import log as cdlog
        cdlog(conn, "LIEFERUNG", vbeln, "VL02N", user, log)
        _status(conn, h["vgbel"])
    return {"message": "Delivery %s changed" % vbeln}


def reverse_gi(conn, vbeln, user, budat=None):
    """VL09: only while not billed."""
    with transaction(conn):
        h = _head(conn, vbeln)
        if h["wbstk"] != "C":
            raise MMError("Goods issue for delivery %s is not posted" % vbeln, "VL", "603")
        if conn.execute("SELECT 1 FROM billing WHERE vgbel=? AND cancelled=0", (vbeln,)).fetchone():
            raise MMError("Delivery %s is already billed - cancel the billing document first (VF11)"
                          % vbeln, "VL", "604")
        from mm.posting import cancel_document
        cancel_document(conn, h["mblnr"], h["mjahr"], budat, user, "VL09 %s" % vbeln)
        conn.execute("UPDATE sd_likp SET wbstk='A', wadat_ist=NULL WHERE vbeln=?", (vbeln,))
        conn.execute("DELETE FROM sd_equi WHERE lieferung=?", (vbeln,))
        _status(conn, h["vgbel"])


def detail(conn, vbeln):
    h = dict(_head(conn, vbeln))
    h["items"] = rows(conn.execute("SELECT * FROM sd_lips WHERE vbeln=? ORDER BY posnr", (vbeln,)))
    c = conn.execute("SELECT name, city, street FROM customer WHERE kunnr=?", (h["kunnr"],)).fetchone()
    h["name"], h["city"] = c["name"], c["city"]
    return h


def monitor(conn, status=""):
    sql = ("SELECT h.*, c.name, k.vdatu, k.auart, (SELECT COUNT(*) FROM sd_lips l WHERE l.vbeln=h.vbeln) n "
           "FROM sd_likp h JOIN customer c ON c.kunnr=h.kunnr LEFT JOIN sd_vbak k ON k.vbeln=h.vgbel")
    args = []
    if status == "open":
        sql += " WHERE h.wbstk<>'C'"
    elif status == "tobill":
        sql += " WHERE h.wbstk='C' AND h.fkstk<>'C' AND k.auart NOT IN ('FD','ZWR')"
    out = rows(conn.execute(sql + " ORDER BY h.vbeln DESC", args))
    for r in out:
        r["on_time"] = 1 if r["wadat_ist"] and r["vdatu"] and r["wadat_ist"] <= r["vdatu"] else 0
    return out
