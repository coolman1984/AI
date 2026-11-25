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
    pay_belnr TEXT, text TEXT, usnam TEXT, ts TEXT);
CREATE INDEX IF NOT EXISTS ix_cus_decl ON cus_decl (status);
CREATE TABLE IF NOT EXISTS cus_item (
    declno TEXT, pos INTEGER, matnr TEXT, text TEXT, hs TEXT, qty INTEGER, meins TEXT,
    value_fc INTEGER,                                      -- goods value of the line, document currency
    cif INTEGER, duty_pct INTEGER, duty INTEGER, vat_pct INTEGER, vat INTEGER,   -- EGP cents
    PRIMARY KEY (declno, pos));
"""


def install(conn):
    conn.executescript(CUSTOMS_SCHEMA)
    conn.execute("INSERT OR IGNORE INTO number_range VALUES ('CUSTOMS', 26000)")
    for k, v in (("storage_egp_day", "1500"), ("free_days", "4"), ("default_broker", "")):
        conn.execute("INSERT OR IGNORE INTO cus_setting VALUES (?,?)", (k, v))
