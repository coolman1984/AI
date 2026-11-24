"""Sorting and lots of ceramic tiles.

Tiles leave the kiln with small differences in colour (shade) and size (caliber). The sorting
line grades every tile: grade 1 (first choice), grade 2 (second choice, own material), grade 3
and broken (no stock). Grade 1 and 2 go into stock as lots - one lot = one shade + one caliber.
A customer must get one shade and one caliber per delivery item, otherwise the floor shows
colour bands: the goods issue of a delivery takes the lots (proposed automatically or chosen
in ZTILE_LOTS) and refuses a mix.

ZTILE_SORT  sort(conn, aufnr, data, user)    grade 1 -> GR 101 to the order, grade 2 -> 501
ZTILE_LOTS  lots(conn, ...), set_status, assign(conn, vbeln, posnr, picks)
            on_goods_issue(conn, vbeln) is called by sd.delivery.post_gi
ZTILE_LAB   test(conn, lot, values, user)    ISO 13006 groups (water absorption, strength ...)
ZTILE_KPI   kpi(conn, frm, to)               first-choice rate, defects, shades
"""
import datetime

from mm import util as clock
from mm.db import transaction
from mm.util import MMError, now_ts, parse_date, parse_int, parse_qty, value_of

DEFECTS = {"CRK": "Crack", "PIN": "Pinholes", "GLZ": "Glaze defect", "PRN": "Print defect",
           "SHD": "Shade out of range", "SIZ": "Size / caliber out of range", "PLN": "Warpage (planarity)",
           "CHP": "Chipped edge or corner", "DOT": "Spots / dirt"}
DEFECTS_AR = {"CRK": "شرخ", "PIN": "ثقوب دقيقة", "GLZ": "عيب جليز", "PRN": "عيب طباعة", "SHD": "لون خارج المدى",
              "SIZ": "مقاس خارج المدى", "PLN": "تقوس", "CHP": "كسر في الحرف", "DOT": "نقط / اتساخ"}
# ISO 13006 groups of dry-pressed tiles: water absorption range (% x 1000 = milli),
# minimum breaking strength (N, thickness >= 7.5 mm). Defaults - check against the standard in use.
GROUPS = {"BIa": ("Porcelain (E <= 0.5 %)", 0, 500, 1300),
          "BIb": ("Stoneware (0.5 < E <= 3 %)", 500, 3000, 1100),
          "BIIa": ("Floor tile (3 < E <= 6 %)", 3000, 6000, 1000),
          "BIIb": ("Floor tile (6 < E <= 10 %)", 6000, 10000, 800),
          "BIII": ("Wall tile (E > 10 %)", 10000, None, 600)}
MAX_PLANARITY = 500        # +/- 0.5 % of the diagonal
MAX_SIZE_DEV = 600         # +/- 0.6 % of the work size
STATUS = {"OK": "Free", "HOLD": "On hold (lab)", "BLOCK": "Blocked"}


# ------------------------------------------------------------------ master
def save_product(conn, matnr, grade2="", fmt="", bgroup="BIIa", m2_box="1.44", boxes_pal="40", kg_m2="20"):
    m = str(matnr or "").strip().upper()
    if not conn.execute("SELECT 1 FROM material WHERE matnr=?", (m,)).fetchone():
        raise MMError("Material %s does not exist" % str(matnr or ""), "TL", "001")
    g2 = str(grade2 or "").strip().upper() or None
    if g2 and not conn.execute("SELECT 1 FROM material WHERE matnr=?", (g2,)).fetchone():
        raise MMError("Grade 2 material %s does not exist" % g2, "TL", "001")
    if g2 == m:
        raise MMError("The grade 2 material must be another material", "TL", "002")
    if bgroup not in GROUPS:
        raise MMError("Group %s is unknown - use %s" % (bgroup, ", ".join(GROUPS)), "TL", "003")
    with transaction(conn):
        conn.execute("INSERT OR REPLACE INTO tile_product (matnr,grade2,fmt,bgroup,m2_box,boxes_pal,kg_m2) "
                     "VALUES (?,?,?,?,?,?,?)",
                     (m, g2, str(fmt or "").strip()[:20], bgroup, parse_qty(m2_box),
                      parse_int(boxes_pal, "boxes per pallet", 1, 500), parse_qty(kg_m2 or "20")))
    return m


