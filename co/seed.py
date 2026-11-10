"""CO demo: master data, plan, and ONE complete sample month (A -> Z).

Sample month = the month before today. Everything in it is posted through
the real engines, in the same order as in a real SAP closing:

 PLAN (every period from the sample month to year end)
   KP06 primary costs -> KP46 stat. key figures -> plan distribution /
   assessment -> KP26 activity quantities -> activity input -> KSPI prices
   -> CK11N standard cost estimates -> CK24 release (new standard price)
   -> KE11 sales plan -> plan overhead credit -> plan assessment to CO-PA

 ACTUAL (sample month)
   CO01 production orders -> MIGO GR raw material (price increase)
   -> MIGO 261 material issues -> CO11N confirmations -> KB21N maintenance
   hours -> MIGO 101 goods receipts -> TECO -> MIGO 201 spare parts ->
   FB50 payroll / energy / rent / depreciation / services -> internal order
   (trade fair) -> KB31N statistical key figures -> VF01 billing (601 + FI +
   CO-PA)

 PERIOD END (last day of the sample month)
   KSV5 distribution (rent by m2) -> KSU5 assessment (energy by kWh) ->
   KGI2 overhead -> KKS2 variances -> KO88 settlement -> KEU5 assessment
   to CO-PA. Afterwards every cost center and order is zero and the CO-PA
   operating result equals the FI result to the cent.
"""
import datetime

from mm.posting import post_goods_movement

from . import actual, copa, costing, master as com, period_end, planning
from .fi import post_gl_document
from mm import util as mmclock  # noqa: E402

USER = "DEMO"


def sample_period_start(today=None):
    t = today or mmclock.today()
    first = t.replace(day=1)
    return (first - datetime.timedelta(days=1)).replace(day=1)


def _periods_from(start):
    """(year, period) from the sample month up to the current month's year end."""
    today = mmclock.today()
    out, y, p = [], start.year, start.month
    while (y < today.year) or (y == today.year and p <= 12):
        out.append((y, p))
        p += 1
        if p > 12:
            y, p = y + 1, 1
    return out


