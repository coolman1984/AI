"""FI tables and the extra FI fields on existing tables (BKPF/BSEG, LFA1, KNA1)."""

FI_COLUMN_ADDS = {
    "acc_doc": [("waers", "TEXT"), ("kursf", "INTEGER"), ("xblnr", "TEXT"),
                ("bldat", "TEXT"), ("monat", "INTEGER"), ("tcode", "TEXT"),
                ("stblg", "TEXT"), ("stgrd", "TEXT"), ("stodt", "TEXT")],
    "acc_doc_item": [("koart", "TEXT"), ("bschl", "TEXT"), ("lifnr", "TEXT"),
                     ("kunnr", "TEXT"), ("anln1", "TEXT"), ("anbwa", "TEXT"),
                     ("mwskz", "TEXT"), ("txbase", "INTEGER"), ("wrbtr", "INTEGER"),
                     ("zfbdt", "TEXT"), ("zterm", "TEXT"), ("zbd1t", "INTEGER"),
                     ("zbd1p", "INTEGER"), ("netdt", "TEXT"), ("augbl", "TEXT"),
                     ("augdt", "TEXT"), ("zuonr", "TEXT"), ("sgtxt", "TEXT"),
                     ("ebeln", "TEXT"), ("ebelp", "INTEGER"), ("manst", "INTEGER"),
                     ("madat", "TEXT"), ("rebzg", "TEXT")],
    "vendor": [("ktokk", "TEXT"), ("akont", "TEXT"), ("zterm", "TEXT"),
               ("waers", "TEXT"), ("stcd1", "TEXT"), ("bankn", "TEXT"),
               ("land", "TEXT"), ("sperr", "INTEGER")],
    "customer": [("akont", "TEXT"), ("zterm", "TEXT"), ("klimk", "INTEGER"),
                 ("stcd1", "TEXT"), ("land", "TEXT")],
    "po_item": [("remng", "INTEGER NOT NULL DEFAULT 0"),
                ("reewr", "INTEGER NOT NULL DEFAULT 0")],
}

FI_SCHEMA = """
CREATE INDEX IF NOT EXISTS ix_bseg_open ON acc_doc_item (koart, augbl);
CREATE TABLE IF NOT EXISTS gl_account (     -- SKA1/SKB1 (FS00)
    hkont TEXT PRIMARY KEY, txt TEXT NOT NULL, typ TEXT NOT NULL,
    fsv TEXT, recon TEXT, oi INTEGER NOT NULL DEFAULT 0, tax TEXT,
    blocked INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS posting_period ( -- OB52 (variant 1000, account type +)
    id INTEGER PRIMARY KEY, y1 INTEGER, p1 INTEGER, y2 INTEGER, p2 INTEGER);
CREATE TABLE IF NOT EXISTS fi_carry_forward ( -- F.16 balance carry-forward runs
    gjahr INTEGER PRIMARY KEY, amount INTEGER, hkont TEXT, run_at TEXT, usnam TEXT);
CREATE TABLE IF NOT EXISTS exch_rate (      -- TCURR (OB08), type M
    waers TEXT, gdatu TEXT, ukurs INTEGER, PRIMARY KEY (waers, gdatu));
CREATE TABLE IF NOT EXISTS asset (          -- ANLA / ANLZ / ANLB
    anln1 TEXT PRIMARY KEY, anlkl TEXT NOT NULL, txt TEXT NOT NULL,
    kostl TEXT, aktiv TEXT, afasl TEXT NOT NULL DEFAULT 'LINS',
    ndjar INTEGER NOT NULL, invnr TEXT, lifnr TEXT, deakt TEXT,
    erdat TEXT, ernam TEXT);
CREATE TABLE IF NOT EXISTS asset_item (     -- ANEP / ANLP
    id INTEGER PRIMARY KEY AUTOINCREMENT, anln1 TEXT, belnr TEXT, gjahr INTEGER,
    perio INTEGER, budat TEXT, bwasl TEXT, apc INTEGER NOT NULL DEFAULT 0,
    dep INTEGER NOT NULL DEFAULT 0, txt TEXT);
CREATE INDEX IF NOT EXISTS ix_anep ON asset_item (anln1, gjahr, perio);
CREATE TABLE IF NOT EXISTS payrun (         -- F110 REGUH
    laufi TEXT, laufd TEXT, nextd TEXT, status TEXT, proposal TEXT,
    docs TEXT, usnam TEXT, ts TEXT, PRIMARY KEY (laufd, laufi));
CREATE TABLE IF NOT EXISTS dunning_run (    -- F150 MHNK
    id INTEGER PRIMARY KEY AUTOINCREMENT, ausdt TEXT, status TEXT,
    result TEXT, usnam TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS bank_statement ( -- FF67 FEBKO/FEBEP
    id INTEGER PRIMARY KEY AUTOINCREMENT, hbkid TEXT, azdat TEXT, aznum TEXT,
    ssbtr INTEGER, esbtr INTEGER, lines TEXT, docs TEXT, usnam TEXT, ts TEXT);
"""

FI_NUMBER_RANGE_PREFIX = "FI_"
