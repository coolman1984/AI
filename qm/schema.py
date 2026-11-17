"""Tables of quality management and plant maintenance."""
QM_SCHEMA = """
CREATE TABLE IF NOT EXISTS qm_char (          -- QP01 inspection plan: characteristics per material / plant
    matnr TEXT NOT NULL, werks TEXT NOT NULL, seq INTEGER NOT NULL, name TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'N',           -- N = measured value with limits, A = attribute (OK / not OK)
    lsl INTEGER, usl INTEGER, unit TEXT DEFAULT '', usnam TEXT, ts TEXT,
    PRIMARY KEY (matnr, werks, seq));
CREATE TABLE IF NOT EXISTS qm_lot (           -- QA32 inspection lot
    prueflos TEXT PRIMARY KEY, origin TEXT NOT NULL, matnr TEXT, werks TEXT, lgort TEXT, lgpla TEXT DEFAULT '',
    qty INTEGER NOT NULL, meins TEXT, lifnr TEXT, ebeln TEXT, aufnr TEXT, mblnr TEXT, mjahr INTEGER,
    zeile INTEGER, created TEXT, status TEXT NOT NULL DEFAULT 'OPEN', ud_code TEXT, qty_ok INTEGER DEFAULT 0,
    qty_rej INTEGER DEFAULT 0, ud_date TEXT, ud_by TEXT, ud_mblnr TEXT, note TEXT DEFAULT '', usnam TEXT, ts TEXT);
CREATE INDEX IF NOT EXISTS qm_lot_mat ON qm_lot (matnr, werks, status);
CREATE TABLE IF NOT EXISTS qm_result (        -- QE51N results per characteristic
    prueflos TEXT NOT NULL, seq INTEGER NOT NULL, value INTEGER, ok INTEGER, valuation TEXT,
    note TEXT DEFAULT '', usnam TEXT, ts TEXT, PRIMARY KEY (prueflos, seq));
CREATE TABLE IF NOT EXISTS qm_defect (        -- defects found in a lot (Pareto)
    id INTEGER PRIMARY KEY AUTOINCREMENT, prueflos TEXT, code TEXT, qty INTEGER DEFAULT 0, text TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS qm_notif (         -- QM01 quality notification (complaint / NCR) with corrective action
    qmnum TEXT PRIMARY KEY, qmart TEXT NOT NULL, matnr TEXT, werks TEXT, lifnr TEXT, kunnr TEXT,
    prueflos TEXT, qty INTEGER DEFAULT 0, defect TEXT, text TEXT, cause TEXT DEFAULT '', action TEXT DEFAULT '',
    due TEXT, status TEXT NOT NULL DEFAULT 'OPEN', created TEXT, closed TEXT, usnam TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS pm_equi (          -- IE01 machine / technical object of the factory
    equnr TEXT PRIMARY KEY, eqktx TEXT NOT NULL, werks TEXT, arbpl TEXT, kostl TEXT NOT NULL,
    crit TEXT DEFAULT 'B', inbdt TEXT, active INTEGER DEFAULT 1, usnam TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS pm_plan (          -- IP01 preventive maintenance plan (time based)
    warpl TEXT PRIMARY KEY, equnr TEXT NOT NULL, text TEXT NOT NULL, interval_days INTEGER NOT NULL,
    minutes INTEGER DEFAULT 60, next_due TEXT NOT NULL, last_done TEXT, active INTEGER DEFAULT 1, usnam TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS pm_notif (         -- IW21 maintenance notification: M1 request, M2 breakdown
    qmnum TEXT PRIMARY KEY, qmart TEXT NOT NULL, equnr TEXT NOT NULL, text TEXT, start TEXT, finish TEXT,
    minutes INTEGER DEFAULT 0, aufnr TEXT, status TEXT NOT NULL DEFAULT 'OPEN', created TEXT, usnam TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS pm_order (         -- IW31 maintenance order: PM01 corrective, PM02 preventive
    aufnr TEXT PRIMARY KEY, auart TEXT NOT NULL, equnr TEXT NOT NULL, warpl TEXT, qmnum TEXT, text TEXT,
    status TEXT NOT NULL DEFAULT 'REL', created TEXT, due TEXT, teco TEXT, minutes INTEGER DEFAULT 0,
    labour INTEGER DEFAULT 0, parts INTEGER DEFAULT 0, usnam TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS pm_part (          -- spare parts issued to a maintenance order (goods issue 201)
    id INTEGER PRIMARY KEY AUTOINCREMENT, aufnr TEXT, matnr TEXT, qty INTEGER, value INTEGER, mblnr TEXT,
    mjahr INTEGER, usnam TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS pm_conf (          -- IW41 time confirmation
    id INTEGER PRIMARY KEY AUTOINCREMENT, aufnr TEXT, datum TEXT, minutes INTEGER, text TEXT, usnam TEXT, ts TEXT);
"""

RANGES = {"QLOT": 10000000, "QMEL": 300000, "PMNOT": 10000000, "PMORD": 4000000, "PMPLAN": 100}


def install(conn):
    for obj, start in RANGES.items():
        conn.execute("INSERT OR IGNORE INTO number_range VALUES (?, ?)", (obj, start - 1))
    conn.execute("INSERT OR IGNORE INTO tax_setting VALUES ('pm_rate','25000')")   # labour EGP/hour in cents