# ====================================================================== master
def master(conn):
    ce = [
        ("400000", "Consumption raw materials", 1), ("410000", "Scrapping", 1),
        ("233000", "Inventory differences", 1), ("420000", "Direct wages", 1),
        ("430000", "Salaries", 1), ("440000", "Social security", 1),
        ("450000", "Energy", 1), ("460000", "Rent", 1), ("470000", "Depreciation", 1),
        ("475000", "External maintenance services", 1), ("476000", "Office & IT", 1),
        ("477000", "Marketing & advertising", 1), ("478000", "Freight out", 1),
        ("895000", "Factory output production orders", 1),
        ("800000", "Sales revenue domestic", 11), ("800100", "Sales revenue export", 11),
        ("880000", "Sales deductions", 12),
        ("479000", "Bank charges", 1), ("479500", "Audit & legal fees", 1),
        ("615000", "ILA machine hours", 43), ("616000", "ILA labor hours", 43),
        ("617000", "ILA maintenance hours", 43),
        ("650000", "Assessment internal services", 42),
        ("690000", "Assessment to CO-PA", 42),
        ("655000", "Material overhead", 41), ("656000", "Production overhead", 41),
        ("649000", "Settlement to cost center", 21),
        ("649100", "Settlement to CO-PA", 21),
    ]
    for k, t, c in ce:
        com.create_cost_element(conn, k, t, c)
    for g, t, p in [("H1000", "Factory Egypt (standard hierarchy)", ""),
                    ("H1100", "Production", "H1000"),
                    ("H1200", "Production services", "H1000"),
                    ("H1300", "Sales", "H1000"),
                    ("H1400", "Administration", "H1000")]:
        com.create_cc_group(conn, g, t, p)
    from mm import master as mmm
    for k, n, cat, grp, who in [
            ("4100", "Machining", "F", "H1100", "Eng. Ahmed Fathy"),
            ("4120", "Assembly", "F", "H1100", "Eng. Mona Adel"),
            ("4200", "Maintenance", "H", "H1200", "Eng. Karim Samir"),
            ("4210", "Energy & Utilities", "H", "H1200", "Eng. Karim Samir"),
            ("4300", "Quality Control", "Q", "H1200", "Dr. Hala Nabil"),
            ("4400", "Warehouse & Logistics", "L", "H1200", "Mr. Tarek Ali"),
            ("4500", "Sales Samples", "W", "H1300", "Ms. Dina Fouad"),
            ("8100", "Sales & Marketing", "W", "H1300", "Ms. Dina Fouad"),
            ("9100", "Administration", "V", "H1400", "Mr. Omar Hassan"),
            ("9900", "Building & Facilities", "V", "H1400", "Mr. Omar Hassan")]:
        mmm.create_cost_center(conn, k, n, cat, grp, who)
    com.create_activity_type(conn, "MACH", "Machine hours", "H", "615000", 40)
    com.create_activity_type(conn, "LAB", "Labor hours", "H", "616000", 30)
    com.create_activity_type(conn, "MAINT", "Maintenance hours", "H", "617000", 50)
    com.create_skf(conn, "SQM", "Floor space", "M2", fixed=True)
    com.create_skf(conn, "KWH", "Electricity consumption", "KWH", fixed=False)
    com.create_skf(conn, "EMPL", "Employees", "EA", fixed=True)
    com.set_default_aa(conn, "233000", "4400")      # OKB9
    com.set_default_aa(conn, "410000", "4400")
    com.set_default_aa(conn, "479000", "9100")
    for c in [("C1001", "Cairo Home Center", "Cairo", "CAI", "01", "10"),
              ("C1002", "Delta Kitchens Wholesale", "Tanta", "DLT", "02", "10"),
              ("C1003", "Gulf Export Trading", "Jeddah", "EXP", "03", "20")]:
        com.create_customer(conn, *c)
    com.save_cycle(conn, "DIST01", "Rent distribution by floor space", "D", 10, [
        dict(seg=1, ktext="Rent by m2", senders="9900", sender_kstar="460000",
             receivers="4100,4120,4200,4300,4400,8100,9100", tracing="SKF:SQM")])
    com.save_cycle(conn, "ASSESS01", "Energy assessment by kWh", "A", 20, [
        dict(seg=1, ktext="Energy by kWh", senders="4210", kstar="650000",
             receivers="4100,4120,4200,4300,4400,9100", tracing="SKF:KWH")])
    com.save_cycle(conn, "COPA01", "Assessment of cost centers to CO-PA", "P", 90, [
        dict(seg=1, ktext="Sales & marketing", senders="8100,4500", kstar="690000",
             tracing="VV:vv010", vv="vv100"),
        dict(seg=2, ktext="Administration", senders="9100,9900", kstar="690000",
             tracing="VV:vv010", vv="vv110"),
        dict(seg=3, ktext="Production under/over absorption",
             senders="4100,4120,4200,4210,4300,4400", kstar="690000",
             tracing="VV:vv010", vv="vv090")])


def _logistics(conn):
    com.create_work_center(conn, "WC-MACH", "1000", "CNC machining line", "4100", "MACH")
    com.create_work_center(conn, "WC-ASSY", "1000", "Assembly line", "4120", "LAB")
    com.create_bom(conn, "FG-3001", "1000", "1", [("RM-1001", "18"), ("RM-1003", "1.5"),
                                                  ("PK-2001", "1")])
    com.create_bom(conn, "FG-3002", "1000", "1", [("RM-1001", "11"), ("RM-1003", "1"),
                                                  ("PK-2001", "1")])
    com.create_routing(conn, "FG-3001", "1000", "1", [
        ("0010", "WC-MACH", "Cut, bend and drill", "1.2"),
        ("0020", "WC-ASSY", "Assemble and paint", "2.5")])
    com.create_routing(conn, "FG-3002", "1000", "1", [
        ("0010", "WC-MACH", "Cut, bend and drill", "0.8"),
        ("0020", "WC-ASSY", "Assemble and paint", "1.6")])
    com.set_costing_sheet(conn, [
        (10, "Material overhead", "MAT", 500, 0, "4400", "655000", 20),
        (20, "Production overhead", "ACT", 1000, 0, "4300", "656000", 50)])


