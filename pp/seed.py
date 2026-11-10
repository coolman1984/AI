"""Production demo - one complete PP story in the current month.

master(conn): new product FG-3003 (tall pantry unit) with a 3-level structure
  FG-3003  = SF-3101 carcass (in-house, op. 20 powder coating EXTERNAL at vendor)
           + 2 x SF-3102 glass door (SUBCONTRACTING: we provide glass + steel)
           + 2 x TR-5001 handle (trading good, backflushed) + carton (backflushed)
  work center capacity, routings with control keys PP01/PP02/PP03, production
  versions, cost estimates CK11N + CK24 (external processing and subcontracting
  fee included), product group PG-CAB, forecast-based planning for spare parts.

sample(conn):
  1 MC81 + MC75  rough-cut plan for PG-CAB -> PIRs (strategy 40)
  2 MP38         forecast for spare parts (safety stock / reorder point)
  3 MD01         MRP: planned orders (FG, SF), subcontracting, PRs, exceptions
  4 glass PO + GR, CO40 subcontracting PO, ME2O 541, GR 101 with 543 consumption
  5 CO40 carcass order: release -> external PR -> PO, CO27 picking, CO11N,
    service GR on the order, order GR
  6 CO40 pantry order: picking, CO11N with backflush + scrap, PP03 automatic GR, TECO
  7 second pantry order released with MISSING PARTS, partly confirmed -> WIP
  8 ZP03 rework of 3 defective cabinets (blocked stock), settled to QC cost center
  9 ZREF refurbishment of 10 bearings, settled to the material (MAP up)
 10 MB21 reservation for maintenance + partial issue
 11 period end: overhead, WIP, variances, settlement
"""
import calendar
import datetime

from mm.db import transaction
from mm.posting import post_goods_movement, propose_bin
from mm import util as mmclock  # noqa: E402

USER = "PLANNER"


def _month(offset=0):
    t = mmclock.today().replace(day=1)
    y, m = t.year, t.month + offset
    while m > 12:
        y, m = y + 1, m - 12
    return y, m


