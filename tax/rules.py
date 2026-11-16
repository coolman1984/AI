"""ZTAX_LAW - register of the Egyptian tax rules: every rate, limit and deadline with its
validity, legal reference and status (VERIFIED / VERIFY = to be confirmed with the tax adviser
or the ETA text). A change of the law is entered as a new version with its effective date -
the old version stays (history) and is closed the day before.

The register drives: the payroll parameters (checked / applied to the HR configuration),
the withholding tax codes, the e-invoice deadlines, the tax calendar and the simplified
regime calculation. Values are text; unit says how to read them.
"""
import datetime

from mm import util as clock
from mm.db import transaction
from mm.util import MMError, now_ts, parse_date

AREAS = {"VAT": "Value added tax (Law 67/2016)", "WHT": "Withholding tax (Income Tax Law 91/2005)",
         "SAL": "Salary tax (Law 91/2005, Law 7/2024)", "SI": "Social insurance (Law 148/2019)",
         "CIT": "Corporate income tax", "SIMP": "Simplified regime for small businesses (Law 6/2025)",
         "EINV": "E-invoice / e-receipt (ETA)", "CAL": "Filing deadlines",
         "AUD": "Tax audit (Unified Tax Procedures Law 206/2020)"}

# key, area, text, value, unit, valid_from, legal reference, status, note
SEED = [
    ("VAT_STD", "VAT", "Standard VAT rate", "14", "%", "2017-07-01", "Law 67/2016 art. 3", "VERIFIED", ""),
    ("VAT_EXPORT", "VAT", "Exports of goods and services", "0", "%", "2016-09-08", "Law 67/2016 art. 30", "VERIFIED", ""),
    ("VAT_MACHINERY", "VAT", "Machinery and equipment for industrial production", "5", "%", "2016-09-08",
     "Law 67/2016 art. 3", "VERIFY", "Not on buses and passenger cars"),
    ("VAT_CONSTR_OLD", "VAT", "Construction contracts concluded before 18.07.2025 (ongoing): 14 % on 36 % of the "
     "invoice value, no input VAT deduction", "36", "% of the invoice is taxable", "2025-07-18",
     "Law 157/2025, Ministerial Decree 418/2025", "VERIFY", "Sources give 17.07 / 18.07 / 24.10.2025 as start"),
    ("VAT_CONSTR_NEW", "VAT", "Construction contracts concluded or renewed from 18.07.2025: full 14 % with input "
     "VAT deduction", "14", "%", "2025-07-18", "Law 157/2025, Ministerial Decree 417/2025", "VERIFY", ""),
    ("TABLE_CRUDE", "VAT", "Schedule (table) tax on crude petroleum", "10", "% of value", "2025-07-18",
     "Law 157/2025 (schedule)", "VERIFY", ""),
    ("VAT_RETURN_DAYS", "CAL", "VAT return (form 10): filed and paid by the end of the following month", "1",
     "month after the period", "2016-09-08", "Law 67/2016 art. 16", "VERIFY", ""),
    ("WHT_SUPPLIES", "WHT", "Withholding on local purchases / contracting / supplies", "1", "%", "2023-01-01",
     "Income Tax Law 91/2005 art. 59 + Minister of Finance decree", "VERIFY",
     "Older publications show 0.5 % - confirm the decree in force"),
    ("WHT_SERVICES", "WHT", "Withholding on local services", "3", "%", "2023-01-01",
     "Income Tax Law 91/2005 art. 59 + Minister of Finance decree", "VERIFY", "Older publications show 2 %"),
    ("WHT_COMMISSION", "WHT", "Withholding on commissions, brokerage, non-commercial professional fees", "5", "%",
     "2023-01-01", "Income Tax Law 91/2005 art. 59", "VERIFY", ""),
    ("WHT_MIN", "WHT", "Withholding applies to payments above", "300", "EGP", "2023-01-01",
     "Executive regulations Law 91/2005", "VERIFY", "100 EGP for non-commercial professionals"),
    ("WHT_NONRES", "WHT", "Payments to non-residents for services (before treaty relief)", "20", "%",
     "2005-06-09", "Law 91/2005 art. 56", "VERIFY", ""),
    ("WHT_FORM41_DUE", "CAL", "WHT form 41: quarterly, by the end of the month after the quarter", "1",
     "month after the quarter", "2005-06-09", "Law 91/2005 / executive regulations", "VERIFY", ""),
    ("SAL_EXEMPTION", "SAL", "Personal exemption per year", "20000", "EGP", "2024-03-01", "Law 7/2024", "VERIFY", ""),
    ("SAL_BRACKETS", "SAL", "Annual brackets (upper limit EGP x 100 : rate basis points)",
     "4000000:0,5500000:1000,7000000:1500,20000000:2000,40000000:2250,120000000:2500,999999999999:2750",
     "hr format", "2024-03-01", "Law 7/2024", "VERIFY",
     "0 % to 40,000 · 10 % to 55,000 · 15 % to 70,000 · 20 % to 200,000 · 22.5 % to 400,000 · 25 % to 1.2 m · 27.5 %"),
    ("SAL_HIGH_INCOME", "SAL", "High incomes: above threshold the first part is taxed at one rate (lower brackets "
     "fall away)", "60000000:5500000:1000,70000000:7000000:1500,80000000:20000000:2000,90000000:40000000:2250,"
     "120000000:120000000:2500", "hr format", "2024-03-01", "Law 7/2024", "VERIFY",
     "Above 600,000 no 0 % band ... above 1,200,000 the first 1,200,000 at 25 %"),
    ("SAL_DUE", "CAL", "Salary tax (form 4): paid by the 15th of the following month", "15", "day of next month",
     "2005-06-09", "Law 91/2005", "VERIFY", "Annual settlement in January"),
    ("MARTYRS", "SAL", "Martyrs' fund contribution of gross salaries", "0.05", "%", "2018-06-01", "Law 16/2018",
     "VERIFY", ""),
    ("SI_EE", "SI", "Social insurance - employee share", "11", "%", "2020-01-01", "Law 148/2019", "VERIFIED", ""),
    ("SI_ER", "SI", "Social insurance - employer share", "18.75", "%", "2020-01-01", "Law 148/2019", "VERIFIED", ""),
    ("SI_MIN", "SI", "Minimum insurable wage per month", "2300", "EGP", "2025-01-01", "Law 148/2019 (annual increase)",
     "VERIFY", ""),
    ("SI_MAX", "SI", "Maximum insurable wage per month", "14500", "EGP", "2025-01-01", "Law 148/2019 (annual increase)",
     "VERIFY", ""),
    ("SI_MIN", "SI", "Minimum insurable wage per month", "2700", "EGP", "2026-01-01", "Law 148/2019 (annual increase)",
     "VERIFY", "Published by NOSI every January"),
    ("SI_MAX", "SI", "Maximum insurable wage per month", "16700", "EGP", "2026-01-01", "Law 148/2019 (annual increase)",
     "VERIFY", "Published by NOSI every January"),
    ("CIT_RATE", "CIT", "Corporate income tax", "22.5", "%", "2015-07-01", "Law 91/2005 art. 49 (as amended)",
     "VERIFIED", "Special rates: Suez Canal, petroleum, Central Bank"),
    ("CIT_DUE", "CAL", "Annual corporate tax return: by the end of the 4th month after the year end", "4",
     "months after year end", "2005-06-09", "Law 91/2005 art. 83", "VERIFY", "End of April for a calendar year"),
    ("SIMP_LIMIT", "SIMP", "Simplified regime: annual turnover up to", "20000000", "EGP", "2025-03-01", "Law 6/2025",
     "VERIFY", "Up to 20 % above the limit for up to 5 years still allowed"),
    ("SIMP_BANDS", "SIMP", "Simplified regime: tax on turnover (upper limit EGP : rate %)",
     "500000:0.4,2000000:0.5,3000000:0.75,10000000:1,20000000:1.5", "bands", "2025-03-01", "Law 6/2025", "VERIFY",
     "Sources differ on the intermediate bands - confirm the law text"),
    ("EINV_CANCEL_DAYS", "EINV", "Issuer may cancel a valid e-invoice within", "7", "days", "2020-11-15",
     "ETA e-invoice rules", "VERIFY", "Receiver must approve; not after a credit note"),
    ("EINV_REJECT_DAYS", "EINV", "Receiver may reject a received e-invoice within", "3", "days", "2020-11-15",
     "ETA e-invoice rules", "VERIFY", ""),
    ("AUD_RETENTION", "AUD", "Keep books, records and e-documents (electronic, readable) for at least", "5", "years",
     "2020-10-19", "Unified Tax Procedures Law 206/2020", "VERIFY",
     "Counted from the filing of the return (some sources: end of the year) - NERP never deletes posted documents"),
    ("AUD_WINDOW", "AUD", "Period the tax authority may audit (6 years in case of evasion)", "5", "years", "2020-10-19",
     "Unified Tax Procedures Law 206/2020", "VERIFY", "Risk-based sample audits - a complete file lowers the risk"),
    ("TP_THRESHOLD", "AUD", "Transfer pricing documentation (local file) if related-party transactions exceed", "30000000",
     "EGP per year", "2025-01-01", "Income Tax Law art. 30 + Decree 534/2025", "VERIFY",
     "Older guides: 15 million; local file within 2 months after the CIT return deadline"),
    ("EINV_FINE_MIN", "AUD", "Fine for not issuing / storing e-invoices (from)", "20000", "EGP", "2020-10-19",
     "Law 206/2020 art. 71", "VERIFY", "Up to 100,000 EGP; costs without an e-invoice may be disallowed"),
    ("ERECEIPT_HOURS", "EINV", "E-receipt (B2C) to be sent to the ETA within", "72", "hours", "2025-01-01",
     "ETA resolution 281/2025", "VERIFY", "Needs a point-of-sale integration (outside NERP)"),
]


