"""Sales demo - one complete order-to-cash story in the current month.

master(conn): revenue cost elements, sales views for spare parts, condition
  records (PR00 price lists with scales, customer-specific price, K007 customer
  discount, K004 material discount, ZLAB labour rate), sales deal (ZDEA),
  material exclusion, customer-material number.

sample(conn):
  1  VC01N visit -> VA11 inquiry -> VA21 quotation (70 %) -> VA01 order with reference
  2  second order of the same customer -> CREDIT BLOCK -> VKM1 release by the credit manager
  3  order with partial confirmation (backorder from the open production order)
  4  rush order RO (delivery created at once), free-of-charge sample FD
  5  wholesale order: price scale + customer discount + promotion
  6  VL01N / picking / post goods issue (601), equipment for serialised products
  7  VF01 invoices + e-invoices, VF11 cancellation and re-billing
  8  returns RE -> returns delivery 651 into blocked stock -> credit RE -> scrap
  9  credit memo request (billing block 08, released by a second person) -> G2,
     debit memo request -> L2
 10  service: warranty repair (costs to CO-PA), paid repair billed with DP90,
     warranty replacement ZWR
 11  incoming payment of the first invoice
"""
import calendar
import datetime

from mm.db import transaction
from mm.posting import post_goods_movement
from mm import util as mmclock  # noqa: E402

USER = "SALES01"


def _ym():
    t = mmclock.today()
    return t.year, t.month


def master(conn):
    from co import master as com
    from . import pricing as pr, service as sv
    y, m = _ym()
    d1 = datetime.date(y, m, 1)
    start = (d1 - datetime.timedelta(days=60)).isoformat()
    for k, t in (("805000", "Freight revenue"), ("810000", "Service revenue")):
        if not conn.execute("SELECT 1 FROM cost_element WHERE kstar=?", (k,)).fetchone():
            com.create_cost_element(conn, k, t, 11)
    with transaction(conn):
        for matnr, price in (("SP-4001", 14000), ("SP-4002", 11000), ("SP-4003", 15000)):
            conn.execute("INSERT OR IGNORE INTO md_mvke (matnr,vkorg,vtweg,dwerk,ktgrm,mtpos,taxm1,kbetr) VALUES "
                         "(?,?,?,?,?,?,?,?)", (matnr, "1000", "10", "1000", "01", "NORM", "1", price))
            conn.execute("UPDATE material SET vpsta=? WHERE matnr=?", ("KVEDLSQBG", matnr))
    for r in conn.execute("SELECT matnr, MAX(kbetr) k FROM md_mvke WHERE vtweg='10' AND kbetr>0 GROUP BY matnr"
                          ).fetchall():
        scales = [dict(**{"from": "20", "kbetr": "4150"}), dict(**{"from": "50", "kbetr": "4050"})] \
            if r["matnr"] == "FG-3001" else []
        pr.save_condition(conn, "PR00", "A304", dict(matnr=r["matnr"], kbetr=r["k"] / 100.0, datab=start,
                                                     scales=scales), "MIGRATION")
    pr.save_condition(conn, "PR00", "A305", dict(kunnr="C1004", matnr="FG-3003", kbetr="7600", datab=start),
                      "MIGRATION")
    pr.save_condition(conn, "K007", "A307", dict(kunnr="C1002", kbetr="5", datab=start), "MIGRATION")
    pr.save_condition(conn, "K004", "A304", dict(matnr="TR-5001", kbetr="2", datab=start), "MIGRATION")
    pr.save_condition(conn, "ZLAB", "A304", dict(kbetr="350", datab=start), "MIGRATION")
    last = calendar.monthrange(y, m)[1]
    sv.save_deal(conn, dict(knuma="WINTER%d" % y, botext="Winter promotion wall cabinets",
                            datab=d1.isoformat(), datbi=datetime.date(y, m, last).isoformat(), budget="20000",
                            materials=[dict(matnr="FG-3002", pct="3")]), "MIGRATION")
    sv.save_listing(conn, "C1003", "FG-3003", "B", start)
    sv.save_custmat(conn, "C1004", "FG-3003", "RSH-PANTRY-60", "Pantry unit (hotel rooms)")