# ====================================================================== plan
PLAN_COSTS = [  # kostl, cost element, fixed, variable, activity (per month)
    ("4100", "420000", "30000", "0", ""), ("4100", "470000", "60000", "0", ""),
    ("4100", "475000", "0", "6000", "MACH"),
    ("4120", "420000", "45000", "30000", "LAB"), ("4120", "440000", "9062.50", "0", ""),
    ("4120", "470000", "6000", "0", ""),
    ("4200", "420000", "12000", "0", ""), ("4200", "400000", "4000", "0", ""),
    ("4200", "475000", "0", "4000", "MAINT"),
    ("4210", "450000", "20000", "0", ""),
    ("4300", "430000", "15000", "0", ""), ("4400", "430000", "10000", "0", ""),
    ("8100", "430000", "25000", "0", ""), ("8100", "477000", "15000", "0", ""),
    ("8100", "478000", "5000", "0", ""),
    ("9100", "430000", "40000", "0", ""), ("9100", "476000", "10000", "0", ""),
    ("9900", "460000", "30000", "0", ""),
]
SQM = {"4100": "1500", "4120": "1000", "4200": "200", "4300": "150", "4400": "800",
       "8100": "150", "9100": "200"}
KWH_PLAN = {"4100": "6000", "4120": "2000", "4200": "500", "4300": "500", "4400": "500",
            "9100": "500"}
EMPL = {"4100": "12", "4120": "25", "4200": "5", "4300": "4", "4400": "6", "8100": "8",
        "9100": "10"}
SALES_PLAN = [  # customer, product, qty, price, discount %
    ("C1001", "FG-3001", "40", "4200", "0"), ("C1001", "FG-3002", "60", "2600", "0"),
    ("C1002", "FG-3001", "40", "4200", "8"), ("C1002", "FG-3002", "70", "2600", "8"),
    ("C1003", "FG-3001", "20", "4000", "0"), ("C1003", "FG-3002", "30", "2500", "0"),
]


def plan_period(conn, y, p):
    for kostl, kstar, fix, var, lstar in PLAN_COSTS:
        if lstar:
            continue
        planning.plan_costs(conn, y, p, p, kostl, kstar, fix, var, "", False, USER)
    for k, v in SQM.items():
        planning.plan_skf(conn, y, p, p, k, "SQM", v)
        planning.plan_skf(conn, y, p, p, k, "EMPL", EMPL[k])
    for k, v in KWH_PLAN.items():
        planning.plan_skf(conn, y, p, p, k, "KWH", v)
    planning.plan_activity(conn, y, p, p, "4100", "MACH", "250", "320")
    planning.plan_activity(conn, y, p, p, "4120", "LAB", "500", "620")
    planning.plan_activity(conn, y, p, p, "4200", "MAINT", "80", "100")
    for kostl, kstar, fix, var, lstar in PLAN_COSTS:
        if lstar:
            planning.plan_costs(conn, y, p, p, kostl, kstar, fix, var, lstar, False, USER)
    planning.plan_activity_input(conn, y, p, p, "4100", "4200", "MAINT", "50")
    planning.plan_activity_input(conn, y, p, p, "4120", "4200", "MAINT", "30")
    period_end.run_cycle(conn, "DIST01", y, p, "01", user=USER)
    period_end.run_cycle(conn, "ASSESS01", y, p, "01", user=USER)
    planning.kspi(conn, y, p, USER)


def plan_overhead_credit(conn, y, p):
    """Planned overhead absorption on the credit cost centers (from the sales
    & operations plan quantities x overhead per unit of the cost estimate)."""
    from mm.util import rdiv
    from .core import ks, post_co_doc
    conn.execute("DELETE FROM co_item WHERE wrttp='01' AND vrgng='KZPP' AND gjahr=? AND "
                 "perio=?", (y, p))
    sheet = {r["kstar"]: r for r in conn.execute("SELECT * FROM costing_sheet")}
    items = []
    for r in conn.execute("SELECT matnr, SUM(qty) AS q FROM copa_plan_qty WHERE gjahr=? "
                          "AND perio=? GROUP BY matnr", (y, p)).fetchall():
        e = conn.execute("SELECT * FROM cost_estimate WHERE matnr=? AND status='FR' "
                         "ORDER BY id DESC LIMIT 1", (r["matnr"],)).fetchone()
        if not e:
            continue
        for i in conn.execute("SELECT * FROM cost_estimate_item WHERE id=? AND typ='G'",
                              (e["id"],)):
            v = rdiv(i["wert"] * r["q"], e["losgr"])
            f = rdiv(i["wkf"] * r["q"], e["losgr"])
            items.append(dict(objnr=ks(sheet[i["kstar"]]["kostl"]), kstar=i["kstar"],
                              wtg=-v, wkf=-f, sgtxt="Plan overhead %s" % r["matnr"]))
    post_co_doc(conn, "KZPP", "01", y, p, items, "Plan overhead absorption", USER,
                balanced=False)


