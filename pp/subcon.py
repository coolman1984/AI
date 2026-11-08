"""Subcontracting (external production, item category L).

ME21N (L)  subcontracting PO: the vendor makes the product from components we
           provide; the PO price is only the processing fee
ME2O       subcontracting cockpit: components to provide -> 541 to the
           subcontractor stock (special stock O, storage location 0009)
MBLB       stock provided to vendor
MIGO 101   receipt of the product: the provided components are consumed
           automatically (543) and their value is added to the product value:
           product (BSX) = fee (GR/IR) + component value (BSV / VBO net to zero)
"""
from mm.db import rows, transaction
from mm.util import MMError, parse_date, parse_qty, rdiv

from .config import SUBCON_SLOC


def create_po(conn, lifnr, matnr, qty, eindt, user, werks="1000", lgort="0002", bedat=None,
              netpr=None, plnum=None):
    """Subcontracting PO item; fee from the info record when not given."""
    matnr = matnr.upper()
    with transaction(conn):
        if not conn.execute("SELECT 1 FROM bom WHERE matnr=? AND werks=?", (matnr, werks)).fetchone():
            raise MMError("Subcontracting item %s needs a BOM (components to provide)" % matnr,
                          "06", "450")
        if netpr is None:
            ir = conn.execute("SELECT brutto, peinh FROM info_record WHERE lifnr=? AND matnr=? AND "
                              "COALESCE(loekz,0)=0", (lifnr, matnr)).fetchone()
            if not ir:
                raise MMError("No subcontracting info record for vendor %s / %s" % (lifnr, matnr),
                              "06", "451")
            netpr = "%.2f" % (ir["brutto"] / 100.0 / ir["peinh"])
        from pur.po import create_po as _po
        ebeln = _po(conn, {"lifnr": lifnr, "bedat": parse_date(bedat), "ekgrp": "001",
                           "items": [{"matnr": matnr, "menge": qty, "netpr": netpr, "werks": werks,
                                      "lgort": lgort, "eindt": eindt}]}, user)
        conn.execute("UPDATE po_item SET pstyp='L' WHERE ebeln=? AND ebelp=10", (ebeln,))
        for b in conn.execute("SELECT * FROM bom WHERE matnr=? AND werks=?", (matnr, werks)):
            q = b["menge"] + rdiv(b["menge"] * (b["ausch"] or 0), 10000)
            conn.execute("INSERT INTO pp_po_comp VALUES (?,?,?,?,?,?)",
                         (ebeln, 10, b["idnrk"], werks, q, b["basis"]))
        if plnum:
            conn.execute("UPDATE pp_plaf SET conv=? WHERE plnum=?", ("PO " + ebeln, plnum))
            conn.execute("DELETE FROM pp_depreq WHERE plnum=?", (plnum,))
    return ebeln


def cockpit(conn, lifnr=None):
    """ME2O: per subcontracting PO item the components required, provided,
    consumed and still to provide."""
    sql = ("SELECT i.ebeln, i.ebelp, i.matnr AS product, i.menge AS po_qty, i.wemng, h.lifnr, "
           "v.name, c.matnr, c.menge, c.basis, m.maktx, m.meins FROM po_item i JOIN po_header h "
           "USING (ebeln) JOIN vendor v ON v.lifnr=h.lifnr JOIN pp_po_comp c ON c.ebeln=i.ebeln "
           "AND c.ebelp=i.ebelp JOIN material m ON m.matnr=c.matnr WHERE i.pstyp='L'")
    args = []
    if lifnr:
        sql += " AND h.lifnr=?"
        args.append(lifnr)
    out = []
    for r in conn.execute(sql + " ORDER BY i.ebeln, c.matnr", args):
        d = dict(r)
        d["required"] = rdiv(r["menge"] * r["po_qty"], r["basis"])
        d["consumed"] = rdiv(r["menge"] * r["wemng"], r["basis"])
        st = vendor_stock(conn, r["lifnr"], r["matnr"])
        d["at_vendor"] = st
        d["to_provide"] = max(0, d["required"] - d["consumed"] - st)
        out.append(d)
    return out


