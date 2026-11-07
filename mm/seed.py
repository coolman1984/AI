"""Demo data: 2 plants, storage locations, bins, materials, vendors, POs and
about four months of goods movements (all posted through the real engine)."""
import datetime
import random

from . import master, posting

USER = "DEMO"


ANCHOR = [datetime.date.today()]


def _d(days_ago):
    """Date 'days_ago' before the anchor. The MM history ends on the last day
    before the CO sample month, so that month only holds the CO sample."""
    return (ANCHOR[0] - datetime.timedelta(days=days_ago)).isoformat()


def seed(conn):
    """Full demo: CO master data, ~4 months of MM history, then the CO plan
    and one complete CO sample month (see co/seed.py)."""
    if conn.execute("SELECT COUNT(*) FROM plant").fetchone()[0]:
        return None
    from co import seed as co_seed
    sample_start = co_seed.sample_period_start()
    ANCHOR[0] = sample_start - datetime.timedelta(days=1)
    failed = seed_mm(conn, before=lambda: co_seed.master(conn))
    from fi import seed as fi_seed
    from pur import seed as pur_seed
    pur_seed.master(conn)
    hist_start = ANCHOR[0] - datetime.timedelta(days=130)
    fi_seed.history(conn, hist_start.replace(day=1), ANCHOR[0])
    from md import seed as md_seed
    md_seed.master(conn)
    failed += co_seed.plan_and_sample(conn)
    return failed


