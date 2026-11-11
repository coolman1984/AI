"""SD tables: VBAK/VBAP/VBEP/KONV/VBFA, LIKP/LIPS, A-tables + KONP, deals,
activities, equipment, notifications, e-invoices. Billing uses the existing
VBRK/VBRP tables (billing / billing_item) with additional fields."""

SD_COLUMN_ADDS = {
    "sd_vbak": [("cmfre", "TEXT"),           # date of the last credit release (VKM1)
                # document currency (customer currency): rate at the pricing date + values in it
                ("kursk", "INTEGER"), ("netwr_fc", "INTEGER DEFAULT 0"), ("mwsbk_fc", "INTEGER DEFAULT 0")],
    "sd_vbap": [("kzwi1_fc", "INTEGER"), ("kzwi2_fc", "INTEGER"), ("freight_fc", "INTEGER"),
                ("netwr_fc", "INTEGER"), ("mwsbp_fc", "INTEGER"), ("netpr_fc", "INTEGER")],
    "billing": [("fkart", "TEXT DEFAULT 'F2'"), ("vbtyp", "TEXT DEFAULT 'M'"), ("vgbel", "TEXT"),
                ("kunrg", "TEXT"), ("zterm", "TEXT"), ("mwsbk", "INTEGER DEFAULT 0"),
                ("waerk", "TEXT DEFAULT 'EGP'"), ("rfbsk", "TEXT DEFAULT 'C'"), ("sfakn", "TEXT"),
                ("vkorg", "TEXT DEFAULT '1000'"), ("vtweg", "TEXT"), ("eta_uuid", "TEXT"),
                ("eta_status", "TEXT"), ("aubel", "TEXT"), ("kurrf", "INTEGER"),
                ("netwr_fc", "INTEGER"), ("mwsbk_fc", "INTEGER")],
    "billing_item": [("vgbel", "TEXT"), ("vgpos", "INTEGER"), ("aubel", "TEXT"),
                     ("aupos", "INTEGER"), ("pstyv", "TEXT"), ("mwsbp", "INTEGER DEFAULT 0"),
                     ("freight", "INTEGER DEFAULT 0"), ("arktx", "TEXT"), ("gross_fc", "INTEGER"),
                     ("disc_fc", "INTEGER"), ("freight_fc", "INTEGER"), ("net_fc", "INTEGER")],
}