def vendor_stock(conn, lifnr, matnr=None):
    """MBLB: stock provided to the vendor = 541 - 542 - 543 + 544."""
    sql = ("SELECT COALESCE(SUM(CASE WHEN i.bwart IN ('541','544') AND i.shkzg='S' THEN i.menge "
           "WHEN i.bwart IN ('542','543') AND i.shkzg='H' THEN -i.menge ELSE 0 END),0) FROM "
           "mat_doc_item i WHERE i.lgort=? AND i.lifnr=?")
    args = [SUBCON_SLOC, lifnr]
    if matnr:
        sql += " AND i.matnr=?"
        args.append(matnr)
    return conn.execute(sql, args).fetchone()[0]


def stock_list(conn):
    out = []
    for r in conn.execute("SELECT DISTINCT i.lifnr, i.matnr, v.name, m.maktx, m.meins FROM "
                          "mat_doc_item i JOIN vendor v ON v.lifnr=i.lifnr JOIN material m ON "
                          "m.matnr=i.matnr WHERE i.lgort=? ORDER BY i.lifnr, i.matnr",
                          (SUBCON_SLOC,)):
        q = vendor_stock(conn, r["lifnr"], r["matnr"])
        val = conn.execute("SELECT verpr, stprs, vprsv, peinh FROM valuation WHERE matnr=? AND "
                           "bwkey='1000'", (r["matnr"],)).fetchone()
        p = val["stprs"] if val["vprsv"] == "S" else val["verpr"]
        out.append(dict(lifnr=r["lifnr"], name=r["name"], matnr=r["matnr"], maktx=r["maktx"],
                        meins=r["meins"], qty=q, value=rdiv(q * p, 1000 * val["peinh"])))
    return out


def provide(conn, ebeln, budat, user, from_lgort="0001", items=None):
    """ME2O 'post goods issue': 541 transfer of the missing components."""
    rows_ = [r for r in cockpit(conn) if r["ebeln"] == ebeln]
    if not rows_:
        raise MMError("%s is not a subcontracting purchase order" % ebeln, "ME", "450")
    lines = []
    for r in rows_:
        q = parse_qty(items[r["matnr"]]) if items and r["matnr"] in items else r["to_provide"]
        if q <= 0:
            continue
        lines.append({"bwart": "541", "matnr": r["matnr"], "werks": "1000", "lgort": from_lgort,
                      "umlgo": SUBCON_SLOC, "qty": "%.3f" % (q / 1000.0), "lifnr": r["lifnr"],
                      "sgtxt": "Provision for PO %s" % ebeln})
    if not lines:
        raise MMError("All components for %s are already provided" % ebeln, "ME", "452")
    from mm.posting import post_goods_movement
    return post_goods_movement(conn, {"budat": budat, "bktxt": "ME2O %s" % ebeln}, lines, user,
                               tcode="ME2O")


def consume_components(doc, po, qty, line):
    """Called by MIGO for a 101 on a subcontracting item: 543 per component."""
    conn = doc.conn
    total = 0
    for c in conn.execute("SELECT * FROM pp_po_comp WHERE ebeln=? AND ebelp=?",
                          (po["ebeln"], po["ebelp"])).fetchall():
        q = rdiv(c["menge"] * qty, c["basis"])
        have = vendor_stock(conn, po["lifnr"], c["matnr"])
        if have < q:
            raise MMError("Component %s: only %.3f provided to vendor %s, %.3f needed (ME2O)"
                          % (c["matnr"], have / 1000.0, po["lifnr"], q / 1000.0), "M7", "302")
        cl = dict(bwart="543", matnr=c["matnr"], werks=c["werks"], lgort=SUBCON_SLOC, insmk="U",
                  qty=q, lgpla="", lifnr=po["lifnr"], xauto=1, kostl=None, aufnr=None,
                  ebeln=None, ebelp=None,
                  sgtxt="Consumption PO %s/%s" % (po["ebeln"], po["ebelp"]))
        res = doc.minus_line(cl)
        doc.post_values(cl, res, "VBO", -1)
        total += res["value"]
    doc.blart = "WE"
    return total


def subcon_items(conn):
    return rows(conn.execute(
        "SELECT i.*, h.lifnr, v.name FROM po_item i JOIN po_header h USING (ebeln) JOIN vendor v "
        "ON v.lifnr=h.lifnr WHERE i.pstyp='L' ORDER BY i.ebeln DESC"))
