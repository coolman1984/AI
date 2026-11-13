"""Master data tables (MARA/MARC/MARD/MARM/MVKE/MLGN, KNA1/KNB1/KNVV/KNVP,
LFA1/LFB1/LFM1, CDHDR/CDPOS, J_1IMTCHID / J_1IMOCUST / J_1IMOVEND)."""

MD_COLUMN_ADDS = {
    "material": [  # MARA
        ("mbrsh", "TEXT DEFAULT 'M'"), ("spart", "TEXT DEFAULT '00'"),
        ("mtpos_mara", "TEXT DEFAULT 'NORM'"), ("brgew", "INTEGER DEFAULT 0"),
        ("ntgew", "INTEGER DEFAULT 0"), ("gewei", "TEXT DEFAULT 'KG'"),
        ("volum", "INTEGER DEFAULT 0"), ("voleh", "TEXT DEFAULT ''"),
        ("ean11", "TEXT DEFAULT ''"), ("bismt", "TEXT DEFAULT ''"),
        ("mstae", "TEXT DEFAULT ''"), ("lvorm", "INTEGER DEFAULT 0"),
        ("prdha", "TEXT DEFAULT ''"), ("raube", "TEXT DEFAULT ''"),
        ("tempb", "TEXT DEFAULT ''"), ("mhdhb", "INTEGER DEFAULT 0"),
        ("mhdrz", "INTEGER DEFAULT 0"), ("vpsta", "TEXT DEFAULT ''"),
        ("laeda", "TEXT"), ("aenam", "TEXT")],
    "material_plant": [  # MARC
        ("mmsta", "TEXT DEFAULT ''"), ("lvorm", "INTEGER DEFAULT 0"),
        ("insmk", "INTEGER DEFAULT 0"), ("webaz", "INTEGER DEFAULT 0"),
        ("uebto", "INTEGER DEFAULT 0"), ("untto", "INTEGER DEFAULT 0"),
        ("kordb", "INTEGER DEFAULT 0"), ("dispo", "TEXT DEFAULT ''"),
        ("beskz", "TEXT DEFAULT 'F'"), ("dzeit", "INTEGER DEFAULT 0"),
        ("mtvfp", "TEXT DEFAULT '02'"), ("lgfsb", "TEXT DEFAULT ''"),
        ("lgpro", "TEXT DEFAULT ''"), ("prctr", "TEXT DEFAULT ''"),
        ("ncost", "INTEGER DEFAULT 0"), ("losgr", "INTEGER DEFAULT 0"),
        ("awsls", "TEXT DEFAULT ''"), ("qmatv", "INTEGER DEFAULT 0"),
        ("ssqss", "TEXT DEFAULT ''"), ("vpsta", "TEXT DEFAULT ''"),
        ("abcin", "TEXT DEFAULT ''")],
    "valuation": [  # MBEW
        ("zplp1", "INTEGER DEFAULT 0"), ("zpld1", "TEXT"),
        ("bwprh", "INTEGER DEFAULT 0"), ("bwph1", "INTEGER DEFAULT 0"),
        ("hrkft", "TEXT DEFAULT ''")],
    "customer": [  # KNA1 / KNB1
        ("ktokd", "TEXT DEFAULT '0001'"), ("name2", "TEXT DEFAULT ''"),
        ("street", "TEXT DEFAULT ''"), ("pstlz", "TEXT DEFAULT ''"),
        ("telf1", "TEXT DEFAULT ''"), ("email", "TEXT DEFAULT ''"),
        ("stceg", "TEXT DEFAULT ''"), ("bankn", "TEXT DEFAULT ''"),
        ("bankl", "TEXT DEFAULT ''"), ("sperr", "INTEGER DEFAULT 0"),
        ("aufsd", "TEXT DEFAULT ''"), ("lifsd", "TEXT DEFAULT ''"),
        ("faksd", "TEXT DEFAULT ''"), ("loevm", "INTEGER DEFAULT 0"),
        ("mahna", "TEXT DEFAULT ''"), ("busab", "TEXT DEFAULT ''"),
        ("zwels", "TEXT DEFAULT 'T'"), ("xzver", "INTEGER DEFAULT 0"),
        ("erdat", "TEXT"), ("ernam", "TEXT")],
    "vendor": [  # LFA1 / LFB1 / LFM1
        ("altkn", "TEXT"),                  # LFB1-ALTKN previous (legacy) account number
        ("name2", "TEXT DEFAULT ''"), ("street", "TEXT DEFAULT ''"),
        ("pstlz", "TEXT DEFAULT ''"), ("telf1", "TEXT DEFAULT ''"),
        ("email", "TEXT DEFAULT ''"), ("stceg", "TEXT DEFAULT ''"),
        ("bankl", "TEXT DEFAULT ''"), ("iban", "TEXT DEFAULT ''"),
        ("swift", "TEXT DEFAULT ''"), ("sperm", "INTEGER DEFAULT 0"),
        ("loevm", "INTEGER DEFAULT 0"), ("zahls", "TEXT DEFAULT ''"),
        ("zwels", "TEXT DEFAULT 'T'"), ("reprf", "INTEGER DEFAULT 1"),
        ("witht", "TEXT DEFAULT ''"), ("busab", "TEXT DEFAULT ''"),
        ("ekorg", "TEXT DEFAULT '1000'"), ("minbw", "INTEGER DEFAULT 0"),
        ("webre", "INTEGER DEFAULT 1"), ("verkf", "TEXT DEFAULT ''"),
        ("lfabc", "TEXT DEFAULT ''"), ("ekgrp", "TEXT DEFAULT ''"),
        ("plifz", "INTEGER DEFAULT 0"), ("inco1", "TEXT DEFAULT ''"),
        ("inco2", "TEXT DEFAULT ''"), ("erdat", "TEXT"), ("ernam", "TEXT")],
}

