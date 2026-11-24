"""Export: sales of the export distribution channel (20) and foreign customers, and the export
documents of a delivery - packing list (boxes, pallets, weights, shades) and the data sheet for the
certificate of origin (HS code of ceramic tiles by water absorption group)."""
import datetime

from mm.util import MMError, parse_date

EXPORT_CHANNEL = "20"
# HS codes of glazed ceramic tiles by water absorption (ISO 13006 group) - check with the customs broker
HS = {"BIa": ("6907.21", "Ceramic tiles, water absorption <= 0.5 %"),
      "BIb": ("6907.22", "Ceramic tiles, water absorption > 0.5 % and <= 10 %"),
      "BIIa": ("6907.22", "Ceramic tiles, water absorption > 0.5 % and <= 10 %"),
      "BIIb": ("6907.22", "Ceramic tiles, water absorption > 0.5 % and <= 10 %"),
      "BIII": ("6907.23", "Ceramic tiles, water absorption > 10 %")}


def hs_code(conn, matnr):
    from .pack import _product
    p = _product(conn, matnr)
    return HS.get(p["bgroup"]) if p else None


def report(conn, frm=None, to=None):
    """ZSD_EXPORT: export invoices per country and customer (document currency + EGP), open export orders"""
    to = parse_date(to)
    frm = parse_date(frm) if frm else datetime.date.fromisoformat(to).replace(month=1, day=1).isoformat()
    bills = conn.execute(
        "SELECT b.vbeln, b.fkdat, b.kunnr, c.name, c.land, b.waerk, b.netwr, b.netwr_fc, b.mwsbk, "
        "(SELECT COALESCE(SUM(i.fkimg),0) FROM billing_item i WHERE i.vbeln=b.vbeln) qty, k.vtweg "
        "FROM billing b JOIN customer c ON c.kunnr=b.kunnr LEFT JOIN sd_vbak k ON k.vbeln=b.aubel "
        "WHERE b.cancelled=0 AND b.vbtyp IN ('M','O','P') AND b.fkdat BETWEEN ? AND ? "
        "AND (k.vtweg=? OR c.land<>'EG') ORDER BY b.fkdat DESC", (frm, to, EXPORT_CHANNEL)).fetchall()
    rows = [dict(r) for r in bills]
    countries, customers = {}, {}
    for r in rows:
        for d, k in ((countries, r["land"]), (customers, (r["kunnr"], r["name"], r["land"], r["waerk"]))):
            x = d.setdefault(k, dict(egp=0, fc=0, qty=0, invoices=0))
            x["egp"] += r["netwr"] or 0
            x["fc"] += r["netwr_fc"] or 0
            x["qty"] += r["qty"] or 0
            x["invoices"] += 1
    open_orders = [dict(r) for r in conn.execute(
        "SELECT k.vbeln, k.audat, k.kunnr, c.name, c.land, k.waerk, k.netwr, k.gbstk FROM sd_vbak k JOIN customer c "
        "USING (kunnr) WHERE k.vbtyp='C' AND COALESCE(k.gbstk,'A')<>'C' AND (k.vtweg=? OR c.land<>'EG') "
        "ORDER BY k.audat", (EXPORT_CHANNEL,))]
    tot_egp = sum(r["netwr"] or 0 for r in rows)
    all_sales = conn.execute("SELECT COALESCE(SUM(netwr),0) FROM billing WHERE cancelled=0 AND vbtyp IN ('M','O','P') "
                             "AND fkdat BETWEEN ? AND ?", (frm, to)).fetchone()[0]
    return dict(frm=frm, to=to, invoices=rows, open_orders=open_orders,
                countries=[dict(land=k, **v) for k, v in sorted(countries.items(), key=lambda x: -x[1]["egp"])],
                customers=[dict(kunnr=k[0], name=k[1], land=k[2], waerk=k[3], **v)
                           for k, v in sorted(customers.items(), key=lambda x: -x[1]["egp"])],
                total_egp=tot_egp, share=round(100.0 * tot_egp / all_sales, 1) if all_sales else None)


def documents(conn, vbeln):
    """data of the export documents of a delivery"""
    from .pack import delivery
    d = delivery(conn, vbeln)
    c = conn.execute("SELECT * FROM customer WHERE kunnr=?", (d["kunnr"],)).fetchone()
    k = conn.execute("SELECT * FROM sd_vbak WHERE vbeln=?", (d["vgbel"],)).fetchone()
    inv = conn.execute("SELECT vbeln, fkdat, waerk, netwr_fc, netwr FROM billing WHERE vbtyp='M' AND cancelled=0 AND "
                       "vbeln IN (SELECT DISTINCT vbeln FROM billing_item WHERE vgbel=?)", (d["vbeln"],)).fetchone() \
        if _has_col(conn, "billing_item", "vgbel") else None
    if not inv:
        inv = conn.execute("SELECT vbeln, fkdat, waerk, netwr_fc, netwr FROM billing WHERE vbtyp='M' AND cancelled=0 "
                           "AND aubel=? ORDER BY vbeln DESC", (d["vgbel"],)).fetchone()
    for it in d["items"]:
        h = hs_code(conn, it["matnr"])
        it["hs"], it["hs_text"] = (h if h else ("", ""))
    return dict(d, customer=dict(c) if c else {}, order=dict(k) if k else {}, invoice=dict(inv) if inv else None,
                export=bool((k and k["vtweg"] == EXPORT_CHANNEL) or (c and c["land"] != "EG")))


def _has_col(conn, table, col):
    return col in {r[1] for r in conn.execute("PRAGMA table_info(%s)" % table)}


def check_delivery(conn, vbeln):
    if not conn.execute("SELECT 1 FROM sd_likp WHERE vbeln=?", (str(vbeln or "").strip(),)).fetchone():
        raise MMError("Delivery %s does not exist" % (vbeln or ""), "TL", "062")
