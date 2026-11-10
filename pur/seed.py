"""Procurement demo (inside the sample month, integrated with MM / FI / CO).

Master data: purchasing groups per material, MRP parameters, new vendors,
info records with delivery times and freight, source list + quota 60/40 for
steel, quantity contract for granules.

Sample month:
 d5  MD01 MRP run -> requisitions for materials below reorder point
 d5  ME51N maintenance requisition: bearings (stock) + gearbox overhaul
     (text item, cost center 4200) -> needs release R1
 d6  ME54N release requisitions;  RFQ ME41 copper wire to 3 vendors
 d7  ME51N production requisition steel 12,000 kg -> release
 d8  ME47 quotations, ME49 comparison, award cheapest -> PO
 d8  ME59N automatic POs (source determination: info record, quota, fixed vendor)
 d9  ME21N call-off from the granules contract
 d7-d10  ME29N releases (R1 purchasing manager, R2 finance director)
 d12-d24 MIGO goods receipts (some late, one partial + delivery completed),
     goods receipt for the service -> cost center 4200 (CO)
 d18 return to vendor (122) - quality
 d16-d26 MIRO invoices incl. planned freight and price differences
"""
import datetime

from mm import master as mmm
from mm.posting import post_goods_movement

from . import mrp, po, pr, sourcing

from mm import util as mmclock  # noqa: E402

USER = "DEMO"


def master(conn):
    # buyer closed partially delivered history orders (ME22N 'delivery completed')
    conn.execute("UPDATE po_item SET elikz=1 WHERE wemng>0 AND wemng<menge")
    conn.execute("UPDATE material_plant SET dismm='ND' WHERE matnr LIKE 'FG-%'")
    conn.execute("UPDATE material_plant SET ekgrp='002', plifz=5 WHERE matnr LIKE 'SP-%'")
    conn.execute("UPDATE material_plant SET ekgrp='001', plifz=10 WHERE matnr LIKE 'RM-%' OR "
                 "matnr LIKE 'PK-%'")
    conn.execute("UPDATE material_plant SET mabst=minbe*3 WHERE mabst=0")
    for v in [("100007", "Ezz Flat Steel", "Sadat City", "Z210"),
              ("100008", "Alex Cables & Wires", "Alexandria", "NT30"),
              ("100009", "Cairo Metals Trading", "Cairo", "NT30")]:
        mmm.create_vendor(conn, v[0], v[1], v[2], zterm=v[3])
    # info records (history POs already created some; set delivery times)
    sourcing.save_info_record(conn, "100001", "RM-1001", "49.50", 1, 0, 0, 7)
    sourcing.save_info_record(conn, "100007", "RM-1001", "48.90", 1, 0, "3000", 10,
                              idnlf="EZZ-CR2")
    sourcing.save_info_record(conn, "100005", "SP-4002", "58.00", 1, 0, 0, 5)
    sourcing.save_info_record(conn, "100005", "SP-4001", "88.00", 1, 0, 0, 7)
    sourcing.save_info_record(conn, "100003", "RM-1003", "196.00", 1, "1.5", 0, 6)
    sourcing.save_source_list(conn, "RM-1001", "1000", [
        {"lifnr": "100001"}, {"lifnr": "100007"}])
    sourcing.save_quota(conn, "RM-1001", "1000", [{"lifnr": "100001", "quote": 60},
                                                  {"lifnr": "100007", "quote": 40}])
    conn.execute("UPDATE quota SET qubmg=20000000 WHERE matnr='RM-1001' AND lifnr='100001'")


