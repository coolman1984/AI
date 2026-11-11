"""HR tables (PA / OM / PT / PY) and installation of the customizing and the HR roles."""

HR_SCHEMA = """
CREATE TABLE IF NOT EXISTS hr_config (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS hr_orgunit (       -- HRP1000 O
    orgeh TEXT PRIMARY KEY, text TEXT, parent TEXT DEFAULT '', kostl TEXT DEFAULT '', manager TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS hr_position (      -- HRP1000 S
    plans TEXT PRIMARY KEY, text TEXT, orgeh TEXT, kostl TEXT DEFAULT '', persk TEXT DEFAULT 'S');
CREATE TABLE IF NOT EXISTS hr_employee (      -- PA0001 / 0002 / 0008 / 0009 / 0105
    pernr TEXT PRIMARY KEY, name TEXT NOT NULL, name_ar TEXT DEFAULT '', national_id TEXT DEFAULT '',
    birth_date TEXT, gender TEXT DEFAULT '', hire_date TEXT NOT NULL, leave_date TEXT DEFAULT '',
    leave_reason TEXT DEFAULT '', status TEXT DEFAULT 'A', orgeh TEXT, plans TEXT DEFAULT '', kostl TEXT,
    werks TEXT DEFAULT '1000', persg TEXT DEFAULT '1', persk TEXT DEFAULT 'S', job TEXT DEFAULT '',
    basic INTEGER NOT NULL DEFAULT 0, allow_transport INTEGER DEFAULT 0, allow_housing INTEGER DEFAULT 0,
    allow_other INTEGER DEFAULT 0, ins_wage INTEGER DEFAULT 0, iban TEXT DEFAULT '', si_no TEXT DEFAULT '',
    phone TEXT DEFAULT '', email TEXT DEFAULT '', bname TEXT DEFAULT '', created TEXT, changed TEXT,
    changed_by TEXT DEFAULT '', waers TEXT DEFAULT 'EGP');
CREATE INDEX IF NOT EXISTS hr_emp_org ON hr_employee (orgeh);
CREATE TABLE IF NOT EXISTS hr_action (        -- PA0000 personnel actions
    id INTEGER PRIMARY KEY AUTOINCREMENT, pernr TEXT, massn TEXT, begda TEXT, reason TEXT DEFAULT '',
    detail TEXT DEFAULT '', usnam TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS hr_change (        -- change documents of HR master data
    id INTEGER PRIMARY KEY AUTOINCREMENT, pernr TEXT, field TEXT, old TEXT, new TEXT, usnam TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS hr_absence (       -- PA2001 (requests and approved absences)
    id INTEGER PRIMARY KEY AUTOINCREMENT, pernr TEXT, awart TEXT, begda TEXT, endda TEXT, days INTEGER,
    status TEXT DEFAULT 'R', reason TEXT DEFAULT '', created TEXT, created_by TEXT DEFAULT '',
    decided_by TEXT DEFAULT '', decided TEXT DEFAULT '');
CREATE INDEX IF NOT EXISTS hr_abs_emp ON hr_absence (pernr, begda);
CREATE TABLE IF NOT EXISTS hr_overtime (      -- PA2002 attendances / overtime
    id INTEGER PRIMARY KEY AUTOINCREMENT, pernr TEXT, datum TEXT, ottype TEXT, hours INTEGER,
    created TEXT, created_by TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS hr_payroll_run (   -- payroll control record
    gjahr INTEGER, perio INTEGER, status TEXT, run_ts TEXT, usnam TEXT, belnr TEXT DEFAULT '',
    pay_belnr TEXT DEFAULT '', employees INTEGER DEFAULT 0, PRIMARY KEY (gjahr, perio));
CREATE TABLE IF NOT EXISTS hr_payroll (       -- payroll results (RT) per employee and period
    gjahr INTEGER, perio INTEGER, pernr TEXT, kostl TEXT, persk TEXT, days INTEGER, paid_days INTEGER,
    basic INTEGER, allowances INTEGER, overtime INTEGER, unpaid INTEGER, gross INTEGER, ins_wage INTEGER,
    si_ee INTEGER, si_er INTEGER, taxable INTEGER, tax INTEGER, martyrs INTEGER, other INTEGER DEFAULT 0,
    net INTEGER, waers TEXT DEFAULT 'EGP', kurs INTEGER DEFAULT 100000, gross_fc INTEGER, net_fc INTEGER,
    PRIMARY KEY (gjahr, perio, pernr));
"""

# upgrades of older databases: pay currency (EGP / USD) of the employee and the results
HR_COLUMN_ADDS = {
    "hr_employee": [("waers", "TEXT DEFAULT 'EGP'")],
    "hr_payroll": [("waers", "TEXT DEFAULT 'EGP'"), ("kurs", "INTEGER DEFAULT 100000"), ("gross_fc", "INTEGER"),
                   ("net_fc", "INTEGER")],
}


def install(conn):
    from .config import DEFAULTS
    for table, cols in HR_COLUMN_ADDS.items():
        have = {r[1] for r in conn.execute("PRAGMA table_info(%s)" % table)}
        for col, typ in cols:
            if col not in have:
                conn.execute("ALTER TABLE %s ADD COLUMN %s %s" % (table, col, typ))
    for k, v in DEFAULTS.items():
        conn.execute("INSERT OR IGNORE INTO hr_config VALUES (?,?)", (k, v))
    # HR roles for databases that already have users (the demo bootstrap creates them too)
    if conn.execute("SELECT name FROM sqlite_master WHERE name='role'").fetchone() and \
            conn.execute("SELECT COUNT(*) FROM role").fetchone()[0]:
        from sec.config import DEMO_ROLES
        for name in ("HR_ADMIN", "PAYROLL"):
            text, tcodes, auths = DEMO_ROLES[name]
            if conn.execute("SELECT 1 FROM role WHERE name=?", (name,)).fetchone():
                continue
            conn.execute("INSERT INTO role (name,text,changed,changed_by) VALUES (?,?,datetime('now'),'SYSTEM')",
                         (name, text))
            for t in tcodes:
                conn.execute("INSERT OR IGNORE INTO role_tcode VALUES (?,?)", (name, t))
            for o, v, a in auths:
                conn.execute("INSERT OR IGNORE INTO role_auth VALUES (?,?,?,?)", (name, o, v, a))