def master(conn):
    from co import master as com, costing
    from md import material as mat, partner as bp
    from md.config import MATERIAL_GROUPS
    from mm import master as mmm
    from pur.sourcing import save_info_record
    from . import master as ppm, planning
    MATERIAL_GROUPS.setdefault("GLASS", "Glass")
    y, m = _month()
    d1 = datetime.date(y, m, 1).isoformat()
    if not conn.execute("SELECT 1 FROM cost_element WHERE kstar='417000'").fetchone():
        com.create_cost_element(conn, "417000", "Subcontracting & external processing", 1)
    if not conn.execute("SELECT 1 FROM sloc WHERE werks='1000' AND lgort='0009'").fetchone():
        mmm.create_sloc(conn, "1000", "0009", "Stock provided to subcontractors")
    v_glass = bp.create_vendor(conn, dict(ktokk="0001", name="Sinai Glass Industries", city="Suez",
                                          stcd1="612-450-117", bankn="000091234501", akont="160000",
                                          zterm="NT30", ekgrp="001", plifz="10"), "MIGRATION")["lifnr"]
    v_coat = bp.create_vendor(conn, dict(ktokk="0002", name="Cairo Powder Coating Co.", city="Cairo",
                                         stcd1="612-450-226", bankn="000091234502", akont="160000",
                                         zterm="NT30", ekgrp="003", plifz="3"), "MIGRATION")["lifnr"]
    v_sub = bp.create_vendor(conn, dict(ktokk="0002", name="Alex Glass Works (subcontractor)",
                                        city="Alexandria", stcd1="612-450-335", bankn="000091234503",
                                        akont="160000", zterm="NT30", ekgrp="001", plifz="5"),
                             "MIGRATION")["lifnr"]
    mat.create_material(conn, dict(matnr="RM-1005", mtart="ROH", maktx="Tempered glass 4mm 40x60",
                                   meins="PC", matkl="GLASS", plants=[dict(
                                       werks="1000", price="85", dismm="VB", minbe="100", eisbe="40",
                                       mabst="400", disls="HB", plifz="10", lgfsb="0001",
                                       dispo="001")]), "MIGRATION")
    mat.create_material(conn, dict(matnr="SF-3101", mtart="HALB", maktx="Pantry carcass 60x200 coated",
                                   meins="PC", matkl="CABINET", spart="10", plants=[dict(
                                       werks="1000", vprsv="S", price="1500", dismm="PD", disls="EX",
                                       beskz="E", dzeit="3", dispo="002", lgfsb="0002", lgpro="0002",
                                       prctr="PC1000")]), "MIGRATION")
    mat.create_material(conn, dict(matnr="SF-3102", mtart="HALB", maktx="Glass door panel framed",
                                   meins="PC", matkl="CABINET", spart="10", plants=[dict(
                                       werks="1000", vprsv="S", price="400", dismm="PD", disls="EX",
                                       beskz="F", plifz="5", dispo="002", lgfsb="0002",
                                       prctr="PC1000")]), "MIGRATION")
    mat.create_material(conn, dict(matnr="FG-3003", mtart="FERT", maktx="Tall pantry unit 60cm",
                                   meins="PC", matkl="CABINET", spart="10", plants=[dict(
                                       werks="1000", vprsv="S", price="5200", dismm="PD", disls="EX",
                                       beskz="E", dzeit="2", dispo="002", lgfsb="0003", lgpro="0002",
                                       prctr="PC1000")],
                                   sales=[dict(vtweg="10", kbetr="7900"),
                                          dict(vtweg="20", kbetr="7500", taxm1="0")]), "MIGRATION")
    conn.execute("UPDATE material_plant SET sobsl='30' WHERE matnr='SF-3102'")
    conn.execute("UPDATE material_plant SET strgr='40', dismm='PD', disls='EX', lgfsb='0003' WHERE "
                 "matnr IN ('FG-3001','FG-3002','FG-3003')")
    conn.execute("UPDATE material_plant SET dismm='VV', prmod='G', lgrad=95 WHERE matnr LIKE 'SP-%'")
    save_info_record(conn, v_glass, "RM-1005", "85", aplfz=10)
    save_info_record(conn, v_sub, "SF-3102", "55", aplfz=5)
    # work centers: capacity + new repair shop
    for arbpl, ktext, kostl, lstar, kap, sh, ut in (
            ("WC-MACH", "CNC machining line", "4100", "MACH", "8", 2, 85),
            ("WC-ASSY", "Assembly line", "4120", "LAB", "8", 1, 90),
            ("WC-REPR", "Repair & refurbishment shop", "4200", "MAINT", "8", 1, 80)):
        ppm.save_work_center(conn, dict(arbpl=arbpl, ktext=ktext, kostl=kostl, lstar=lstar, kapaz=kap,
                                        shifts=sh, ngrad=ut, veran="Production"), "MIGRATION",
                             "CR02" if arbpl != "WC-REPR" else "CR01")
    ppm.save_bom(conn, "SF-3101", "1000", "1", [
        dict(idnrk="RM-1001", menge="24", ausch="5", lgort="0001"),
        dict(idnrk="RM-1003", menge="2", lgort="0001")], "MIGRATION")
    ppm.save_bom(conn, "SF-3102", "1000", "1", [
        dict(idnrk="RM-1005", menge="1"), dict(idnrk="RM-1001", menge="1.5")], "MIGRATION")
    ppm.save_bom(conn, "FG-3003", "1000", "1", [
        dict(idnrk="SF-3101", menge="1", lgort="0002"),
        dict(idnrk="SF-3102", menge="2", lgort="0002"),
        dict(idnrk="TR-5001", menge="2", lgort="0004", rgekz=1),
        dict(idnrk="PK-2001", menge="1", lgort="0001", rgekz=1)], "MIGRATION")
    ppm.save_routing(conn, "SF-3101", "1000", "1", [
        dict(vornr="0010", arbpl="WC-MACH", ltxa1="Cut, punch and bend carcass", vgw="1.6",
             vgw_setup="1"),
        dict(vornr="0020", steus="PP02", ltxa1="Powder coating RAL9010", lifnr=v_coat, preis="140",
             plifz=3, ekgrp="003")], "MIGRATION")
    ppm.save_routing(conn, "FG-3003", "1000", "1", [
        dict(vornr="0010", arbpl="WC-ASSY", ltxa1="Assemble carcass, doors and handles", vgw="2.2",
             vgw_setup="0.5"),
        dict(vornr="0020", arbpl="WC-ASSY", steus="PP03", ltxa1="Final inspection and packing",
             vgw="0.4")], "MIGRATION")
    end = datetime.date(y + 1, 12, 31).isoformat()
    d1 = (datetime.date(y, m, 1) - datetime.timedelta(days=40)).isoformat()
    ppm.save_version(conn, "FG-3003", "1000", "0001", "Assembly line 1", d1, end, "1", "500")
    ppm.save_version(conn, "SF-3101", "1000", "0001", "CNC + external coating", d1, end)
    for matnr in ("SF-3102", "SF-3101", "FG-3003"):
        k = datetime.date(y, m, 1).isoformat()
        eid = costing.cost_estimate(conn, matnr, "1000", k, "100", "MIGRATION")
        costing.mark_release(conn, eid, k, "MIGRATION")
    planning.save_group(conn, "PG-CAB", "Kitchen cabinets (product group)", [
        dict(matnr="FG-3001", factor=40), dict(matnr="FG-3002", factor=35),
        dict(matnr="FG-3003", factor=25)])
    return dict(glass=v_glass, coat=v_coat, sub=v_sub)


