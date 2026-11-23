"""Demo data for GMES: skills and operator certifications, stations on the assembly and machining lines,
serial numbers of the open pantry order with three days of bookings (first-pass, failures, repairs, one
scrap), genealogy of the components, andon calls and an SPC characteristic with measurements."""
import datetime
import random

from mm import util as clock

USER = "MESADMIN"


def sample(conn):
    from hr import skills
    from . import track
    rnd = random.Random(7)
    t = clock.today()
    day = lambda k: t - datetime.timedelta(days=k)                      # noqa: E731
    at = lambda k, h, m=0: datetime.datetime.combine(day(k), datetime.time(h, m))  # noqa: E731
    for code, text, months in (("CNC", "CNC machining", 24), ("ASSY", "Cabinet assembly", 24),
                               ("TEST", "Final test and inspection", 12), ("REPAIR", "Repair of failed units", 24),
                               ("FORK", "Forklift licence", 36)):
        skills.save_skill(conn, code, text, months)
    start = (t - datetime.timedelta(days=200)).isoformat()
    for pernr, skill, level in (("10004", "CNC", 3), ("10005", "CNC", 2), ("10007", "ASSY", 3), ("10007", "TEST", 3),
                                ("10007", "REPAIR", 3), ("10008", "ASSY", 2), ("10009", "ASSY", 2), ("10010", "ASSY", 1),
                                ("10013", "TEST", 3), ("10014", "TEST", 2), ("10011", "REPAIR", 2), ("10017", "FORK", 2)):
        skills.qualify(conn, pernr, skill, level, start, USER, trainer="10007" if skill == "ASSY" else "10013")
    skills.qualify(conn, "10006", "CNC", 1, (t - datetime.timedelta(days=400)).isoformat(), USER,
                   valid_to=(t - datetime.timedelta(days=10)).isoformat(), note="Refresher training due")    # expired
    skills.qualify(conn, "10014", "REPAIR", 1, start, USER, valid_to=(t + datetime.timedelta(days=12)).isoformat())  # expiring
    for st in (dict(station="MACH-10", arbpl="WC-MACH", vornr="0010", kind="OP", text="CNC cell 1", skill="CNC", ct_std=70),
               dict(station="ASSY-10", arbpl="WC-ASSY", vornr="0010", kind="OP", text="Assembly station 1", skill="ASSY", ct_std=180, opps=4),
               dict(station="ASSY-20", arbpl="WC-ASSY", vornr="0020", kind="TEST", text="Final test and packing", skill="TEST",
                    ct_std=60, opps=6),
               dict(station="ASSY-RP", arbpl="WC-ASSY", kind="REPAIR", text="Repair bench", skill="REPAIR")):
        track.save_station(conn, st)
    o = conn.execute("SELECT aufnr, gamng FROM orders WHERE auart='PP01' AND matnr='FG-3003' AND stat='REL' ORDER BY aufnr").fetchone()
    if not o:
        return
    aufnr = o["aufnr"]
    n = o["gamng"] // 1000
    sns = track.release_units(conn, aufnr, n, USER)["serials"]
    comps = [r["idnrk"] for r in conn.execute("SELECT idnrk FROM bom WHERE matnr='FG-3003' ORDER BY posnr")]
    for k in (3, 2, 1):                                                   # line plan of the last days (8 units per shift)
        conn.execute("INSERT OR IGNORE INTO pp_lineplan (datum,arbpl,aufnr,matnr,plan,uph,man,start,hours,usnam,ts) "
                     "VALUES (?,?,?,?,?,?,?,?,?,?,?)", (day(k).isoformat(), "WC-ASSY", aufnr, "FG-3003", 10000, 1250, 4, "08:00",
                                                       8, USER, clock.now_ts()))
    ops = ["10008", "10009", "10010"]
    i = 0
    for k, count in ((3, 10), (2, 11), (1, 7)):                          # assembly (op 0010) per day
        for j in range(count):
            sn = sns[i]
            i += 1
            h, m = 8 + (j * 7) // 10, (j * 41) % 60
            lots = [dict(matnr=c, lot="L-%s-%s" % (c.replace("-", ""), day(k + 2).strftime("%m%d")), qty=1) for c in comps]
            track.book(conn, sn, "ASSY-10", "OK", ops[j % 3], USER, cycle_sec=int(rnd.gauss(195, 25)), components=lots,
                       at=at(k, h, m))
    for idx, sn in enumerate(sns[:23]):                                   # final test (op 0020)
        k = 2 if idx < 12 else 1
        base = at(k, 9 + (idx % 12) * 7 // 12, (idx * 23) % 60)
        if idx in (3, 9, 15, 20):
            track.book(conn, sn, "ASSY-20", "NG", "10014", USER, defect=["FUNC", "ASSY", "SURF", "FUNC"][[3, 9, 15, 20].index(idx)],
                       cycle_sec=int(rnd.gauss(70, 8)), at=base)
            if idx == 20:
                track.book(conn, sn, "ASSY-RP", "SCRAP", "10007", USER, defect="MAT", note="Carcass cracked - not repairable",
                           at=base + datetime.timedelta(minutes=40))
                continue
            track.book(conn, sn, "ASSY-RP", "REPAIRED", "10007", USER, note="Readjusted / replaced part",
                       at=base + datetime.timedelta(minutes=30))
            base += datetime.timedelta(minutes=50)
        if idx == 22:
            continue                                                       # waits at the test station
        track.book(conn, sn, "ASSY-20", "OK", "10013" if idx % 2 else "10014", USER, cycle_sec=int(rnd.gauss(62, 7)), at=base)
    track.book(conn, sns[23], "ASSY-20", "NG", "10014", USER, defect="ELEC", cycle_sec=75, at=at(1, 14, 10))   # in repair now
    for kind, text, k, h, ack, close, res in (
            ("MAT", "Hinges missing at assembly 1", 3, 10, 6, 25, "Hinges brought from warehouse"),
            ("QUAL", "Door gaps too wide", 2, 11, 4, 55, "Jig re-adjusted, first 5 units checked"),
            ("MAINT", "Screwdriver torque fault", 1, 13, 9, 70, "Torque controller replaced"),
            ("HELP", "New worker needs support", 1, 15, 3, None, None)):
        a = track.andon_open(conn, "WC-ASSY", kind, text, USER, station="ASSY-10", at=at(k, h))["id"]
        track.andon_step(conn, a, "ack", USER, at=at(k, h, ack))
        if close:
            track.andon_step(conn, a, "close", USER, res, at=at(k, h, 0) + datetime.timedelta(minutes=close))
    track.save_char(conn, dict(code="GAP", text="Door gap", station="ASSY-20", unit="mm", lsl="2.0", usl="4.0", target="3.0", n="5"))
    for g in range(24):                                                    # 24 subgroups of 5, the last ones drift upwards
        k = 3 - g // 8
        for s in range(5):
            mu = 3.0 + (0.18 if g >= 18 else 0.0)
            track.measure(conn, "GAP", round(rnd.gauss(mu, 0.15), 3), USER, station="ASSY-20", operator="10013",
                          at=at(k, 8 + (g % 8), s * 10))
