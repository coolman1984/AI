"""CO tables. Names follow SAP where useful (CSKA/CSKS/CSLA/COEP/AUFK/...)."""

CO_SCHEMA = """
CREATE TABLE IF NOT EXISTS cost_element (   -- CSKA/CSKB
    kstar TEXT PRIMARY KEY, ktext TEXT NOT NULL, katyp INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS cc_group (       -- standard hierarchy (OKEON)
    khinr TEXT PRIMARY KEY, ktext TEXT, parent TEXT);
CREATE TABLE IF NOT EXISTS activity_type (  -- CSLA
    lstar TEXT PRIMARY KEY, ktext TEXT NOT NULL, meinh TEXT NOT NULL,
    kstar TEXT NOT NULL,
    ccomp INTEGER NOT NULL DEFAULT 30);     -- cost component in costing
CREATE TABLE IF NOT EXISTS stat_kf (        -- TKA03
    stagr TEXT PRIMARY KEY, ktext TEXT NOT NULL, meinh TEXT, fixed INTEGER);
CREATE TABLE IF NOT EXISTS default_aa (     -- OKB9
    kstar TEXT PRIMARY KEY, kostl TEXT);
CREATE TABLE IF NOT EXISTS cc_activity (    -- COST/CSSL: activity plan & prices
    gjahr INTEGER, perio INTEGER, kostl TEXT, lstar TEXT,
    plan_qty INTEGER NOT NULL DEFAULT 0,    -- milli
    capacity INTEGER NOT NULL DEFAULT 0,    -- milli
    price_fix INTEGER NOT NULL DEFAULT 0,   -- cents per unit (x1000 precision below)
    price_var INTEGER NOT NULL DEFAULT 0,
    price_ind TEXT NOT NULL DEFAULT '1',    -- 1 = calculated (KSPI), 3 = manual
    PRIMARY KEY (gjahr, perio, kostl, lstar));
CREATE TABLE IF NOT EXISTS skf_value (      -- statistical key figure values
    wrttp TEXT, gjahr INTEGER, perio INTEGER, kostl TEXT, stagr TEXT,
    value INTEGER NOT NULL,                 -- milli
    PRIMARY KEY (wrttp, gjahr, perio, kostl, stagr));
CREATE TABLE IF NOT EXISTS co_doc (         -- COBK
    belnr TEXT PRIMARY KEY, gjahr INTEGER, perio INTEGER, budat TEXT,
    vrgng TEXT, wrttp TEXT, bltxt TEXT, usnam TEXT, cpudt TEXT,
    refbn TEXT, run_id INTEGER, stflg INTEGER NOT NULL DEFAULT 0,
    stokz TEXT);
CREATE TABLE IF NOT EXISTS co_item (        -- COEP (actual 04 / plan 01)
    belnr TEXT, buzei INTEGER, gjahr INTEGER, perio INTEGER,
    wrttp TEXT NOT NULL, objnr TEXT NOT NULL, kstar TEXT NOT NULL,
    wtg INTEGER NOT NULL,                   -- value, cents, debit +
    wkf INTEGER NOT NULL DEFAULT 0,         -- fixed portion of value
    qty INTEGER NOT NULL DEFAULT 0,         -- milli
    meinh TEXT, lstar TEXT, parob TEXT, vrgng TEXT, matnr TEXT,
    budat TEXT, sgtxt TEXT,
    PRIMARY KEY (belnr, buzei));
CREATE INDEX IF NOT EXISTS ix_coep ON co_item (wrttp, gjahr, perio, objnr, kstar);
CREATE TABLE IF NOT EXISTS orders (         -- AUFK / AFKO
    aufnr TEXT PRIMARY KEY, auart TEXT NOT NULL, ktext TEXT,
    kostl TEXT,                             -- responsible cost center
    matnr TEXT, werks TEXT, lgort TEXT,
    gamng INTEGER NOT NULL DEFAULT 0,       -- planned qty (milli)
    wemng INTEGER NOT NULL DEFAULT 0,       -- delivered qty (milli)
    stat TEXT NOT NULL DEFAULT 'CRTD', erdat TEXT, ernam TEXT,
    estimate_id INTEGER, gjahr INTEGER, perio INTEGER);
CREATE TABLE IF NOT EXISTS settle_rule (    -- COBRB
    aufnr TEXT, lfdnr INTEGER, konty TEXT, receiver TEXT, prozs INTEGER,
    PRIMARY KEY (aufnr, lfdnr));
CREATE TABLE IF NOT EXISTS bom (            -- STKO/STPO (single level)
    matnr TEXT, werks TEXT, posnr INTEGER, idnrk TEXT,
    menge INTEGER NOT NULL,                 -- milli per base quantity
    basis INTEGER NOT NULL,                 -- base quantity milli
    PRIMARY KEY (matnr, werks, posnr));
CREATE TABLE IF NOT EXISTS work_center (    -- CRHD
    arbpl TEXT PRIMARY KEY, werks TEXT, ktext TEXT, kostl TEXT NOT NULL,
    lstar TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS routing (        -- PLKO/PLPO
    matnr TEXT, werks TEXT, vornr TEXT, arbpl TEXT, ltxa1 TEXT,
    vgw INTEGER NOT NULL,                   -- std value milli per base qty
    basis INTEGER NOT NULL,
    PRIMARY KEY (matnr, werks, vornr));
CREATE TABLE IF NOT EXISTS costing_sheet (  -- KZS2 (sheet COGS01)
    zeile INTEGER PRIMARY KEY, ktext TEXT, base TEXT NOT NULL,
    pct_fix INTEGER NOT NULL DEFAULT 0,     -- 1/100 percent (500 = 5.00 %)
    pct_var INTEGER NOT NULL DEFAULT 0,
    kostl TEXT NOT NULL,                    -- credit cost center
    kstar TEXT NOT NULL,                    -- overhead cost element (41)
    ccomp INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS cost_estimate (  -- KEKO
    id INTEGER PRIMARY KEY AUTOINCREMENT, matnr TEXT, werks TEXT,
    kadky TEXT, losgr INTEGER, total INTEGER, fixed INTEGER,
    status TEXT NOT NULL,                   -- KA costed, VO marked, FR released
    gjahr INTEGER, perio INTEGER, usnam TEXT, cpudt TEXT);
CREATE TABLE IF NOT EXISTS cost_estimate_item (  -- CKIS itemization
    id INTEGER, posnr INTEGER, typ TEXT, ressource TEXT, ktext TEXT,
    menge INTEGER, meinh TEXT, price INTEGER, peinh INTEGER,
    wert INTEGER, wkf INTEGER, ccomp INTEGER, kstar TEXT,
    PRIMARY KEY (id, posnr));
CREATE TABLE IF NOT EXISTS customer (       -- KNA1/KNVV
    kunnr TEXT PRIMARY KEY, name TEXT, city TEXT, region TEXT,
    kdgrp TEXT, vtweg TEXT);
CREATE TABLE IF NOT EXISTS billing (        -- VBRK
    vbeln TEXT PRIMARY KEY, fkdat TEXT, kunnr TEXT, netwr INTEGER,
    usnam TEXT, mblnr TEXT, mjahr INTEGER, belnr TEXT, copa TEXT,
    cancelled INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS billing_item (   -- VBRP
    vbeln TEXT, posnr INTEGER, matnr TEXT, werks TEXT, lgort TEXT,
    fkimg INTEGER, price INTEGER, disc_pct INTEGER, gross INTEGER,
    disc INTEGER, net INTEGER, cogs INTEGER,
    PRIMARY KEY (vbeln, posnr));
CREATE TABLE IF NOT EXISTS copa_plan_qty (  -- KE11 sales plan input
    gjahr INTEGER, perio INTEGER, kunnr TEXT, matnr TEXT,
    qty INTEGER, price INTEGER, disc_pct INTEGER,
    PRIMARY KEY (gjahr, perio, kunnr, matnr));
CREATE TABLE IF NOT EXISTS copa_item (      -- CE1EG01 (costing-based CO-PA)
    id INTEGER PRIMARY KEY AUTOINCREMENT, belnr TEXT, vrgar TEXT,
    plikz INTEGER NOT NULL DEFAULT 0, gjahr INTEGER, perio INTEGER,
    budat TEXT, kunnr TEXT, matnr TEXT, matkl TEXT, region TEXT,
    kdgrp TEXT, vtweg TEXT, werks TEXT, kostl TEXT, aufnr TEXT,
    refdoc TEXT, qty INTEGER NOT NULL DEFAULT 0, usnam TEXT,
    vv010 INTEGER NOT NULL DEFAULT 0, vv020 INTEGER NOT NULL DEFAULT 0,
    vv030 INTEGER NOT NULL DEFAULT 0, vv040 INTEGER NOT NULL DEFAULT 0,
    vv050 INTEGER NOT NULL DEFAULT 0, vv051 INTEGER NOT NULL DEFAULT 0,
    vv060 INTEGER NOT NULL DEFAULT 0, vv061 INTEGER NOT NULL DEFAULT 0,
    vv070 INTEGER NOT NULL DEFAULT 0, vv080 INTEGER NOT NULL DEFAULT 0,
    vv090 INTEGER NOT NULL DEFAULT 0, vv100 INTEGER NOT NULL DEFAULT 0,
    vv110 INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS ix_copa ON copa_item (plikz, gjahr, perio);
CREATE TABLE IF NOT EXISTS plan_act_input ( -- KP06 layout 1-102: activity input
    gjahr INTEGER, perio INTEGER, kostl TEXT, skostl TEXT, lstar TEXT,
    qty INTEGER NOT NULL, PRIMARY KEY (gjahr, perio, kostl, skostl, lstar));
CREATE TABLE IF NOT EXISTS order_variance ( -- KKS2 result (COSB-like)
    aufnr TEXT, gjahr INTEGER, perio INTEGER, kstar TEXT, ressource TEXT,
    target INTEGER, actual INTEGER, price_var INTEGER, qty_var INTEGER,
    res_var INTEGER, rem_var INTEGER,
    PRIMARY KEY (aufnr, gjahr, perio, kstar, ressource));
CREATE TABLE IF NOT EXISTS confirmation (   -- AFRU (CO11N)
    rueck INTEGER PRIMARY KEY AUTOINCREMENT, aufnr TEXT, vornr TEXT,
    arbpl TEXT, lmnga INTEGER, ism INTEGER, budat TEXT, codoc TEXT,
    usnam TEXT, stokz INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS cycle (          -- KSU1 / KSV1 / KEU1
    cycle TEXT PRIMARY KEY, ktext TEXT, typ TEXT NOT NULL,  -- D / A / P
    seq INTEGER NOT NULL DEFAULT 10);
CREATE TABLE IF NOT EXISTS cycle_segment (
    cycle TEXT, seg INTEGER, ktext TEXT,
    senders TEXT NOT NULL,       -- cost centers, comma separated
    sender_kstar TEXT,           -- distribution: cost elements to distribute
    kstar TEXT,                  -- assessment cost element (42)
    receivers TEXT,              -- cost centers, comma separated (A / D)
    tracing TEXT NOT NULL,       -- SKF:<stagr> | PCT:<k=v,...> | VV:<field>
    vv TEXT,                     -- COPA: value field that receives the costs
    PRIMARY KEY (cycle, seg));
CREATE TABLE IF NOT EXISTS cycle_run (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT, cycle TEXT, kind TEXT,
    wrttp TEXT, gjahr INTEGER, perio INTEGER, belnr TEXT, ts TEXT,
    usnam TEXT, reversed INTEGER NOT NULL DEFAULT 0, summary TEXT);
"""

# columns added to MM tables when CO is active (migration for old databases)
MM_COLUMN_ADDS = {
    "acc_doc_item": [("kostl", "TEXT"), ("aufnr", "TEXT"), ("paobj", "TEXT")],
    "cost_center": [("kosar", "TEXT"), ("khinr", "TEXT"), ("verak", "TEXT")],
}

CO_NUMBER_RANGES = {
    "CODOC": 300000000,
    "COPA": 100000000,
    "BILL": 90000000,
    "ORD_INT": 400000,
    "ORD_PP": 1000000,
    "FIDOC": 100000000,
    "CYCLE_RUN": 1,
}
