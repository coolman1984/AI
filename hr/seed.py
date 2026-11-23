"""HR demo data: organization (units, positions on the existing cost centers),
25 employees (fictional names, one paid in USD), leave and overtime, and posted payroll for the
two months before the CO sample month (paid); the sample month itself is released only."""
import datetime

from mm import util as mmclock

from . import engine, payroll

USER = "HR1"
ORG = [
    ("10000000", "Factory Egypt S.A.E.", "", "9100"),
    ("10001000", "Production", "10000000", "4100"),
    ("10001100", "Machining", "10001000", "4100"),
    ("10001200", "Assembly", "10001000", "4120"),
    ("10002000", "Maintenance & Utilities", "10000000", "4200"),
    ("10003000", "Quality Control", "10000000", "4300"),
    ("10004000", "Warehouse & Logistics", "10000000", "4400"),
    ("10005000", "Sales & Marketing", "10000000", "8100"),
    ("10006000", "Finance & Administration", "10000000", "9100"),
]
# name, Arabic name, gender, birth, hire, unit, job, subgroup, basic, transport, housing, user
EMP = [
    ("Ahmed Hassan", "أحمد حسن", "M", "1972-03-14", "2008-02-01", "10000000", "General Manager", "M", 85000, 4000, 8000, "ADMIN"),
    ("Mona Abdelrahman", "منى عبد الرحمن", "F", "1981-07-22", "2012-05-01", "10006000", "Finance Manager", "M", 52000, 3000, 5000, "GL1"),
    ("Karim Mostafa", "كريم مصطفى", "M", "1985-11-03", "2014-09-15", "10001000", "Production Manager", "M", 48000, 3000, 5000, "PLAN1"),
    ("Youssef Ali", "يوسف علي", "M", "1990-01-19", "2016-03-01", "10001100", "Machining Supervisor", "S", 22000, 1500, 2000, "SHOP1"),
    ("Mahmoud Ibrahim", "محمود إبراهيم", "M", "1993-06-08", "2018-01-07", "10001100", "CNC Operator", "W", 9500, 800, 0, ""),
    ("Hany Fathy", "هاني فتحي", "M", "1995-09-27", "2019-04-01", "10001100", "CNC Operator", "W", 9000, 800, 0, ""),
    ("Tarek Samir", "طارق سمير", "M", "1998-12-11", "2021-06-01", "10001100", "Machine Operator", "W", 8000, 800, 0, ""),
    ("Islam Gamal", "إسلام جمال", "M", "1996-04-02", "2020-02-15", "10001200", "Assembly Lead", "S", 14000, 1000, 1000, ""),
    ("Omar Khaled", "عمر خالد", "M", "1999-08-30", "2022-01-10", "10001200", "Assembly Worker", "W", 7500, 800, 0, ""),
    ("Sherif Adel", "شريف عادل", "M", "2000-02-17", "2023-03-01", "10001200", "Assembly Worker", "W", 7200, 800, 0, ""),
    ("Nour Hamdy", "نور حمدي", "F", "2001-05-05", "2024-07-01", "10001200", "Assembly Worker", "W", 7000, 800, 0, ""),
    ("Waleed Saad", "وليد سعد", "M", "1984-10-21", "2011-08-01", "10002000", "Maintenance Engineer", "S", 26000, 1500, 2000, ""),
    ("Ayman Fouad", "أيمن فؤاد", "M", "1991-03-09", "2017-11-01", "10002000", "Electrician", "W", 10500, 800, 0, ""),
    ("Rania Magdy", "رانيا مجدي", "F", "1988-12-25", "2015-06-01", "10003000", "Quality Engineer", "S", 21000, 1500, 1500, "QM1"),
    ("Mostafa Nabil", "مصطفى نبيل", "M", "1997-07-14", "2021-09-01", "10003000", "Quality Inspector", "W", 9200, 800, 0, ""),
    ("Hossam Reda", "حسام رضا", "M", "1987-04-28", "2013-03-01", "10004000", "Warehouse Supervisor", "S", 19000, 1500, 1500, "WH1"),
    ("Ashraf Zaki", "أشرف زكي", "M", "1994-11-16", "2019-10-01", "10004000", "Storekeeper", "W", 8500, 800, 0, ""),
    ("Sameh Lotfy", "سامح لطفي", "M", "1996-01-23", "2020-12-01", "10004000", "Forklift Driver", "W", 8200, 800, 0, ""),
    ("Dina Samy", "دينا سامي", "F", "1989-09-09", "2014-01-15", "10005000", "Sales Manager", "M", 42000, 3000, 4000, "SALES1"),
    ("Amr Wagdy", "عمرو وجدي", "M", "1992-02-12", "2017-05-01", "10005000", "Sales Engineer", "S", 18000, 2000, 1500, ""),
    ("Salma Yasser", "سلمى ياسر", "F", "1995-10-31", "2020-08-01", "10005000", "Marketing Specialist", "S", 15000, 1500, 1000, ""),
    ("Heba Osama", "هبة أسامة", "F", "1990-06-18", "2016-10-01", "10006000", "Accountant", "S", 17000, 1500, 1000, "AP1"),
    ("Mohamed Tawfik", "محمد توفيق", "M", "1993-08-04", "2019-02-01", "10006000", "Accountant", "S", 16000, 1500, 1000, "AR1"),
    ("Laila Fawzy", "ليلى فوزي", "F", "1994-03-27", "2021-01-15", "10006000", "HR Specialist", "S", 16500, 1500, 1000, "HR1"),
]