def sample(conn, y, p):
    d = lambda day: mmclock.day_in_month(y, p, day).isoformat()   # noqa: E731
    start = datetime.date(y, 1, 1).isoformat()
    konnr = sourcing.create_contract(conn, {
        "lifnr": "100002", "bsart": "MK", "kdatb": start, "kdate": "%s-12-31" % y,
        "items": [{"matnr": "RM-1002", "ktmng": "20000", "netpr": "63.00"}]}, USER)
    sourcing.save_source_list(conn, "RM-1002", "1000", [{"lifnr": "100002",
                                                         "konnr": konnr}])
    # ------------------------------------------------------------ requirements
    mrp.run(conn, "1000", d(5), USER)
    maint = pr.create_pr(conn, [
        {"matnr": "SP-4001", "menge": "40", "lgort": "0004", "lfdat": d(14),
         "afnam": "Eng. Karim Samir"},
        {"txz01": "Gearbox overhaul CNC line", "matkl": "SERVICE", "meins": "AU",
         "menge": "1", "knttp": "K", "kostl": "4200", "sakto": "475000",
         "preis": "28000", "lfdat": d(15), "ekgrp": "003", "flief": "200003",
         "afnam": "Eng. Karim Samir"}], USER, badat=d(5))
    for b in {r["banfn"] for r in pr.pr_list(conn, ["B"])}:
        pr.release_pr(conn, b, "R1", USER)
    steel = pr.create_pr(conn, [{"matnr": "RM-1001", "menge": "12000", "lgort": "0001",
                                 "lfdat": d(18), "afnam": "Production planning"}],
                         USER, badat=d(7))
    pr.release_pr(conn, steel["banfn"], "R1", USER)
    # ------------------------------------------------------------ RFQ copper wire
    r = sourcing.create_rfq(conn, {"matnr": "RM-1004", "menge": "300", "lfdat": d(16),
                                   "angdt": d(8), "vendors": ["100006", "100008",
                                                              "100009"]}, USER)
    for anfnr, price, lead in zip(r["rfqs"], ("560.00", "548.00", "552.00"), (5, 7, 9)):
        sourcing.enter_quotation(conn, anfnr, price, lead, d(8))
    cmp = sourcing.price_comparison(conn, r["submi"])
    copper_po = sourcing.award(conn, cmp["items"][0]["anfnr"], USER, d(9))
    # ------------------------------------------------------------ POs from requisitions
    pr.convert_to_po(conn, USER, bedat=d(8))
    call_off = po.create_po(conn, {"lifnr": "100002", "bedat": d(9), "ekgrp": "001",
                                   "items": [{"matnr": "RM-1002", "menge": "2000",
                                              "lgort": "0001", "konnr": konnr,
                                              "ktpnr": 10}]}, USER)
    # releases in the order of the strategy
    for h in conn.execute("SELECT ebeln, frgst FROM po_header WHERE frgke='B' AND bedat>=?",
                          (d(1),)).fetchall():
        for code in h["frgst"].split(","):
            po.release_po(conn, h["ebeln"], code, USER)
    # ------------------------------------------------------------ goods receipts
    def gr(day, ebeln, ebelp, qty, lgpla="", lgort=""):
        return post_goods_movement(conn, {"budat": d(day), "xblnr": "DN-%s" % ebeln[-3:]},
                                   [{"bwart": "101", "ebeln": ebeln, "ebelp": ebelp,
                                     "qty": qty, "lgpla": lgpla, "lgort": lgort}], USER)

    def po_of(matnr=None, txt=None):
        sql = "SELECT i.ebeln, i.ebelp, i.menge FROM po_item i JOIN po_header h USING (ebeln) " \
              "WHERE h.bedat>=? AND i.banfn IS NOT NULL AND "
        q = sql + ("i.matnr=?" if matnr else "i.txz01=?")
        return conn.execute(q + " ORDER BY i.ebeln DESC", (d(1), matnr or txt)).fetchone()
    paint = po_of("RM-1003")
    if paint:
        gr(12, paint["ebeln"], paint["ebelp"], str(paint["menge"] / 1000.0), "C-01-03",
           "0001")
    belts = po_of("SP-4002")
    if belts:
        gr(13, belts["ebeln"], belts["ebelp"], str(belts["menge"] / 1000.0), "S-02", "0004")
    bear = po_of("SP-4001")
    gr(14, bear["ebeln"], bear["ebelp"], "40", "S-04")
    svc = po_of(txt="Gearbox overhaul CNC line")
    gr(15, svc["ebeln"], svc["ebelp"], "1")
    gr(16, copper_po, 10, "290", "C-02-02", "0001")
    po.change_po(conn, copper_po, 10, USER, elikz=True)
    post_goods_movement(conn, {"budat": d(18), "bktxt": "Defective coils"}, [
        {"bwart": "122", "ebeln": copper_po, "ebelp": 10, "qty": "10", "lgort": "0001",
         "lgpla": "C-02-02", "sgtxt": "Insulation damaged"}], USER)
    st = po_of("RM-1001")
    gr(19, st["ebeln"], st["ebelp"], "8000", "A-03-02")
    gr(24, st["ebeln"], st["ebelp"], "4000", "A-03-03")
    gr(20, call_off, 10, "2000", "B-03-01")
    # ------------------------------------------------------------ invoices (MIRO)
    from fi import ap

    def miro(day, ebeln, items, ref):
        return ap.miro(conn, {"ebeln": ebeln, "bldat": d(day), "budat": d(day),
                              "xblnr": ref, "mwskz": "V1"}, items, USER)
    if paint:
        miro(16, paint["ebeln"], [{"ebelp": paint["ebelp"],
                                   "qty": str(paint["menge"] / 1000.0)}], "PP-9077")
    if belts:
        miro(17, belts["ebeln"], [{"ebelp": belts["ebelp"],
                                   "qty": str(belts["menge"] / 1000.0)}], "PB-3321")
    miro(17, bear["ebeln"], [{"ebelp": bear["ebelp"], "qty": "40"}], "PB-3322")
    miro(20, copper_po, [{"ebelp": 10, "qty": "280", "amount": "154840"}], "AC-7781")
    miro(26, st["ebeln"], [{"ebelp": st["ebelp"], "qty": "12000"}], "EZZ-1190")
    miro(22, call_off, [{"ebelp": 10, "qty": "2000"}], "NP-5520")
    miro(25, svc["ebeln"], [{"ebelp": svc["ebelp"], "qty": "1", "amount": "28500"}],
         "DFS-902")
