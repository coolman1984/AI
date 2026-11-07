"""Master data: plants, storage locations, bins, materials, vendors, cost
centers, purchase orders (MM01/MM02/MM03, OX10, OX09, LS01, XK01, KS01, ME21N)."""
from .config import MATERIAL_TYPES, UNITS
from .db import next_number, rows, transaction
from .util import MMError, parse_amount, parse_date, parse_qty, now_ts, value_of


# ---------------------------------------------------------------- org units
def create_plant(conn, werks, name, city=""):
    werks = _key(werks, "plant", 4)
    with transaction(conn):
        if conn.execute("SELECT 1 FROM plant WHERE werks=?", (werks,)).fetchone():
            raise MMError("Plant %s already exists" % werks, "OX", "001")
        conn.execute("INSERT INTO plant VALUES (?,?,?)", (werks, name, city))


def create_sloc(conn, werks, lgort, name, bin_managed=False):
    werks = _key(werks, "plant", 4)
    lgort = _key(lgort, "storage location", 4)
    with transaction(conn):
        _must(conn, "SELECT 1 FROM plant WHERE werks=?", (werks,),
              "Plant %s does not exist" % werks)
        if conn.execute("SELECT 1 FROM sloc WHERE werks=? AND lgort=?",
                        (werks, lgort)).fetchone():
            raise MMError("Storage location %s %s already exists" % (werks, lgort))
        conn.execute("INSERT INTO sloc VALUES (?,?,?,?)",
                     (werks, lgort, name, 1 if bin_managed else 0))


def create_bin(conn, werks, lgort, lgpla, bin_type=""):
    lgpla = _key(lgpla, "storage bin", 18)
    with transaction(conn):
        s = conn.execute("SELECT bin_managed FROM sloc WHERE werks=? AND lgort=?",
                         (werks, lgort)).fetchone()
        if not s:
            raise MMError("Storage location %s %s does not exist" % (werks, lgort))
        if not s["bin_managed"]:
            raise MMError("Storage location %s %s is not bin-managed"
                          % (werks, lgort), "L3", "011")
        if conn.execute("SELECT 1 FROM bin WHERE werks=? AND lgort=? AND lgpla=?",
                        (werks, lgort, lgpla)).fetchone():
            raise MMError("Storage bin %s already exists" % lgpla, "L3", "012")
        conn.execute("INSERT INTO bin VALUES (?,?,?,?,0)",
                     (werks, lgort, lgpla, bin_type))


def set_bin_blocked(conn, werks, lgort, lgpla, blocked):
    with transaction(conn):
        cur = conn.execute("UPDATE bin SET blocked=? WHERE werks=? AND lgort=? "
                           "AND lgpla=?", (1 if blocked else 0, werks, lgort, lgpla))
        if cur.rowcount == 0:
            raise MMError("Storage bin %s does not exist" % lgpla, "L3", "013")


def create_vendor(conn, lifnr, name, city="", akont="160000", zterm="NT30",
                  waers="EGP", land="EG", stcd1="", bankn="", ktokk="0001"):
    """XK01: general data + company code data (reconciliation account,
    payment terms) + purchasing currency."""
    lifnr = _key(lifnr, "vendor", 10)
    if not (name or "").strip():
        raise MMError("Enter a name", "F2", "002")
    from fi.config import PAYMENT_TERMS, CURRENCIES
    if zterm not in PAYMENT_TERMS:
        raise MMError("Payment terms %s are not defined (OBB8)" % zterm, "F2", "030")
    if waers not in CURRENCIES:
        raise MMError("Currency %s is not defined" % waers, "F2", "031")
    with transaction(conn):
        if conn.execute("SELECT 1 FROM vendor WHERE lifnr=?", (lifnr,)).fetchone():
            raise MMError("Vendor %s already exists" % lifnr, "F2", "001")
        acc = conn.execute("SELECT recon FROM gl_account WHERE hkont=?", (akont,)).fetchone()
        if not acc or acc["recon"] != "K":
            raise MMError("Account %s is not a vendor reconciliation account" % akont,
                          "F2", "032")
        conn.execute("INSERT INTO vendor (lifnr,name,city,ktokk,akont,zterm,waers,"
                     "stcd1,bankn,land,sperr) VALUES (?,?,?,?,?,?,?,?,?,?,0)",
                     (lifnr, name.strip(), city, ktokk, akont, zterm, waers, stcd1,
                      bankn, land))


