"""Ceramic factory demo - this month's business after the go-live (see mm/demo_ceramic.py):
purchase -> goods receipt -> invoice, body preparation and tile production orders with
confirmations and scrap, domestic and export sales with delivery and billing."""
import datetime

from mm import util as mmclock
from mm.posting import post_goods_movement

USER = "MIGRATION"
# cost center, activity, hours per month (3 shifts), price fix, price var per hour (EGP)
PLAN_PRICES = [("4100", "MACH", "620", "1400", "1400"), ("4200", "MACH", "620", "1900", "1600"),
               ("4300", "MACH", "620", "1700", "1500"), ("4400", "KILN", "700", "3500", "6000"),
               ("4500", "LAB", "1800", "300", "150")]


OPENING_LOTS = [("FG-F45", "C1", "44.8", "18000"), ("FG-F60", "A1", "9.8", "20000"), ("FG-F60", "A2", "9.9", "22000"),
                ("FG-F60B", "A1", "9.8", "6500"), ("FG-W36", "B1", "29.7", "15000"), ("FG-W36", "B3", "29.8", "10000"),
                ("FG-P612", "P1", "59.6", "9000")]
# one sorting per day: grade 1 lots (shade, caliber, m2), grade 2, grade 3, broken, defects
SORTING = {
    "FG-F60": [dict(lots=[dict(shade="A1", caliber="9.8", qty="7200"), dict(shade="A2", caliber="9.8", qty="2100")],
                    grade2=[dict(shade="A1", caliber="9.8", qty="500")], grade3="150", broken="100",
                    defects={"GLZ": "260", "PIN": "180", "CHP": "160", "PRN": "150"}),
               dict(lots=[dict(shade="A1", caliber="9.9", qty="6800"), dict(shade="A3", caliber="9.8", qty="1500")],
                    grade2=[dict(shade="A3", caliber="9.8", qty="450")], grade3="200", broken="100",
                    defects={"PLN": "300", "GLZ": "180", "SHD": "150", "CHP": "120"})],
    "FG-W36": [dict(lots=[dict(shade="B1", caliber="29.7", qty="7200"), dict(shade="B2", caliber="29.7", qty="1800")],
                    grade3="450", broken="250", defects={"CRK": "300", "GLZ": "250", "CHP": "150"}),
               dict(lots=[dict(shade="B1", caliber="29.8", qty="3800")], grade3="650", broken="300",
                    defects={"CRK": "400", "PLN": "300", "DOT": "250"})]}
# meter, text, kind, area, price per unit (EGP per m3 / kWh) - illustrative tariffs, set your own
METERS = [("GAS-KILN", "غاز الفرن", "GAS", "FIRING", "8.50"), ("GAS-SPRAY", "غاز المجفف الرذاذي", "GAS",
                                                                "PREPARATION", "8.50"),
          ("GAS-DRY", "غاز المجففات الرأسية", "GAS", "FORMING", "8.50"),
          ("POWER", "الكهرباء - العداد الرئيسي", "POWER", "PLANT", "2.34")]
# per m2 sorted: m3 gas of each meter and kWh; idle day (no sorting): holding the kiln hot
PER_M2 = {"GAS-KILN": 1.10, "GAS-SPRAY": 0.42, "GAS-DRY": 0.22, "POWER": 3.3}
IDLE = {"GAS-KILN": 950, "GAS-SPRAY": 0, "GAS-DRY": 60, "POWER": 2600}


def _energy(conn, energy, go_live, t):
    import datetime as _dt
    day = _dt.date.fromisoformat(go_live)
    read = {m: 1000000.0 for m in PER_M2}
    n = 0
    while day <= t:
        ds = day.isoformat()
        m2 = (conn.execute("SELECT COALESCE(SUM(grade1+grade2),0) FROM tile_sort WHERE day=?", (ds,)).fetchone()[0]
              / 1000.0)
        if day.isoformat() != go_live:
            for m in PER_M2:
                use = PER_M2[m] * m2 * (1.18 if m2 and n == 3 else 1.0 + 0.03 * ((n % 5) - 2)) if m2 else IDLE[m]
                read[m] += round(use, 1)
            n += 1 if m2 else 0
        for m in PER_M2:
            energy.save_reading(conn, m, ds, "%.1f" % read[m], "SHOP1")
        day += _dt.timedelta(days=1)


def _vendor(conn, altkn):
    return conn.execute("SELECT lifnr FROM vendor WHERE altkn=?", (altkn,)).fetchone()[0]