def seed_rules(conn):
    for key, area, text, value, unit, frm, ref, status, note in SEED:
        conn.execute("INSERT OR IGNORE INTO tax_rule (key,area,text,value,unit,valid_from,legal_ref,status,note,ts) "
                     "VALUES (?,?,?,?,?,?,?,?,?,?)", (key, area, text, value, unit, frm, ref, status, note, now_ts()))
    # close older versions where a later one exists
    for k in [r[0] for r in conn.execute("SELECT DISTINCT key FROM tax_rule")]:
        vs = conn.execute("SELECT id, valid_from FROM tax_rule WHERE key=? ORDER BY valid_from", (k,)).fetchall()
        for a, b in zip(vs, vs[1:]):
            end = (datetime.date.fromisoformat(b["valid_from"]) - datetime.timedelta(days=1)).isoformat()
            conn.execute("UPDATE tax_rule SET valid_to=? WHERE id=? AND valid_to>?", (end, a["id"], end))


def get(conn, key, day=None):
    day = parse_date(day) if day else clock.today().isoformat()
    r = conn.execute("SELECT * FROM tax_rule WHERE key=? AND valid_from<=? AND valid_to>=? ORDER BY valid_from DESC",
                     (key, day, day)).fetchone()
    if not r:
        raise MMError("No tax rule %s valid on %s (ZTAX_LAW)" % (key, day), "TX", "901")
    return r