# one expatriate paid in US dollars (pay currency USD): insurance and tax on the EGP amount
EXPAT = ("Adam Clarke", "آدم كلارك", "M", "1986-05-20", "2023-09-01", "10005000", "Export Sales Manager", "M",
         1800, 150, 400, "")


def _nid(birth, i):
    y = int(birth[:4])
    return "%d%s%s%s%02d%04d%d" % (2 if y < 2000 else 3, birth[2:4], birth[5:7], birth[8:10], 1, 100 + i, i % 10)


def _iban(i):
    return "EG38%04d%04d%017d" % (19, 1, 4100000000 + i * 1371)


def seed(conn):
    if conn.execute("SELECT COUNT(*) FROM hr_employee").fetchone()[0]:
        return
    for orgeh, text, parent, kostl in ORG:
        engine.save_orgunit(conn, orgeh, text, parent, kostl)
    t = mmclock.today()
    for i, (name, ar, g, birth, hire, unit, job, sg, basic, tr, ho, bname) in enumerate(EMP + [EXPAT], start=1):
        plans = "5%07d" % i
        kostl = [o for o in ORG if o[0] == unit][0][3]
        engine.save_position(conn, plans, job, unit, kostl, sg)
        engine.hire(conn, dict(name=name, name_ar=ar, gender=g, birth_date=birth, national_id=_nid(birth, i),
                               hire_date=hire, orgeh=unit, plans=plans, kostl=kostl, persk=sg, job=job,
                               basic=str(basic), allow_transport=str(tr), allow_housing=str(ho), iban=_iban(i),
                               si_no="%09d" % (310000000 + i * 37), bname=bname,
                               email="%s@factory-egypt.example" % name.split()[0].lower(),
                               waers="USD" if name == EXPAT[0] else "EGP"), USER)
    for o in ORG:                                       # managers of the units
        m = conn.execute("SELECT pernr FROM hr_employee WHERE orgeh=? ORDER BY basic DESC LIMIT 1", (o[0],)).fetchone()
        if m:
            conn.execute("UPDATE hr_orgunit SET manager=? WHERE orgeh=?", (m[0], o[0]))
    first = t.replace(day=1)
    months = []
    d = first
    for _ in range(3):                                  # three closed months + the current one
        d = (d - datetime.timedelta(days=1)).replace(day=1)
        months.append(d)
    months = months[::-1]
    pern = [r[0] for r in conn.execute("SELECT pernr FROM hr_employee ORDER BY pernr")]

    def wd(m, day):
        return mmclock.day_in_month(m.year, m.month, day).isoformat()
    # leave and overtime in the closed months (approved)
    for k, m in enumerate(months):
        engine.request_absence(conn, pern[4 + k], "ANN", wd(m, 5), wd(m, 8), USER, "Family", approve=True)
        engine.request_absence(conn, pern[9 + k], "SIC", wd(m, 12), wd(m, 13), USER, "Medical certificate", approve=True)
        for p_ in pern[4:8]:
            engine.add_overtime(conn, p_, wd(m, 15), "D", "6", USER)
        engine.add_overtime(conn, pern[12], wd(m, 20), "R", "8", USER)
    engine.request_absence(conn, pern[16], "UNP", wd(months[-1], 18), wd(months[-1], 19), USER, "Personal", approve=True)
    # the two older months are posted and paid; the last closed month is the CO sample month, whose
    # salaries the CO sample posts itself - its payroll is released (calculated) but not posted
    for m in months[:-1]:
        payroll.run(conn, m.year, m.month, USER)
        payroll.post(conn, m.year, m.month, USER)
        payroll.pay(conn, m.year, m.month, USER)
    payroll.run(conn, months[-1].year, months[-1].month, USER)
    # open leave requests for next month (approval inbox)
    nxt = (first + datetime.timedelta(days=40)).replace(day=1)
    try:
        engine.request_absence(conn, pern[8], "ANN", wd(nxt, 3), wd(nxt, 6), "OMAR", "Wedding of my brother")
        engine.request_absence(conn, pern[20], "CAS", wd(nxt, 10), wd(nxt, 10), "SALMA", "Personal matter")
    except Exception:  # noqa - demo extras must never stop the seed (e.g. year end quota)
        pass
    # fixed-term contract ending soon and a new hire in probation (ZHR_EVENTS follow-up)
    from mm import util as clock
    t = clock.today()
    conn.execute("UPDATE hr_employee SET persg='2', contract_end=? WHERE pernr=?",
                 ((t + datetime.timedelta(days=45)).isoformat(), pern[10]))