def sample(conn, vendors):
    from co import period_end
    from pur import po as purpo, pr as purpr
    from . import order, planning, service, subcon
    y, m = _month()
    d = lambda day: mmclock.day_in_month(y, m, day, cap=mmclock.today()).isoformat()
    months = planning._months("%04d-%02d" % (y, m), 3)
    # 1 SOP -> demand management
    planning.sop_plan(conn, "PG-CAB", [dict(month=months[0], sales="200"),
                                       dict(month=months[1], sales="210"),
                                       dict(month=months[2], sales="230")], target_days=10, user=USER)
    planning.transfer_to_demand(conn, "PG-CAB", USER)
    # 2 forecast for spare parts (service level 95 %)
    service.mass_forecast(conn, "1000", USER, apply=True, today=d(1))
    # 3 MRP
    planning.mrp_run(conn, USER, today=d(1))
    pl = {p["matnr"]: p for p in reversed(planning.planned_orders(conn))}
    # 4 glass + subcontracting
    e_glass = purpo.create_po(conn, {"lifnr": vendors["glass"], "bedat": d(1), "items": [
        {"matnr": "RM-1005", "menge": "300", "netpr": "85", "lgort": "0001", "eindt": d(2)}]}, USER)
    purpo.release_all(conn, e_glass, USER)
    pb = propose_bin(conn, "RM-1005", "1000", "0001")
    post_goods_movement(conn, {"budat": d(2), "xblnr": "DN-G1"}, [
        {"bwart": "101", "ebeln": e_glass, "ebelp": 10, "qty": "300", "lgpla": pb["lgpla"]}], USER)
    sc_plan = min((p for p in planning.planned_orders(conn, "SF-3102")), key=lambda p: p["pedtr"])
    sc = planning.convert(conn, sc_plan["plnum"], USER)["number"]
    subcon.provide(conn, sc, d(3), USER)
    post_goods_movement(conn, {"budat": d(5), "xblnr": "AGW-117"}, [
        {"bwart": "101", "ebeln": sc, "ebelp": 10,
         "qty": "%.3f" % (conn.execute("SELECT menge FROM po_item WHERE ebeln=?", (sc,))
                          .fetchone()[0] / 1000.0)}], USER)
    # 5 carcass order with external operation
    car_plan = min(planning.planned_orders(conn, "SF-3101"), key=lambda p: p["pedtr"])
    a_car = planning.convert(conn, car_plan["plnum"], USER, today=d(2))["number"]
    order.release(conn, a_car, USER, d(2))
    ext_pr = conn.execute("SELECT banfn FROM pp_oper WHERE aufnr=? AND steus='PP02'",
                          (a_car,)).fetchone()["banfn"]
    if conn.execute("SELECT statu FROM pr_item WHERE banfn=?", (ext_pr,)).fetchone()[0] == "B":
        purpr.release_pr(conn, ext_pr, "R1", USER)
    e_coat = purpr.convert_to_po(conn, USER, [ext_pr], d(2))["pos"][0]["ebeln"]
    purpo.release_all(conn, e_coat, USER)
    order.post_picking(conn, [dict(rsnum=r["rsnum"], rspos=r["rspos"])
                              for r in order.picking_list(conn) if r["aufnr"] == a_car], d(2), USER)
    q_car = conn.execute("SELECT gamng FROM orders WHERE aufnr=?", (a_car,)).fetchone()[0]
    order.confirm(conn, a_car, "0010", "%.3f" % (q_car / 1000.0), budat=d(3), user=USER)
    post_goods_movement(conn, {"budat": d(5), "xblnr": "CPC-889"}, [
        {"bwart": "101", "ebeln": e_coat, "ebelp": 10, "qty": "%.3f" % (q_car / 1000.0)}], USER)
    post_goods_movement(conn, {"budat": d(5), "bktxt": "GR carcasses"}, [
        {"bwart": "101", "aufnr": a_car, "qty": "%.3f" % (q_car / 1000.0), "lgort": "0002"}], USER)
    # 6 pantry order: picking, confirmation with scrap + backflush, auto GR, TECO
    fg_plan = min(planning.planned_orders(conn, "FG-3003"), key=lambda p: p["pedtr"])
    a_fg = planning.convert(conn, fg_plan["plnum"], USER, today=d(5))["number"]
    order.release(conn, a_fg, USER, d(5))
    order.post_picking(conn, [dict(rsnum=r["rsnum"], rspos=r["rspos"])
                              for r in order.picking_list(conn) if r["aufnr"] == a_fg], d(5), USER)
    q_fg = conn.execute("SELECT gamng FROM orders WHERE aufnr=?", (a_fg,)).fetchone()[0]
    order.confirm(conn, a_fg, "0010", "%.3f" % ((q_fg - 2000) / 1000.0), "2", budat=d(6), user=USER)
    order.confirm(conn, a_fg, "0020", "%.3f" % ((q_fg - 2000) / 1000.0), budat=d(7), final=True,
                  user=USER)
    order.teco(conn, a_fg, USER)
    # 7 second pantry order: missing parts, partial confirmation -> WIP
    a_fg2 = order.create(conn, {"auart": "PP01", "matnr": "FG-3003", "gamng": "30", "gstrp": d(6),
                                "lgort": "0003"}, USER)
    order.release(conn, a_fg2, USER, d(6))
    order.confirm(conn, a_fg2, "0010", "10", budat=d(7), user=USER)
    # 8 rework order
    b = conn.execute("SELECT lgpla FROM quant WHERE matnr='FG-3001' AND werks='1000' AND lgort='0003' AND insmk='U' "
                     "AND qty>=3000 ORDER BY wdatu LIMIT 1").fetchone()
    post_goods_movement(conn, {"budat": d(3), "bktxt": "Hinge defect - block"}, [
        {"bwart": "344", "matnr": "FG-3001", "werks": "1000", "lgort": "0003", "lgpla": b["lgpla"],
         "qty": "3"}], USER)
    a_rw = order.create(conn, {"auart": "ZP03", "matnr": "FG-3001", "gamng": "3", "gstrp": d(4),
                               "lgort": "0003", "comp_lgort": "0003", "kostl": "4300",
                               "ops": [dict(arbpl="WC-ASSY", ltxa1="Rework hinge alignment", vgw="1.5")]},
                        USER)
    order.release(conn, a_rw, USER, d(4))
    order.post_picking(conn, [dict(rsnum=a_rw, rspos=1, lgpla=b["lgpla"])], d(4), USER)
    order.confirm(conn, a_rw, "0010", "3", budat=d(4), user=USER)
    post_goods_movement(conn, {"budat": d(4), "bktxt": "Rework done"}, [
        {"bwart": "101", "aufnr": a_rw, "qty": "3", "lgort": "0003", "lgpla": b["lgpla"]}], USER)
    # 9 refurbishment order
    bb = conn.execute("SELECT lgpla FROM quant WHERE matnr='SP-4001' AND werks='1000' AND lgort='0004' AND insmk='U' "
                      "AND qty>=10000 ORDER BY wdatu LIMIT 1").fetchone()
    post_goods_movement(conn, {"budat": d(3), "bktxt": "Returned bearings (worn)"}, [
        {"bwart": "344", "matnr": "SP-4001", "werks": "1000", "lgort": "0004", "lgpla": bb["lgpla"],
         "qty": "10"}], USER)
    a_ref = order.create(conn, {"auart": "ZREF", "matnr": "SP-4001", "gamng": "10", "gstrp": d(4),
                                "lgort": "0004", "comp_lgort": "0004",
                                "ops": [dict(arbpl="WC-REPR", ltxa1="Clean, regrease and test", vgw="4")],
                                "comps": [dict(matnr="SP-4003", menge="2", lgort="0004")]}, USER)
    order.release(conn, a_ref, USER, d(4))
    order.post_picking(conn, [dict(rsnum=a_ref, rspos=1, lgpla=bb["lgpla"]),
                              dict(rsnum=a_ref, rspos=2)], d(4), USER)
    order.confirm(conn, a_ref, "0010", "10", budat=d(5), user=USER)
    post_goods_movement(conn, {"budat": d(5), "bktxt": "Refurbished bearings"}, [
        {"bwart": "101", "aufnr": a_ref, "qty": "10", "lgort": "0004", "lgpla": bb["lgpla"]}], USER)
    # 10 reservation for maintenance
    rs = service.create_reservation(conn, "4200", [dict(matnr="SP-4003", menge="20", lgort="0004")],
                                    d(6), USER)
    service.issue_reservation(conn, rs, d(6), USER, {"1": "15"})
    # 11 period end of the current month
    period_end.overhead(conn, y, m, user=USER)
    service.wip(conn, y, m, USER)
    period_end.variances(conn, y, m, user=USER)
    period_end.settle(conn, y, m, user=USER)
    with transaction(conn):
        conn.execute("INSERT OR REPLACE INTO settings VALUES ('pp_sample', ?)", ("%04d-%02d" % (y, m),))
    return dict(carcass=a_car, pantry=a_fg, pantry2=a_fg2, rework=a_rw, refurb=a_ref, subcon=sc,
                coating=e_coat, reservation=rs)