def num(conn, key, day=None):
    return float(get(conn, key, day)["value"])


def register(conn, day=None, area=None):
    day = parse_date(day) if day else clock.today().isoformat()
    out = []
    for k in conn.execute("SELECT DISTINCT key FROM tax_rule %s ORDER BY area, key" % ("WHERE area=?" if area else ""),
                          (area,) if area else ()).fetchall():
        vs = [dict(r) for r in conn.execute("SELECT * FROM tax_rule WHERE key=? ORDER BY valid_from", (k[0],))]
        cur = [v for v in vs if v["valid_from"] <= day <= v["valid_to"]]
        nxt = [v for v in vs if v["valid_from"] > day]
        c = cur[-1] if cur else vs[-1]
        out.append(dict(c, versions=len(vs), area_text=AREAS.get(c["area"], c["area"]),
                        current=bool(cur), next_value=nxt[0]["value"] if nxt else "",
                        next_from=nxt[0]["valid_from"] if nxt else ""))
    return out


def history(conn, key):
    return [dict(r) for r in conn.execute("SELECT * FROM tax_rule WHERE key=? ORDER BY valid_from DESC", (key,))]


def new_version(conn, data, user):
    """a change of the law: the new value from its effective date; the previous version ends the day before"""
    key = (data.get("key") or "").strip().upper()
    value = (data.get("value") or "").strip()
    if not value:
        raise MMError("Enter the new value", "TX", "902")
    frm = parse_date(data.get("valid_from"))
    if not (data.get("legal_ref") or "").strip():
        raise MMError("Enter the legal reference (law / decree / resolution number)", "TX", "903")
    with transaction(conn):
        prev = conn.execute("SELECT * FROM tax_rule WHERE key=? ORDER BY valid_from DESC", (key,)).fetchone()
        if not prev:
            raise MMError("Tax rule %s does not exist" % key, "TX", "904")
        if frm <= prev["valid_from"]:
            raise MMError("The new version must start after %s (the latest version)" % prev["valid_from"], "TX", "905")
        try:
            float(value) if prev["unit"] not in ("hr format", "bands") else None
        except ValueError:
            raise MMError("%s needs a number" % key, "TX", "906")
        end = (datetime.date.fromisoformat(frm) - datetime.timedelta(days=1)).isoformat()
        conn.execute("UPDATE tax_rule SET valid_to=? WHERE id=?", (end, prev["id"]))
        conn.execute("INSERT INTO tax_rule (key,area,text,value,unit,valid_from,legal_ref,status,note,usnam,ts) VALUES "
                     "(?,?,?,?,?,?,?,?,?,?,?)", (key, prev["area"], prev["text"], value, prev["unit"], frm,
                                                 data["legal_ref"].strip()[:120],
                                                 "VERIFIED" if data.get("verified") else "VERIFY",
                                                 (data.get("note") or "")[:200], user, now_ts()))
    return {"message": "%s = %s %s from %s (previous version ends %s)" % (key, value, prev["unit"], frm, end)}