SD_SCHEMA = """
CREATE TABLE IF NOT EXISTS sd_vbak (        -- VBAK sales document header
    vbeln TEXT PRIMARY KEY, auart TEXT, vbtyp TEXT, vkorg TEXT, vtweg TEXT, spart TEXT,
    kunnr TEXT, kunwe TEXT, kunrg TEXT, bstnk TEXT, audat TEXT, vdatu TEXT, prsdt TEXT,
    bnddt TEXT, zterm TEXT, inco1 TEXT, inco2 TEXT, kalsm TEXT, waerk TEXT DEFAULT 'EGP',
    netwr INTEGER DEFAULT 0, mwsbk INTEGER DEFAULT 0, vgbel TEXT, vgtyp TEXT, augru TEXT,
    faksk TEXT DEFAULT '', lifsk TEXT DEFAULT '', cmgst TEXT DEFAULT '', gbstk TEXT DEFAULT 'A',
    prob INTEGER DEFAULT 0, kostl TEXT, ernam TEXT, erdat TEXT, credit_note TEXT);
CREATE TABLE IF NOT EXISTS sd_vbap (        -- VBAP items
    vbeln TEXT, posnr INTEGER, matnr TEXT, arktx TEXT, pstyv TEXT, kwmeng INTEGER,
    vrkme TEXT, werks TEXT, lgort TEXT, vstel TEXT DEFAULT '1000', netwr INTEGER DEFAULT 0,
    netpr INTEGER DEFAULT 0, mwsbp INTEGER DEFAULT 0, wavwr INTEGER DEFAULT 0,
    kzwi1 INTEGER DEFAULT 0, kzwi2 INTEGER DEFAULT 0, freight INTEGER DEFAULT 0,
    abgru TEXT DEFAULT '', vgbel TEXT, vgpos INTEGER, kdmat TEXT, equnr TEXT,
    PRIMARY KEY (vbeln, posnr));
CREATE TABLE IF NOT EXISTS sd_vbep (        -- VBEP schedule lines
    vbeln TEXT, posnr INTEGER, etenr INTEGER, edatu TEXT, wmeng INTEGER, bmeng INTEGER,
    mbdat TEXT, ettyp TEXT, PRIMARY KEY (vbeln, posnr, etenr));
CREATE TABLE IF NOT EXISTS sd_konv (        -- KONV conditions of a document item
    knumv TEXT, kposn INTEGER, stunr INTEGER, kschl TEXT, krech TEXT, kbetr INTEGER,
    kpein INTEGER DEFAULT 1, kwert INTEGER, kinak TEXT DEFAULT '', manual INTEGER DEFAULT 0,
    knumh INTEGER, PRIMARY KEY (knumv, kposn, stunr));
CREATE TABLE IF NOT EXISTS sd_vbfa (        -- VBFA document flow
    vbelv TEXT, posnv INTEGER, vbeln TEXT, posnn INTEGER, vbtyp_v TEXT, vbtyp_n TEXT,
    rfmng INTEGER, rfwrt INTEGER, erdat TEXT);
CREATE INDEX IF NOT EXISTS ix_vbfa_v ON sd_vbfa (vbelv);
CREATE INDEX IF NOT EXISTS ix_vbfa_n ON sd_vbfa (vbeln);
CREATE TABLE IF NOT EXISTS sd_likp (        -- LIKP delivery header
    vbeln TEXT PRIMARY KEY, lfart TEXT, vstel TEXT, kunnr TEXT, kunag TEXT, lfdat TEXT,
    wadat TEXT, wadat_ist TEXT, kostk TEXT DEFAULT 'A', wbstk TEXT DEFAULT 'A',
    fkstk TEXT DEFAULT 'A', mblnr TEXT, mjahr INTEGER, btgew INTEGER DEFAULT 0,
    ernam TEXT, erdat TEXT, vgbel TEXT);
CREATE TABLE IF NOT EXISTS sd_lips (        -- LIPS delivery items
    vbeln TEXT, posnr INTEGER, matnr TEXT, arktx TEXT, lfimg INTEGER, pikmg INTEGER DEFAULT 0,
    werks TEXT, lgort TEXT, lgpla TEXT DEFAULT '', vgbel TEXT, vgpos INTEGER, pstyv TEXT,
    cogs INTEGER DEFAULT 0, PRIMARY KEY (vbeln, posnr));
CREATE TABLE IF NOT EXISTS sd_cond (        -- A-tables + KONH/KONP condition records
    knumh INTEGER PRIMARY KEY AUTOINCREMENT, kschl TEXT, kotab TEXT, vkorg TEXT, vtweg TEXT,
    kunnr TEXT, matnr TEXT, inco1 TEXT, datab TEXT, datbi TEXT, kbetr INTEGER,
    konwa TEXT, kpein INTEGER DEFAULT 1, scales TEXT DEFAULT '', loevm INTEGER DEFAULT 0,
    knuma TEXT, ernam TEXT, erdat TEXT);
CREATE INDEX IF NOT EXISTS ix_cond ON sd_cond (kschl, kotab);
CREATE TABLE IF NOT EXISTS sd_listing (     -- material listing / exclusion (VB01)
    kunnr TEXT, matnr TEXT, kind TEXT, datab TEXT, datbi TEXT, PRIMARY KEY (kunnr, matnr, kind));
CREATE TABLE IF NOT EXISTS sd_custmat (     -- VD51 customer-material info record
    kunnr TEXT, matnr TEXT, kdmat TEXT, postx TEXT, PRIMARY KEY (kunnr, matnr));
CREATE TABLE IF NOT EXISTS sd_deal (        -- VB21 sales deals / promotions
    knuma TEXT PRIMARY KEY, botext TEXT, datab TEXT, datbi TEXT, budget INTEGER DEFAULT 0,
    status TEXT DEFAULT 'A', ernam TEXT);
CREATE TABLE IF NOT EXISTS sd_activity (    -- VC01N sales activities
    id INTEGER PRIMARY KEY AUTOINCREMENT, kunnr TEXT, ktaar TEXT, datum TEXT, subject TEXT,
    result TEXT, vbeln TEXT, followup TEXT, usnam TEXT, status TEXT DEFAULT 'C');
CREATE TABLE IF NOT EXISTS sd_equi (        -- IE01 equipment (installed base)
    equnr TEXT PRIMARY KEY, matnr TEXT, sernr TEXT, kunnr TEXT, inbdt TEXT, gwlen TEXT,
    vbeln TEXT, lieferung TEXT, status TEXT DEFAULT 'INST', eqktx TEXT);
CREATE TABLE IF NOT EXISTS sd_qmel (        -- IW51 service notification
    qmnum TEXT PRIMARY KEY, qmart TEXT, equnr TEXT, kunnr TEXT, matnr TEXT, qmtxt TEXT,
    erdat TEXT, priok TEXT, warranty INTEGER DEFAULT 0, aufnr TEXT, status TEXT DEFAULT 'OSNO',
    billed TEXT, ernam TEXT);
CREATE TABLE IF NOT EXISTS sd_einv (        -- e-invoice (Egyptian Tax Authority) log
    vbeln TEXT PRIMARY KEY, uuid TEXT, payload TEXT, status TEXT, ts TEXT);
"""

SD_NUMBER_RANGES = {"INQ": 10000000, "QUOT": 20000000, "SORD": 30000000, "RET": 60000000,
                    "DLV": 80000000, "EQUI": 10000000, "QMEL": 300000000}
