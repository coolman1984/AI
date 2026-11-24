"""Ceramic factory demo - this month's business after the go-live (see mm/demo_ceramic.py):
purchase -> goods receipt -> invoice, body preparation and tile production orders with
confirmations and scrap, domestic and export sales with delivery and billing."""
from mm import util as mmclock
from mm.posting import post_goods_movement

USER = "MIGRATION"
# cost center, activity, hours per month (3 shifts), price fix, price var per hour (EGP)
PLAN_PRICES = [("4100", "MACH", "620", "1400", "1400"), ("4200", "MACH", "620", "1900", "1600"),
               ("4300", "MACH", "620", "1700", "1500"), ("4400", "KILN", "700", "3500", "6000"),
               ("4500", "LAB", "1800", "300", "150")]


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

    body = order.create(conn, {"auart": "PP01", "matnr": "SF-SPR", "gamng": "600000", "gstrp": d(5),
                               "lgort": "0001"}, USER)
    order.release(conn, body, USER, d(5))
    picking(body, 5)
    order.confirm(conn, body, "0010", "600000", budat=d(6), user=USER)
    order.confirm(conn, body, "0020", "594000", "6000", budat=d(7), final=True, user=USER, grund="01")
    receive(body, "594000", "0001", 7)
    tiles = [("FG-F60", "20000", "19100", "900", 8, True), ("FG-W36", "15000", "14450", "550", 9, True),
             ("FG-P612", "6000", "3000", "120", 10, False)]
    for matnr, qty, good, scrap, day, done in tiles:
        a = order.create(conn, {"auart": "PP01", "matnr": matnr, "gamng": qty, "gstrp": d(day),
                                "lgort": "0003"}, USER)
        order.release(conn, a, USER, d(day))
        picking(a, day)
        ops = ["0010", "0020", "0030", "0040", "0050"] if done else ["0010", "0020"]
        for n, vornr in enumerate(ops):
            last = done and vornr == "0050"
            order.confirm(conn, a, vornr, good, scrap if vornr == "0040" else "0",
                          budat=d(day + 1 + n // 3), final=last, user=USER,
                          grund="02" if vornr == "0040" and scrap != "0" else None)
        if done:
            receive(a, good, "0003", day + 2)
    # one more order for next week, only released
    nxt = order.create(conn, {"auart": "PP01", "matnr": "FG-F45", "gamng": "12000", "gstrp": d(20),
                              "lgort": "0003"}, USER)
    order.release(conn, nxt, USER, d(min(20, t.day)))

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