def set_verified(conn, rid, user):
    with transaction(conn):
        if not conn.execute("SELECT 1 FROM tax_rule WHERE id=?", (int(rid),)).fetchone():
            raise MMError("Rule %s does not exist" % rid, "TX", "904")
        conn.execute("UPDATE tax_rule SET status='VERIFIED', usnam=?, ts=? WHERE id=?", (user, now_ts(), int(rid)))
    return {"message": "Rule marked as verified"}


# ------------------------------------------------------------------ the register drives the payroll and WHT
def _payroll_targets(conn, day):
    def cents(k):
        return str(int(round(num(conn, k, day) * 100)))

    def bp(k):
        return str(int(round(num(conn, k, day) * 100)))
    return {"tax_exemption": cents("SAL_EXEMPTION"), "tax_brackets": get(conn, "SAL_BRACKETS", day)["value"],
            "tax_high_income": get(conn, "SAL_HIGH_INCOME", day)["value"], "si_min": cents("SI_MIN"),
            "si_max": cents("SI_MAX"), "si_ee_pct": bp("SI_EE"), "si_er_pct": bp("SI_ER"), "martyrs_pct": bp("MARTYRS")}


def payroll_check(conn, day=None):
    """differences between the law register and the payroll configuration (PC00 uses the configuration)"""
    from hr.engine import cfg
    day = parse_date(day) if day else clock.today().isoformat()
    out = []
    for k, v in _payroll_targets(conn, day).items():
        cur = cfg(conn, k)
        if str(cur) != v:
            out.append(dict(key=k, payroll=cur, law=v))
    return {"day": day, "differences": out}


def apply_payroll(conn, day, user):
    from hr.engine import save_config
    day = parse_date(day)
    diffs = payroll_check(conn, day)["differences"]
    if diffs:
        save_config(conn, {d["key"]: d["law"] for d in diffs}, user)
    return {"changed": len(diffs), "message": "%d payroll parameter(s) updated to the law valid on %s" % (len(diffs), day)}


WHT_MAP = {"W1": "WHT_SUPPLIES", "W3": "WHT_SERVICES", "W5": "WHT_COMMISSION"}


def wht_check(conn, day=None):
    day = parse_date(day) if day else clock.today().isoformat()
    out = []
    for code, key in WHT_MAP.items():
        r = conn.execute("SELECT pct FROM wht_code WHERE code=?", (code,)).fetchone()
        law = int(round(num(conn, key, day) * 100))
        if r and r["pct"] != law:
            out.append(dict(code=code, key=key, system=r["pct"] / 100.0, law=law / 100.0))
    return {"day": day, "differences": out}


def apply_wht(conn, day, user):
    day = parse_date(day)
    diffs = wht_check(conn, day)["differences"]
    with transaction(conn):
        for d in diffs:
            conn.execute("UPDATE wht_code SET pct=? WHERE code=?", (int(round(d["law"] * 100)), d["code"]))
    return {"changed": len(diffs), "message": "%d withholding tax code(s) updated" % len(diffs)}
