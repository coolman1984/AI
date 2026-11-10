"""PP tables (AFKO/AFPO/AFVC/RESB/PLAF/PBED/MKAL/AFRU additions, SOP, forecast)."""

PP_COLUMN_ADDS = {
    "orders": [("gstrp", "TEXT"), ("gltrp", "TEXT"), ("ftrmi", "TEXT"), ("getri", "TEXT"),
               ("plnum", "TEXT"), ("verid", "TEXT"), ("igmng", "INTEGER DEFAULT 0"),
               ("iasmg", "INTEGER DEFAULT 0"), ("sysst", "TEXT DEFAULT ''"),
               ("ref_matnr", "TEXT"), ("rsnum", "TEXT"), ("dispo", "TEXT")],
    "work_center": [("kapaz", "INTEGER DEFAULT 8000"), ("ngrad", "INTEGER DEFAULT 85"),
                    ("shifts", "INTEGER DEFAULT 1"), ("verwe", "TEXT DEFAULT '0001'"),
                    ("steus", "TEXT DEFAULT 'PP01'"), ("veran", "TEXT DEFAULT ''")],
    "routing": [("steus", "TEXT DEFAULT 'PP01'"), ("vgw_setup", "INTEGER DEFAULT 0"),
                ("lifnr", "TEXT"), ("preis", "INTEGER DEFAULT 0"),
                ("plifz", "INTEGER DEFAULT 0"), ("ekgrp", "TEXT")],
    "bom": [("ausch", "INTEGER DEFAULT 0"), ("rgekz", "INTEGER DEFAULT 0"),
            ("lgort", "TEXT DEFAULT ''"), ("vornr", "TEXT DEFAULT ''"),
            ("postp", "TEXT DEFAULT 'L'")],
    "material_plant": [("strgr", "TEXT DEFAULT ''"), ("sobsl", "TEXT DEFAULT ''"),
                       ("rgekz", "INTEGER DEFAULT 0"), ("fxhor", "INTEGER DEFAULT 0"),
                       ("prmod", "TEXT DEFAULT ''"), ("lgrad", "INTEGER DEFAULT 0"),
                       ("disgr", "TEXT DEFAULT ''")],
    "po_item": [("pstyp", "TEXT DEFAULT ''"), ("vornr", "TEXT")],
    "confirmation": [("xmnga", "INTEGER DEFAULT 0"), ("aueru", "INTEGER DEFAULT 0"),
                     ("mblnr", "TEXT"), ("ersda", "TEXT"), ("grund", "TEXT")],
}

PP_SCHEMA = """
CREATE TABLE IF NOT EXISTS pp_oper (        -- AFVC / AFVV order operations
    aufnr TEXT, vornr TEXT, arbpl TEXT, steus TEXT, ltxa1 TEXT,
    mgvrg INTEGER, vgw INTEGER, vgw_setup INTEGER DEFAULT 0, ism INTEGER DEFAULT 0,
    lmnga INTEGER DEFAULT 0, xmnga INTEGER DEFAULT 0, status TEXT DEFAULT 'CRTD',
    ssavd TEXT, ssedd TEXT, lifnr TEXT, preis INTEGER DEFAULT 0, banfn TEXT,
    PRIMARY KEY (aufnr, vornr));
CREATE TABLE IF NOT EXISTS pp_resb (        -- RESB reservations / dependent requirements
    rsnum TEXT, rspos INTEGER, aufnr TEXT, kostl TEXT, matnr TEXT, werks TEXT,
    lgort TEXT, bdmng INTEGER, enmng INTEGER DEFAULT 0, bdter TEXT, vornr TEXT,
    rgekz INTEGER DEFAULT 0, kzear INTEGER DEFAULT 0, xloek INTEGER DEFAULT 0,
    bwart TEXT DEFAULT '261', usnam TEXT, PRIMARY KEY (rsnum, rspos));
CREATE INDEX IF NOT EXISTS ix_resb ON pp_resb (matnr, werks);
CREATE TABLE IF NOT EXISTS pp_plaf (        -- PLAF planned orders
    plnum TEXT PRIMARY KEY, matnr TEXT, werks TEXT, gsmng INTEGER, psttr TEXT,
    pedtr TEXT, paart TEXT, beskz TEXT, sobsl TEXT DEFAULT '', auffx INTEGER DEFAULT 0,
    dispo TEXT, run INTEGER, pir_month TEXT, ersda TEXT, conv TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS pp_depreq (      -- dependent requirements of planned orders
    plnum TEXT, matnr TEXT, werks TEXT, bdmng INTEGER, bdter TEXT);
CREATE TABLE IF NOT EXISTS pp_pir (         -- PBED planned independent requirements
    matnr TEXT, werks TEXT, versb TEXT, month TEXT, plnmg INTEGER, bedae TEXT,
    ernam TEXT, PRIMARY KEY (matnr, werks, versb, month));
CREATE TABLE IF NOT EXISTS pp_prodver (     -- MKAL production versions
    matnr TEXT, werks TEXT, verid TEXT, text TEXT, adatu TEXT, bdatu TEXT,
    bstmi INTEGER DEFAULT 0, bstma INTEGER DEFAULT 0, alnal TEXT DEFAULT '01',
    lock INTEGER DEFAULT 0, PRIMARY KEY (matnr, werks, verid));
CREATE TABLE IF NOT EXISTS pp_sop_group (   -- MC84 product group
    prgrp TEXT, ktext TEXT, matnr TEXT, werks TEXT, factor INTEGER,
    PRIMARY KEY (prgrp, matnr));
CREATE TABLE IF NOT EXISTS pp_sop_plan (    -- MC81 rough-cut plan
    prgrp TEXT, vers TEXT, month TEXT, sales INTEGER, production INTEGER,
    stock INTEGER, target_days INTEGER, PRIMARY KEY (prgrp, vers, month));
CREATE TABLE IF NOT EXISTS pp_mrp_run (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, usnam TEXT, scope TEXT,
    planned INTEGER, prs INTEGER, exceptions INTEGER, materials INTEGER);
CREATE TABLE IF NOT EXISTS pp_mrp_msg (     -- MDKP/MDTB exception messages
    run INTEGER, matnr TEXT, werks TEXT, dat TEXT, ausk TEXT, ref TEXT, text TEXT);
CREATE TABLE IF NOT EXISTS pp_forecast (    -- MPOP / PROP forecast results
    matnr TEXT, werks TEXT, month TEXT, kind TEXT, value INTEGER,
    PRIMARY KEY (matnr, werks, month, kind));
CREATE TABLE IF NOT EXISTS pp_fc_param (
    matnr TEXT, werks TEXT, prmod TEXT, alpha INTEGER, beta INTEGER, periods INTEGER,
    mad INTEGER, mape INTEGER, tsig INTEGER, ss INTEGER, rop INTEGER, ts TEXT,
    PRIMARY KEY (matnr, werks));
CREATE TABLE IF NOT EXISTS pp_po_comp (     -- subcontracting components of a PO item
    ebeln TEXT, ebelp INTEGER, matnr TEXT, werks TEXT, menge INTEGER, basis INTEGER,
    PRIMARY KEY (ebeln, ebelp, matnr));
CREATE TABLE IF NOT EXISTS pp_wip (         -- results analysis (KKAX / KKAO)
    aufnr TEXT, gjahr INTEGER, perio INTEGER, wip INTEGER, belnr TEXT,
    PRIMARY KEY (aufnr, gjahr, perio));
"""