def time_and_talent(conn):
    """time clock and evaluation of the last working days of this month, approved overtime, a training that certifies,
    appraisals of the previous year and drafts of this year"""
    import random
    from pp.config import WORKDAYS
    from . import talent, time as tm
    rnd = random.Random(11)
    today = mmclock.today()
    staff = [r["pernr"] for r in conn.execute("SELECT pernr FROM hr_employee WHERE orgeh LIKE '1000%' AND pernr BETWEEN '10003' AND '10017' "
                                              "AND status='A' ORDER BY pernr")]
    conn.execute("UPDATE hr_employee SET shift='N1' WHERE pernr='10011'")         # maintenance on nights
    conn.execute("UPDATE hr_employee SET time_rec=CASE WHEN pernr IN (%s) THEN 1 ELSE 0 END" % ",".join("?" * len(staff)), staff)
    days = []
    d = today - datetime.timedelta(days=1)
    while len(days) < 8 and d.month == today.month:
        if d.weekday() in WORKDAYS:
            days.append(d)
        d -= datetime.timedelta(days=1)
    for d in sorted(days):
        for p in staff:
            r = rnd.random()
            if p == "10009" and d == days[0]:
                continue                                                         # unexcused absence yesterday
            if r < 0.04:
                continue
            night = p == "10011"
            start = datetime.datetime.combine(d, datetime.time(22 if night else 8, 0))
            late = rnd.choice([0, 0, 0, 0, 3, 6, 18, 35]) if r < 0.9 else 0
            stay = 0 if rnd.random() < 0.75 else rnd.choice([45, 60, 90, 120])
            tm.punch(conn, p, "IN", USER, at=start + datetime.timedelta(minutes=late - rnd.randint(0, 8)), source="TERMINAL")
            tm.punch(conn, p, "OUT", USER, at=start + datetime.timedelta(minutes=510 + stay + rnd.randint(0, 6)), source="TERMINAL")
        tm.evaluate(conn, d.isoformat())
    for d in sorted(days)[:-2]:                                                  # overtime approved, notified except the last
        try:
            tm.approve_overtime(conn, d.isoformat(), USER)
        except Exception:                                                        # day without overtime
            continue
    for d in sorted(days)[:-4]:
        if conn.execute("SELECT 1 FROM hr_overtime WHERE datum=?", (d.isoformat(),)).fetchone():
            tm.notify_overtime(conn, d.isoformat(), "LO-%s" % d.strftime("%m%d"), USER)
    t = talent.plan_training(conn, {"title": "Final test and inspection - certification", "skill": "TEST",
                                    "datum": (today - datetime.timedelta(days=20)).isoformat(), "hours": "16", "trainer": "Rania Magdy",
                                    "cost": "4500", "participants": ["10008", "10009"]}, USER)["id"]
    talent.complete_training(conn, t, {"10008": "PASS", "10009": "FAIL"}, USER)
    talent.plan_training(conn, {"title": "CNC refresher", "skill": "CNC", "datum": (today + datetime.timedelta(days=10)).isoformat(),
                                "hours": "8", "trainer": "Mahmoud Ibrahim", "participants": ["10006"]}, USER)
    talent.plan_training(conn, {"title": "Fire safety and first aid", "datum": (today - datetime.timedelta(days=40)).isoformat(),
                                "hours": "4", "trainer": "External", "cost": "6000",
                                "participants": [p for p in staff[:8]]}, USER)
    for pernr, g, c, a, comment in (("10004", 5, 5, 5, ""), ("10005", 4, 4, 4, ""), ("10006", 3, 3, 2, ""),
                                    ("10007", 5, 4, 5, ""), ("10008", 3, 4, 4, ""), ("10009", 2, 2, 2, "Absences - improvement plan agreed"),
                                    ("10013", 4, 5, 5, ""), ("10014", 3, 3, 4, "")):
        talent.save_appraisal(conn, dict(pernr=pernr, year=today.year - 1, goals=g, competencies=c, attendance=a, comment=comment,
                                         final=True), "HRADMIN")
    for pernr, g, c in (("10004", 4, 5), ("10010", 3, 3)):
        talent.save_appraisal(conn, dict(pernr=pernr, year=today.year, goals=g, competencies=c), "HRADMIN")
