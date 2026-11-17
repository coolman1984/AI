"""Demo data: quality inspection of tempered glass and maintenance of the factory machines."""
import datetime

from mm import util as clock

USER = "QMADMIN"


def sample(conn):
    from mm.posting import post_goods_movement, propose_bin
    from pur import po as purpo
    from . import maintenance as pm, quality as qm
    t = clock.today()
    d = lambda k: (t - datetime.timedelta(days=k)).isoformat()            # noqa: E731
    # ---------------------------------------------------------------- quality: glass from the glass vendor
    qm.set_active(conn, "RM-1005", "1000", True, USER)
    qm.save_plan(conn, "RM-1005", "1000", [
        dict(name="Thickness", kind="N", lsl="3.8", usl="4.2", unit="mm"),
        dict(name="Length", kind="N", lsl="398", usl="402", unit="mm"),
        dict(name="Edges ground, no chips", kind="A"),
        dict(name="Tempering certificate", kind="A")], USER)
    v = conn.execute("SELECT lifnr FROM info_record WHERE matnr='RM-1005' ORDER BY infnr").fetchone()
    lifnr = v["lifnr"] if v else conn.execute("SELECT lifnr FROM vendor ORDER BY lifnr").fetchone()[0]
    lots = []
    for k, qty in ((9, "200"), (4, "150"), (1, "120")):
        e = purpo.create_po(conn, {"lifnr": lifnr, "bedat": d(k + 7), "items": [
            {"matnr": "RM-1005", "menge": qty, "netpr": "85", "lgort": "0001", "eindt": d(k)}]}, USER)
        purpo.release_all(conn, e, USER)
        pb = propose_bin(conn, "RM-1005", "1000", "0001")
        r = post_goods_movement(conn, {"budat": d(k), "xblnr": "DN-Q%d" % k}, [
            {"bwart": "101", "ebeln": e, "ebelp": 10, "qty": qty, "lgpla": pb["lgpla"]}], USER)
        lots.append(r["lots"][0])
    qm.record(conn, lots[0], {"10": "4.02", "20": "400.5", "30": "OK", "40": "OK"}, USER)
    qm.usage_decision(conn, lots[0], {"qty_ok": "200", "datum": d(8)}, USER)
    qm.record(conn, lots[1], {"10": "3.95", "20": "401.2", "30": "NOK", "40": "OK"}, USER)
    qm.usage_decision(conn, lots[1], {"qty_ok": "138", "qty_rej": "12", "defect": "DMG", "datum": d(3),
                                      "override": "12 chipped panes sorted out, rest checked 100 %",
                                      "note": "Chipped edges - packaging of the vendor"}, USER)
    qm.record(conn, lots[2], {"10": "4.05"}, USER)                     # still in inspection
    n = conn.execute("SELECT qmnum FROM qm_notif WHERE prueflos=?", (lots[1],)).fetchone()["qmnum"]
    qm.update_notification(conn, n, {"cause": "Pallets without corner protection"}, USER)
    qm.create_notification(conn, {"qmart": "Q3", "matnr": "FG-3001", "defect": "SURF", "qty": "3",
                                  "text": "Scratches on cabinet doors after assembly", "datum": d(2)}, USER)
    # ---------------------------------------------------------------- maintenance: machines on the lines
    for e in (dict(equnr="CNC-01", eqktx="CNC machining centre 5-axis", arbpl="WC-MACH", crit="A", inbdt="2019-03-01"),
              dict(equnr="PRS-01", eqktx="Hydraulic press 200 t", arbpl="WC-MACH", crit="A", inbdt="2017-06-15"),
              dict(equnr="ROB-01", eqktx="Assembly robot cell", arbpl="WC-ASSY", crit="B", inbdt="2021-09-01"),
              dict(equnr="CMP-01", eqktx="Air compressor 37 kW", kostl="4100", crit="B", inbdt="2018-01-10")):
        pm.save_equipment(conn, e, USER)
    pm.save_plan(conn, dict(equnr="CNC-01", text="Lubrication and spindle check", interval_days="30",
                            minutes="90", next_due=d(2)), USER)
    pm.save_plan(conn, dict(equnr="PRS-01", text="Hydraulic oil and seals inspection", interval_days="90",
                            minutes="240", next_due=(t + datetime.timedelta(days=12)).isoformat()), USER)
    pm.save_plan(conn, dict(equnr="CMP-01", text="Filter change and belt tension", interval_days="60",
                            minutes="60", next_due=d(20)), USER)
    # a preventive order done last month
    o = pm.schedule(conn, USER)["orders"]
    for a in o:
        if conn.execute("SELECT equnr FROM pm_order WHERE aufnr=?", (a,)).fetchone()[0] == "CNC-01":
            pm.issue_parts(conn, a, [{"matnr": "SP-4001", "qty": "2", "lgort": "0004"}], USER, d(1))
        if conn.execute("SELECT equnr FROM pm_order WHERE aufnr=?", (a,)).fetchone()[0] == "CMP-01":
            pm.issue_parts(conn, a, [{"matnr": "SP-4002", "qty": "1", "lgort": "0004"}], USER, d(1))
            pm.confirm(conn, a, {"minutes": "70", "datum": d(1)}, USER)
            pm.complete(conn, a, {}, USER)
    # a breakdown of the CNC machine before the production sample month (its downtime goes to the line)
    m = conn.execute("SELECT value FROM settings WHERE key='pp_sample'").fetchone()
    first = datetime.date.fromisoformat(m[0] + "-01") if m else t.replace(day=1)
    day = min(first, t.replace(day=1)) - datetime.timedelta(days=6)
    b = pm.create_notification(conn, dict(qmart="M2", equnr="CNC-01", text="Spindle bearing noise - machine stopped",
                                          start=day.isoformat() + " 09:10"), USER)
    pm.confirm(conn, b["aufnr"], {"minutes": "150", "datum": day.isoformat()}, USER)
    pm.complete(conn, b["aufnr"], {"finish": day.isoformat() + " 11:40"}, USER)
    # the air compressor (not on a line) stopped three days ago
    b = pm.create_notification(conn, dict(qmart="M2", equnr="CMP-01", text="Pressure drop - compressor tripped",
                                          start=d(3) + " 14:00"), USER)
    pm.confirm(conn, b["aufnr"], {"minutes": "45", "datum": d(3)}, USER)
    pm.complete(conn, b["aufnr"], {"finish": d(3) + " 14:50"}, USER)
    pm.create_notification(conn, dict(qmart="M1", equnr="ROB-01", text="Gripper sensor sometimes not detecting"), USER)
