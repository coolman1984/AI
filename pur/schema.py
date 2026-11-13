"""Procurement tables (EBAN, EINA/EINE, EORD, EQUP, EKKO/EKPO extensions, ...)."""

PUR_COLUMN_ADDS = {
    "po_header": [("bsart", "TEXT DEFAULT 'NB'"), ("ekorg", "TEXT DEFAULT '1000'"),
                  ("ekgrp", "TEXT DEFAULT '001'"), ("frgke", "TEXT DEFAULT ''"),
                  ("frgzu", "TEXT DEFAULT ''"), ("frgst", "TEXT DEFAULT ''"),
                  ("angnr", "TEXT"), ("zterm", "TEXT"), ("waers", "TEXT DEFAULT 'EGP'"),
                  ("printed", "INTEGER DEFAULT 0"), ("rfq_reason", "TEXT DEFAULT ''"),
                  ("ihrez", "TEXT")],                     # your reference (legacy PO number)
    "po_item": [("eindt", "TEXT"), ("knttp", "TEXT DEFAULT ''"), ("kostl", "TEXT"),
                ("aufnr", "TEXT"), ("sakto", "TEXT"), ("txz01", "TEXT"),
                ("matkl", "TEXT"), ("meins", "TEXT"), ("banfn", "TEXT"),
                ("bnfpo", "INTEGER"), ("konnr", "TEXT"), ("ktpnr", "INTEGER"),
                ("infnr", "TEXT"), ("brtwr", "INTEGER DEFAULT 0"),
                ("rabatt", "INTEGER DEFAULT 0"), ("frb", "INTEGER DEFAULT 0"),
                ("loekz", "INTEGER DEFAULT 0")],
    "material_plant": [("dismm", "TEXT DEFAULT 'VB'"), ("mabst", "INTEGER DEFAULT 0"),
                       ("bstfe", "INTEGER DEFAULT 0"), ("disls", "TEXT DEFAULT 'HB'"),
                       ("plifz", "INTEGER DEFAULT 7"), ("ekgrp", "TEXT DEFAULT '001'")],
}

PUR_SCHEMA = """
CREATE TABLE IF NOT EXISTS pur_ekgrp (       -- OME4 purchasing groups added by the customer
    ekgrp TEXT PRIMARY KEY, text TEXT);
CREATE TABLE IF NOT EXISTS pr_item (        -- EBAN purchase requisition
    banfn TEXT, bnfpo INTEGER, bsart TEXT DEFAULT 'NB', matnr TEXT, txz01 TEXT,
    matkl TEXT, menge INTEGER NOT NULL, meins TEXT, werks TEXT, lgort TEXT,
    lfdat TEXT, ekgrp TEXT, knttp TEXT DEFAULT '', kostl TEXT, aufnr TEXT,
    sakto TEXT, preis INTEGER NOT NULL DEFAULT 0, peinh INTEGER DEFAULT 1,
    afnam TEXT, estkz TEXT DEFAULT 'R', statu TEXT NOT NULL DEFAULT 'N',
    frgst TEXT DEFAULT '', frgzu TEXT DEFAULT '', lifnr TEXT, flief TEXT,
    konnr TEXT, ktpnr INTEGER, infnr TEXT, ebeln TEXT, ebelp INTEGER,
    badat TEXT, ernam TEXT, PRIMARY KEY (banfn, bnfpo));
CREATE TABLE IF NOT EXISTS info_record (    -- EINA / EINE
    infnr TEXT PRIMARY KEY, lifnr TEXT NOT NULL, matnr TEXT NOT NULL,
    ekorg TEXT DEFAULT '1000', werks TEXT DEFAULT '1000',
    brutto INTEGER NOT NULL,                -- PB00 gross price (cents / peinh)
    rabatt INTEGER NOT NULL DEFAULT 0,      -- RA01 discount, 1/100 %
    frb INTEGER NOT NULL DEFAULT 0,         -- FRB1 freight per order item
    peinh INTEGER NOT NULL DEFAULT 1, aplfz INTEGER NOT NULL DEFAULT 7,
    norbm INTEGER DEFAULT 0, minbm INTEGER DEFAULT 0, idnlf TEXT,
    datab TEXT, ebeln TEXT, ebelp INTEGER, loekz INTEGER DEFAULT 0,
    UNIQUE (lifnr, matnr, ekorg, werks));
CREATE TABLE IF NOT EXISTS source_list (    -- EORD (ME01)
    matnr TEXT, werks TEXT, zeord INTEGER, lifnr TEXT, vdatu TEXT, bdatu TEXT,
    flifn INTEGER DEFAULT 0, notkz INTEGER DEFAULT 0, konnr TEXT,
    PRIMARY KEY (matnr, werks, zeord));
CREATE TABLE IF NOT EXISTS quota (          -- EQUK / EQUP (MEQ1)
    matnr TEXT, werks TEXT, lifnr TEXT, quote INTEGER NOT NULL,
    qubmg INTEGER NOT NULL DEFAULT 0, basmg INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (matnr, werks, lifnr));
CREATE TABLE IF NOT EXISTS contract (       -- EKKO type K (ME31K)
    konnr TEXT PRIMARY KEY, bsart TEXT, lifnr TEXT, ekorg TEXT, ekgrp TEXT,
    kdatb TEXT, kdate TEXT, ktwrt INTEGER DEFAULT 0, zterm TEXT, ernam TEXT,
    erdat TEXT, loekz INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS contract_item (  -- EKPO of contract
    konnr TEXT, ktpnr INTEGER, matnr TEXT, werks TEXT, ktmng INTEGER,
    netpr INTEGER, peinh INTEGER DEFAULT 1, PRIMARY KEY (konnr, ktpnr));
CREATE TABLE IF NOT EXISTS rfq (            -- EKKO type A (ME41 / ME47)
    anfnr TEXT PRIMARY KEY, submi TEXT, lifnr TEXT, matnr TEXT, werks TEXT,
    menge INTEGER, lfdat TEXT, angdt TEXT, ekgrp TEXT, netpr INTEGER,
    peinh INTEGER DEFAULT 1, aplfz INTEGER, quodt TEXT, statu TEXT DEFAULT 'O',
    banfn TEXT, bnfpo INTEGER, ebeln TEXT, ernam TEXT, erdat TEXT);
CREATE TABLE IF NOT EXISTS release_log (    -- release history (PR / PO)
    id INTEGER PRIMARY KEY AUTOINCREMENT, objtyp TEXT, objkey TEXT,
    frgco TEXT, action TEXT, usnam TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS mrp_run (        -- MD01 log
    id INTEGER PRIMARY KEY AUTOINCREMENT, werks TEXT, rundt TEXT,
    result TEXT, usnam TEXT, ts TEXT);
"""

PUR_NUMBER_RANGES = {"PR": 10000000, "INFO": 5300000000, "CONTRACT": 4600000000,
                     "RFQ": 6000000000, "SUBMI": 1}
