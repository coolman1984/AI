"""Tiles are sold per m2 but leave the warehouse in boxes and pallets.

sales_qty  order items of tile products: quantity in M2, BOX or PAL -> m2, rounded UP to full boxes
packing    m2 -> boxes, full pallets + loose boxes, gross weight
delivery   packing list of a delivery (used by ZTILE_LOTS and the export packing list)"""
from mm.util import MMError, parse_qty

UNITS = ("M2", "BOX", "PAL")
CARTON_KG = 600            # weight of one empty carton (g -> milli kg), pallet below
PALLET_KG = 25000


def _product(conn, matnr):
    """tile product of a material (the grade 2 material uses its grade 1 product)"""
    return conn.execute("SELECT * FROM tile_product WHERE matnr=? OR grade2=? ORDER BY matnr=? DESC",
                        (matnr, matnr, matnr)).fetchone()


def sales_qty(conn, matnr, qty_milli, unit=None):
    """(m2 milli, note): converts BOX / PAL and rounds up to full boxes. Non-tile materials: unchanged."""
    u = str(unit or "").strip().upper()
    p = _product(conn, matnr)
    if not p:
        if u and u not in ("M2",):
            m = conn.execute("SELECT meins FROM material WHERE matnr=?", (matnr,)).fetchone()
            if not m or u != m["meins"]:
                raise MMError("Unit %s is only possible for tile products (ZTILE_CONF)" % u, "TL", "060")
        return qty_milli, None
    if u and u not in UNITS:
        raise MMError("Unit %s is not possible for tiles - use M2, BOX or PAL" % u, "TL", "061")
    box = p["m2_box"]
    if u == "BOX":
        qty_milli = qty_milli * box // 1000
    elif u == "PAL":
        qty_milli = qty_milli * box * p["boxes_pal"] // 1000
    boxes = -(-qty_milli // box)
    rounded = boxes * box
    note = None
    if u in ("BOX", "PAL"):
        note = "%s: %s %s = %s m2 (%d boxes)" % (matnr, "{:g}".format(qty_milli / box if u == "BOX" else
                                                                       qty_milli / box / p["boxes_pal"]),
                                                  u, "{:,.3f}".format(rounded / 1000.0).rstrip("0").rstrip("."), boxes)
    elif rounded != qty_milli:
        note = "%s: rounded up to full boxes - %d boxes = %s m2" % (
            matnr, boxes, "{:,.3f}".format(rounded / 1000.0).rstrip("0").rstrip("."))
    return rounded, note


def packing(conn, matnr, qty_milli):
    p = _product(conn, matnr)
    if not p:
        return None
    boxes = -(-qty_milli // p["m2_box"])
    full, loose = divmod(boxes, p["boxes_pal"])
    pallets = full + (1 if loose else 0)
    kg = (qty_milli * p["kg_m2"] // 1000 + boxes * CARTON_KG + pallets * PALLET_KG) // 1000
    return dict(boxes=boxes, full_pallets=full, loose_boxes=loose, pallets=pallets, gross_kg=kg,
                m2_box=p["m2_box"], boxes_pal=p["boxes_pal"], fmt=p["fmt"])


def parse_unit_qty(conn, matnr, text, unit=None):
    """screen input -> m2 milli (helper for the API)"""
    return sales_qty(conn, matnr, parse_qty(text), unit)[0]


def delivery(conn, vbeln):
    """packing list of a delivery: per item boxes / pallets / weight and the lots (shade, caliber)"""
    h = conn.execute("SELECT * FROM sd_likp WHERE vbeln=?", (str(vbeln or "").strip(),)).fetchone()
    if not h:
        raise MMError("Delivery %s does not exist" % (vbeln or ""), "TL", "062")
    rows, tot = [], dict(boxes=0, pallets=0, gross_kg=0, m2=0)
    for l in conn.execute("SELECT * FROM sd_lips WHERE vbeln=? ORDER BY posnr", (h["vbeln"],)).fetchall():
        q = l["lfimg"]
        pk = packing(conn, l["matnr"], q) or {}
        lots_ = [dict(r) for r in conn.execute("SELECT p.lot, p.qty, t.shade, t.caliber FROM tile_pick p JOIN tile_lot t "
                                                "USING (lot) WHERE p.vbeln=? AND p.posnr=?", (h["vbeln"], l["posnr"]))]
        rows.append(dict(posnr=l["posnr"], matnr=l["matnr"], arktx=l["arktx"], qty=q, lots=lots_, **pk))
        if pk:
            tot["boxes"] += pk["boxes"]
            tot["pallets"] += pk["pallets"]
            tot["gross_kg"] += pk["gross_kg"]
            tot["m2"] += q
    return dict(vbeln=h["vbeln"], kunnr=h["kunnr"], vgbel=h["vgbel"], lfdat=h["lfdat"], gi=h["wadat_ist"],
                items=rows, total=tot)
