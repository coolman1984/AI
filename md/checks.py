"""Master data checks used by the business transactions (like SAP does it):

ME21N   vendor purchasing block / deletion flag (LFA1-SPERM, LOEVM),
        material status for purchasing (MARA-MSTAE, MARC-MMSTA), plant deletion
        flag, import legal control (Exim) for foreign vendors
MIGO    material status for inventory management, deletion flag (receipts),
        QM "post to inspection stock" (MARC-INSMK), over-delivery tolerance
        (MARC-UEBTO), automatic creation of storage location data (MARD)
VF01    customer order / billing block, deletion flag, material sales view
        (MVKE) and distribution-chain status (VMSTA)
FB60... posting block of vendor / customer (LFB1-SPERR, KNB1-SPERR)
F110    payment block (ZAHLS) and unconfirmed sensitive changes (FK08)
"""
from mm.util import MMError, now_ts

from .config import MATERIAL_STATUS, AREA, SALES_STATUS, EXIM_CONTROL


def _status(code, area):
    st = MATERIAL_STATUS.get(code or "")
    return (st[AREA[area]], st[0]) if st else ("", "")


def material(conn, matnr, werks, area, warnings=None):
    """Raise when the X-plant or plant status blocks the business area
    (OMS4 'B'); collect warnings for 'A'."""
    m = conn.execute("SELECT mstae, lvorm FROM material WHERE matnr=?", (matnr,)).fetchone()
    if not m:
        return
    p = conn.execute("SELECT mmsta, lvorm FROM material_plant WHERE matnr=? AND werks=?",
                     (matnr, werks)).fetchone() if werks else None
    for code, lvl in ((m["mstae"], "X-plant"), (p["mmsta"] if p else "", "plant")):
        eff, text = _status(code, area)
        if eff == "B":
            msgid = {"purch": ("06", "347"), "inv": ("M7", "121"),
                     "sales": ("V1", "028"), "cost": ("CK", "102"), "bom": ("29", "030")}[area]
            raise MMError("Material %s has %s status %s: %s" % (matnr, lvl, code, text),
                          *msgid)
        if eff == "A" and warnings is not None:
            warnings.append("Material %s has %s status %s: %s" % (matnr, lvl, code, text))


def vendor_for_purchasing(conn, v):
    if v["sperm"] if "sperm" in v.keys() else 0:
        raise MMError("Vendor %s is blocked for purchasing (XK05)" % v["lifnr"], "06", "302")
    if v["loevm"] if "loevm" in v.keys() else 0:
        raise MMError("Vendor %s is flagged for deletion (XK06)" % v["lifnr"], "06", "303")


def purchasing_item(conn, v, matnr, werks, bedat):
    """Material checks on a purchase order item."""
    material(conn, matnr, werks, "purch")
    p = conn.execute("SELECT lvorm FROM material_plant WHERE matnr=? AND werks=?",
                     (matnr, werks)).fetchone()
    if p and p["lvorm"]:
        raise MMError("Material %s is flagged for deletion in plant %s (MM06)"
                      % (matnr, werks), "06", "076")
    land = v["land"] if "land" in v.keys() else "EG"
    if land and land != "EG":
        e = conn.execute("SELECT * FROM md_exim WHERE matnr=?", (matnr,)).fetchone()
        if e and e["impctl"] == "B":
            raise MMError("Import of material %s is blocked (legal control: embargo)"
                          % matnr, "EXIM", "001")
        if e and e["impctl"] == "L" and not (e["lic_no"] and (e["lic_valid"] or "") >= bedat):
            raise MMError("Import license for material %s is missing or expired (ZEXIM)"
                          % matnr, "EXIM", "002")


def overdelivery_tolerance(conn, matnr, werks):
    """MARC-UEBTO in basis points (0 = none)."""
    if not matnr:
        return 0
    r = conn.execute("SELECT uebto FROM material_plant WHERE matnr=? AND werks=?",
                     (matnr, werks)).fetchone()
    return (r["uebto"] or 0) if r else 0


