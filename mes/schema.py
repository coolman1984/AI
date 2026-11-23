"""GMES tables."""

MES_SCHEMA = """
CREATE TABLE IF NOT EXISTS mes_station (       -- a work place on a line: performs operation vornr of the line's routings
    station TEXT PRIMARY KEY, arbpl TEXT NOT NULL, vornr TEXT, kind TEXT NOT NULL DEFAULT 'OP',   -- OP / TEST / REPAIR
    text TEXT, skill TEXT, ct_std INTEGER NOT NULL DEFAULT 0,       -- standard cycle time (seconds per unit)
    opps INTEGER NOT NULL DEFAULT 1,                                -- defect opportunities per unit (DPMO)
    active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS mes_unit (          -- one serial number = one produced unit
    serial TEXT PRIMARY KEY, aufnr TEXT NOT NULL, matnr TEXT NOT NULL, werks TEXT,
    status TEXT NOT NULL DEFAULT 'WIP',                             -- WIP / REPAIR / DONE / SCRAP
    next_vornr TEXT, repairs INTEGER NOT NULL DEFAULT 0, created TEXT, finished TEXT,
    confirmed INTEGER NOT NULL DEFAULT 0, vbeln TEXT, kunnr TEXT, shipped TEXT);
CREATE INDEX IF NOT EXISTS ix_mes_unit_order ON mes_unit (aufnr, status);
CREATE TABLE IF NOT EXISTS mes_event (         -- every booking of a unit at a station
    id INTEGER PRIMARY KEY AUTOINCREMENT, serial TEXT NOT NULL, aufnr TEXT, matnr TEXT, arbpl TEXT, vornr TEXT,
    station TEXT, operator TEXT, ts TEXT NOT NULL, day TEXT NOT NULL,
    result TEXT NOT NULL,                                           -- OK / NG / REPAIRED / SCRAP
    attempt INTEGER NOT NULL DEFAULT 1, defect TEXT, cycle_sec INTEGER, note TEXT, usnam TEXT);
CREATE INDEX IF NOT EXISTS ix_mes_event_day ON mes_event (day, arbpl);
CREATE INDEX IF NOT EXISTS ix_mes_event_serial ON mes_event (serial);
CREATE TABLE IF NOT EXISTS mes_genealogy (     -- components (lot / serial) built into a unit
    id INTEGER PRIMARY KEY AUTOINCREMENT, serial TEXT NOT NULL, matnr TEXT NOT NULL, lot TEXT NOT NULL,
    qty INTEGER NOT NULL DEFAULT 1000, vornr TEXT, station TEXT, ts TEXT, usnam TEXT);
CREATE INDEX IF NOT EXISTS ix_mes_gen_lot ON mes_genealogy (lot);
CREATE TABLE IF NOT EXISTS mes_andon (         -- andon calls from the line
    id INTEGER PRIMARY KEY AUTOINCREMENT, arbpl TEXT NOT NULL, station TEXT, kind TEXT NOT NULL, text TEXT,
    opened TEXT NOT NULL, opened_by TEXT, ack TEXT, ack_by TEXT, closed TEXT, closed_by TEXT, resolution TEXT,
    status TEXT NOT NULL DEFAULT 'OPEN');                           -- OPEN / ACK / CLOSED
CREATE TABLE IF NOT EXISTS mes_char (          -- SPC characteristic measured at a station
    code TEXT PRIMARY KEY, text TEXT NOT NULL, station TEXT, unit TEXT, lsl REAL, usl REAL, target REAL,
    n INTEGER NOT NULL DEFAULT 5);                                  -- subgroup size
CREATE TABLE IF NOT EXISTS mes_measure (
    id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT NOT NULL, value REAL NOT NULL, serial TEXT, station TEXT,
    operator TEXT, ts TEXT NOT NULL, day TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_mes_measure ON mes_measure (code, ts);
"""


def install(conn):
    conn.executescript(MES_SCHEMA)