MD_SCHEMA = """
CREATE TABLE IF NOT EXISTS md_matgroup (    -- OMSF material groups added by the customer (data takeover)
    matkl TEXT PRIMARY KEY, text TEXT);
CREATE TABLE IF NOT EXISTS md_marm (         -- MARM units of measure
    matnr TEXT, meinh TEXT, umrez INTEGER NOT NULL, umren INTEGER NOT NULL,
    ean11 TEXT DEFAULT '', PRIMARY KEY (matnr, meinh));
CREATE TABLE IF NOT EXISTS md_mard (         -- MARD storage location data
    matnr TEXT, werks TEXT, lgort TEXT, lgpbe TEXT DEFAULT '',
    auto INTEGER DEFAULT 0, ersda TEXT, PRIMARY KEY (matnr, werks, lgort));
CREATE TABLE IF NOT EXISTS md_mvke (         -- MVKE sales org data + MLAN tax
    matnr TEXT, vkorg TEXT, vtweg TEXT, dwerk TEXT, ktgrm TEXT, mtpos TEXT,
    aumng INTEGER DEFAULT 0, vmsta TEXT DEFAULT '', kondm TEXT DEFAULT '',
    versg TEXT DEFAULT '1', taxm1 TEXT DEFAULT '1', kbetr INTEGER DEFAULT 0,
    PRIMARY KEY (matnr, vkorg, vtweg));
CREATE TABLE IF NOT EXISTS md_mlgn (         -- MLGN warehouse data
    matnr TEXT, lgnum TEXT, ltkze TEXT, ltkza TEXT, lhmg1 INTEGER DEFAULT 0,
    lety1 TEXT DEFAULT '', PRIMARY KEY (matnr, lgnum));
CREATE TABLE IF NOT EXISTS md_exim (         -- foreign trade / legal control
    matnr TEXT PRIMARY KEY, stawn TEXT, herkl TEXT, herkr TEXT DEFAULT '',
    impctl TEXT DEFAULT '', expctl TEXT DEFAULT '', lic_no TEXT DEFAULT '',
    lic_valid TEXT DEFAULT '', duty INTEGER DEFAULT 0, prefz TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS md_cin_mat (      -- J_1IMTCHID
    matnr TEXT, werks TEXT, chapid TEXT, mtype TEXT, hsn TEXT,
    gst INTEGER DEFAULT 0, subcon INTEGER DEFAULT 0, PRIMARY KEY (matnr, werks));
CREATE TABLE IF NOT EXISTS md_cin_cust (     -- J_1IMOCUST
    kunnr TEXT PRIMARY KEY, gstin TEXT, pan TEXT, excise_reg TEXT DEFAULT '',
    ecc_no TEXT DEFAULT '', cst_no TEXT DEFAULT '', exempt INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS md_cin_vend (     -- J_1IMOVEND
    lifnr TEXT PRIMARY KEY, gstin TEXT, pan TEXT, vtype TEXT, ssi TEXT DEFAULT '',
    excise_reg TEXT DEFAULT '', ecc_no TEXT DEFAULT '', cenvat INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS md_br_mat (       -- Brazil: NCM, usage, origin
    matnr TEXT, werks TEXT, steuc TEXT, mtuse TEXT, mtorg TEXT,
    cfop_cat TEXT DEFAULT '', PRIMARY KEY (matnr, werks));
CREATE TABLE IF NOT EXISTS md_knvv (         -- KNVV customer sales area
    kunnr TEXT, vkorg TEXT, vtweg TEXT, spart TEXT, bzirk TEXT, kdgrp TEXT,
    konda TEXT, kalks TEXT, vsbed TEXT, vwerk TEXT, inco1 TEXT, inco2 TEXT,
    zterm TEXT, ktgrd TEXT, taxkd TEXT, waers TEXT, PRIMARY KEY (kunnr, vkorg, vtweg, spart));
CREATE TABLE IF NOT EXISTS md_knvp (         -- KNVP partner functions
    kunnr TEXT, vkorg TEXT, vtweg TEXT, parvw TEXT, kunn2 TEXT,
    PRIMARY KEY (kunnr, vkorg, vtweg, parvw, kunn2));
CREATE TABLE IF NOT EXISTS md_cdhdr (        -- CDHDR change document header
    changenr INTEGER PRIMARY KEY, objectclas TEXT, objectid TEXT, username TEXT,
    udate TEXT, utime TEXT, tcode TEXT, change_ind TEXT);
CREATE INDEX IF NOT EXISTS ix_cdhdr ON md_cdhdr (objectclas, objectid);
CREATE TABLE IF NOT EXISTS md_cdpos (        -- CDPOS change document items
    changenr INTEGER, tabname TEXT, tabkey TEXT, fname TEXT, chngind TEXT,
    value_old TEXT, value_new TEXT);
CREATE INDEX IF NOT EXISTS ix_cdpos ON md_cdpos (changenr);
CREATE TABLE IF NOT EXISTS md_sensitive (    -- FK08/FD08 dual control
    id INTEGER PRIMARY KEY AUTOINCREMENT, koart TEXT, objectid TEXT,
    changenr INTEGER, fields TEXT, changed_by TEXT, changed_at TEXT,
    status TEXT DEFAULT 'P', confirmed_by TEXT, confirmed_at TEXT);
"""