def goods_movement(conn, line, bwart, kind, raw_insmk, st_choice):
    """Called by MIGO for every line after material / plant / sloc are known."""
    matnr, werks = line["matnr"], line["werks"]
    material(conn, matnr, werks, "inv")
    p = conn.execute("SELECT lvorm, insmk FROM material_plant WHERE matnr=? AND werks=?",
                     (matnr, werks)).fetchone()
    m = conn.execute("SELECT lvorm FROM material WHERE matnr=?", (matnr,)).fetchone()
    if kind == "receipt" and bwart not in ("102", "262", "202", "123") and \
            ((p and p["lvorm"]) or (m and m["lvorm"])):
        raise MMError("Material %s is flagged for deletion - receipts are not allowed"
                      % matnr, "M7", "127")
    # QM: 'post to inspection stock' from the purchasing view
    if bwart == "101" and st_choice and not raw_insmk and p and p["insmk"]:
        line["insmk"] = "Q"
    if kind in ("receipt", "transfer") and line.get("lgort"):
        # OMB3: automatic creation of storage location data on first receipt
        conn.execute("INSERT OR IGNORE INTO md_mard (matnr,werks,lgort,auto,ersda) "
                     "VALUES (?,?,?,1,?)", (matnr, werks, line["lgort"], now_ts()[:10]))


def customer_for_billing(conn, c):
    k = c.keys()
    if "loevm" in k and c["loevm"]:
        raise MMError("Customer %s is flagged for deletion (XD06)" % c["kunnr"], "VF", "011")
    if "aufsd" in k and c["aufsd"]:
        raise MMError("Customer %s has an order block (%s) - XD05" % (c["kunnr"], c["aufsd"]),
                      "V1", "058")
    if "faksd" in k and c["faksd"]:
        raise MMError("Customer %s has a billing block (%s) - XD05" % (c["kunnr"], c["faksd"]),
                      "VF", "039")
    if "lifsd" in k and c["lifsd"]:
        raise MMError("Customer %s has a delivery block (%s) - XD05" % (c["kunnr"], c["lifsd"]),
                      "VL", "302")


def material_for_sales(conn, matnr, vkorg, vtweg, werks):
    if not conn.execute("SELECT 1 FROM md_mvke").fetchone():
        return            # sales views not used at all (old database)
    v = conn.execute("SELECT vmsta FROM md_mvke WHERE matnr=? AND vkorg=? AND vtweg=?",
                     (matnr, vkorg, vtweg)).fetchone()
    if not v:
        raise MMError("Material %s is not defined for sales org. %s, distr. channel %s "
                      "(MM01 sales view)" % (matnr, vkorg, vtweg), "V1", "320")
    st = SALES_STATUS.get(v["vmsta"] or "")
    if st and st[1] == "B":
        raise MMError("Material %s: distribution-chain status %s (%s)"
                      % (matnr, v["vmsta"], st[0]), "V1", "028")
    material(conn, matnr, werks, "sales")


def posting_block(conn, koart, key):
    if koart == "K":
        r = conn.execute("SELECT sperr FROM vendor WHERE lifnr=?", (key,)).fetchone()
        if r and r["sperr"]:
            raise MMError("Vendor %s is blocked for posting (XK05)" % key, "F5", "350")
    elif koart == "D":
        r = conn.execute("SELECT * FROM customer WHERE kunnr=?", (key,)).fetchone()
        if r and "sperr" in r.keys() and r["sperr"]:
            raise MMError("Customer %s is blocked for posting (XD05)" % key, "F5", "351")
        if r and "ktokd" in r.keys() and r["ktokd"] == "0002":
            raise MMError("Customer %s (ship-to party) is not defined in company code 1000"
                          % key, "F5", "352")


def payment_exception(conn, lifnr):
    """Reason why F110 must not pay this vendor, or None."""
    v = conn.execute("SELECT sperr, zahls FROM vendor WHERE lifnr=?", (lifnr,)).fetchone()
    if not v:
        return "Vendor does not exist"
    if v["sperr"]:
        return "Vendor blocked for posting"
    if v["zahls"]:
        return "Payment block %s" % v["zahls"]
    if conn.execute("SELECT 1 FROM md_sensitive WHERE koart='K' AND objectid=? AND "
                    "status='P'", (lifnr,)).fetchone():
        return "Sensitive fields changed - not yet confirmed (FK08)"
    return None


def exim_text(code):
    return EXIM_CONTROL.get(code or "", "")