def run(conn):
    from fi import ap
    from pp import order
    from pur import po
    from sd import billing as bl, delivery as dl, order as so
    t = mmclock.today()
    d = lambda day: mmclock.day_in_month(t.year, t.month, day, cap=t).isoformat()

    # ------------------------------------------------------------ plan prices of the lines (KP26)
    from co import planning
    nxt_y, nxt_p = (t.year + 1, 1) if t.month == 12 else (t.year, t.month + 1)
    for kostl, lstar, hours, fix, var in PLAN_PRICES:
        for y, p in ((t.year, t.month), (nxt_y, nxt_p)):
            planning.plan_activity(conn, y, p, p, kostl, lstar, hours, None, fix, var)

    # ------------------------------------------------------------ purchasing
    def buy(day, altkn, ekgrp, items, ref):
        h = po.create_po(conn, {"lifnr": _vendor(conn, altkn), "bedat": d(day), "ekgrp": ekgrp,
                                "items": items}, USER)
        e = h["ebeln"] if isinstance(h, dict) else h
        if conn.execute("SELECT frgke FROM po_header WHERE ebeln=?", (e,)).fetchone()[0] == "B":
            po.release_all(conn, e, USER)
        return e

    def gr(day, ebeln, ebelp, qty):
        post_goods_movement(conn, {"budat": d(day), "xblnr": "DN-%s" % ebeln[-4:]},
                            [{"bwart": "101", "ebeln": ebeln, "ebelp": ebelp, "qty": qty}], USER)

    clay = buy(1, "V-CLY", "101", [{"matnr": "RM-CLR", "menge": "600000", "lgort": "0001"},
                                    {"matnr": "RM-CLW", "menge": "150000", "lgort": "0001"}], "")
    feld = buy(2, "V-FLD", "101", [{"matnr": "RM-FLD", "menge": "250000", "lgort": "0001"},
                                    {"matnr": "RM-KAO", "menge": "80000", "lgort": "0001"}], "")
    ctn = buy(2, "V-CTN", "103", [{"matnr": "PK-CTN", "menge": "40000", "lgort": "0005"}], "")
    buy(3, "V-FRT", "102", [{"matnr": "RM-FRT", "menge": "20000", "lgort": "0002"},
                             {"matnr": "RM-GLZ", "menge": "12000", "lgort": "0002"}], "")   # import, in transit
    gr(4, clay, 10, "600000")
    gr(4, clay, 20, "150000")
    gr(6, feld, 10, "150000")                                     # partial delivery
    gr(5, ctn, 10, "40000")
    ap.miro(conn, {"ebeln": clay, "bldat": d(6), "budat": d(6), "xblnr": "CLY-%d-118" % t.year},
            [{"ebelp": 10, "qty": "600000"}, {"ebelp": 20, "qty": "150000"}], USER)

    # ------------------------------------------------------------ production
    def picking(aufnr, day):
        order.post_picking(conn, [dict(rsnum=r["rsnum"], rspos=r["rspos"])
                                  for r in order.picking_list(conn) if r["aufnr"] == aufnr], d(day), USER)

    def receive(aufnr, qty, lgort, day):
        if not conn.execute("SELECT 1 FROM mat_doc_item WHERE aufnr=? AND bwart='101' AND canceled=0", (aufnr,)).fetchone():
            post_goods_movement(conn, {"budat": d(day), "bktxt": "GR production order"}, [
                {"bwart": "101", "aufnr": aufnr, "qty": qty, "lgort": lgort}], USER)

    body = order.create(conn, {"auart": "PP01", "matnr": "SF-SPR", "gamng": "900000", "gstrp": d(5),
                               "lgort": "0001"}, USER)
    order.release(conn, body, USER, d(5))
    picking(body, 5)
    order.confirm(conn, body, "0010", "900000", budat=d(6), user=USER)
    order.confirm(conn, body, "0020", "891000", "9000", budat=d(7), final=True, user=USER, grund="01")
    receive(body, "891000", "0001", 7)
    # tile products, lots of the opening stock (one shade + caliber each)
    from tile import energy, lots
    for m, g2, fmt, grp, box, pal in (("FG-F45", "", "45x45", "BIIa", "1.62", "48"),
                                      ("FG-F60", "FG-F60B", "60x60", "BIIa", "1.44", "40"),
                                      ("FG-W36", "", "30x60", "BIII", "1.44", "48"),
                                      ("FG-P612", "", "60x120", "BIa", "1.44", "24")):
        lots.save_product(conn, m, g2, fmt, grp, box, pal)
    go_live = (t.replace(day=1) - datetime.timedelta(days=1)).isoformat()
    for m, shade, cal, q in OPENING_LOTS:
        lots.opening_lot(conn, m, shade, cal, q, go_live)
    tiles = [("FG-F60", "20000", "19100", "900", 8, True), ("FG-W36", "15000", "14450", "550", 9, True),
             ("FG-P612", "6000", "3000", "120", 10, False)]
    for matnr, qty, good, scrap, day, done in tiles:
        a = order.create(conn, {"auart": "PP01", "matnr": matnr, "gamng": qty, "gstrp": d(day),
                                "lgort": "0003"}, USER)
        order.release(conn, a, USER, d(day))
        picking(a, day)
        ops = ["0010", "0020", "0030", "0040"] if done else ["0010", "0020"]
        for n, vornr in enumerate(ops):
            order.confirm(conn, a, vornr, good, scrap if vornr == "0040" else "0",
                          budat=d(day + 1 + n // 3), user=USER,
                          grund="02" if vornr == "0040" and scrap != "0" else None)
        if done:                                    # sorting line: grades, shades, calibers -> stock + lots
            first = 0
            for k, srt in enumerate(SORTING[matnr]):
                r = lots.sort(conn, a, dict(srt, day=d(day + 2 + k), arbpl="WC-SORT"), USER)
                first += sum(float(x["qty"]) for x in srt["lots"])
            order.confirm(conn, a, "0050", "%.3f" % first, budat=d(day + 3), final=True, user=USER)
    # lab: lots of this month tested; one fails planarity and is blocked
    for n, lot in enumerate(r0["lot"] for r0 in conn.execute(
            "SELECT lot FROM tile_lot WHERE sort_id IS NOT NULL ORDER BY lot").fetchall()):
        grp = conn.execute("SELECT bgroup FROM tile_product p JOIN tile_lot l ON l.matnr IN (p.matnr, p.grade2) "
                           "WHERE l.lot=?", (lot,)).fetchone()[0]
        wa, st = {"BIa": ("0.35", "1650"), "BIIa": ("4.6", "1250"), "BIII": ("13.8", "820")}[grp]
        lots.test(conn, lot, dict(day=d(13), water_abs=wa, strength=st, planarity="0.65" if n == 3 else "0.30",
                                  size_dev="0.25"), "QM1")
    # floor 45x45 runs on line 1 every day since the 14th: sorted daily (first-choice rate, gas per m2)
    f45 = order.create(conn, {"auart": "PP01", "matnr": "FG-F45", "gamng": "12000", "gstrp": d(14),
                              "lgort": "0003"}, USER)
    order.release(conn, f45, USER, d(14))
    picking(f45, 14)
    for vornr in ("0010", "0020", "0030", "0040"):
        order.confirm(conn, f45, vornr, "11700", "300" if vornr == "0040" else "0", budat=d(14), user=USER,
                      grund="02" if vornr == "0040" else None)
    days = list(range(14, t.day)) or [14]
    per = 11700.0 / len(days)
    sorted_g1 = 0.0
    for n, day in enumerate(days):
        fc = (0.935, 0.948, 0.921, 0.952, 0.94, 0.886, 0.945)[n % 7]      # one bad day (glaze line)
        g1 = round(per * fc)
        g3 = round(per * (1 - fc) * 0.6)
        br = round(per) - g1 - g3
        shade = "C%d" % (1 + n // 4)
        lots.sort(conn, f45, dict(day=d(day), arbpl="WC-SORT", lots=[dict(shade=shade, caliber="44.8", qty=str(g1))],
                                  grade3=str(g3), broken=str(br),
                                  defects={"GLZ": str(round(g3 * 0.5)), "PIN": str(g3 - round(g3 * 0.5)),
                                           "CHP": str(br)}), USER)
        sorted_g1 += g1
    order.confirm(conn, f45, "0050", "%.3f" % sorted_g1, budat=d(days[-1]), final=True, user=USER)
    # porcelain for next week: released only
    nxt = order.create(conn, {"auart": "PP01", "matnr": "FG-P612", "gamng": "8000", "gstrp": d(25),
                              "lgort": "0003"}, USER)
    order.release(conn, nxt, USER, d(min(25, t.day)))

    # ------------------------------------------------------------ sales
    orders = [("C1001", 10, "DST-7781", [("FG-F60", "8000"), ("FG-W36", "4000")], True),
              ("C1002", 11, "ALX-2210", [("FG-W36", "5000"), ("FG-F60B", "2500")], True),
              ("C1005", 11, "NCP-PH2-118", [("FG-P612", "3000")], True),
              ("C1006", 12, "GBM-EXP-55", [("FG-F60", "6000")], True),
              ("C1003", 13, "DLT-411", [("FG-F45", "3500")], False),
              ("C1004", 13, "UPE-090", [("FG-F60", "2000"), ("FG-W36", "1500")], False)]
    for kunnr, day, ref, items, ship in orders:
        r = so.create(conn, dict(auart="OR", kunnr=kunnr, audat=d(day), vdatu=d(day + 2), bstnk=ref,
                                 items=[dict(matnr=m, qty=q) for m, q in items]), USER)
        v = r["vbeln"]
        if conn.execute("SELECT cmgst FROM sd_vbak WHERE vbeln=?", (v,)).fetchone()[0] == "B":
            so.release_credit(conn, v, "CREDITMGR")
        if ship:
            dn = dl.create(conn, v, USER, d(day + 1))["vbeln"]
            dl.pick(conn, dn)
            dl.post_gi(conn, dn, USER, d(day + 1))
            bl.create(conn, dn, USER, d(day + 1))

    # energy meters, one reading per day from the go-live (gas per m2 of the sorted tiles)
    for m, txt, kind, area, price in METERS:
        energy.save_meter(conn, m, txt, kind, area, price)
    _energy(conn, energy, go_live, t)