# ====================================================================== sample
def plan_and_sample(conn):
    failed = []
    start = sample_period_start()
    y, p = start.year, start.month
    d = lambda day: mmclock.day_in_month(y, p, day).isoformat()   # noqa: E731
    eom = (start.replace(day=28) + datetime.timedelta(days=4)).replace(day=1) - \
        datetime.timedelta(days=1)
    _logistics(conn)
    periods = _periods_from(start)
    for (yy, pp) in periods:
        plan_period(conn, yy, pp)
    # standard cost estimates, released on the last day before the sample month
    release_day = (start - datetime.timedelta(days=1)).isoformat()
    for m in ("FG-3001", "FG-3002"):
        eid = costing.cost_estimate(conn, m, "1000", start.isoformat(), "100", USER)
        costing.mark_release(conn, eid, release_day, USER)
    for (yy, pp) in periods:
        for kunnr, matnr, q, pr, disc in SALES_PLAN:
            copa.plan_sales(conn, yy, pp, kunnr, matnr, q, pr, disc, user=USER)
        plan_overhead_credit(conn, yy, pp)
        period_end.run_cycle(conn, "COPA01", yy, pp, "01", user=USER)

    # ------------------------------------------------------------ actual month
    def mm(budat, items, text):
        try:
            return post_goods_movement(conn, {"budat": budat, "bktxt": text}, items, USER)
        except Exception as e:  # keep the demo going, report at the end
            failed.append((budat, text, str(e)))
            return None

    oa = com.create_order(conn, {"auart": "PP01", "matnr": "FG-3001", "werks": "1000",
                                 "lgort": "0003", "gamng": "100", "release": True,
                                 "erdat": d(1)}, USER)
    ob = com.create_order(conn, {"auart": "PP01", "matnr": "FG-3002", "werks": "1000",
                                 "lgort": "0003", "gamng": "160", "release": True,
                                 "erdat": d(1)}, USER)
    oi = com.create_order(conn, {"auart": "ZINT", "ktext": "Trade fair Cairo Kitchen Expo",
                                 "kostl": "8100", "release": True, "erdat": d(1),
                                 "rules": [{"konty": "KS", "receiver": "8100",
                                            "prozs": 100}]}, USER)
    # raw material purchase at a higher price -> material price variance
    from mm import master as mmm
    ebeln = mmm.create_po(conn, {"lifnr": "100003", "bedat": d(1), "items": [
        {"matnr": "RM-1003", "werks": "1000", "lgort": "0001", "menge": "300",
         "netpr": "195.00"}]}, USER)
    mm(d(2), [{"bwart": "101", "ebeln": ebeln, "ebelp": 10, "qty": "300",
               "lgpla": "C-01-02"}], "Paint delivery")
    mm(d(3), [{"bwart": "261", "matnr": "RM-1001", "werks": "1000", "lgort": "0001",
               "qty": "1830", "aufnr": oa},
              {"bwart": "261", "matnr": "RM-1003", "werks": "1000", "lgort": "0001",
               "qty": "150", "aufnr": oa},
              {"bwart": "261", "matnr": "PK-2001", "werks": "1000", "lgort": "0001",
               "qty": "100", "aufnr": oa}], "Staging order %s" % oa)
    mm(d(4), [{"bwart": "261", "matnr": "RM-1001", "werks": "1000", "lgort": "0001",
               "qty": "1760", "aufnr": ob},
              {"bwart": "261", "matnr": "RM-1003", "werks": "1000", "lgort": "0001",
               "qty": "165", "aufnr": ob},
              {"bwart": "261", "matnr": "PK-2001", "werks": "1000", "lgort": "0001",
               "qty": "160", "aufnr": ob}], "Staging order %s" % ob)
    actual.confirm(conn, oa, "0010", "100", "125", d(12), USER)
    actual.confirm(conn, oa, "0020", "100", "245", d(14), USER)
    actual.confirm(conn, ob, "0010", "158", "130", d(18), USER)
    actual.confirm(conn, ob, "0020", "158", "262", d(20), USER)
    actual.allocate_activity(conn, d(25), "4200", "MAINT", "52", {"kostl": "4100"},
                             "Machine overhaul", USER)
    actual.allocate_activity(conn, d(25), "4200", "MAINT", "28", {"kostl": "4120"},
                             "Conveyor repair", USER)
    mm(d(15), [{"bwart": "101", "aufnr": oa, "qty": "100", "lgpla": "F-06"}],
       "GR order %s" % oa)
    mm(d(21), [{"bwart": "101", "aufnr": ob, "qty": "158", "lgpla": "F-07"}],
       "GR order %s" % ob)
    com.set_order_status(conn, ob, "TECO")
    mm(d(9), [{"bwart": "201", "matnr": "SP-4001", "werks": "1000", "lgort": "0004",
               "qty": "10", "kostl": "4200"},
              {"bwart": "201", "matnr": "SP-4003", "werks": "1000", "lgort": "0004",
               "qty": "40", "kostl": "4200"}], "Spare parts maintenance")
    post_gl_document(conn, {"budat": eom.isoformat(), "bktxt": "Payroll"}, [
        dict(hkont="420000", debit="31200", kostl="4100"),
        dict(hkont="420000", debit="76500", kostl="4120"),
        dict(hkont="440000", debit="9100", kostl="4120"),
        dict(hkont="420000", debit="12400", kostl="4200"),
        dict(hkont="430000", debit="15000", kostl="4300"),
        dict(hkont="430000", debit="10500", kostl="4400"),
        dict(hkont="430000", debit="26000", kostl="8100"),
        dict(hkont="430000", debit="41000", kostl="9100"),
        dict(hkont="176000", credit="221700")], USER)
    for k, v in SQM.items():
        actual.post_skf(conn, d(28), k, "SQM", v)
    for k, v in {"4100": "6300", "4120": "2100", "4200": "450", "4300": "500",
                 "4400": "550", "9100": "600"}.items():
        actual.post_skf(conn, d(28), k, "KWH", v)
    sales = [("C1001", d(16), [("FG-3001", "35", "4200", "0"), ("FG-3002", "62", "2600", "0")]),
             ("C1002", d(22), [("FG-3001", "45", "4150", "8"), ("FG-3002", "66", "2600", "10")]),
             ("C1003", d(27), [("FG-3001", "18", "4000", "0"), ("FG-3002", "34", "2500", "0")])]
    for kunnr, day, items in sales:
        copa.create_billing(conn, {"kunnr": kunnr, "fkdat": day, "items": [
            dict(matnr=m, qty=q, price=pr, disc=ds, werks="1000", lgort="0003")
            for m, q, pr, ds in items]}, USER)
    # FI postings of the month that create costs (vendor invoices, depreciation...)
    from fi import seed as fi_seed
    from pur import seed as pur_seed
    pur_seed.sample(conn, y, p)
    from md import seed as md_seed
    md_seed.sample(conn, y, p)
    fi_seed.sample_before_closing(conn, y, p, oi, ebeln)
    # ------------------------------------------------------------ period end
    period_end.run_cycle(conn, "DIST01", y, p, "04", user=USER)
    period_end.run_cycle(conn, "ASSESS01", y, p, "04", user=USER)
    period_end.overhead(conn, y, p, user=USER)
    period_end.variances(conn, y, p, user=USER)
    period_end.settle(conn, y, p, user=USER)
    period_end.run_cycle(conn, "COPA01", y, p, "04", user=USER)
    conn.execute("INSERT OR REPLACE INTO settings VALUES ('co_sample', ?)",
                 ("%04d-%02d" % (y, p),))
    fi_seed.sample_after_closing(conn, y, p)
    return failed
