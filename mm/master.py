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


def create_vendor(conn, lifnr, name, city=""):
    lifnr = _key(lifnr, "vendor", 10)
    with transaction(conn):
        if conn.execute("SELECT 1 FROM vendor WHERE lifnr=?", (lifnr,)).fetchone():
            raise MMError("Vendor %s already exists" % lifnr, "F2", "001")
        conn.execute("INSERT INTO vendor VALUES (?,?,?)", (lifnr, name, city))


def create_cost_center(conn, kostl, name):
    kostl = _key(kostl, "cost center", 10)
    with transaction(conn):
        if conn.execute("SELECT 1 FROM cost_center WHERE kostl=?",
                        (kostl,)).fetchone():
            raise MMError("Cost center %s already exists" % kostl, "KS", "001")
        conn.execute("INSERT INTO cost_center VALUES (?,?)", (kostl, name))


# ---------------------------------------------------------------- materials
def create_material(conn, data, user):
    """MM01. data: matnr (optional), maktx, mtart, meins, matkl,
    plants: [{werks, vprsv, price, peinh, minbe, eisbe}]"""
    maktx = (data.get("maktx") or "").strip()
    if not maktx:
        raise MMError("Enter a material description", "M3", "301")
    mtart = (data.get("mtart") or "").upper()
    if mtart not in MATERIAL_TYPES:
        raise MMError("Material type %s does not exist" % mtart, "M3", "302")
    meins = (data.get("meins") or "").upper()
    if meins not in UNITS:
        raise MMError("Unit of measure %s is not defined" % meins, "M3", "303")
    plants = data.get("plants") or []
    if not plants:
        raise MMError("Maintain at least one plant (plant views)", "M3", "304")
    bklas = MATERIAL_TYPES[mtart][1]
    with transaction(conn):
        matnr = (data.get("matnr") or "").strip().upper()
        if not matnr:
            matnr = str(next_number(conn, "MATNR"))
        if len(matnr) > 18:
            raise MMError("Material number may have at most 18 characters")
        if conn.execute("SELECT 1 FROM material WHERE matnr=?", (matnr,)).fetchone():
            raise MMError("Material %s already exists" % matnr, "M3", "305")
        conn.execute("INSERT INTO material VALUES (?,?,?,?,?,?,?,?)",
                     (matnr, maktx, mtart, meins, data.get("matkl") or "",
                      bklas, now_ts()[:10], user))
        for p in plants:
            _add_plant_view(conn, matnr, p)
    return matnr


def _add_plant_view(conn, matnr, p):
    werks = p.get("werks")
    _must(conn, "SELECT 1 FROM plant WHERE werks=?", (werks,),
          "Plant %s does not exist" % werks)
    vprsv = (p.get("vprsv") or "V").upper()
    if vprsv not in ("V", "S"):
        raise MMError("Price control must be V (moving average) or S (standard)",
                      "M3", "306")
    peinh = int(p.get("peinh") or 1)
    if peinh <= 0:
        raise MMError("Price unit must be greater than zero")
    price = parse_amount(p.get("price") or "0", allow_zero=True)
    if vprsv == "S" and price == 0:
        raise MMError("Enter a standard price for price control S", "M3", "307")
    minbe = parse_qty(p.get("minbe") or "0", allow_zero=True)
    eisbe = parse_qty(p.get("eisbe") or "0", allow_zero=True)
    if conn.execute("SELECT 1 FROM material_plant WHERE matnr=? AND werks=?",
                    (matnr, werks)).fetchone():
        raise MMError("Material %s already exists in plant %s" % (matnr, werks))
    conn.execute("INSERT INTO material_plant VALUES (?,?,?,?)",
                 (matnr, werks, minbe, eisbe))
    conn.execute("INSERT INTO valuation (matnr,bwkey,vprsv,verpr,stprs,peinh,"
                 "lbkum,salk3) VALUES (?,?,?,?,?,?,0,0)",
                 (matnr, werks, vprsv, price, price, peinh))
    conn.execute("INSERT INTO price_history (matnr,bwkey,ts,budat,ref,reason,"
                 "old_price,new_price,peinh,lbkum,salk3) VALUES "
                 "(?,?,?,?,?,?,?,?,?,0,0)",
                 (matnr, werks, now_ts(), now_ts()[:10], "MM01", "Material created",
                  None, price, peinh))


def extend_material(conn, matnr, plant_view):
    with transaction(conn):
        _must(conn, "SELECT 1 FROM material WHERE matnr=?", (matnr,),
              "Material %s does not exist" % matnr)
        _add_plant_view(conn, matnr, plant_view)


def change_material(conn, matnr, data):
    """MM02 (basic fields and MRP fields only; price via MR21)."""
    with transaction(conn):
        _must(conn, "SELECT 1 FROM material WHERE matnr=?", (matnr,),
              "Material %s does not exist" % matnr)
        if data.get("maktx"):
            conn.execute("UPDATE material SET maktx=? WHERE matnr=?",
                         (data["maktx"].strip(), matnr))
        if "matkl" in data:
            conn.execute("UPDATE material SET matkl=? WHERE matnr=?",
                         (data.get("matkl") or "", matnr))
        for p in data.get("plants") or []:
            sets, args = [], []
            for f in ("minbe", "eisbe"):
                if p.get(f) not in (None, ""):
                    sets.append("%s=?" % f)
                    args.append(parse_qty(p[f], allow_zero=True))
            if sets:
                conn.execute("UPDATE material_plant SET %s WHERE matnr=? AND werks=?"
                             % ",".join(sets), args + [matnr, p["werks"]])


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
    """ME21N. data: lifnr, bedat, items: [{matnr, werks, lgort, menge, netpr,
    peinh}]"""
    lifnr = data.get("lifnr")
    items = data.get("items") or []
    if not items:
        raise MMError("Enter at least one item", "06", "001")
    bedat = parse_date(data.get("bedat"))
    with transaction(conn):
        _must(conn, "SELECT 1 FROM vendor WHERE lifnr=?", (lifnr,),
              "Vendor %s does not exist" % lifnr)
        ebeln = str(next_number(conn, "PO"))
        conn.execute("INSERT INTO po_header VALUES (?,?,?,?,?)",
                     (ebeln, lifnr, bedat, user, now_ts()))
        for i, it in enumerate(items, start=1):
            matnr, werks = it.get("matnr"), it.get("werks")
            _must(conn, "SELECT 1 FROM material_plant WHERE matnr=? AND werks=?",
                  (matnr, werks),
                  "Material %s not maintained in plant %s" % (matnr, werks))
            lgort = it.get("lgort") or ""
            if lgort:
                _must(conn, "SELECT 1 FROM sloc WHERE werks=? AND lgort=?",
                      (werks, lgort),
                      "Storage location %s %s does not exist" % (werks, lgort))
            peinh = int(it.get("peinh") or 1)
            conn.execute("INSERT INTO po_item VALUES (?,?,?,?,?,?,?,?,0,0)",
                         (ebeln, i * 10, matnr, werks, lgort,
                          parse_qty(it.get("menge")), parse_amount(it.get("netpr")),
                          peinh))
    return ebeln


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