def create_cost_center(conn, kostl, name, kosar="", khinr="", verak=""):
    """KS01. kosar = cost center category, khinr = standard hierarchy node."""
    kostl = _key(kostl, "cost center", 10)
    if not (name or "").strip():
        raise MMError("Enter a name", "KS", "002")
    with transaction(conn):
        if conn.execute("SELECT 1 FROM cost_center WHERE kostl=?",
                        (kostl,)).fetchone():
            raise MMError("Cost center %s already exists" % kostl, "KS", "001")
        if khinr and not conn.execute("SELECT 1 FROM cc_group WHERE khinr=?",
                                      (khinr,)).fetchone():
            raise MMError("Hierarchy node %s does not exist" % khinr, "KS", "003")
        conn.execute("INSERT INTO cost_center (kostl,name,kosar,khinr,verak) "
                     "VALUES (?,?,?,?,?)", (kostl, name.strip(), kosar or "",
                                            khinr or "", verak or ""))


# ---------------------------------------------------------------- materials
def create_material(conn, data, user):
    """MM01 - see md/material.py (views, OMS2 checks, change documents)."""
    from md.material import create_material as _create
    return _create(conn, data, user)


def extend_material(conn, matnr, plant_view, user=""):
    from md.material import extend_material as _extend
    return _extend(conn, matnr, {"plants": [plant_view]}, user)


def change_material(conn, matnr, data, user=""):
    """MM02 - see md/material.py."""
    from md.material import change_material as _change
    return _change(conn, matnr, data, user)


def get_material(conn, matnr):
    m = conn.execute("SELECT * FROM material WHERE matnr=?", (matnr,)).fetchone()
    if not m:
        raise MMError("Material %s does not exist" % matnr, "M3", "305")
    m = dict(m)
    m["mtart_text"] = MATERIAL_TYPES.get(m["mtart"], ("",))[0]
    m["plants"] = rows(conn.execute(
        "SELECT mp.*, v.vprsv, v.verpr, v.stprs, v.peinh, v.lbkum, v.salk3, "
        "p.name AS plant_name FROM material_plant mp "
        "JOIN valuation v ON v.matnr=mp.matnr AND v.bwkey=mp.werks "
        "JOIN plant p ON p.werks=mp.werks WHERE mp.matnr=? ORDER BY mp.werks",
        (matnr,)))
    return m


def search_materials(conn, q="", limit=200):
    like = "%" + (q or "").strip() + "%"
    return rows(conn.execute(
        "SELECT matnr, maktx, mtart, meins, matkl FROM material "
        "WHERE matnr LIKE ? OR maktx LIKE ? ORDER BY matnr LIMIT ?",
        (like, like, limit)))


# ---------------------------------------------------------------- purchasing
def create_po(conn, data, user):
    """ME21N - see pur/po.py (conditions, account assignment, release)."""
    from pur import po
    return po.create_po(conn, data, user)


def get_po(conn, ebeln):
    h = conn.execute("SELECT h.*, v.name AS vendor_name FROM po_header h "
                     "LEFT JOIN vendor v ON v.lifnr=h.lifnr WHERE ebeln=?",
                     (ebeln,)).fetchone()
    if not h:
        raise MMError("Purchase order %s does not exist" % ebeln, "06", "019")
    h = dict(h)
    h["items"] = rows(conn.execute(
        "SELECT i.*, m.maktx, m.meins FROM po_item i JOIN material m "
        "ON m.matnr=i.matnr WHERE ebeln=? ORDER BY ebelp", (ebeln,)))
    for it in h["items"]:
        it["open"] = max(it["menge"] - it["wemng"], 0)
        it["value"] = value_of(it["menge"], it["netpr"], it["peinh"])
    return h


def list_pos(conn, open_only=False):
    sql = ("SELECT h.ebeln, h.lifnr, v.name AS vendor_name, h.bedat, i.ebelp, "
           "i.matnr, m.maktx, i.werks, i.lgort, i.menge, i.wemng, i.netpr, "
           "i.peinh, m.meins, i.elikz FROM po_header h JOIN po_item i "
           "ON i.ebeln=h.ebeln JOIN material m ON m.matnr=i.matnr "
           "LEFT JOIN vendor v ON v.lifnr=h.lifnr")
    if open_only:
        sql += " WHERE i.wemng < i.menge AND i.elikz = 0"
    out = rows(conn.execute(sql + " ORDER BY h.ebeln DESC, i.ebelp"))
    for r in out:
        r["open"] = max(r["menge"] - r["wemng"], 0)
    return out


# ---------------------------------------------------------------- helpers
def _key(v, what, maxlen):
    v = (v or "").strip().upper()
    if not v:
        raise MMError("Enter a %s" % what, "00", "055")
    if len(v) > maxlen:
        raise MMError("%s may have at most %d characters" % (what.capitalize(),
                                                              maxlen))
    return v


def _must(conn, sql, args, msg):
    if not conn.execute(sql, args).fetchone():
        raise MMError(msg)
