"""Tables of the Egyptian taxes module."""

TAX_SCHEMA = """
CREATE TABLE IF NOT EXISTS tax_rule (        -- ZTAX_LAW law register: every rate / limit with validity
    id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT NOT NULL, area TEXT NOT NULL, text TEXT NOT NULL,
    value TEXT NOT NULL, unit TEXT NOT NULL DEFAULT '', valid_from TEXT NOT NULL, valid_to TEXT NOT NULL
    DEFAULT '9999-12-31', legal_ref TEXT DEFAULT '', status TEXT NOT NULL DEFAULT 'VERIFY', note TEXT DEFAULT '',
    usnam TEXT DEFAULT 'SYSTEM', ts TEXT, UNIQUE (key, valid_from));
CREATE TABLE IF NOT EXISTS tax_filing (      -- ZTAX_CAL returns filed / paid
    typ TEXT NOT NULL, period TEXT NOT NULL, filed_on TEXT, ref_no TEXT, amount INTEGER DEFAULT 0,
    paid_on TEXT, pay_ref TEXT, usnam TEXT, ts TEXT, PRIMARY KEY (typ, period));
CREATE TABLE IF NOT EXISTS tax_setting (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS eta_out (         -- ZTAX_EINV result of every issued e-invoice (manual or API)
    vbeln TEXT PRIMARY KEY, uuid TEXT, long_id TEXT, status TEXT, submitted TEXT, mode TEXT,
    cancel_req TEXT, reason TEXT, usnam TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS eta_in (          -- ZTAX_EIN documents received from vendors (ETA portal export)
    uuid TEXT PRIMARY KEY, issuer_id TEXT, issuer_name TEXT, internal_id TEXT, issued TEXT,
    doc_type TEXT DEFAULT 'I', net INTEGER DEFAULT 0, tax INTEGER DEFAULT 0, total INTEGER DEFAULT 0,
    status TEXT, lifnr TEXT, belnr TEXT, gjahr INTEGER, imported TEXT, usnam TEXT);
"""


def install(conn):
    from .rules import seed_rules
    seed_rules(conn)
    conn.execute("INSERT OR IGNORE INTO tax_setting VALUES ('eta_mode','MANUAL')")
    conn.execute("INSERT OR IGNORE INTO tax_setting VALUES ('eta_env','preprod')")