def products(conn):
    return [dict(r) for r in conn.execute("SELECT p.*, m.maktx FROM tile_product p LEFT JOIN material m "
                                          "USING (matnr) ORDER BY matnr")]


def managed(conn):
    """materials kept in lots: the tile products and their grade 2 materials"""
    s = set()
    for r in conn.execute("SELECT matnr, grade2 FROM tile_product"):
        s.add(r[0])
        if r[1]:
            s.add(r[1])
    return s


def _product_of(conn, matnr):
    return conn.execute("SELECT * FROM tile_product WHERE matnr=? OR grade2=?", (matnr, matnr)).fetchone()


def _new_lot(conn, day):
    pre = "L" + day.replace("-", "")[2:] + "-"
    n = conn.execute("SELECT COUNT(*) FROM tile_lot WHERE lot LIKE ?", (pre + "%",)).fetchone()[0]
    return pre + "%03d" % (n + 1)


def _code(v, what):
    s = str(v or "").strip().upper()
    if not s or len(s) > 10:
        raise MMError("Enter the %s (up to 10 characters, e.g. A1)" % what, "TL", "004")
    return s


def _lot_rows(rows, what):
    out = []
    for r in (rows if isinstance(rows, list) else []):
        if not isinstance(r, dict):
            raise MMError("Wrong %s line" % what, "TL", "004")
        q = parse_qty(r.get("qty"), allow_zero=True)
        if q:
            out.append((_code(r.get("shade"), "shade of the " + what), _code(r.get("caliber"), "caliber of the " + what), q))
    return out


