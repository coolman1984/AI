"""Tables of the customs module (amounts in cents, quantities in milli, percentages in 1/100 %)."""

CUSTOMS_SCHEMA = """
CREATE TABLE IF NOT EXISTS cus_tariff (          -- customs tariff per HS code (maintained by the user)
    hs TEXT PRIMARY KEY, text TEXT, duty_pct INTEGER NOT NULL DEFAULT 0, vat_pct INTEGER NOT NULL DEFAULT 1400,
    export_support_pct INTEGER NOT NULL DEFAULT 0, note TEXT);
CREATE TABLE IF NOT EXISTS cus_mat_hs (          -- HS code of a material
    matnr TEXT PRIMARY KEY, hs TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS cus_setting (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS cus_decl (            -- customs declaration (import or export)
    declno TEXT PRIMARY KEY, direction TEXT NOT NULL,      -- IMP / EXP
    impno TEXT, ebeln TEXT, vbeln TEXT, partner TEXT, broker TEXT,
    acid TEXT, decl_ref TEXT, coo_no TEXT, bl_no TEXT, port TEXT, country TEXT, incoterm TEXT,
    waers TEXT, goods INTEGER NOT NULL DEFAULT 0,          -- document currency cents
    freight INTEGER NOT NULL DEFAULT 0, insurance INTEGER NOT NULL DEFAULT 0,
    kurs INTEGER,                                           -- customs exchange rate x 100000
    fees INTEGER NOT NULL DEFAULT 0,                        -- other customs fees EGP cents
    status TEXT NOT NULL DEFAULT 'DRAFT',
    d_acid TEXT, d_arrival TEXT, d_submitted TEXT, d_inspection TEXT, d_assessed TEXT, d_paid TEXT,
    d_released TEXT, d_shipped TEXT, free_days INTEGER NOT NULL DEFAULT 4,
    pay_belnr TEXT, text TEXT, usnam TEXT, ts TEXT,
    regime TEXT NOT NULL DEFAULT 'HOME');                 -- HOME (duty paid) / TA (temporary admission)
CREATE INDEX IF NOT EXISTS ix_cus_decl ON cus_decl (status);
CREATE TABLE IF NOT EXISTS cus_item (
    declno TEXT, pos INTEGER, matnr TEXT, text TEXT, hs TEXT, qty INTEGER, meins TEXT,
    value_fc INTEGER,                                      -- goods value of the line, document currency
    cif INTEGER, duty_pct INTEGER, duty INTEGER, vat_pct INTEGER, vat INTEGER,   -- EGP cents
    PRIMARY KEY (declno, pos));
CREATE TABLE IF NOT EXISTS cus_ta (              -- temporary admission balance per import line
    declno TEXT, pos INTEGER, matnr TEXT, qty INTEGER, discharged INTEGER NOT NULL DEFAULT 0,
    duty INTEGER, vat INTEGER,                              -- suspended amounts of the whole line (EGP cents)
    released TEXT, deadline TEXT, status TEXT NOT NULL DEFAULT 'OPEN',   -- OPEN / DONE / HOME
    home_qty INTEGER, home_day TEXT, home_belnr TEXT, PRIMARY KEY (declno, pos));
CREATE TABLE IF NOT EXISTS cus_ta_use (          -- export declarations that discharged a balance
    id INTEGER PRIMARY KEY AUTOINCREMENT, exp_declno TEXT, declno TEXT, pos INTEGER, matnr TEXT, qty INTEGER,
    day TEXT, ts TEXT);
"""


def install(conn):
    conn.executescript(CUSTOMS_SCHEMA)
    if "regime" not in {r[1] for r in conn.execute("PRAGMA table_info(cus_decl)")}:
        conn.execute("ALTER TABLE cus_decl ADD COLUMN regime TEXT NOT NULL DEFAULT 'HOME'")
    conn.execute("INSERT OR IGNORE INTO number_range VALUES ('CUSTOMS', 26000)")
    for k, v in (("storage_egp_day", "1500"), ("free_days", "4"), ("default_broker", ""), ("ta_months", "12"),
                 ("ta_warn_days", "60")):
        conn.execute("INSERT OR IGNORE INTO cus_setting VALUES (?,?)", (k, v))