def seed_mm(conn, before=None):
    if conn.execute("SELECT COUNT(*) FROM plant").fetchone()[0]:
        return None
    rnd = random.Random(42)

    # ---------------------------------------------------------- org structure
    master.create_plant(conn, "1000", "Cairo Plant", "Cairo")
    master.create_plant(conn, "1100", "Alexandria Plant", "Alexandria")
    if before:
        before()
    slocs = [("1000", "0001", "Raw Material WH", True),
             ("1000", "0002", "Production Supply", False),
             ("1000", "0003", "Finished Goods WH", True),
             ("1000", "0004", "Spare Parts Store", True),
             ("1000", "0005", "QA / Quarantine", False),
             ("1100", "0001", "Raw Material WH", False),
             ("1100", "0003", "Finished Goods WH", False)]
    for s in slocs:
        master.create_sloc(conn, *s[:3], bin_managed=s[3])
    for rack in ("A", "B", "C"):
        for level in range(1, 4):
            for pos in range(1, 4):
                master.create_bin(conn, "1000", "0001",
                                  "%s-%02d-%02d" % (rack, level, pos), "Rack")
    master.create_bin(conn, "1000", "0001", "GR-ZONE", "Goods receipt zone")
    for i in range(1, 9):
        master.create_bin(conn, "1000", "0003", "F-%02d" % i, "Floor")
    for i in range(1, 13):
        master.create_bin(conn, "1000", "0004", "S-%02d" % i, "Shelf")

    for v in [("100001", "Delta Steel Trading", "Cairo"),
              ("100002", "Nile Polymers", "Alexandria"),
              ("100003", "Pyramid Paints", "Giza"),
              ("100004", "Cairo Packaging Co.", "Cairo"),
              ("100005", "Precision Bearings Co.", "10th of Ramadan"),
              ("100006", "Suez Copper Works", "Suez")]:
        master.create_vendor(conn, *v)
    for k in [("4100", "Production Line 1"), ("4200", "Maintenance"),
              ("4300", "Quality Control"), ("4400", "Warehouse"),
              ("4500", "Sales Samples")]:
        if not conn.execute("SELECT 1 FROM cost_center WHERE kostl=?",
                            (k[0],)).fetchone():
            master.create_cost_center(conn, *k)

    # ---------------------------------------------------------- materials
    both = ["1000", "1100"]
    mats = [
        ("RM-1001", "Steel sheet 2mm cold rolled", "ROH", "KG", "STEEL", "V", "45.00", 1, "1500", both),
        ("RM-1002", "Polypropylene granules", "ROH", "KG", "PLAST", "V", "62.00", 1, "800", ["1000"]),
        ("RM-1003", "Paint white RAL9010", "ROH", "L", "PAINT", "V", "180.00", 1, "400", ["1000"]),
        ("RM-1004", "Copper wire 1.5mm", "ROH", "KG", "COPPER", "V", "520.00", 1, "150", ["1000"]),
        ("PK-2001", "Carton box 40x30x30", "VERP", "PC", "PACK", "V", "1250.00", 100, "2000", ["1000"]),
        ("FG-3001", "Kitchen cabinet unit 60cm", "FERT", "PC", "CABINET", "S", "2450.00", 1, "20", both),
        ("FG-3002", "Wall cabinet unit 40cm", "FERT", "PC", "CABINET", "S", "1580.00", 1, "20", ["1000"]),
        ("SP-4001", "Ball bearing 6205-2RS", "HIBE", "PC", "BEARING", "V", "85.00", 1, "40", ["1000"]),
        ("SP-4002", "V-belt A-42", "HIBE", "PC", "BELT", "V", "60.00", 1, "30", ["1000"]),
        ("SP-4003", "Hydraulic oil ISO 46", "HIBE", "L", "OIL", "V", "95.00", 1, "200", ["1000"]),
    ]
    for (matnr, txt, mtart, meins, matkl, vprsv, price, peinh, minbe,
         plants) in mats:
        master.create_material(conn, {
            "matnr": matnr, "maktx": txt, "mtart": mtart, "meins": meins,
            "matkl": matkl, "plants": [{"werks": w, "vprsv": vprsv, "price": price,
                                        "peinh": peinh, "minbe": minbe,
                                        "eisbe": str(int(int(minbe) * 0.4))}
                                       for w in plants]}, USER)

    def post(days_ago, items, text=""):
        try:
            return posting.post_goods_movement(
                conn, {"budat": _d(days_ago), "bktxt": text}, items, USER)
        except Exception:
            failed.append((days_ago, items))
            return None

    failed = []

    # ---------------------------------------------------------- opening stock
    post(130, [
        {"bwart": "561", "matnr": "RM-1001", "werks": "1000", "lgort": "0001",
         "lgpla": "A-01-01", "qty": "2500", "amount": "110000"},
        {"bwart": "561", "matnr": "RM-1002", "werks": "1000", "lgort": "0001",
         "lgpla": "B-01-01", "qty": "1800", "amount": "109800"},
        {"bwart": "561", "matnr": "RM-1003", "werks": "1000", "lgort": "0001",
         "lgpla": "C-01-01", "qty": "300", "amount": "52500"},
        {"bwart": "561", "matnr": "RM-1004", "werks": "1000", "lgort": "0001",
         "lgpla": "C-02-01", "qty": "200", "amount": "102000"},
        {"bwart": "561", "matnr": "PK-2001", "werks": "1000", "lgort": "0001",
         "lgpla": "C-03-01", "qty": "3000", "amount": "36600"},
        {"bwart": "561", "matnr": "FG-3001", "werks": "1000", "lgort": "0003",
         "lgpla": "F-01", "qty": "40"},
        {"bwart": "561", "matnr": "FG-3002", "werks": "1000", "lgort": "0003",
         "lgpla": "F-02", "qty": "55"},
        {"bwart": "561", "matnr": "SP-4001", "werks": "1000", "lgort": "0004",
         "lgpla": "S-01", "qty": "60", "amount": "4950"},
        {"bwart": "561", "matnr": "SP-4002", "werks": "1000", "lgort": "0004",
         "lgpla": "S-02", "qty": "35", "amount": "2030"},
        {"bwart": "561", "matnr": "SP-4003", "werks": "1000", "lgort": "0004",
         "lgpla": "S-03", "qty": "400", "amount": "36800"},
        {"bwart": "561", "matnr": "RM-1001", "werks": "1100", "lgort": "0001",
         "qty": "800", "amount": "37600"},
    ], "Initial stock takeover")

    # ---------------------------------------------------------- purchasing
    buys = [("RM-1001", "100001", 45.0, 2600, "0001", ["A-01-02", "A-02-01",
                                                      "A-02-02", "A-03-01"]),
            ("RM-1002", "100002", 62.0, 1000, "0001", ["B-01-02", "B-02-01",
                                                      "B-02-02"]),
            ("RM-1003", "100003", 180.0, 150, "0001", ["C-01-02", "C-01-03"]),
            ("RM-1004", "100006", 520.0, 80, "0001", ["C-02-02"]),
            ("PK-2001", "100004", 12.5, 1000, "0001", ["C-03-02"]),
            ("SP-4001", "100005", 85.0, 20, "0004", ["S-01", "S-04"])]
    day = 118
    k = 0
    while day > 3:
        matnr, lifnr, base, qty, lgort, bins = buys[k % len(buys)]
        k += 1
        price = round(base * (1 + rnd.uniform(-0.06, 0.10) + (118 - day) * 0.0006), 2)
        peinh = 100 if matnr == "PK-2001" else 1
        netpr = "%.2f" % (price * peinh)
        try:
            ebeln = master.create_po(conn, {"lifnr": lifnr, "bedat": _d(day + 7),
                                            "items": [{"matnr": matnr, "werks": "1000",
                                                       "lgort": lgort, "menge": qty,
                                                       "netpr": netpr,
                                                       "peinh": peinh}]}, USER)
        except Exception:
            day -= 4
            continue
        from pur.po import release_all
        release_all(conn, ebeln, USER)
        to_qi = rnd.random() < 0.25 and matnr.startswith("RM")
        lgpla = rnd.choice(bins)
        part = qty if rnd.random() < 0.8 else int(qty * 0.6)
        post(day, [{"bwart": "101", "ebeln": ebeln, "ebelp": 10, "qty": part,
                    "lgpla": lgpla, "insmk": "Q" if to_qi else "U"}],
             "DN-%05d" % rnd.randint(10000, 99999))
        if to_qi:
            post(max(day - 2, 0), [{"bwart": "321", "matnr": matnr, "werks": "1000",
                                    "lgort": "0001", "lgpla": lgpla,
                                    "qty": int(part * 0.95)}], "QC release")
        day -= rnd.randint(3, 6)

    # ---------------------------------------------------------- consumption
    order = 1000100
    for day in range(115, 0, -1):
        if day % 7 in (5, 6):      # Friday / Saturday off
            continue
        order += 1
        items = [
            {"bwart": "201", "matnr": "RM-1001", "werks": "1000", "lgort": "0001",
             "qty": rnd.randint(60, 140), "kostl": "4100"},
            {"bwart": "201", "matnr": "RM-1002", "werks": "1000", "lgort": "0001",
             "qty": rnd.randint(40, 90), "kostl": "4100"},
        ]
        if day % 2 == 0:
            items.append({"bwart": "201", "matnr": "RM-1003", "werks": "1000",
                          "lgort": "0001", "qty": rnd.randint(8, 18),
                          "kostl": "4100"})
        if day % 3 == 0:
            items.append({"bwart": "201", "matnr": "PK-2001", "werks": "1000",
                          "lgort": "0001", "qty": rnd.randint(80, 200),
                          "kostl": "4100"})
        if day % 4 == 0:
            items.append({"bwart": "201", "matnr": "RM-1004", "werks": "1000",
                          "lgort": "0001", "qty": rnd.randint(4, 12),
                          "kostl": "4100"})
        post(day, items, "Prod. order %s" % order)
        if day % 5 == 0:
            post(day, [{"bwart": "201", "matnr": rnd.choice(["SP-4001", "SP-4002",
                                                             "SP-4003"]),
                        "werks": "1000", "lgort": "0004",
                        "qty": rnd.randint(2, 9), "kostl": "4200"}],
                 "Maintenance request")
        if day % 6 == 0:
            post(day, [{"bwart": "501", "matnr": rnd.choice(["FG-3001", "FG-3002"]),
                        "werks": "1000", "lgort": "0003",
                        "lgpla": rnd.choice(["F-03", "F-04", "F-05"]),
                        "qty": rnd.randint(10, 25)}], "Production output")
        if day % 9 == 0:
            post(day, [{"bwart": "311", "matnr": "RM-1001", "werks": "1000",
                        "lgort": "0001", "umlgo": "0002",
                        "qty": rnd.randint(50, 120)}], "Line-side supply")

    # ---------------------------------------------------------- special cases
    post(60, [{"bwart": "301", "matnr": "FG-3001", "werks": "1000", "lgort": "0003",
               "umwrk": "1100", "umlgo": "0003", "qty": "15"}], "Stock to Alexandria")
    post(45, [{"bwart": "301", "matnr": "RM-1001", "werks": "1000", "lgort": "0001",
               "umwrk": "1100", "umlgo": "0001", "qty": "400"}], "Support Alex plant")
    post(30, [{"bwart": "344", "matnr": "FG-3002", "werks": "1000", "lgort": "0003",
               "lgpla": "F-02", "qty": "6"}], "Damaged in handling")
    post(28, [{"bwart": "551", "matnr": "FG-3002", "werks": "1000", "lgort": "0003",
               "lgpla": "F-02", "qty": "2", "insmk": "B", "kostl": "4400"}],
         "Scrap damaged units")
    post(20, [{"bwart": "702", "matnr": "SP-4003", "werks": "1000", "lgort": "0004",
               "qty": "12"}], "Cycle count difference")
    post(18, [{"bwart": "701", "matnr": "SP-4001", "werks": "1000", "lgort": "0004",
               "lgpla": "S-01", "qty": "3"}], "Cycle count difference")
    wrong = post(10, [{"bwart": "201", "matnr": "SP-4001", "werks": "1000",
                       "lgort": "0004", "qty": "20", "kostl": "4300"}],
                 "Wrong cost center")
    if wrong:
        try:
            posting.cancel_document(conn, wrong["mblnr"], wrong["mjahr"], _d(10),
                                    USER, "Wrong cost center")
        except Exception:
            pass
    post(4, [{"bwart": "201", "matnr": "SP-4002", "werks": "1000", "lgort": "0004",
              "qty": "5", "kostl": "4200"}], "Belt replacement line 1")

    # ---------------------------------------------------------- open POs
    master.create_po(conn, {"lifnr": "100001", "bedat": _d(2), "items": [
        {"matnr": "RM-1001", "werks": "1000", "lgort": "0001", "menge": "2000",
         "netpr": "49.50"},
        {"matnr": "RM-1004", "werks": "1000", "lgort": "0001", "menge": "100",
         "netpr": "545.00"}]}, USER)
    master.create_po(conn, {"lifnr": "100005", "bedat": _d(1), "items": [
        {"matnr": "SP-4002", "werks": "1000", "lgort": "0004", "menge": "50",
         "netpr": "58.00"},
        {"matnr": "SP-4001", "werks": "1000", "lgort": "0004", "menge": "30",
         "netpr": "88.00"}]}, USER)
    conn.execute("INSERT OR REPLACE INTO settings VALUES ('seeded', ?)", (_d(0),))
    return failed