def sample(conn):
    from fi.ap import pay
    from . import billing as bl, delivery as dl, order as so, service as sv
    y, m = _ym()
    d = lambda day: mmclock.day_in_month(y, m, day, cap=mmclock.today()).isoformat()
    # 1 pre-sales
    sv.save_activity(conn, dict(kunnr="C1004", ktaar="0002", datum=d(2), subject="Visit Hurghada hotel project",
                                result="Needs 12 pantry units for the new wing"), USER)
    inq = so.create(conn, dict(auart="IN", kunnr="C1004", audat=d(2), items=[dict(kdmat="RSH-PANTRY-60",
                                                                                  qty="12")]), USER)["vbeln"]
    qt = so.create(conn, dict(auart="QT", vgbel=inq, audat=d(2), prob=70), USER)["vbeln"]
    o1 = so.create(conn, dict(auart="OR", vgbel=qt, audat=d(3), vdatu=d(5), bstnk="RSH-PO-7781", items=[
        dict(matnr="FG-3003", qty="10", vgbel=qt, vgpos=10, price="7600"),
        dict(matnr="TR-5001", qty="50")]), USER)["vbeln"]
    # 2 credit block
    r2 = so.create(conn, dict(auart="OR", kunnr="C1004", audat=d(3), vdatu=d(5), bstnk="RSH-PO-7790",
                              items=[dict(matnr="FG-3003", qty="6")]), USER)
    o2 = r2["vbeln"]
    so.release_credit(conn, o2, "CREDITMGR")
    # 3 partial confirmation / backorder
    o3 = so.create(conn, dict(auart="OR", kunnr="C1001", audat=d(3), vdatu=d(5), bstnk="CHC-4411",
                              items=[dict(matnr="FG-3003", qty="6")]), USER)["vbeln"]
    # 4 rush order + sample
    ro = so.create(conn, dict(auart="RO", kunnr="C1001", audat=d(4), vdatu=d(4), bstnk="CHC-4415",
                              items=[dict(matnr="TR-5001", qty="20")]), USER)
    fd = so.create(conn, dict(auart="FD", kunnr="C1002", audat=d(4), vdatu=d(5), augru="001",
                              items=[dict(matnr="FG-3002", qty="1")]), USER)["vbeln"]
    # 5 wholesale: scale price + customer discount + promotion
    o4 = so.create(conn, dict(auart="OR", kunnr="C1002", audat=d(4), vdatu=d(6), bstnk="DKW-2026-118",
                              items=[dict(matnr="FG-3001", qty="25"), dict(matnr="FG-3002", qty="10")]),
                   USER)["vbeln"]
    # Delta Kitchens has an item overdue > 30 days -> credit block; the credit manager
    # releases after the customer promised payment (VKM1)
    if conn.execute("SELECT cmgst FROM sd_vbak WHERE vbeln=?", (o4,)).fetchone()[0] == "B":
        so.release_credit(conn, o4, "CREDITMGR")
    # 6 shipping
    dls = {}
    for v, day in ((o1, 5), (o2, 5), (o3, 5), (fd, 4), (o4, 6)):
        dls[v] = dl.create(conn, v, USER, d(day))["vbeln"]
        dl.pick(conn, dls[v])
        dl.post_gi(conn, dls[v], USER, d(day))
    dl.pick(conn, ro["delivery"])
    dl.post_gi(conn, ro["delivery"], USER, d(4))
    # 7 billing
    inv = {}
    for v, ref, day in ((o1, dls[o1], 5), (o2, dls[o2], 5), (o3, dls[o3], 5), (o4, dls[o4], 6)):
        inv[v] = bl.create(conn, ref, USER, d(day))["vbeln"]
    bad = bl.create(conn, ro["delivery"], USER, d(4))["vbeln"]
    bl.cancel(conn, bad, USER, d(5))
    inv[ro["vbeln"]] = bl.create(conn, ro["delivery"], USER, d(5))["vbeln"]
    for v in inv.values():
        bl.einvoice(conn, v, USER)
    # 8 returns
    fg_pos = conn.execute("SELECT posnr FROM billing_item WHERE vbeln=? AND matnr='FG-3003'",
                          (inv[o1],)).fetchone()["posnr"]
    re_ = so.create(conn, dict(auart="RE", vgbel=inv[o1], audat=d(7), augru="101", items=[
        dict(matnr="FG-3003", qty="1", vgbel=inv[o1], vgpos=fg_pos, price="7600")]), USER)["vbeln"]
    lr = dl.create(conn, re_, USER, d(7))["vbeln"]
    dl.post_gi(conn, lr, USER, d(7))
    bl.create(conn, lr, USER, d(7))
    blk = conn.execute("SELECT lgpla FROM quant WHERE matnr='FG-3003' AND werks='1000' AND insmk='B' AND qty>0 "
                       "LIMIT 1").fetchone()
    post_goods_movement(conn, {"budat": d(7), "bktxt": "Returned unit beyond repair"}, [
        {"bwart": "551", "matnr": "FG-3003", "werks": "1000", "lgort": "0003", "lgpla": blk["lgpla"],
         "insmk": "B", "qty": "1", "kostl": "4300"}], USER)
    # 9 credit / debit memo requests
    cr = so.create(conn, dict(auart="CR", vgbel=inv[o4], audat=d(7), augru="201", items=[
        dict(matnr="FG-3001", qty="1", price="500", vgbel=inv[o4], vgpos=10)]), USER)["vbeln"]
    so.change(conn, cr, {"faksk": ""}, "SALESMGR")
    bl.create(conn, cr, USER, d(7))
    dr = so.create(conn, dict(auart="DR", vgbel=inv[ro["vbeln"]], audat=d(7), augru="202", items=[
        dict(matnr="TR-5001", qty="1", price="150", vgbel=inv[ro["vbeln"]], vgpos=10)]), USER)["vbeln"]
    bl.create(conn, dr, USER, d(7))
    # 10 service
    eq = conn.execute("SELECT equnr FROM sd_equi WHERE kunnr='C1004' ORDER BY equnr LIMIT 1").fetchone()["equnr"]
    n1 = sv.create_notification(conn, dict(equnr=eq, qmtxt="Door hinge loose", erdat=d(7), priok="2"), USER)
    a1 = sv.create_service_order(conn, n1["qmnum"], dict(gstrp=d(7), ops=[dict(arbpl="WC-REPR",
                                 ltxa1="Adjust hinges on site", vgw="1.5")],
                                 comps=[dict(matnr="SP-4001", menge="1", lgort="0004")]), USER)
    from pp import order as ppo
    ppo.post_picking(conn, [dict(rsnum=a1, rspos=1)], d(7), USER)
    ppo.confirm(conn, a1, "0010", "1", budat=d(7), user=USER)
    sv.complete(conn, n1["qmnum"], USER)
    n2 = sv.create_notification(conn, dict(kunnr="C1001", matnr="FG-3001", qmtxt="Door damaged by customer",
                                           erdat=d(7)), USER)
    a2 = sv.create_service_order(conn, n2["qmnum"], dict(gstrp=d(7), ops=[dict(arbpl="WC-REPR",
                                 ltxa1="Replace door belt and adjust", vgw="2")],
                                 comps=[dict(matnr="SP-4002", menge="1", lgort="0004")]), USER)
    ppo.post_picking(conn, [dict(rsnum=a2, rspos=1)], d(7), USER)
    ppo.confirm(conn, a2, "0010", "1", budat=d(7), user=USER)
    sv.complete(conn, n2["qmnum"], USER)
    sv.dp90(conn, n2["qmnum"], USER, d(8))
    zwr = so.create(conn, dict(auart="ZWR", kunnr="C1004", audat=d(7), vdatu=d(8), augru="301",
                               items=[dict(matnr="SP-4001", qty="1", equnr=eq)]), USER)["vbeln"]
    wd = dl.create(conn, zwr, USER, d(8))["vbeln"]
    dl.post_gi(conn, wd, USER, d(8))
    # 11 incoming payment of the first invoice
    b = conn.execute("SELECT belnr FROM billing WHERE vbeln=?", (inv[o1],)).fetchone()
    it = conn.execute("SELECT belnr, gjahr, buzei FROM acc_doc_item WHERE belnr=? AND koart='D'",
                      (b["belnr"],)).fetchone()
    pay(conn, "D", "C1004", d(8), [(it["belnr"], it["gjahr"], it["buzei"])], USER, bktxt="Payment RSH",
        tcode="F-28")
    # period end for the service orders (settlement to CO-PA)
    from co import period_end
    for a in (a1, a2):
        period_end.settle(conn, y, m, aufnr=a, user=USER)
    with transaction(conn):
        conn.execute("INSERT OR REPLACE INTO settings VALUES ('sd_sample', ?)", ("%04d-%02d" % (y, m),))
    return dict(inquiry=inq, quotation=qt, orders=[o1, o2, o3, o4], rush=ro["vbeln"], sample=fd, returns=re_,
                credit=cr, debit=dr, invoices=inv, service=[a1, a2], warranty=zwr)