# ------------------------------------------------------------------ sorting
def sort(conn, aufnr, data, user):
    """result of the sorting line for a production order: lots of grade 1 / grade 2 (shade, caliber,
    m2), grade 3 and broken m2, defects {code: m2}. Posts the stock and creates the lots."""
    from mm.posting import post_goods_movement
    day = parse_date(data.get("day"))
    o = conn.execute("SELECT * FROM orders WHERE aufnr=?", (str(aufnr or "").strip(),)).fetchone()
    if not o:
        raise MMError("Production order %s does not exist" % str(aufnr or ""), "TL", "005")
    if o["stat"] not in ("REL", "DLV"):
        raise MMError("Order %s has status %s - sorting not possible" % (o["aufnr"], o["stat"]), "TL", "006")
    p = conn.execute("SELECT * FROM tile_product WHERE matnr=?", (o["matnr"],)).fetchone()
    if not p:
        raise MMError("Material %s is not a tile product (ZTILE_CONF)" % o["matnr"], "TL", "007")
    g1 = _lot_rows(data.get("lots"), "grade 1 lot")
    g2 = _lot_rows(data.get("grade2"), "grade 2 lot")
    if g2 and not p["grade2"]:
        raise MMError("Material %s has no grade 2 material (ZTILE_CONF)" % o["matnr"], "TL", "008")
    g3 = parse_qty(data.get("grade3") or "0", allow_zero=True)
    br = parse_qty(data.get("broken") or "0", allow_zero=True)
    q1, q2 = sum(x[2] for x in g1), sum(x[2] for x in g2)
    if not (q1 or q2 or g3 or br):
        raise MMError("Enter the sorted quantities", "TL", "009")
    defects = {}
    raw = data.get("defects")
    for k, v in (raw.items() if isinstance(raw, dict) else []):
        code = str(k or "").strip().upper()
        if code not in DEFECTS:
            raise MMError("Defect code %s is unknown (%s)" % (k, ", ".join(DEFECTS)), "TL", "010")
        q = parse_qty(v, allow_zero=True)
        if q:
            defects[code] = q
    if sum(defects.values()) > q2 + g3 + br:
        raise MMError("More defects than grade 2 + grade 3 + broken tiles", "TL", "011")
    lgort = o["lgort"] if "lgort" in o.keys() and o["lgort"] else "0003"
    werks = o["werks"] if "werks" in o.keys() and o["werks"] else "1000"
    with transaction(conn):
        lines = []
        if q1:
            lines.append({"bwart": "101", "aufnr": o["aufnr"], "qty": "%.3f" % (q1 / 1000.0), "lgort": lgort,
                          "sgtxt": "Sorting grade 1"})
        if q2:
            v = conn.execute("SELECT * FROM valuation WHERE matnr=? AND bwkey=?", (p["grade2"], werks)).fetchone()
            price = (v["stprs"] if v and v["vprsv"] == "S" else v["verpr"]) if v else 0
            peinh = v["peinh"] if v else 1
            lines.append({"bwart": "501", "matnr": p["grade2"], "werks": werks, "lgort": lgort,
                          "qty": "%.3f" % (q2 / 1000.0), "amount": "%.2f" % (value_of(q2, price, peinh) / 100.0),
                          "sgtxt": "Sorting grade 2 of order %s" % o["aufnr"]})
        mblnr = None
        if lines:
            r = post_goods_movement(conn, {"budat": day, "bktxt": "Sorting %s" % o["aufnr"]}, lines, user,
                                    tcode="ZTILE_SORT")
            mblnr = r["mblnr"]
        cur = conn.execute("INSERT INTO tile_sort (aufnr,day,matnr,arbpl,grade1,grade2,grade3,broken,mblnr,usnam,ts) "
                           "VALUES (?,?,?,?,?,?,?,?,?,?,?)", (o["aufnr"], day, o["matnr"], str(data.get("arbpl") or "")[:20],
                                                            q1, q2, g3, br, mblnr, user, now_ts()))
        sid = cur.lastrowid
        for code, q in defects.items():
            conn.execute("INSERT INTO tile_defect VALUES (?,?,?)", (sid, code, q))
        made = []
        for grade, matnr, rows in (("1", o["matnr"], g1), ("2", p["grade2"], g2)):
            for shade, cal, q in rows:
                lot = _new_lot(conn, day)
                conn.execute("INSERT INTO tile_lot (lot,matnr,werks,lgort,aufnr,sort_id,prod_date,grade,shade,caliber,"
                             "qty) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                             (lot, matnr, werks, lgort, o["aufnr"], sid, day, grade, shade, cal, q))
                made.append(lot)
    tot = q1 + q2 + g3 + br
    return {"sort_id": sid, "lots": made, "mblnr": mblnr, "first_choice": round(100.0 * q1 / tot, 1),
            "message": "Sorting saved: %s m2 grade 1 (%.1f %%), %d lots" % (q1 / 1000.0, 100.0 * q1 / tot, len(made))}


def opening_lot(conn, matnr, shade, caliber, qty, day=None, werks="1000", lgort="0003", grade="1"):
    """stock that was in the warehouse before lots were used (go-live): a lot without sorting"""
    m = str(matnr or "").strip().upper()
    if m not in managed(conn):
        raise MMError("Material %s is not a tile product (ZTILE_CONF)" % str(matnr or ""), "TL", "007")
    day = parse_date(day)
    q = parse_qty(qty)
    with transaction(conn):
        lot = _new_lot(conn, day)
        conn.execute("INSERT INTO tile_lot (lot,matnr,werks,lgort,prod_date,grade,shade,caliber,qty,note) "
                     "VALUES (?,?,?,?,?,?,?,?,?,?)", (lot, m, werks, lgort, day, grade, _code(shade, "shade"),
                                                      _code(caliber, "caliber"), q, "Opening stock"))
    return lot


# ------------------------------------------------------------------ lots
def lots(conn, matnr=None, only_open=True):
    sql = ("SELECT l.*, l.qty - l.issued AS rest, m.maktx FROM tile_lot l LEFT JOIN material m USING (matnr) "
           "WHERE 1=1")
    a = []
    if matnr:
        sql += " AND l.matnr=?"
        a.append(matnr.upper())
    if only_open:
        sql += " AND l.qty > l.issued"
    rows = [dict(r) for r in conn.execute(sql + " ORDER BY l.matnr, l.prod_date, l.lot", a)]
    # free stock per material and shade + caliber: what a single delivery item can get
    groups = {}
    for r in rows:
        if r["status"] == "OK":
            k = (r["matnr"], r["shade"], r["caliber"])
            groups[k] = groups.get(k, 0) + r["rest"]
    return {"rows": rows, "groups": [dict(matnr=k[0], shade=k[1], caliber=k[2], qty=v) for k, v in
                                     sorted(groups.items())], "status": STATUS}


def reconcile(conn):
    """lot stock per material against the stock in MM (differences = stock without lots)"""
    out = []
    for m in sorted(managed(conn)):
        lot = conn.execute("SELECT COALESCE(SUM(qty-issued),0) FROM tile_lot WHERE matnr=?", (m,)).fetchone()[0]
        mm = conn.execute("SELECT COALESCE(SUM(qty),0) FROM quant WHERE matnr=?", (m,)).fetchone()[0]
        out.append(dict(matnr=m, lots=lot, stock=mm, difference=mm - lot))
    return out


def set_status(conn, lot, status, note, user):
    s = str(status or "").strip().upper()
    if s not in STATUS:
        raise MMError("Status %s is unknown (OK, HOLD, BLOCK)" % str(status or ""), "TL", "012")
    with transaction(conn):
        if not conn.execute("UPDATE tile_lot SET status=?, note=? WHERE lot=?",
                            (s, str(note or "")[:80], str(lot or "").strip().upper())).rowcount:
            raise MMError("Lot %s does not exist" % str(lot or ""), "TL", "013")
    return {"message": "Lot %s: %s" % (lot, STATUS[s])}


def _items(conn, vbeln):
    man = managed(conn)
    return [l for l in conn.execute("SELECT * FROM sd_lips WHERE vbeln=? ORDER BY posnr", (vbeln,)).fetchall()
            if l["matnr"] in man]


def propose(conn, matnr, werks, qty, taken=None):
    """lots for one delivery item: one shade + caliber, oldest first; a single lot if it is enough"""
    taken = taken or {}
    free = [dict(r) for r in conn.execute("SELECT * FROM tile_lot WHERE matnr=? AND werks=? AND status='OK' AND "
                                          "qty > issued ORDER BY prod_date, lot", (matnr, werks))]
    for r in free:
        r["rest"] = r["qty"] - r["issued"] - taken.get(r["lot"], 0)
    free = [r for r in free if r["rest"] > 0]
    for r in free:
        if r["rest"] >= qty:
            return [(r["lot"], qty)]
    groups = {}
    for r in free:
        groups.setdefault((r["shade"], r["caliber"]), []).append(r)
    for (shade, cal), rs in groups.items():
        if sum(r["rest"] for r in rs) >= qty:
            out, need = [], qty
            for r in rs:
                t = min(need, r["rest"])
                out.append((r["lot"], t))
                need -= t
                if not need:
                    return out
    best = max((sum(r["rest"] for r in rs) for rs in groups.values()), default=0)
    raise MMError("Material %s: no single shade / caliber has %s m2 free (largest: %s m2) - deliver less or "
                  "split the item" % (matnr, qty / 1000.0, best / 1000.0), "TL", "014")


def assign(conn, vbeln, posnr, picks):
    """ZTILE_LOTS: the lots for one delivery item, chosen by the warehouse. picks: [{lot, qty}]"""
    vbeln = str(vbeln or "").strip()
    pos = parse_int(posnr, "item")
    l = conn.execute("SELECT * FROM sd_lips WHERE vbeln=? AND posnr=?", (vbeln, pos)).fetchone()
    if not l:
        raise MMError("Delivery item %s/%s does not exist" % (vbeln, posnr), "TL", "015")
    h = conn.execute("SELECT wbstk FROM sd_likp WHERE vbeln=?", (vbeln,)).fetchone()
    if h and h["wbstk"] == "C":
        raise MMError("Goods issue of delivery %s is already posted" % vbeln, "TL", "016")
    rows = []
    for p in (picks if isinstance(picks, list) else []):
        if not isinstance(p, dict):
            raise MMError("Wrong lot line", "TL", "013")
        lot = conn.execute("SELECT * FROM tile_lot WHERE lot=?", (str(p.get("lot") or "").strip().upper(),)).fetchone()
        if not lot:
            raise MMError("Lot %s does not exist" % str(p.get("lot") or ""), "TL", "013")
        q = parse_qty(p.get("qty"))
        if lot["matnr"] != l["matnr"]:
            raise MMError("Lot %s is material %s, not %s" % (lot["lot"], lot["matnr"], l["matnr"]), "TL", "017")
        if lot["status"] != "OK":
            raise MMError("Lot %s is %s" % (lot["lot"], STATUS[lot["status"]].lower()), "TL", "018")
        if q > lot["qty"] - lot["issued"]:
            raise MMError("Lot %s has only %s m2 free" % (lot["lot"], (lot["qty"] - lot["issued"]) / 1000.0), "TL", "019")
        rows.append((lot, q))
    _check_one_shade([r[0] for r in rows], l["matnr"])
    need = l["pikmg"] or l["lfimg"]
    if sum(q for _, q in rows) != need:
        raise MMError("The lots give %s m2 - the item needs %s m2" % (sum(q for _, q in rows) / 1000.0, need / 1000.0),
                      "TL", "020")
    with transaction(conn):
        conn.execute("DELETE FROM tile_pick WHERE vbeln=? AND posnr=? AND done=0", (vbeln, pos))
        for lot, q in rows:
            conn.execute("INSERT INTO tile_pick VALUES (?,?,?,?,0)", (vbeln, pos, lot["lot"], q))
    return {"message": "Item %s: %d lot(s), shade %s, caliber %s" % (pos, len(rows), rows[0][0]["shade"],
                                                                      rows[0][0]["caliber"])}


def _check_one_shade(lots_, matnr):
    if len({(x["shade"], x["caliber"]) for x in lots_}) > 1:
        raise MMError("%s: one delivery item may only have one shade and one caliber - the lots differ (%s)" % (
            matnr, ", ".join(sorted({"%s/%s" % (x["shade"], x["caliber"]) for x in lots_}))), "TL", "021")


def picks(conn, vbeln):
    """lots of a delivery: proposal for items without a choice"""
    out, taken = [], {}
    for l in _items(conn, vbeln):
        need = l["pikmg"] or l["lfimg"]
        cur = conn.execute("SELECT p.*, t.shade, t.caliber FROM tile_pick p JOIN tile_lot t USING (lot) WHERE "
                           "p.vbeln=? AND p.posnr=?", (vbeln, l["posnr"])).fetchall()
        if cur:
            out.append(dict(posnr=l["posnr"], matnr=l["matnr"], qty=need, chosen=True,
                            lots=[dict(lot=c["lot"], qty=c["qty"], shade=c["shade"], caliber=c["caliber"]) for c in cur]))
            continue
        try:
            pr = propose(conn, l["matnr"], l["werks"], need, taken)
            for lot, q in pr:
                taken[lot] = taken.get(lot, 0) + q
            info = {r["lot"]: r for r in conn.execute("SELECT * FROM tile_lot WHERE lot IN (%s)" % ",".join(
                "?" * len(pr)), [x[0] for x in pr])}
            out.append(dict(posnr=l["posnr"], matnr=l["matnr"], qty=need, chosen=False, lots=[
                dict(lot=lot, qty=q, shade=info[lot]["shade"], caliber=info[lot]["caliber"]) for lot, q in pr]))
        except MMError as e:
            out.append(dict(posnr=l["posnr"], matnr=l["matnr"], qty=need, chosen=False, lots=[], error=e.msg))
    return out


def on_goods_issue(conn, vbeln):
    """called by the goods issue of a delivery (sd.delivery.post_gi): every tile item gets its lots
    (the chosen ones or the proposal), one shade + caliber, and the lots are reduced."""
    items = _items(conn, vbeln)
    if not items:
        return
    taken = {}
    for l in items:
        need = l["pikmg"] or l["lfimg"]
        cur = conn.execute("SELECT * FROM tile_pick WHERE vbeln=? AND posnr=? AND done=0", (vbeln, l["posnr"])).fetchall()
        if cur:
            rows = [(c["lot"], c["qty"]) for c in cur]
        else:
            rows = propose(conn, l["matnr"], l["werks"], need, taken)
            for lot, q in rows:
                conn.execute("INSERT OR REPLACE INTO tile_pick VALUES (?,?,?,?,0)", (vbeln, l["posnr"], lot, q))
        info = [conn.execute("SELECT * FROM tile_lot WHERE lot=?", (lot,)).fetchone() for lot, _ in rows]
        _check_one_shade(info, l["matnr"])
        if sum(q for _, q in rows) != need:
            raise MMError("Delivery %s item %s: the lots give %s m2, the item needs %s m2 - choose the lots again "
                          "(ZTILE_LOTS)" % (vbeln, l["posnr"], sum(q for _, q in rows) / 1000.0, need / 1000.0),
                          "TL", "020")
        for (lot, q), t in zip(rows, info):
            if t["status"] != "OK" or t["qty"] - t["issued"] - taken.get(lot, 0) < q:
                raise MMError("Lot %s is not free any more - choose the lots again (ZTILE_LOTS)" % lot, "TL", "022")
            taken[lot] = taken.get(lot, 0) + q
    for lot, q in taken.items():
        conn.execute("UPDATE tile_lot SET issued = issued + ? WHERE lot=?", (q, lot))
    conn.execute("UPDATE tile_pick SET done=1 WHERE vbeln=?", (vbeln,))


# ------------------------------------------------------------------ lab
def test(conn, lot, values, user):
    """lab test of a lot against its ISO 13006 group; a failed test blocks the lot"""
    t = conn.execute("SELECT * FROM tile_lot WHERE lot=?", (str(lot or "").strip().upper(),)).fetchone()
    if not t:
        raise MMError("Lot %s does not exist" % str(lot or ""), "TL", "013")
    p = _product_of(conn, t["matnr"])
    g = GROUPS[p["bgroup"]] if p and p["bgroup"] in GROUPS else GROUPS["BIIa"]
    wa = parse_qty(values.get("water_abs"), allow_zero=True)          # % with 3 decimals -> milli
    st = parse_int(values.get("strength"), "breaking strength (N)", 0, 100000)
    pl = parse_qty(values.get("planarity") or "0", allow_zero=True)
    sz = parse_qty(values.get("size_dev") or "0", allow_zero=True)
    failed = []
    if wa < g[1] or (g[2] is not None and wa > g[2]):
        failed.append("water absorption %.2f %% outside %s" % (wa / 1000.0, g[0]))
    if st < g[3]:
        failed.append("breaking strength %d N < %d N" % (st, g[3]))
    if pl > MAX_PLANARITY:
        failed.append("planarity %.2f %% > %.1f %%" % (pl / 1000.0, MAX_PLANARITY / 1000.0))
    if sz > MAX_SIZE_DEV:
        failed.append("size %.2f %% > %.1f %%" % (sz / 1000.0, MAX_SIZE_DEV / 1000.0))
    result = "FAIL" if failed else "PASS"
    day = parse_date(values.get("day"))
    with transaction(conn):
        conn.execute("INSERT INTO tile_test (lot,day,water_abs,strength,planarity,size_dev,result,failed,usnam,ts) "
                     "VALUES (?,?,?,?,?,?,?,?,?,?)", (t["lot"], day, wa, st, pl, sz, result, "; ".join(failed),
                                                      user, now_ts()))
        if failed:
            conn.execute("UPDATE tile_lot SET status='BLOCK', note=? WHERE lot=?", ("Lab: " + failed[0], t["lot"]))
        elif t["status"] == "HOLD":
            conn.execute("UPDATE tile_lot SET status='OK', note='Lab passed' WHERE lot=?", (t["lot"],))
    return {"result": result, "failed": failed, "group": p["bgroup"] if p else "BIIa",
            "message": "Lot %s: %s" % (t["lot"], "passed" if not failed else "FAILED - lot blocked: " + "; ".join(failed))}


def tests(conn, limit=100):
    return [dict(r) for r in conn.execute("SELECT x.*, l.matnr, l.shade, l.caliber FROM tile_test x JOIN tile_lot l "
                                          "USING (lot) ORDER BY x.id DESC LIMIT ?", (limit,))]


# ------------------------------------------------------------------ KPI
def kpi(conn, frm=None, to=None):
    """first-choice rate = grade 1 / everything sorted, per day and product; defects Pareto"""
    to = parse_date(to)
    frm = parse_date(frm) if frm else (datetime.date.fromisoformat(to) - datetime.timedelta(days=29)).isoformat()
    rows = conn.execute("SELECT * FROM tile_sort WHERE day BETWEEN ? AND ? ORDER BY day", (frm, to)).fetchall()

    def agg(rs):
        g = [sum(r[k] for r in rs) for k in ("grade1", "grade2", "grade3", "broken")]
        tot = sum(g)
        return dict(grade1=g[0], grade2=g[1], grade3=g[2], broken=g[3], total=tot,
                    first_choice=round(100.0 * g[0] / tot, 1) if tot else None)
    days, prods = {}, {}
    for r in rows:
        days.setdefault(r["day"], []).append(r)
        prods.setdefault(r["matnr"], []).append(r)
    ids = [r["id"] for r in rows]
    defects = []
    if ids:
        for d in conn.execute("SELECT code, SUM(qty) q FROM tile_defect WHERE sort_id IN (%s) GROUP BY code ORDER BY q "
                              "DESC" % ",".join("?" * len(ids)), ids):
            defects.append(dict(code=d["code"], text=DEFECTS[d["code"]], text_ar=DEFECTS_AR[d["code"]], qty=d["q"]))
    names = {r["matnr"]: r["maktx"] for r in conn.execute("SELECT matnr, maktx FROM material")}
    return dict(frm=frm, to=to, total=agg(rows),
                days=[dict(day=k, **agg(v)) for k, v in sorted(days.items())],
                products=[dict(matnr=k, maktx=names.get(k, ""), **agg(v)) for k, v in sorted(prods.items())],
                defects=defects, target=95.0)


def day_text(conn, day=None):
    """one line for the morning briefing: yesterday's first-choice rate (empty without sorting data)"""
    d = parse_date(day) if day else (clock.today() - datetime.timedelta(days=1)).isoformat()
    last = conn.execute("SELECT MAX(day) FROM tile_sort WHERE day<=?", (d,)).fetchone()[0]
    if not last:
        return ""
    k = kpi(conn, last, last)["total"]
    prev = kpi(conn, (datetime.date.fromisoformat(last) - datetime.timedelta(days=28)).isoformat(),
               (datetime.date.fromisoformat(last) - datetime.timedelta(days=1)).isoformat())["total"]
    arrow = ""
    if prev["first_choice"] is not None:
        diff = k["first_choice"] - prev["first_choice"]
        arrow = " (%s %.1f عن متوسط الشهر)" % ("▲" if diff >= 0 else "▼", abs(diff))
    flag = " ⚠️ أقل من الهدف 95%" if k["first_choice"] < 95 else ""
    return "- الفرز الأول يوم %s: %.1f%% من %s م2%s%s" % (last[8:10] + "/" + last[5:7], k["first_choice"],
                                                     "{:,.0f}".format(k["total"] / 1000.0), arrow, flag)
